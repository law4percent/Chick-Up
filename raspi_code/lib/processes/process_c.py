import time
from lib.services import firebase_rtdb
from datetime import datetime
import logging

from lib import logger_config

import RPi.GPIO as GPIO
from lib.services.hardware import (
    keypad_controller as keypad,
    motor_controller as motor,
    ultrasonic_contoller as distance
)

logger = logger_config.setup_logger(name=__name__, level=logging.DEBUG)

# ================= HELPER FUNCTIONS =================
def _handle_feed_dispense(state: bool) -> None:
    if state:
        motor.run_left_motor()
    motor.stop_left_motor()
    
    
def _handle_water_refill(state: bool) -> None:
    if state:
        motor.run_right_motor()
    motor.stop_right_motor()


def _read_pins_data(PC_MODE: bool):
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
    
    # ============== DISPENSE OR REFILL ==============
    key = keypad.scan_key()
    if key != None:
        # Check if this is * or #
        if key == '*':
            current_feed_physical_button_state = True
        elif key == '#':
            current_water_physical_button_state = True
    
    feed_level = distance.read_left_distance()
    percentage_feed_level = _convert_to_percentage(feed_level)
    water_level = distance.read_left_distance()
    percentage_water_level = _convert_to_percentage(water_level)
    return {
        "status"                                : "success",
        "current_feed_level"                    : percentage_feed_level,
        "current_water_level"                   : percentage_water_level,
        "current_feed_physical_button_state"    : current_feed_physical_button_state,
        "current_water_physical_button_state"   : current_water_physical_button_state,
    }
            

def _current_millis():
    return int(time.monotonic() * 1000)


def _convert_to_percentage(distance_cm, min_dist=10, max_dist=300) -> float:
    if distance_cm <= min_dist:
        return 100
    if distance_cm >= max_dist:
        return 0
    
    percent = (max_dist - distance_cm) / (max_dist - min_dist) * 100
    return round(percent, 2)


def _dispense_it(
        feed_button_state: bool,
        dispense_active: bool,
        dispense_countdown_start: int,
        DISPENSE_COUNTDOWN_TIME: int
    ):
    now = _current_millis()

    # Start countdown ONLY once
    if feed_button_state and not dispense_active:
        dispense_active = True
        dispense_countdown_start = now

    if dispense_active:
        elapsed = now - dispense_countdown_start
        if elapsed >= DISPENSE_COUNTDOWN_TIME:
            dispense_active = False

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
    if current_auto_refill_water_enabled_state:
        if current_water_level <= current_water_threshold_warning:
            refill_active = True
            
    if not refill_active and water_button_state:#
        refill_active = True
            
    if current_water_level >= MAX_REFILL_LEVEL and refill_active:
        refill_active = False
    
    _handle_water_refill(refill_active)
    return refill_active
        


