"""
Path: lib/processes/process_b.py
Description:
    Hardware control process — sensors, motors, LCD display.
    Reads Firebase RTDB state and physical keypad, drives feed/water motors,
    updates LCD, and logs analytics back to Firebase.
"""

import time
from datetime import datetime

import RPi.GPIO as GPIO
from firebase_admin import db

from lib.services import firebase_rtdb
from lib.services.firebase_rtdb import FirebaseInitError, FirebaseReadError
from lib.services.hardware import (
    motor_controller        as motor,
    ultrasonic_controller   as distance,
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
    """
    Read the last-known dispense countdown from local cache file.
    Returns None if file missing or corrupt.
    """
    try:
        with open(_COUNTDOWN_CACHE_PATH, "r") as f:
            value = int(f.read().strip())
            return value if value > 0 else None
    except Exception:
        return None


def _save_cached_countdown(value_ms: int) -> None:
    """Persist the countdown value to cache so it survives offline reboots."""
    try:
        with open(_COUNTDOWN_CACHE_PATH, "w") as f:
            f.write(str(value_ms))
    except Exception:
        pass  # Cache write failure is non-critical


def _fetch_dispense_countdown(user_uid: str, task_name: str) -> int:
    """
    Read dispenseCountdownMs from Firebase settings/{userUid}/feed/.

    Resolution order:
        1. Firebase  settings/{userUid}/feed/dispenseCountdownMs
        2. Local     credentials/dispense_countdown_ms.txt  (last known good)
        3. Hardcoded DEFAULT_DISPENSE_COUNTDOWN_MS (60 000 ms)

    Always persists a successful Firebase read to the local cache.
    """
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

# Python weekday → JS weekday
# Python: Mon=0 ... Sun=6
# JS:     Sun=0, Mon=1 ... Sat=6
_PY_TO_JS_DAY = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 0}


# ─────────────────────────── HARDWARE HELPERS ────────────────────────────────

def _handle_water_refill(state: bool) -> None:
    """
    Drive water motor relay (GPIO 27).

    Raises:
        MotorError: Propagated from motor_controller on GPIO failure.
    """
    if state:
        motor.start_water_motor()
    else:
        motor.stop_water_motor()


def _handle_feed_dispense(state: bool) -> None:
    """
    Drive feed motor relay (GPIO 17).

    Raises:
        MotorError: Propagated from motor_controller on GPIO failure.
    """
    if state:
        motor.start_feed_motor()
    else:
        motor.stop_feed_motor()


def _read_pins_data(keypad_instance: Keypad4x4) -> dict:
    """
    Read all sensors and keypad state.

    Args:
        keypad_instance: Initialized Keypad4x4 instance.

    Returns:
        dict with keys:
            current_feed_level                  : float
            current_water_level                 : float
            current_feed_physical_button_state  : bool
            current_water_physical_button_state : bool
            raw_key                             : str | None  — the raw key pressed

    Raises:
        KeypadError: If keypad scan fails.
        RuntimeError: If sensor read fails unexpectedly.
    """
    current_feed_physical_button_state  = False
    current_water_physical_button_state = False

    key = keypad_instance.scan_key()
    if key == "*":
        current_feed_physical_button_state  = True
    elif key == "#":
        current_water_physical_button_state = True

    feed_level  = distance.read_left_distance()
    water_level = distance.read_right_distance()

    return {
        "current_feed_level"                    : _convert_to_percentage(feed_level),
        "current_water_level"                   : _convert_to_percentage(water_level),
        "current_feed_physical_button_state"    : current_feed_physical_button_state,
        "current_water_physical_button_state"   : current_water_physical_button_state,
        "raw_key"                               : key,
    }


def _convert_to_percentage(distance_cm, min_dist: int = 10, max_dist: int = 300) -> float:
    """
    Convert ultrasonic distance reading to fill percentage.
    100% = full (min_dist), 0% = empty (max_dist).
    """
    if distance_cm <= min_dist:
        return 100.0
    if distance_cm >= max_dist:
        return 0.0
    return round((max_dist - distance_cm) / (max_dist - min_dist) * 100, 2)


def _current_millis() -> int:
    return int(time.monotonic() * 1000)


# ─────────────────────────── FIREBASE HELPERS ────────────────────────────────

def _update_button_timestamp(database_ref: dict, button_type: str) -> None:
    """
    Write SERVER_TIMESTAMP to the button's lastUpdateAt path on physical keypad
    press — mirrors what the app does via buttonService.updateButtonTimestamp().

    Args:
        database_ref: Dict from firebase_rtdb.setup_RTDB()
        button_type:  "feed" or "water"

    Raises:
        FirebaseWriteError: If the Firebase write fails.
    """
    ref_key = "df_app_button_ref" if button_type == "feed" else "wr_app_button_ref"
    try:
        database_ref[ref_key].set({".sv": "timestamp"})
    except Exception as e:
        raise firebase_rtdb.FirebaseWriteError(
            f"Failed to update {button_type} button timestamp: {e}. Source: {__name__}"
        ) from e


