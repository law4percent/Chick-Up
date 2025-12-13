import time
from firebase_admin import db
from lib.services import firebase_rtdb, handle_hardware
from datetime import datetime
import logging

from lib import logger_config

logger = logger_config.setup_logger(name=__name__, level=logging.DEBUG)

# ================= HELPER FUNCTIONS =================
def _handle_live_stream(current_live_button_state, live_status) -> None:
    if current_live_button_state:
        live_status.set()
    live_status.clear()
    
    
def _handle_feed_dispense(feed_motor_relay: any, delay: int) -> None:
    feed_motor_relay.on()
    time.sleep(delay)
    feed_motor_relay.off()
    
    
def _handle_water_refill(water_pump_relay: any, refill_now_state: bool, PC_MODE: bool) -> None:
    if PC_MODE:
        return
    if refill_now_state:
        water_pump_relay.on()
    water_pump_relay.off()
    

# ========================= WIP =========================
def process_C(**kwargs) -> None:
    process_C_args  = kwargs["process_C_args"]
    TASK_NAME       = process_C_args["TASK_NAME"]
    status_checker  = process_C_args["status_checker"]
    live_status     = process_C_args["live_status"]
    annotated_option= process_C_args["annotated_option"] # work in progress
    USER_CREDENTIAL = process_C_args["USER_CREDENTIAL"]
    PC_MODE         = True # process_C_args["PC_MODE"]
    SAVE_LOGS       = process_C_args["SAVE_LOGS"]
    FEED_DELAY      = process_C_args["FEED_DELAY"] 
    
    print(f"{TASK_NAME} - Running✅")
    logger.info(f"{TASK_NAME} - Running✅")
    
    init_result = firebase_rtdb.initialize_firebase()
    if init_result["status"] == "error":
        status_checker.clear()
        logger.error(f"{TASK_NAME} - {init_result["message"]}. Source: {__name__}")
        exit()
        
    user_uid    = USER_CREDENTIAL["userUid"]
    device_uid  = USER_CREDENTIAL["deviceUid"]
    
    feed_level_sensor, water_level_sensor = handle_hardware.setup_level_sensors(
        feed_level_sensor_data= {
            "echo"          : 5,
            "trigger"       : 3,
            "max_distance"  : 4
        },
        water_level_sensor_data={
            "echo"          : 7,
            "trigger"       : 6,
            "max_distance"  : 4
        },
        is_pc_device = PC_MODE
    )
    feed_physical_button, water_physical_button = handle_hardware.setup_physical_buttons(
        feed_physical_button_data = {
            "gpio"      : 12,
            "pull_up"   : True
        },
        water_physical_button_data = {
            "gpio"      : 13,
            "pull_up"   : True
        },
        is_pc_device = PC_MODE
    )
    
    keypad_pins = handle_hardware.setup_keypad(
        keypad_pins_data    = {
            "row_pins": [20, 21, 22, 26],
            "col_pins": [16, 17, 18, 19]
        },
        is_pc_device        = PC_MODE
    )
    
    database = firebase_rtdb.setup_RTDB(
        user_uid    = user_uid,
        device_uid  = device_uid,
    )
    
    lcd = handle_hardware.setup_lcd(
        is_pc_device= True, #PC_MODE,
        lcd_data    = {
            "i2c_driver"    : "PCF8574",
            "i2c_address"   : 0x27  # change to 0x3F if your module has a different address
        }
    )
    
    water_pump_relay = handle_hardware.setup_relay(
        is_pc_device=PC_MODE,
        relay_data  ={
            "gpio"          : 12,        
            "active_high"   : False,
            "initial_value" : True
        }
    )

    feed_motor_relay = handle_hardware.setup_relay(
        is_pc_device=PC_MODE,
        relay_data  ={
            "gpio"          : 13,        
            "active_high"   : False,
            "initial_value" : True
        }
    )

    # feed_motor = handle_hardware.setup_motor_driver(
    #     is_pc_device=PC_MODE,
    #     motor_data={
    #         "in1": 13,
    #         "in2": 14,
    #         "ena": 15
    #     }
    # )
    
    feed_threshold_warning      = 20 # minimum
    water_threshold_warning     = 20 # minimum
    auto_refill_water_enabled   = True
    MAX_REFILL_LEVEL            = 95
    
    current_feed_level                  = 0
    current_water_level                 = 0
    current_feed_physical_button_state  = 0
    current_water_physical_button_state = 0
    
    current_feed_app_button_state   = 0
    current_water_app_button_state  = 0
    current_feed_schedule_state     = 0
    current_live_button_state       = 0
    
    feed_threshold_warning      = 20 #minimun
    dispense_volume_percent     = 0 # Work in progress
    water_threshold_warning     = 20 #minimun
    auto_refill_water_enabled   = False
    
    refill_now_state = False
        
    settings_ref    = db.reference(f"settings/{user_uid}")
    sensors_ref     = db.reference(f"sensors/{user_uid}/{device_uid}")
    
    while True:
        if not status_checker.is_set():
            logger.error(f"{TASK_NAME} - One of the processes got error.")
            exit()
            
        time.sleep(0.1)
        pins_data_result = handle_hardware.read_pins_data(
            feed_physical_button    = feed_physical_button, 
            water_physical_button   = water_physical_button,
            feed_level_sensor       = feed_level_sensor,
            water_level_sensor      = water_level_sensor,
            keypad_pins             = keypad_pins,
            is_pc_device            = PC_MODE,
            save_logs               = SAVE_LOGS,
            user_uid                = user_uid, 
            device_uid              = device_uid
        )
        if pins_data_result["status"] == "error":
            logger.error(f"{TASK_NAME} - {pins_data_result["message"]}")
        
        # ================== ALL DATA FROM PINS ==================
        current_feed_level                  = pins_data_result["current_feed_level"]
        current_water_level                 = pins_data_result["current_water_level"]
        current_feed_physical_button_state  = pins_data_result["current_feed_physical_button_state"]
        current_water_physical_button_state = pins_data_result["current_water_physical_button_state"]
        
        # ================== ALL DATA FROM DB ==================
        try:
            database_data                   = firebase_rtdb.read_RTDB(database=database)
            current_feed_app_button_state   = database_data["current_feed_app_button_state"]
            current_water_app_button_state  = database_data["current_water_app_button_state"]
            current_feed_schedule_state     = database_data["current_feed_schedule_state"]
            current_live_button_state       = database_data["current_live_button_state"]
        except Exception as e:
            logger.warning(f"{TASK_NAME} - {e}. Skip reading buttons from RTDB. No internet.")
        
        # Modify Live Stream Status
        if current_live_button_state:
            live_status.set()
            #print("current_live_button_state:", current_live_button_state)
        else:
            live_status.clear()
        #_handle_live_stream(current_live_button_state, live_status)
        
        # Dispense it!
        if current_feed_physical_button_state or current_feed_app_button_state or current_feed_schedule_state:
            _handle_feed_dispense(feed_motor_relay, FEED_DELAY)
        
        # ==================== GET USER SETTINGS ====================
        try:
            settings                    = settings_ref.get() or {}
            feed_threshold_warning      = settings.get("feed", {}).get("thresholdPercent")
            dispense_volume_percent     = settings.get("feed", {}).get("dispenseVolumePercent") # Work in progress
            water_threshold_warning     = settings.get("water", {}).get("thresholdPercent")
            auto_refill_water_enabled   = settings.get("water", {}).get("autoRefillEnabled")
        except Exception as e:
            logger.warning(f"{TASK_NAME} - {e}. Skip reading user settings. No internet.")
        
        # Warn it!
        if current_feed_level <= feed_threshold_warning:
            # print("FEED LEVEL LOW!")
            # handle_hardware.lcd_print(lcd, "FEED LOW", f"Level: {feed_level}%")
            pass
                
        # Warn it!
        if current_water_level <= water_threshold_warning:
            # print("WATER LEVEL LOW!")
            # handle_hardware.lcd_print(lcd, "WATER LOW", f"Level: {water_level}%") 
            pass
        
        # Refill it!
        if auto_refill_water_enabled:
            if current_water_level <= water_threshold_warning:
                refill_now_state = True
                
        if current_water_level == MAX_REFILL_LEVEL and refill_now_state:
            refill_now_state = False
        
        if not refill_now_state and current_water_physical_button_state or current_water_app_button_state:
            refill_now_state = False
        
        _handle_water_refill(water_pump_relay, refill_now_state, PC_MODE)
        
        # ================= UPDATE ALL DATA TO DB =================
        try:
            sensors_ref.update({
                "feedLevel" : current_feed_level,
                "waterLevel": current_water_level,
                "updatedAt" : datetime.now().strftime('%m/%d/%Y %H:%M:%S')
            })
        except Exception as e:
            logger.warning(f"{TASK_NAME} - {e}. Skip update feedLevel and waterLevel to database. No internet.")
