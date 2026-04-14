"""
Path: lib/processes/process_b.py
Description:
    Hardware control process — motors, LCD display, keypad, Firebase.
    Reads Firebase RTDB state and physical keypad, drives feed/water motors,
    updates LCD, and logs analytics back to Firebase.

    Sensor reads (v3 — offloaded to process_c):
        Feed and water level percentages are no longer read directly in this
        process. process_c runs the HC-SR04 ultrasonic sensors in a dedicated
        loop with the median filter enabled and writes the latest values into
        two shared multiprocessing.Value floats:

            shared_feed_level  : multiprocessing.Value('d')
            shared_water_level : multiprocessing.Value('d')

        This process reads those values on every tick via:
            current_feed_level  = shared_feed_level.value
            current_water_level = shared_water_level.value

        No locks are acquired on the read side — reading a double is atomic
        on all supported platforms and the occasional torn read of a float
        (one stale byte) is harmless compared to blocking the tick loop.

    Water refill behaviour (v2):
        Refill is now fully manual and toggle-based.
        - Keypad '#' toggles the pump ON on first press, OFF on second press.
        - App water button also toggles (Pi side ready; app wired separately).
        - The ultrasonic sensor is used ONLY for monitoring (LCD, Firebase,
          low-level warnings). It is NOT used to start or stop the pump.
        - Auto-refill feature has been removed entirely.
        - On stop, durationSeconds is written to the analytics log entry.

    Water toggle fix (v2.1):
        App button and physical keypad are now processed as separate independent
        toggle signals. Previously both were OR'd into a single water_button_pressed
        flag — if the app was ON when the keypad fired, both signals cancelled each
        other in the same tick and the pump appeared to not respond.
        Each source now calls _refill_it() independently with a 1s cooldown on
        the physical keypad to prevent bounce re-triggers.

    Settings restart:
        When the app saves new settings (settingsService.updateSettings writes
        settings/{userId}/updatedAt), the inner tick loop detects the timestamp
        change, waits for any active dispense/refill cycle to finish, then breaks
        back to the outer restart loop which re-reads all settings cleanly.
        Hardware (GPIO, motors, LCD) is NOT re-initialized on a settings restart —
        only settings and per-loop state are refreshed.

    Analytics (v3):
        Feed analytics now logs kgPerDispense per completed dispense cycle
        instead of a sensor-derived percentage delta.
        - kgPerDispense is fetched from Firebase settings on every restart.
        - It live-reloads from user_settings in the inner loop without restart.
        - Water analytics logs durationSeconds (start→stop span) unchanged.
"""

import time
from datetime import datetime

import RPi.GPIO as GPIO
from firebase_admin import db

from lib.services import firebase_rtdb
from lib.services.firebase_rtdb import FirebaseInitError, FirebaseReadError
from lib.services.hardware import (
    motor_controller        as motor,
    lcd_controller          as lcd,
)
from lib.services.hardware.keypad_controller import Keypad4x4, KeypadError
from lib.services.hardware.motor_controller  import MotorError, MotorSetupError
from lib.services.logger import get_logger

log = get_logger("process_b.py")

# ─────────────────────────── DISPENSE COUNTDOWN CONFIG ───────────────────────

DEFAULT_DISPENSE_COUNTDOWN_MS = 1000 * 60          # 60 seconds — hard fallback
_COUNTDOWN_CACHE_PATH         = "credentials/dispense_countdown_ms.txt"


def _load_cached_countdown() -> int | None:
    try:
        with open(_COUNTDOWN_CACHE_PATH, "r") as f:
            value = int(f.read().strip())
            return value if value > 0 else None
    except Exception:
        return None


def _save_cached_countdown(value_ms: int) -> None:
    try:
        with open(_COUNTDOWN_CACHE_PATH, "w") as f:
            f.write(str(value_ms))
    except Exception:
        pass