def _log_analytics(user_uid: str, action_type: str, volume_percent: float) -> None:
    """
    Write an analytics entry to analytics/logs/{userId}.
    Matches analyticsService.ts logAction() shape so AnalyticsScreen can
    read both app and keypad logs together.

    Raises:
        FirebaseWriteError: If the Firebase push fails.
    """
    now = datetime.now()
    log_entry = {
        "action"        : "refill" if action_type == "water" else "dispense",
        "type"          : action_type,
        "volumePercent" : round(volume_percent, 2),
        "timestamp"     : int(now.timestamp() * 1000),
        "date"          : now.strftime("%m/%d/%Y"),
        "time"          : now.strftime("%H:%M:%S"),
        "dayOfWeek"     : _PY_TO_JS_DAY[now.weekday()],
        "userId"        : user_uid,
        "source"        : "keypad",
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
    """
    Handle feed dispensing with countdown timer.

    Returns:
        (dispense_active, dispense_countdown_start)
    """
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
    current_auto_refill_water_enabled_state : bool,
    current_water_level                     : float,
    current_water_threshold_warning         : int,
    water_button_state                      : bool,
    MAX_REFILL_LEVEL                        : int,
    refill_active                           : bool,
) -> bool:
    """
    Handle water refilling — auto-refill and manual button control.

    Latch behaviour:
        - Refill starts when button pressed OR auto-refill threshold crossed.
        - Once active, only the level check (>= MAX_REFILL_LEVEL) stops it.
        - Button state is IGNORED while refill is already active to prevent
          the relay from flickering if water_button_pressed stays True across
          multiple ticks (e.g. is_fresh() returns True for 60s after one press).

    Returns:
        bool: Whether refilling should be active.
    """
    if not refill_active:
        # Only START refill from these conditions
        if water_button_state and current_water_level < MAX_REFILL_LEVEL:
            # Guard: don't start if tank is already at/above capacity.
            # Prevents a 1-tick relay pulse and a useless analytics entry.
            refill_active = True
        elif current_auto_refill_water_enabled_state:
            if current_water_level <= current_water_threshold_warning:
                refill_active = True

    if refill_active and current_water_level >= MAX_REFILL_LEVEL:
        refill_active = False

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
    """
    Update LCD with current system status.
    Silent on failure — LCD errors must not crash the main loop.
    """
    if lcd_obj is None:
        return
    try:
        line1 = (
            "DISPENSING..."             if dispense_active else
            f"FEED LOW {current_feed_level}%"  if feed_warning    else
            f"Feed: {current_feed_level}%"
        )
        line2 = (
            "REFILLING..."              if refill_active   else
            f"WATER LOW {current_water_level}%" if water_warning  else
            f"Water: {current_water_level}%"
        )
        lcd_obj.show([line1, line2])
    except Exception:
        pass  # LCD failure is non-critical; caller already has a reference to log if desired


# ─────────────────────────── PROCESS B ───────────────────────────────────────

