"""
Process C - Hardware Control with LCD Display
Handles sensors, motors, and LCD status display
"""
import time
from lib.services import firebase_rtdb
from datetime import datetime
import logging
import RPi.GPIO as GPIO

from lib import logger_config
from lib.services.hardware import (
    keypad_controller as keypad,
    motor_controller as motor,
    ultrasonic_contoller as distance,
    lcd_controller as lcd
)

logger = logger_config.setup_logger(name=__name__, level=logging.INFO)

# ================= HELPER FUNCTIONS =================
def _handle_water_refill(state: bool) -> None:
    """Control water motor (GPIO 27 Relay)"""
    if state:
        logger.debug("Starting water motor")
        motor.start_water_motor()
    else:
        logger.debug("Stopping water motor")
        motor.stop_water_motor()


def _handle_feed_dispense(state: bool) -> None:
    """Control feed motor (GPIO 17 Relay)"""
    if state:
        logger.debug("Starting feed motor")
        motor.start_feed_motor()
    else:
        logger.debug("Stopping feed motor")
        motor.stop_feed_motor()


def _read_pins_data(PC_MODE: bool):
    """Read data from all sensors and buttons."""
    if PC_MODE:
        return {    
            "status"                                : "error",
            "message"                               : f"Cannot get data from pins due in PC MODE. Source: {__name__}",
            "current_feed_level"                    : 0,
            "current_water_level"                   : 0,
            "current_key_pressed"                   : 0,
            "current_feed_physical_button_state"    : 0,
            "current_water_physical_button_state"   : 0,
        }
        
    current_feed_physical_button_state  = False
    current_water_physical_button_state = False
    
    # ============== KEYPAD BUTTONS ==============
    key = keypad.scan_key()
    if key is not None:
        logger.debug(f"Key pressed: {key}")
        # Check if this is * or #
        if key == '*':
            current_feed_physical_button_state = True
            logger.info("Feed button pressed on keypad (*)")
        elif key == '#':
            current_water_physical_button_state = True
            logger.info("Water button pressed on keypad (#)")
    
    # ============== ULTRASONIC SENSORS ==============
    feed_level              = distance.read_left_distance()
    percentage_feed_level   = _convert_to_percentage(feed_level)
    water_level             = distance.read_right_distance()
    percentage_water_level  = _convert_to_percentage(water_level)
    
    return {
        "status"                                : "success",
        "current_feed_level"                    : percentage_feed_level,
        "current_water_level"                   : percentage_water_level,
        "current_feed_physical_button_state"    : current_feed_physical_button_state,
        "current_water_physical_button_state"   : current_water_physical_button_state,
    }
            

def _current_millis():
    """Get current time in milliseconds."""
    return int(time.monotonic() * 1000)


def _convert_to_percentage(distance_cm, min_dist=10, max_dist=300) -> float:
    """
    Convert distance to percentage (100% = full, 0% = empty).
    
    Args:
        distance_cm: Distance in centimeters
        min_dist: Minimum distance (100% full)
        max_dist: Maximum distance (0% empty)
    """
    if distance_cm <= min_dist:
        return 100.0
    if distance_cm >= max_dist:
        return 0.0
    
    percent = (max_dist - distance_cm) / (max_dist - min_dist) * 100
    return round(percent, 2)


def _dispense_it(
        feed_button_state: bool,
        dispense_active: bool,
        dispense_countdown_start: int,
        DISPENSE_COUNTDOWN_TIME: int
    ):
    """
    Handle feed dispensing with countdown timer.
    
    Args:
        feed_button_state: Whether button is pressed
        dispense_active: Whether dispensing is currently active
        dispense_countdown_start: Start time of dispense countdown
        DISPENSE_COUNTDOWN_TIME: Duration to dispense in milliseconds
    
    Returns:
        Tuple of (dispense_active, dispense_countdown_start)
    """
    now = _current_millis()

    # Start countdown ONLY once when button is pressed
    if feed_button_state and not dispense_active:
        dispense_active = True
        dispense_countdown_start = now
        logger.info(f"Feed dispense started (duration: {DISPENSE_COUNTDOWN_TIME}ms)")

    if dispense_active:
        elapsed = now - dispense_countdown_start
        if elapsed >= DISPENSE_COUNTDOWN_TIME:
            dispense_active = False
            logger.info("Feed dispense completed")

    _handle_feed_dispense(dispense_active)
    return dispense_active, dispense_countdown_start

    