def _fetch_dispense_countdown(user_uid: str, task_name: str) -> int:
    try:
        from firebase_admin import db as _db
        value = _db.reference(f"settings/{user_uid}/feed/dispenseCountdownMs").get()
        if isinstance(value, (int, float)) and value > 0:
            ms = int(value)
            _save_cached_countdown(ms)
            log(
                details=f"{task_name} - dispenseCountdownMs={ms}ms loaded from Firebase",
                log_type="info"
            )
            return ms
    except Exception as e:
        log(
            details=f"{task_name} - Could not read dispenseCountdownMs from Firebase: {e}",
            log_type="warning"
        )

    cached = _load_cached_countdown()
    if cached is not None:
        log(
            details=f"{task_name} - dispenseCountdownMs={cached}ms loaded from local cache",
            log_type="warning"
        )
        return cached

    log(
        details=f"{task_name} - dispenseCountdownMs using hardcoded default {DEFAULT_DISPENSE_COUNTDOWN_MS}ms",
        log_type="warning"
    )
    return DEFAULT_DISPENSE_COUNTDOWN_MS


# ─────────────────────────── KG PER DISPENSE CONFIG ──────────────────────────

DEFAULT_KG_PER_DISPENSE     = 0.5
_KG_PER_DISPENSE_CACHE_PATH = "credentials/kg_per_dispense.txt"


def _load_cached_kg_per_dispense() -> float | None:
    try:
        with open(_KG_PER_DISPENSE_CACHE_PATH, "r") as f:
            value = float(f.read().strip())
            return value if value > 0 else None
    except Exception:
        return None


def _save_cached_kg_per_dispense(value: float) -> None:
    try:
        with open(_KG_PER_DISPENSE_CACHE_PATH, "w") as f:
            f.write(str(value))
    except Exception:
        pass


def _fetch_kg_per_dispense(user_uid: str, task_name: str) -> float:
    try:
        from firebase_admin import db as _db
        value = _db.reference(f"settings/{user_uid}/feed/kgPerDispense").get()
        if isinstance(value, (int, float)) and value > 0:
            kg = float(value)
            _save_cached_kg_per_dispense(kg)
            log(
                details=f"{task_name} - kgPerDispense={kg}kg loaded from Firebase",
                log_type="info"
            )
            return kg
    except Exception as e:
        log(
            details=f"{task_name} - Could not read kgPerDispense from Firebase: {e}",
            log_type="warning"
        )

    cached = _load_cached_kg_per_dispense()
    if cached is not None:
        log(
            details=f"{task_name} - kgPerDispense={cached}kg loaded from local cache",
            log_type="warning"
        )
        return cached

    log(
        details=f"{task_name} - kgPerDispense using hardcoded default {DEFAULT_KG_PER_DISPENSE}kg",
        log_type="warning"
    )
    return DEFAULT_KG_PER_DISPENSE


# Python weekday → JS weekday
_PY_TO_JS_DAY = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 0}


# ─────────────────────────── HARDWARE HELPERS ────────────────────────────────

def _handle_water_refill(state: bool) -> None:
    if state:
        motor.start_water_motor()
    else:
        motor.stop_water_motor()


def _handle_feed_dispense(state: bool) -> None:
    if state:
        motor.start_feed_motor()
    else:
        motor.stop_feed_motor()


def _read_pins_data(keypad_instance: Keypad4x4) -> dict:
    """
    Read keypad state only.

    Sensor levels are NO LONGER read here — they come from shared memory
    (shared_feed_level, shared_water_level) written by process_c.

    Uses scan_key() (no debounce) — debouncing for the toggle logic is
    handled upstream via the physical button cooldown timer, not here.
    The D-key hold detection also requires raw scan_key() output.
    """
    current_feed_physical_button_state  = False
    current_water_physical_button_state = False

    key = keypad_instance.scan_key()
    if key == "*":
        current_feed_physical_button_state  = True
    elif key == "#":
        current_water_physical_button_state = True

    return {
        "current_feed_physical_button_state"    : current_feed_physical_button_state,
        "current_water_physical_button_state"   : current_water_physical_button_state,
        "raw_key"                               : key,
    }


def _convert_to_percentage(distance_cm, min_dist: int = 10, max_dist: int = 300) -> float:
    if distance_cm <= min_dist:
        return 100.0
    if distance_cm >= max_dist:
        return 0.0
    return round((max_dist - distance_cm) / (max_dist - min_dist) * 100, 2)


def _current_millis() -> int:
    return int(time.monotonic() * 1000)


# ─────────────────────────── FIREBASE HELPERS ────────────────────────────────

def _update_button_timestamp(database_ref: dict, button_type: str) -> None:
    ref_key = "df_app_button_ref" if button_type == "feed" else "wr_app_button_ref"
    try:
        database_ref[ref_key].set({".sv": "timestamp"})
    except Exception as e:
        raise firebase_rtdb.FirebaseWriteError(
            f"Failed to update {button_type} button timestamp: {e}. Source: {__name__}"
        ) from e