def process_B(**kwargs) -> None:
    """
    Hardware control process — sensors, motors, LCD, Firebase sync.

    Expected kwargs["process_B_args"] keys:
        TASK_NAME          : str
        status_checker     : multiprocessing.Event
        live_status        : multiprocessing.Event
        logout_requested   : multiprocessing.Event  — set when user holds D for 3 s
        USER_CREDENTIAL    : dict  {userUid, deviceUid}
        LCD_I2C_ADDR       : int   (default 0x27)

    DISPENSE_COUNTDOWN_TIME is no longer passed from main.py.
    Process B reads it from settings/{userUid}/feed/dispenseCountdownMs after
    Firebase is initialized. Falls back to a local cache file, then to the
    hardcoded DEFAULT_DISPENSE_COUNTDOWN_MS if both are unavailable.
    """
    args              = kwargs["process_B_args"]
    TASK_NAME         = args["TASK_NAME"]
    status_checker    = args["status_checker"]
    live_status       = args["live_status"]
    logout_requested  = args["logout_requested"]
    USER_CREDENTIAL   = args["USER_CREDENTIAL"]
    LCD_I2C_ADDR      = args.get("LCD_I2C_ADDR", 0x27)

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

    # ── Fetch dispense countdown from Firebase (with local cache fallback) ─
    DISPENSE_COUNTDOWN_TIME = _fetch_dispense_countdown(user_uid, TASK_NAME)

    # ── Init hardware ─────────────────────────────────────────────────────
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
    distance.setup_ultrasonics()

    lcd_obj = None
    try:
        lcd_obj = lcd.setup_lcd(addr=LCD_I2C_ADDR, cols=16, rows=2)
        lcd_obj.show(["Chick-Up", "Initializing..."])
        time.sleep(2)
    except Exception as e:
        log(details=f"{TASK_NAME} - LCD init failed, continuing without LCD: {e}", log_type="warning")
        lcd_obj = None

    # ── State ─────────────────────────────────────────────────────────────
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

    current_feed_threshold_warning          = 20
    current_dispense_volume_percent         = 0
    current_water_threshold_warning         = 20
    current_auto_refill_water_enabled_state = False

    refill_active            = False
    dispense_active          = False
    dispense_countdown_start = 0
    MAX_REFILL_LEVEL         = 95

    # Boot stabilization — skip motor logic for the first N ticks.
    # Without this, sensors read 0.0% on the very first loop iteration
    # (before the ultrasonic median filter has a stable reading), which
    # causes auto-refill to fire immediately if water_threshold_warning > 0.
    # 20 ticks × 100 ms = 2 seconds of settling time.
    BOOT_STABILIZATION_TICKS = 20
    boot_ticks_elapsed        = 0

    # Last button timestamps the device has already acted on.
    # Prevents re-triggering while is_fresh() still returns True
    # (the app timestamp stays "fresh" for 60s after a single press).
    last_acted_feed_timestamp  = None
    last_acted_water_timestamp = None

    water_level_before_refill   = 0.0
    feed_level_before_dispense  = 0.0
    prev_refill_active          = False
    prev_dispense_active        = False

    last_lcd_update      = 0.0
    LCD_UPDATE_INTERVAL  = 1.0    # seconds

    last_db_error_log    = 0.0
    DB_ERROR_LOG_INTERVAL = 10.0  # suppress repeated DB error logs

    # ── Logout via D-key hold ─────────────────────────────────────────
    # Holding D for LOGOUT_HOLD_SECONDS triggers a logout request.
    # main.py monitors logout_requested Event and handles the actual logout.
    LOGOUT_HOLD_SECONDS  = 3.0
    d_key_hold_start     = 0.0   # monotonic time when D was first seen held
    d_key_held           = False

    # ── Main loop ─────────────────────────────────────────────────────────
    try:
        while True:
            if not status_checker.is_set():
                log(details=f"{TASK_NAME} - status_checker cleared, shutting down", log_type="warning")
                break

            current_time = time.time()
            time.sleep(0.1)

            # ── Read pins ─────────────────────────────────────────────
            try:
                pins_data = _read_pins_data(keypad_instance)
                current_feed_level                  = pins_data["current_feed_level"]
                current_water_level                 = pins_data["current_water_level"]
                current_feed_physical_button_state  = pins_data["current_feed_physical_button_state"]
                current_water_physical_button_state = pins_data["current_water_physical_button_state"]
                raw_key                             = pins_data["raw_key"]
            except Exception as e:
                log(details=f"{TASK_NAME} - Sensor read failed: {e}", log_type="error")
                status_checker.clear()
                break

            # ── D-key hold → logout request ───────────────────────────
            # Hold D for LOGOUT_HOLD_SECONDS to request a logout.
            # main.py monitors the logout_requested Event and handles
            # stopping processes + calling auth.logout() + re-pairing.
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
                current_feed_app_button_state   = database_data["current_feed_app_button_state"]
                current_water_app_button_state  = database_data["current_water_app_button_state"]
                raw_feed_timestamp              = database_data["raw_feed_timestamp"]
                raw_water_timestamp             = database_data["raw_water_timestamp"]
                current_feed_schedule_state     = database_data["current_feed_schedule_state"]
                current_live_button_state       = database_data["current_live_button_state"]

                user_settings                           = database_data["current_user_settings"]
                current_feed_threshold_warning          = user_settings["feed_threshold_warning"]
                current_dispense_volume_percent         = user_settings["dispense_volume_percent"]
                current_water_threshold_warning         = user_settings["water_threshold_warning"]
                current_auto_refill_water_enabled_state = user_settings["auto_refill_water_enabled"]

                # Live update — picks up app changes to dispense countdown mid-session.
                # Only update if the value changed to avoid redundant cache writes.
                new_countdown = user_settings.get("dispense_countdown_ms")
                if isinstance(new_countdown, int) and new_countdown > 0 and new_countdown != DISPENSE_COUNTDOWN_TIME:
                    log(details=f"{TASK_NAME} - dispenseCountdownMs updated: {DISPENSE_COUNTDOWN_TIME}ms → {new_countdown}ms", log_type="info")
                    DISPENSE_COUNTDOWN_TIME = new_countdown
                    _save_cached_countdown(new_countdown)
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

            # ── Level warnings ────────────────────────────────────────
            feed_warning  = current_feed_level  <= current_feed_threshold_warning
            water_warning = current_water_level <= current_water_threshold_warning

            # ── Physical keypad → Firebase timestamp ──────────────────
            if current_feed_physical_button_state:
                try:
                    _update_button_timestamp(database_ref, "feed")
                except firebase_rtdb.FirebaseWriteError as e:
                    log(details=f"{TASK_NAME} - {e}", log_type="warning")

            if current_water_physical_button_state:
                try:
                    _update_button_timestamp(database_ref, "water")
                except firebase_rtdb.FirebaseWriteError as e:
                    log(details=f"{TASK_NAME} - {e}", log_type="warning")

            # ── Button aggregation ────────────────────────────────────
            # App button: only treat as a new press if the timestamp has
            # changed since we last acted on it. This prevents re-triggering
            # for the full 60s that is_fresh() stays True after a single press.
            feed_app_new_press  = (
                current_feed_app_button_state and
                raw_feed_timestamp  is not None and
                raw_feed_timestamp  != last_acted_feed_timestamp
            )
            water_app_new_press = (
                current_water_app_button_state and
                raw_water_timestamp is not None and
                raw_water_timestamp != last_acted_water_timestamp
            )

            feed_button_pressed = (
                current_feed_physical_button_state or
                feed_app_new_press                 or
                current_feed_schedule_state
            ) and not dispense_active

            water_button_pressed = (
                current_water_physical_button_state or
                water_app_new_press
            )

            # Acknowledge timestamps once we act on them
            if feed_app_new_press:
                last_acted_feed_timestamp  = raw_feed_timestamp
            if water_app_new_press:
                last_acted_water_timestamp = raw_water_timestamp

            # ── Boot stabilization ────────────────────────────────────
            # Skip motor / refill / dispense logic for the first
            # BOOT_STABILIZATION_TICKS iterations so ultrasonic sensors
            # have time to produce stable readings. Without this, 0%
            # sensor readings at boot can trigger auto-refill immediately
            # if auto-refill is enabled and the threshold is > 0.
            if boot_ticks_elapsed < BOOT_STABILIZATION_TICKS:
                boot_ticks_elapsed += 1
                continue

            # ── Snapshot levels before new action starts ──────────────
            if feed_button_pressed and not dispense_active:
                feed_level_before_dispense = current_feed_level

            # Manual button snapshot — taken before _refill_it runs
            if water_button_pressed and not refill_active:
                water_level_before_refill = current_water_level

            # Auto-refill snapshot — button is never pressed for this path,
            # so we must snapshot here before _refill_it starts the pump.
            # Without this, water_level_before_refill stays 0.0 and the
            # analytics entry logs a meaningless volume.
            if (
                not refill_active
                and not water_button_pressed
                and current_auto_refill_water_enabled_state
                and current_water_level <= current_water_threshold_warning
            ):
                water_level_before_refill = current_water_level

            # ── Motor logic ───────────────────────────────────────────
            dispense_active, dispense_countdown_start = _dispense_it(
                feed_button_state        = feed_button_pressed,
                dispense_active          = dispense_active,
                dispense_countdown_start = dispense_countdown_start,
                DISPENSE_COUNTDOWN_TIME  = DISPENSE_COUNTDOWN_TIME,
            )

            refill_active = _refill_it(
                current_auto_refill_water_enabled_state = current_auto_refill_water_enabled_state,
                current_water_level                     = current_water_level,
                current_water_threshold_warning         = current_water_threshold_warning,
                water_button_state                      = water_button_pressed,
                MAX_REFILL_LEVEL                        = MAX_REFILL_LEVEL,
                refill_active                           = refill_active,
            )

            # ── Analytics on action completion ────────────────────────
            if prev_dispense_active and not dispense_active:
                try:
                    _log_analytics(user_uid, "feed", max(feed_level_before_dispense - current_feed_level, 0))
                except firebase_rtdb.FirebaseWriteError as e:
                    log(details=f"{TASK_NAME} - Analytics write failed: {e}", log_type="warning")
                feed_level_before_dispense = 0.0

            if prev_refill_active and not refill_active:
                try:
                    _log_analytics(user_uid, "water", max(current_water_level - water_level_before_refill, 0))
                except firebase_rtdb.FirebaseWriteError as e:
                    log(details=f"{TASK_NAME} - Analytics write failed: {e}", log_type="warning")
                water_level_before_refill = 0.0

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

    except Exception as e:
        log(details=f"{TASK_NAME} - Unexpected error: {e}", log_type="error")
        status_checker.clear()
        raise

    finally:
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