def _refill_it(
        current_auto_refill_water_enabled_state: bool, 
        current_water_level: float, 
        current_water_threshold_warning: int, 
        water_button_state: bool, 
        MAX_REFILL_LEVEL: int,
        refill_active: bool
    ) -> bool:
    """
    Handle water refilling with auto-refill and manual control.
    
    Args:
        current_auto_refill_water_enabled_state: Auto refill enabled?
        current_water_level: Current water level percentage
        current_water_threshold_warning: Minimum threshold
        water_button_state: Manual button pressed?
        MAX_REFILL_LEVEL: Maximum level to stop refilling
        refill_active: Currently refilling?
    
    Returns:
        bool: Whether refilling should be active
    """
    # Auto refill if enabled and below threshold
    if current_auto_refill_water_enabled_state:
        if current_water_level <= current_water_threshold_warning and not refill_active:
            refill_active = True
            logger.info(f"Auto refill started (level: {current_water_level}%)")
            
    # Manual refill button
    if not refill_active and water_button_state:
        refill_active = True
        logger.info("Manual refill started")
            
    # Stop when full
    if current_water_level >= MAX_REFILL_LEVEL and refill_active:
        refill_active = False
        logger.info(f"Refill stopped (level: {current_water_level}%)")
    
    _handle_water_refill(refill_active)
    return refill_active


def _update_lcd_display(
        lcd_obj,
        current_feed_level: float,
        current_water_level: float,
        feed_warning: bool,
        water_warning: bool,
        dispense_active: bool,
        refill_active: bool
    ):
    """
    Update LCD display with current status.
    
    Args:
        lcd_obj: LCD controller instance
        current_feed_level: Feed level percentage
        current_water_level: Water level percentage
        feed_warning: Feed level low?
        water_warning: Water level low?
        dispense_active: Currently dispensing?
        refill_active: Currently refilling?
    """
    if lcd_obj is None:
        return
    
    try:
        # Line 1: Feed status
        if dispense_active:
            line1 = "DISPENSING..."
        elif feed_warning:
            line1 = f"FEED LOW {current_feed_level}%"
        else:
            line1 = f"Feed: {current_feed_level}%"
        
        # Line 2: Water status
        if refill_active:
            line2 = "REFILLING..."
        elif water_warning:
            line2 = f"WATER LOW {current_water_level}%"
        else:
            line2 = f"Water: {current_water_level}%"
        
        # Update display
        lcd_obj.display_message(line1, line2)
        
    except Exception as e:
        logger.error(f"Error updating LCD: {e}")