# ========================= WIP: LCD =========================
def process_C(**kwargs) -> None:
    process_C_args          = kwargs["process_C_args"]
    TASK_NAME               = process_C_args["TASK_NAME"]
    status_checker          = process_C_args["status_checker"]
    live_status             = process_C_args["live_status"]
    annotated_option        = process_C_args["annotated_option"] # work in progress
    USER_CREDENTIAL         = process_C_args["USER_CREDENTIAL"]
    PC_MODE                 = process_C_args["PC_MODE"]
    SAVE_LOGS               = process_C_args["SAVE_LOGS"]
    DISPENSE_COUNTDOWN_TIME = process_C_args["DISPENSE_COUNTDOWN_TIME"] 
    
    print(f"{TASK_NAME} - Running✅")
    logger.info(f"{TASK_NAME} - Running✅")
    
    init_result = firebase_rtdb.initialize_firebase()
    if init_result["status"] == "error":
        status_checker.clear()
        if SAVE_LOGS:
            logger.error(f"{TASK_NAME} - {init_result["message"]}. Source: {__name__}")
        exit()
        
        
    user_uid    = USER_CREDENTIAL["userUid"]
    device_uid  = USER_CREDENTIAL["deviceUid"]
    
    database_ref = firebase_rtdb.setup_RTDB(
        user_uid    = user_uid,
        device_uid  = device_uid,
    )
    
    keypad.setup_keypad()
    motor.setup_motors()
    distance.setup_ultrasonics()
    
    current_feed_level                  = 0
    current_water_level                 = 0
    current_feed_physical_button_state  = 0
    current_water_physical_button_state = 0
    
    current_feed_app_button_state   = 0
    current_water_app_button_state  = 0
    current_feed_schedule_state     = 0
    current_live_button_state       = 0
    
    # ========== USER SETTINGS ==========
    current_feed_threshold_warning          = 20 #minimun
    current_dispense_volume_percent         = 0 # Work in progress
    current_water_threshold_warning         = 20 #minimun
    current_auto_refill_water_enabled_state = False
    
    refill_active               = False
    dispense_active             = False
    dispense_countdown_start    = 0
    MAX_REFILL_LEVEL            = 95
    
    try:
        while True:
            if not status_checker.is_set():
                if SAVE_LOGS:
                    logger.error(f"{TASK_NAME} - One of the processes got error.")
                GPIO.cleanup()
                exit()
                
            time.sleep(0.1)
            # ================== GET ALL DATA FROM PINS ==================
            pins_data_result = _read_pins_data(PC_MODE)
            # print("pins_data_result:\n", pins_data_result)
            # print("==================================")
            if pins_data_result["status"] == "error":
                if SAVE_LOGS:
                    logger.error(f"{TASK_NAME} - {pins_data_result["message"]}")
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
                if SAVE_LOGS:
                    logger.warning(f"{TASK_NAME} - {e}. Skip reading buttons from RTDB. No internet.")
            
            # ================== TAKE ACTIONS ==================
            # Modify Live Stream Status
            if current_live_button_state:
                live_status.set()
            else:
                live_status.clear()
            

            
            # ================== WIP ==================
            # Warn it!
            if current_feed_level <= current_feed_threshold_warning:
                # print("FEED LEVEL LOW!")
                # handle_hardware.lcd_print(lcd, "FEED LOW", f"Level: {feed_level}%")
                pass
            
            # ================== WIP ==================
            # Warn it!
            if current_water_level <= current_water_threshold_warning:
                # print("WATER LEVEL LOW!")
                # handle_hardware.lcd_print(lcd, "WATER LOW", f"Level: {water_level}%") 
                pass
            
            # Dispense it!
            dispense_active, dispense_countdown_start = _dispense_it(
                feed_button_state = (
                    (current_feed_physical_button_state or
                    current_feed_app_button_state or
                    current_feed_schedule_state)
                    and not dispense_active
                ),
                dispense_active             = dispense_active, 
                dispense_countdown_start    = dispense_countdown_start, 
                DISPENSE_COUNTDOWN_TIME     = DISPENSE_COUNTDOWN_TIME,
            )
            
            # Refill it!
            refill_active = _refill_it(
                current_auto_refill_water_enabled_state = current_auto_refill_water_enabled_state,
                current_water_level                     = current_water_level,
                current_water_threshold_warning         = current_water_threshold_warning,
                water_button_state                      = current_water_physical_button_state or current_water_app_button_state,
                MAX_REFILL_LEVEL                        = MAX_REFILL_LEVEL,
                refill_active                           = refill_active
            )
            
            print("dispense_active:", dispense_active)
            print("refill_active:", refill_active)
            
            
            # ================= UPDATE ALL DATA TO DB =================
            try:
                sensors_ref = database_ref["sensors_ref"].get()
                sensors_ref.update({
                    "feedLevel" : current_feed_level,
                    "waterLevel": current_water_level,
                    "updatedAt" : datetime.now().strftime('%m/%d/%Y %H:%M:%S')
                })
            except Exception as e:
                if SAVE_LOGS:
                    logger.warning(f"{TASK_NAME} - {e}. Skip update feedLevel and waterLevel to database. No internet.")

    except KeyboardInterrupt:
        logger.warning(f"{TASK_NAME} - Keyboard interrupt detected at {__name__}")
        status_checker.clear()
        
    GPIO.cleanup()