def _log_analytics(
    user_uid        : str,
    action_type     : str,
    volume_percent  : float,
    source          : str = "keypad",
    duration_seconds: int = 0,
) -> None:
    now = datetime.now()
    log_entry = {
        "action"          : "refill" if action_type == "water" else "dispense",
        "type"            : action_type,
        "volumePercent"   : round(volume_percent, 2),
        "durationSeconds" : duration_seconds,
        "timestamp"       : int(now.timestamp() * 1000),
        "date"            : now.strftime("%m/%d/%Y"),
        "time"            : now.strftime("%H:%M:%S"),
        "dayOfWeek"       : _PY_TO_JS_DAY[now.weekday()],
        "userId"          : user_uid,
        "source"          : source,
    }
    try:
        db.reference(f"analytics/logs/{user_uid}").push(log_entry)
    except Exception as e:
        raise firebase_rtdb.FirebaseWriteError(
            f"Failed to log analytics for {action_type}: {e}. Source: {__name__}"
        ) from e


# ─────────────────────────── MOTOR LOGIC ─────────────────────────────────────

def _dispense_it(
    feed_button_state       : bool,
    dispense_active         : bool,
    dispense_countdown_start: int,
    DISPENSE_COUNTDOWN_TIME : int,
) -> tuple:
    now = _current_millis()

    if feed_button_state and not dispense_active:
        dispense_active          = True
        dispense_countdown_start = now

    if dispense_active:
        if now - dispense_countdown_start >= DISPENSE_COUNTDOWN_TIME:
            dispense_active = False

    _handle_feed_dispense(dispense_active)
    return dispense_active, dispense_countdown_start


def _refill_it(
    water_button_state: bool,
    refill_active     : bool,
) -> bool:
    """
    Handle water refilling — fully manual, toggle-based.

    Each call with water_button_state=True flips the pump state once.
    App button and keypad each call this independently so they cannot
    cancel each other out in the same tick.
    """
    if water_button_state:
        refill_active = not refill_active

    _handle_water_refill(refill_active)
    return refill_active


# ─────────────────────────── LCD ─────────────────────────────────────────────

def _update_lcd_display(
    lcd_obj             ,
    current_feed_level  : float,
    current_water_level : float,
    feed_warning        : bool,
    water_warning       : bool,
    dispense_active     : bool,
    refill_active       : bool,
) -> None:
    if lcd_obj is None:
        return
    try:
        line1 = (
            "DISPENSING..."                    if dispense_active else
            f"FEED LOW {current_feed_level}%"  if feed_warning    else
            f"Feed: {current_feed_level}%"
        )
        line2 = (
            "REFILLING..."                      if refill_active  else
            f"WATER LOW {current_water_level}%" if water_warning  else
            f"Water: {current_water_level}%"
        )
        lcd_obj.show([line1, line2])
    except Exception:
        pass


# ─────────────────────────── PROCESS B ───────────────────────────────────────

