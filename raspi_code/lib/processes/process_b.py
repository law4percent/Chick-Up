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
    keypad_controller       as keypad,
    motor_controller        as motor,
    lcd_controller          as lcd,
)
from lib.services.hardware.motor_controller import MotorError, MotorSetupError
from lib.services.logger import get_logger
from raspi_code.lib.services.hardware import ultrasonic_controller as distance

log = get_logger("process_b.py")

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


def _read_pins_data() -> dict:
    """
    Read all sensors and keypad state.

    Returns:
        dict with keys:
            current_feed_level                  : float
            current_water_level                 : float
            current_feed_physical_button_state  : bool
            current_water_physical_button_state : bool

    Raises:
        RuntimeError: If any sensor or keypad read fails unexpectedly.
    """
    current_feed_physical_button_state  = False
    current_water_physical_button_state = False

    key = keypad.scan_key()
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

    Returns:
        bool: Whether refilling should be active.
    """
    if current_auto_refill_water_enabled_state:
        if current_water_level <= current_water_threshold_warning and not refill_active:
            refill_active = True

    if not refill_active and water_button_state:
        refill_active = True

    if current_water_level >= MAX_REFILL_LEVEL and refill_active:
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
        lcd_obj.display_message(line1, line2)
    except Exception:
        pass  # LCD failure is non-critical; caller already has a reference to log if desired


# ─────────────────────────── PROCESS B ───────────────────────────────────────

def process_B(**kwargs) -> None:
    """
    Hardware control process — sensors, motors, LCD, Firebase sync.

    Expected kwargs["process_B_args"] keys:
        TASK_NAME               : str
        status_checker          : multiprocessing.Event
        live_status             : multiprocessing.Event
        USER_CREDENTIAL         : dict  {userUid, deviceUid}
        DISPENSE_COUNTDOWN_TIME : int   (milliseconds)
        LCD_I2C_ADDR            : int   (default 0x27)
    """
    args                    = kwargs["process_B_args"]
    TASK_NAME               = args["TASK_NAME"]
    status_checker          = args["status_checker"]
    live_status             = args["live_status"]
    USER_CREDENTIAL         = args["USER_CREDENTIAL"]
    DISPENSE_COUNTDOWN_TIME = args["DISPENSE_COUNTDOWN_TIME"]
    LCD_I2C_ADDR            = args.get("LCD_I2C_ADDR", 0x27)

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

    # ── Init hardware ─────────────────────────────────────────────────────
    keypad.setup_keypad()
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
        lcd_obj.display_message("Chick-Up", "Initializing...")
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

    current_feed_threshold_warning          = 20
    current_dispense_volume_percent         = 0
    current_water_threshold_warning         = 20
    current_auto_refill_water_enabled_state = False

    refill_active            = False
    dispense_active          = False
    dispense_countdown_start = 0
    MAX_REFILL_LEVEL         = 95

    water_level_before_refill   = 0.0
    feed_level_before_dispense  = 0.0
    prev_refill_active          = False
    prev_dispense_active        = False

    last_lcd_update      = 0.0
    LCD_UPDATE_INTERVAL  = 1.0    # seconds

    last_db_error_log    = 0.0
    DB_ERROR_LOG_INTERVAL = 10.0  # suppress repeated DB error logs

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
                pins_data = _read_pins_data()
                current_feed_level                  = pins_data["current_feed_level"]
                current_water_level                 = pins_data["current_water_level"]
                current_feed_physical_button_state  = pins_data["current_feed_physical_button_state"]
                current_water_physical_button_state = pins_data["current_water_physical_button_state"]
            except Exception as e:
                log(details=f"{TASK_NAME} - Sensor read failed: {e}", log_type="error")
                status_checker.clear()
                break

            # ── Read Firebase ─────────────────────────────────────────
            try:
                database_data = firebase_rtdb.read_RTDB(database_ref=database_ref)
                current_feed_app_button_state   = database_data["current_feed_app_button_state"]
                current_water_app_button_state  = database_data["current_water_app_button_state"]
                current_feed_schedule_state     = database_data["current_feed_schedule_state"]
                current_live_button_state       = database_data["current_live_button_state"]

                user_settings                           = database_data["current_user_settings"]
                current_feed_threshold_warning          = user_settings["feed_threshold_warning"]
                current_dispense_volume_percent         = user_settings["dispense_volume_percent"]
                current_water_threshold_warning         = user_settings["water_threshold_warning"]
                current_auto_refill_water_enabled_state = user_settings["auto_refill_water_enabled"]
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
            feed_button_pressed = (
                current_feed_physical_button_state or
                current_feed_app_button_state      or
                current_feed_schedule_state
            ) and not dispense_active

            water_button_pressed = (
                current_water_physical_button_state or
                current_water_app_button_state
            )

            # ── Snapshot levels before new action starts ──────────────
            if feed_button_pressed and not dispense_active:
                feed_level_before_dispense = current_feed_level

            if water_button_pressed and not refill_active:
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
                lcd_obj.display_message("Chick-Up", "Shutting down...")
                time.sleep(1)
                lcd.cleanup_lcd()
            except Exception:
                pass
        GPIO.cleanup()
        log(details=f"{TASK_NAME} - Process stopped", log_type="info")