# ========================= MAIN PROCESS =========================
def process_C(**kwargs) -> None:
    """Main process for hardware control and LCD display."""
    process_C_args          = kwargs["process_C_args"]
    TASK_NAME               = process_C_args["TASK_NAME"]
    status_checker          = process_C_args["status_checker"]
    live_status             = process_C_args["live_status"]
    USER_CREDENTIAL         = process_C_args["USER_CREDENTIAL"]
    PC_MODE                 = process_C_args["PC_MODE"]
    SAVE_LOGS               = process_C_args["SAVE_LOGS"]
    DISPENSE_COUNTDOWN_TIME = process_C_args["DISPENSE_COUNTDOWN_TIME"]
    LCD_ENABLED             = True # process_C_args.get("LCD_ENABLED", True)  # Enable/disable LCD
    LCD_I2C_ADDR            = 0x27 # process_C_args.get("LCD_I2C_ADDR", 0x27)  # I2C address
    
    print(f"{TASK_NAME} - Running✅")
    if SAVE_LOGS:
        logger.info(f"{TASK_NAME} - Running")
    
    if not PC_MODE:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
    
    # Initialize Firebase
    init_result = firebase_rtdb.initialize_firebase()
    if init_result["status"] == "error":
        status_checker.clear()
        if SAVE_LOGS:
            logger.error(f"{TASK_NAME} - {init_result['message']}. Source: {__name__}")
        if not PC_MODE:
            GPIO.cleanup()
        exit()
        
    user_uid    = USER_CREDENTIAL["userUid"]
    device_uid  = USER_CREDENTIAL["deviceUid"]
    
    database_ref = firebase_rtdb.setup_RTDB(
        user_uid    = user_uid,
        device_uid  = device_uid,
    )
    
    # Setup hardware only if not in PC_MODE
    lcd_obj = None
    if not PC_MODE:
        keypad.setup_keypad()
        motor.setup_motors()
        distance.setup_ultrasonics()
        
        # Setup LCD if enabled
        if LCD_ENABLED:
            try:
                lcd_obj = lcd.setup_lcd(addr=LCD_I2C_ADDR, cols=16, rows=2)
                lcd_obj.display_message("Chick-Up", "Initializing...")
                time.sleep(2)
                logger.info("LCD initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize LCD: {e}")
                logger.error("Continuing without LCD display")
                lcd_obj = None
    
    # Initialize state variables
    current_feed_level                  = 0
    current_water_level                 = 0
    current_feed_physical_button_state  = False
    current_water_physical_button_state = False
    
    current_feed_app_button_state   = False
    current_water_app_button_state  = False
    current_feed_schedule_state     = False
    current_live_button_state       = False
    
    # User settings
    current_feed_threshold_warning          = 20  # minimum %
    current_dispense_volume_percent         = 0   # Work in progress
    current_water_threshold_warning         = 20  # minimum %
    current_auto_refill_water_enabled_state = False
    
    # Motor control state
    refill_active               = False
    dispense_active             = False
    dispense_countdown_start    = 0
    MAX_REFILL_LEVEL            = 95  # Stop refilling at 95%
    
    # LCD update throttling
    last_lcd_update = 0
    LCD_UPDATE_INTERVAL = 1.0  # Update LCD every 1 second
    
    # Debug logging throttling
    last_debug_log = 0
    DEBUG_LOG_INTERVAL = 10.0  # Log debug info every 10 seconds
    
    try:
        logger.info("Process C main loop started")
        
        while True:
            if not status_checker.is_set():
                if SAVE_LOGS:
                    logger.error(f"{TASK_NAME} - One of the processes got error.")
                if not PC_MODE:
                    motor.stop_all_motors()
                    if lcd_obj:
                        lcd.cleanup_lcd()
                    GPIO.cleanup()
                exit()
            
            current_time = time.time()
            time.sleep(0.1)  # 100ms loop
            
            # ================== GET ALL DATA FROM PINS ==================
            pins_data_result = _read_pins_data(PC_MODE)
            if pins_data_result["status"] == "error":
                if SAVE_LOGS:
                    logger.warning(f"{TASK_NAME} - {pins_data_result['message']}")
            
            current_feed_level                  = pins_data_result["current_feed_level"]
            current_water_level                 = pins_data_result["current_water_level"]
            current_feed_physical_button_state  = pins_data_result["current_feed_physical_button_state"]
            current_water_physical_button_state = pins_data_result["current_water_physical_button_state"]
            
            # ================== GET ALL DATA FROM DB ==================
            try:
                database_data                   = firebase_rtdb.read_RTDB(database_ref=database_ref)
                current_feed_app_button_state   = database_data["current_feed_app_button_state"]
                current_water_app_button_state  = database_data["current_water_app_button_state"]
                current_feed_schedule_state     = database_data["current_feed_schedule_state"]
                current_live_button_state       = database_data["current_live_button_state"]
            
                current_user_settings                   = database_data["current_user_settings"]
                current_feed_threshold_warning          = current_user_settings["feed_threshold_warning"]
                current_dispense_volume_percent         = current_user_settings["dispense_volume_percent"]
                current_water_threshold_warning         = current_user_settings["water_threshold_warning"]
                current_auto_refill_water_enabled_state = current_user_settings["auto_refill_water_enabled"]
            except Exception as e:
                if current_time - last_debug_log >= DEBUG_LOG_INTERVAL:
                    logger.warning(f"Skip reading from RTDB - {e}")
                    last_debug_log = current_time
            
            # ================== TAKE ACTIONS ==================
            # Modify Live Stream Status
            if current_live_button_state:
                live_status.set()
            else:
                live_status.clear()
            
            # Check if levels are low
            feed_warning = current_feed_level <= current_feed_threshold_warning
            water_warning = current_water_level <= current_water_threshold_warning
            
            # Dispense feed if button pressed
            feed_button_pressed = (
                current_feed_physical_button_state or
                current_feed_app_button_state or
                current_feed_schedule_state
            ) and not dispense_active
            
            dispense_active, dispense_countdown_start = _dispense_it(
                feed_button_state           = feed_button_pressed,
                dispense_active             = dispense_active, 
                dispense_countdown_start    = dispense_countdown_start, 
                DISPENSE_COUNTDOWN_TIME     = DISPENSE_COUNTDOWN_TIME,
            )
            
            # Refill water if button pressed or auto-refill enabled
            water_button_pressed = (
                current_water_physical_button_state or 
                current_water_app_button_state
            )
            
            refill_active = _refill_it(
                current_auto_refill_water_enabled_state = current_auto_refill_water_enabled_state,
                current_water_level                     = current_water_level,
                current_water_threshold_warning         = current_water_threshold_warning,
                water_button_state                      = water_button_pressed,
                MAX_REFILL_LEVEL                        = MAX_REFILL_LEVEL,
                refill_active                           = refill_active
            )
            
            # ================= UPDATE LCD DISPLAY =================
            if lcd_obj and (current_time - last_lcd_update >= LCD_UPDATE_INTERVAL):
                _update_lcd_display(
                    lcd_obj             = lcd_obj,
                    current_feed_level  = current_feed_level,
                    current_water_level = current_water_level,
                    feed_warning        = feed_warning,
                    water_warning       = water_warning,
                    dispense_active     = dispense_active,
                    refill_active       = refill_active
                )
                last_lcd_update = current_time
            
            # ================= UPDATE SENSORS TO DB =================
            try:
                sensors_ref_object = database_ref["sensors_ref"]
                sensors_ref_object.update({
                    "feedLevel" : current_feed_level,
                    "waterLevel": current_water_level,
                    "updatedAt" : datetime.now().strftime('%m/%d/%Y %H:%M:%S')
                })
            except Exception as e:
                if current_time - last_debug_log >= DEBUG_LOG_INTERVAL:
                    logger.warning(f"Skip update to database - {e}")
                    last_debug_log = current_time
            
            # ================= DEBUG LOGGING =================
            if current_time - last_debug_log >= DEBUG_LOG_INTERVAL:
                logger.debug(f"Status - Feed: {current_feed_level}%, Water: {current_water_level}%")
                logger.debug(f"Motors - Dispense: {dispense_active}, Refill: {refill_active}")
                last_debug_log = current_time

    except KeyboardInterrupt:
        if SAVE_LOGS:
            logger.warning(f"{TASK_NAME} - Keyboard interrupt detected")
        status_checker.clear()
        if not PC_MODE:
            motor.stop_all_motors()
            if lcd_obj:
                lcd_obj.display_message("Chick-Up", "Shutting down...")
                time.sleep(1)
                lcd.cleanup_lcd()
            GPIO.cleanup()

    except Exception as e:
        if SAVE_LOGS:
            logger.error(f"{TASK_NAME} - Unexpected error: {e}", exc_info=True)
        status_checker.clear()
        if not PC_MODE:
            motor.stop_all_motors()
            if lcd_obj:
                lcd_obj.display_message("ERROR", str(e)[:16])
                time.sleep(2)
                lcd.cleanup_lcd()
            GPIO.cleanup()
        raise