def process_B(**kwargs) -> None:
    args               = kwargs["process_B_args"]
    TASK_NAME          = args["TASK_NAME"]
    status_checker     = args["status_checker"]
    live_status        = args["live_status"]
    logout_requested   = args["logout_requested"]
    USER_CREDENTIAL    = args["USER_CREDENTIAL"]
    LCD_I2C_ADDR       = args.get("LCD_I2C_ADDR", 0x27)
    # ── Shared memory from process_c ──────────────────────────────────────
    shared_feed_level  = args["shared_feed_level"]   # multiprocessing.Value('d')
    shared_water_level = args["shared_water_level"]  # multiprocessing.Value('d')

    log(details=f"{TASK_NAME} - Running", log_type="info")

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # ── Init Firebase ─────────────────────────────────────────────────────
    try:
        firebase_rtdb.initialize_firebase()
    except FirebaseInitError as e:
        log(details=f"{TASK_NAME} - Firebase init failed: {e}", log_type="error")
        status_checker.clear()
        GPIO.cleanup()
        return

    user_uid     = USER_CREDENTIAL["userUid"]
    device_uid   = USER_CREDENTIAL["deviceUid"]
    database_ref = firebase_rtdb.setup_RTDB(user_uid=user_uid, device_uid=device_uid)

    # ── Init hardware — once, shared across all settings restarts ─────────
    try:
        keypad_instance = Keypad4x4()
    except KeypadError as e:
        log(details=f"{TASK_NAME} - Keypad init failed: {e}", log_type="error")
        status_checker.clear()
        GPIO.cleanup()
        return

    try:
        motor.setup_motors()
    except MotorSetupError as e:
        log(details=f"{TASK_NAME} - Motor setup failed: {e}", log_type="error")
        status_checker.clear()
        GPIO.cleanup()
        return

    # NOTE: distance.setup_ultrasonics() is intentionally NOT called here.
    # Ultrasonic setup and reads are now owned entirely by process_c.

    lcd_obj = None
    try:
        lcd_obj = lcd.setup_lcd(addr=LCD_I2C_ADDR, cols=16, rows=2)
        lcd_obj.show(["Chick-Up", "Initializing..."])
        time.sleep(2)
    except Exception as e:
        log(details=f"{TASK_NAME} - LCD init failed, continuing without LCD: {e}", log_type="warning")
        lcd_obj = None

    # ── Outer restart loop ────────────────────────────────────────────────
    settings_restart = True
    while settings_restart:
        settings_restart = False

        # ── Fetch settings (fresh on every restart) ───────────────────────
        DISPENSE_COUNTDOWN_TIME = _fetch_dispense_countdown(user_uid, TASK_NAME)
        KG_PER_DISPENSE         = _fetch_kg_per_dispense(user_uid, TASK_NAME)

        try:
            _settings_updated_at_at_start = (
                db.reference(f"settings/{user_uid}/updatedAt").get() or 0
            )
        except Exception:
            _settings_updated_at_at_start = 0

        log(
            details=f"{TASK_NAME} - Settings loaded. updatedAt={_settings_updated_at_at_start}, "
                    f"dispenseCountdown={DISPENSE_COUNTDOWN_TIME}ms, "
                    f"kgPerDispense={KG_PER_DISPENSE}kg",
            log_type="info",
        )

        # ── Per-restart state ─────────────────────────────────────────────
        current_feed_level  = 0.0
        current_water_level = 0.0
        current_feed_physical_button_state  = False
        current_water_physical_button_state = False

        current_feed_app_button_state   = False
        current_water_app_button_state  = False
        current_feed_schedule_state     = False
        current_live_button_state       = False
        raw_feed_timestamp              = None
        raw_water_timestamp             = None

        current_feed_threshold_warning  = 20
        current_water_threshold_warning = 20

        refill_active            = False
        refill_start_monotonic   = 0.0
        dispense_active          = False
        dispense_countdown_start = 0

        # Boot stabilization — 20 ticks × 100 ms = 2 s
        BOOT_STABILIZATION_TICKS = 20
        boot_ticks_elapsed        = 0

        last_acted_feed_timestamp  = None
        last_acted_water_timestamp = None
        last_acted_schedule_key    = None

        prev_refill_active   = False
        prev_dispense_active = False
        pending_feed_source  = "keypad"

        # ── Physical button cooldown ──────────────────────────────────────
        # Prevents the same keypad press from firing the toggle multiple
        # times across consecutive 100ms ticks while the key is held down.
        last_physical_water_press   = 0.0
        last_physical_feed_press    = 0.0
        PHYSICAL_BUTTON_COOLDOWN    = 1.0   # seconds
        APP_AFTER_PHYSICAL_BLACKOUT = 1.0

        last_lcd_update       = 0.0
        LCD_UPDATE_INTERVAL   = 1.0

        last_db_error_log     = 0.0
        DB_ERROR_LOG_INTERVAL = 10.0

        LOGOUT_HOLD_SECONDS = 3.0
        d_key_hold_start    = 0.0
        d_key_held          = False

        _settings_change_pending = False

        # ── Inner main loop ───────────────────────────────────────────────
        try:
            while True:
                if not status_checker.is_set():
                    log(details=f"{TASK_NAME} - status_checker cleared, shutting down", log_type="warning")
                    break

                current_time = time.time()
                time.sleep(0.1)

                # ── Read keypad ───────────────────────────────────────────
                # Sensor levels come from shared memory (process_c), not here.
                try:
                    pins_data = _read_pins_data(keypad_instance)
                    current_feed_physical_button_state  = pins_data["current_feed_physical_button_state"]
                    current_water_physical_button_state = pins_data["current_water_physical_button_state"]
                    raw_key                             = pins_data["raw_key"]
                except Exception as e:
                    log(details=f"{TASK_NAME} - Keypad read failed: {e}", log_type="error")
                    status_checker.clear()
                    break

                # ── Read sensor levels from shared memory (process_c) ─────
                current_feed_level  = shared_feed_level.value
                current_water_level = shared_water_level.value

                # ── D-key hold → logout request ───────────────────────────
                if raw_key == "D":
                    if not d_key_held:
                        d_key_held       = True
                        d_key_hold_start = time.monotonic()
                    elif time.monotonic() - d_key_hold_start >= LOGOUT_HOLD_SECONDS:
                        log(details=f"{TASK_NAME} - Logout requested via D-key hold", log_type="info")
                        if lcd_obj:
                            try:
                                lcd_obj.show(["Hold D: Logout", "Please wait..."])
                            except Exception:
                                pass
                        logout_requested.set()
                        break
                else:
                    d_key_held       = False
                    d_key_hold_start = 0.0

                # ── Read Firebase ─────────────────────────────────────────
                try:
                    database_data = firebase_rtdb.read_RTDB(database_ref=database_ref)
                    current_feed_app_button_state  = database_data["current_feed_app_button_state"]
                    current_water_app_button_state = database_data["current_water_app_button_state"]
                    raw_feed_timestamp             = database_data["raw_feed_timestamp"]
                    raw_water_timestamp            = database_data["raw_water_timestamp"]
                    current_feed_schedule_state    = database_data["current_feed_schedule_state"]
                    current_live_button_state      = database_data["current_live_button_state"]

                    user_settings                   = database_data["current_user_settings"]
                    current_feed_threshold_warning  = user_settings["feed_threshold_warning"]
                    current_water_threshold_warning = user_settings["water_threshold_warning"]

                    # ── Live-reload dispenseCountdownMs ───────────────────
                    new_countdown = user_settings.get("dispense_countdown_ms")
                    if isinstance(new_countdown, int) and new_countdown > 0 and new_countdown != DISPENSE_COUNTDOWN_TIME:
                        log(
                            details=f"{TASK_NAME} - dispenseCountdownMs updated: "
                                    f"{DISPENSE_COUNTDOWN_TIME}ms → {new_countdown}ms",
                            log_type="info",
                        )
                        DISPENSE_COUNTDOWN_TIME = new_countdown
                        _save_cached_countdown(new_countdown)

                    # ── Live-reload kgPerDispense ─────────────────────────
                    new_kg = user_settings.get("kg_per_dispense")
                    if isinstance(new_kg, (int, float)) and new_kg > 0 and new_kg != KG_PER_DISPENSE:
                        log(
                            details=f"{TASK_NAME} - kgPerDispense updated: "
                                    f"{KG_PER_DISPENSE}kg → {new_kg}kg",
                            log_type="info",
                        )
                        KG_PER_DISPENSE = float(new_kg)
                        _save_cached_kg_per_dispense(KG_PER_DISPENSE)

                    # ── Detect settings change → graceful restart ─────────
                    _current_updated_at = user_settings.get("updated_at", 0)
                    if (
                        not _settings_change_pending
                        and _current_updated_at
                        and _current_updated_at != _settings_updated_at_at_start
                    ):
                        log(
                            details=f"{TASK_NAME} - Settings change detected "
                                    f"(updatedAt {_settings_updated_at_at_start} → {_current_updated_at}). "
                                    f"Waiting for motors to idle before restarting.",
                            log_type="info",
                        )
                        _settings_change_pending = True
                        if lcd_obj:
                            try:
                                lcd_obj.show(["Settings updated", "Finishing cycle..."])
                            except Exception:
                                pass

                except FirebaseReadError as e:
                    if current_time - last_db_error_log >= DB_ERROR_LOG_INTERVAL:
                        log(details=f"{TASK_NAME} - RTDB read failed: {e}", log_type="warning")
                        last_db_error_log = current_time
                except Exception as e:
                    if current_time - last_db_error_log >= DB_ERROR_LOG_INTERVAL:
                        log(details=f"{TASK_NAME} - Unexpected RTDB error: {e}", log_type="warning")
                        last_db_error_log = current_time

                # ── Sync live stream status ───────────────────────────────
                if current_live_button_state:
                    live_status.set()
                else:
                    live_status.clear()

                # ── Level warnings (monitoring only) ──────────────────────
                feed_warning  = current_feed_level  <= current_feed_threshold_warning
                water_warning = current_water_level <= current_water_threshold_warning

                # ── Physical keypad → Firebase timestamp ──────────────────
                if current_feed_physical_button_state:
                    try:
                        _update_button_timestamp(database_ref, "feed")
                    except firebase_rtdb.FirebaseWriteError as e:
                        log(details=f"{TASK_NAME} - {e}", log_type="warning")

                # if current_water_physical_button_state:
                #     try:
                #         _update_button_timestamp(database_ref, "water")
                #     except firebase_rtdb.FirebaseWriteError as e:
                #         log(details=f"{TASK_NAME} - {e}", log_type="warning")

                # ── Button aggregation ────────────────────────────────────

                # Physical keypad — cooldown prevents the same held key from
                # firing the toggle on every 100ms tick.
                physical_feed_new_press = (
                    current_feed_physical_button_state and
                    (current_time - last_physical_feed_press) >= PHYSICAL_BUTTON_COOLDOWN
                )
                physical_water_new_press = (
                    current_water_physical_button_state and
                    (current_time - last_physical_water_press) >= PHYSICAL_BUTTON_COOLDOWN
                )
                if physical_water_new_press:
                    last_physical_water_press = current_time   # ← stamp immediately

                # App buttons — guarded by unique Firebase timestamp
                feed_app_new_press = (
                    current_feed_app_button_state and
                    raw_feed_timestamp  is not None and
                    raw_feed_timestamp  != last_acted_feed_timestamp
                )
                water_app_new_press = (
                    current_water_app_button_state and
                    raw_water_timestamp is not None and
                    raw_water_timestamp != last_acted_water_timestamp and
                    (current_time - last_physical_water_press) >= APP_AFTER_PHYSICAL_BLACKOUT
                )

                schedule_key = None
                if current_feed_schedule_state:
                    from datetime import datetime as _dt
                    schedule_key = f"sched:{_dt.now().strftime('%H:%M')}"

                feed_schedule_new_trigger = (
                    current_feed_schedule_state and
                    schedule_key != last_acted_schedule_key
                )

                # Feed — combined flag is fine (not a toggle, just starts countdown)
                feed_button_pressed = (
                    not _settings_change_pending and
                    (
                        physical_feed_new_press    or
                        feed_app_new_press         or
                        feed_schedule_new_trigger
                    ) and not dispense_active
                )

                # Determine analytics source for this dispense trigger
                if feed_schedule_new_trigger and not physical_feed_new_press and not feed_app_new_press:
                    pending_feed_source = "schedule"
                elif feed_app_new_press:
                    pending_feed_source = "app"
                else:
                    pending_feed_source = "keypad"

                # Acknowledge feed timestamps / schedule keys
                if feed_app_new_press:
                    last_acted_feed_timestamp = raw_feed_timestamp
                if feed_schedule_new_trigger:
                    last_acted_schedule_key   = schedule_key
                if physical_feed_new_press:
                    last_physical_feed_press  = current_time

                # ── Boot stabilization ────────────────────────────────────
                if boot_ticks_elapsed < BOOT_STABILIZATION_TICKS:
                    boot_ticks_elapsed += 1
                    continue

                # ── Graceful settings restart — wait for motors to go idle ─
                if _settings_change_pending and not dispense_active and not refill_active:
                    log(
                        details=f"{TASK_NAME} - Motors idle. Restarting inner loop to apply new settings.",
                        log_type="info",
                    )
                    if lcd_obj:
                        try:
                            lcd_obj.show(["Applying settings", "Please wait..."])
                            time.sleep(1)
                        except Exception:
                            pass
                    settings_restart = True
                    break

                # ── Motor logic — feed ────────────────────────────────────
                dispense_active, dispense_countdown_start = _dispense_it(
                    feed_button_state        = feed_button_pressed,
                    dispense_active          = dispense_active,
                    dispense_countdown_start = dispense_countdown_start,
                    DISPENSE_COUNTDOWN_TIME  = DISPENSE_COUNTDOWN_TIME,
                )

                # ── Motor logic — water ───────────────────────────────────
                # Stamp the physical press time BEFORE water_app_new_press
                # is acted on — this ensures the APP_AFTER_PHYSICAL_BLACKOUT
                # check inside water_app_new_press blocks the app toggle on
                # the same tick the keypad fires, preventing both signals
                # from cancelling each other out in one tick.
                if physical_water_new_press:
                    last_physical_water_press = current_time

                if current_water_physical_button_state or water_app_new_press or physical_water_new_press:
                    log(
                        details=(
                            f"WATER DEBUG — "
                            f"physical_raw={current_water_physical_button_state} "
                            f"physical_new={physical_water_new_press} "
                            f"app_new={water_app_new_press} "
                            f"app_state={current_water_app_button_state} "
                            f"raw_ts={raw_water_timestamp} "
                            f"last_acted_ts={last_acted_water_timestamp} "
                            f"blackout_remaining={round(APP_AFTER_PHYSICAL_BLACKOUT - (current_time - last_physical_water_press), 2)} "
                            f"refill_active={refill_active}"
                        ),
                        log_type="info"
                    )

                if not _settings_change_pending:

                    if water_app_new_press:
                        last_acted_water_timestamp = raw_water_timestamp
                        if not refill_active:
                            refill_start_monotonic = time.monotonic()
                        refill_active = _refill_it(
                            water_button_state = True,
                            refill_active      = refill_active,
                        )

                    if physical_water_new_press:
                        if not refill_active:
                            refill_start_monotonic = time.monotonic()
                        refill_active = _refill_it(
                            water_button_state = True,
                            refill_active      = refill_active,
                        )

                # ── Analytics on action completion ────────────────────────
                if prev_dispense_active and not dispense_active:
                    try:
                        _log_analytics(
                            user_uid,
                            "feed",
                            KG_PER_DISPENSE,
                            source=pending_feed_source,
                        )
                    except firebase_rtdb.FirebaseWriteError as e:
                        log(details=f"{TASK_NAME} - Analytics write failed: {e}", log_type="warning")
                    pending_feed_source = "keypad"

                if prev_refill_active and not refill_active:
                    duration_seconds = int(time.monotonic() - refill_start_monotonic)
                    try:
                        _log_analytics(
                            user_uid,
                            "water",
                            0,
                            source="keypad",
                            duration_seconds=duration_seconds,
                        )
                    except firebase_rtdb.FirebaseWriteError as e:
                        log(details=f"{TASK_NAME} - Analytics write failed: {e}", log_type="warning")
                    refill_start_monotonic = 0.0

                prev_dispense_active = dispense_active
                prev_refill_active   = refill_active

                # ── LCD update ────────────────────────────────────────────
                if lcd_obj and (current_time - last_lcd_update >= LCD_UPDATE_INTERVAL):
                    _update_lcd_display(
                        lcd_obj             = lcd_obj,
                        current_feed_level  = current_feed_level,
                        current_water_level = current_water_level,
                        feed_warning        = feed_warning,
                        water_warning       = water_warning,
                        dispense_active     = dispense_active,
                        refill_active       = refill_active,
                    )
                    last_lcd_update = current_time

                # ── Push sensor data to Firebase ──────────────────────────
                try:
                    database_ref["sensors_ref"].update({
                        "feedLevel" : current_feed_level,
                        "waterLevel": current_water_level,
                        "updatedAt" : datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
                    })
                except Exception as e:
                    if current_time - last_db_error_log >= DB_ERROR_LOG_INTERVAL:
                        log(details=f"{TASK_NAME} - Sensor DB update failed: {e}", log_type="warning")
                        last_db_error_log = current_time

        except KeyboardInterrupt:
            log(details=f"{TASK_NAME} - KeyboardInterrupt received", log_type="warning")
            status_checker.clear()
            settings_restart = False

        except Exception as e:
            log(details=f"{TASK_NAME} - Unexpected error: {e}", log_type="error")
            status_checker.clear()
            settings_restart = False
            raise

    # ── Cleanup ───────────────────────────────────────────────────────────
    try:
        motor.stop_all_motors()
    except MotorError as e:
        log(details=f"{TASK_NAME} - Failed to stop motors during cleanup: {e}", log_type="error")
    if lcd_obj:
        try:
            lcd_obj.show(["Chick-Up", "Shutting down..."])
            time.sleep(1)
            lcd.cleanup_lcd()
        except Exception:
            pass
    GPIO.cleanup()
    log(details=f"{TASK_NAME} - Process stopped", log_type="info")