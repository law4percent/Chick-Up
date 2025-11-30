import time
from firebase_admin import db
from lib.services import firebase_rtdb, handle_hardware
from datetime import datetime
import logging

logging.basicConfig(
    filename='logs/debug.log',
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def process_C(task_name: str, 
              live_status: any, 
              annotated_option: any, 
              process_c_args: dict
    ) -> None:

    print(f"{task_name} Running ✅")
    firebase_rtdb.initialize_firebase(save_logs=process_c_args.get("save_logs"))

    user_uid        = process_c_args["user_credentials"]["userUid"]
    device_uid      = process_c_args["user_credentials"]["deviceUid"]
    is_pc_device    = process_c_args["is_pc_device"]
    save_logs       = process_c_args["save_logs"]
    
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
                                                is_pc_device = is_pc_device
                                            )
    feed_physical_button, water_physical_button = handle_hardware.setup_physical_buttons(
                                                        feed_physical_button_data = {
                                                            "gpio"      : 20,
                                                            "pull_up"   : True
                                                        },
                                                        water_physical_button_data = {
                                                            "gpio"      : 28,
                                                            "pull_up"   : True
                                                        },
                                                        is_pc_device = is_pc_device
                                                    )
    
    keypad_pins = handle_hardware.setup_keypad(
                                        keypad_pins_data = {
                                            "row_pins": [20, 21, 22, 26],
                                            "col_pins": [16, 17, 18, 19]
                                        },
                                        is_pc_device = is_pc_device
                                    )
    
    database = firebase_rtdb.setup_RTDB(
                                user_uid=user_uid,
                                device_uid=device_uid,
                            )
    
    lcd = handle_hardware.setup_lcd(
    is_pc_device=is_pc_device,
    lcd_data={
        "i2c_driver": "PCF8574",
        "i2c_address": 0x27  # change to 0x3F if your module has a different address
        }
            )
    
    water_relay = handle_hardware.setup_relay(
        is_pc_device=is_pc_device,
        relay_data={
            "gpio": 12,        
            "active_high": False,
            "initial_value": True
        }
    )

    feed_motor = handle_hardware.setup_motor_driver(
        is_pc_device=is_pc_device,
        motor_data={
            "in1": 13,
            "in2": 14,
            "ena": 15
        }
    )

    while True:
        

        """
            read_pins_data() -> {
                "feed_current_level" : feed_current_level,
                "water_current_level": water_current_level,
                "feed_physical_button_current_state": feed_physical_button_current_status,
                "water_physical_button_current_state": water_physical_button_current_status,
                "pressed_key": pressed_key
            }
        """
        all_pins_data = handle_hardware.read_pins_data(
                            feed_physical_button    = feed_physical_button, 
                            water_physical_button   = water_physical_button,
                            feed_level_sensor       = feed_level_sensor,
                            water_level_sensor      = water_level_sensor,
                            keypad_pins             = keypad_pins,
                            is_pc_device            = is_pc_device,
                            save_logs               = save_logs,
                            user_uid                = user_uid, 
                            device_uid              = device_uid
                        )
        if all_pins_data is None:
            print("❌ ERROR: read_pins_data() returned None")
            time.sleep(0.5)
            continue
        
        """
            read_RTDB() -> {
                "feed_app_button_current_state": is_fresh(df_datetime, min_to_stop=3),
                "water_app_button_current_state": is_fresh(wr_datetime, min_to_stop=3),
                "feed_schedule_current_state": is_schedule_triggered(feed_schedule),
                "live_button_current_state": livestream_on(live_status),
            }
        """
        database_data = firebase_rtdb.read_RTDB(database=database)
        #feed and water button call in read_rtdb
        feed_button_ref  = database["df_app_button_ref"]
        water_button_ref = database["wr_app_button_ref"]
        settings_ref = db.reference(f"settings/{user_uid}")

        settings = settings_ref.get() or {}

        feed_threshold  = settings.get("feed", {}).get("thresholdPercent", 20)
        dispense_volume_percent = settings.get("feed", {}).get("dispenseVolumePercent", 10)
        water_threshold = settings.get("water", {}).get("autoRefillThreshold", 30)
        auto_refill_water_enabled = settings.get("water", {}).get("autoRefillEnabled", False)

        feed_level      = all_pins_data["feed_current_level"]
        water_level     = all_pins_data["water_current_level"]

        feed_button     = all_pins_data["feed_physical_button_current_state"]
        water_button    = all_pins_data["water_physical_button_current_state"]

        feed_schedule_trigger = database_data["feed_schedule_current_state"]

        print("\n===== STATUS UPDATE =====")
        print(f"Feed Level: {feed_level}")
        print(f"Water Level: {water_level}")
        print(f"Feed Btn: {feed_button}, Water Btn: {water_button}")
        print(f"Schedule Trigger: {feed_schedule_trigger}")
        print("=========================\n")


        if feed_level <= feed_threshold:
            print("FEED LEVEL LOW!")
            handle_hardware.lcd_print(lcd, "FEED LOW", f"Level: {feed_level}%")

        if water_level <= water_threshold:
            print("WATER LEVEL LOW!")
            handle_hardware.lcd_print(lcd, "WATER LOW", f"Level: {water_level}%") 

        if feed_button or feed_schedule_trigger:
            if feed_level > 10:
                print("DISPENSING FEED...")
                if feed_motor:
                    handle_hardware.motor_forward(feed_motor)
                    new_feed_level = max(0, feed_level - dispense_volume_percent)
                    print(f"Feed DISPENSED: -{dispense_volume_percent}%")
                    time.sleep(3)           
                    handle_hardware.motor_stop(feed_motor)
                    timestamp = datetime.now().strftime('%m/%d/%Y %H:%M:%S')
                    feed_button_ref.set(timestamp)
            else:
                print("Cannot dispense feed — FEED LEVEL LOW!")

        if water_button:
            if water_level > 10:
                print("DISPENSING WATER...")
                if water_relay:
                    water_relay.off()
                    time.sleep(2)
                    water_relay.on()
                timestamp = datetime.now().strftime('%m/%d/%Y %H:%M:%S')
                water_button_ref.set(timestamp)
            else:
                print("Cannot dispense water — WATER LEVEL LOW!")
        
        if auto_refill_water_enabled:
            if water_level <= water_threshold:
                print("AUTO REFILL: DISPENSING WATER (AUTO MODE)")
                if water_relay:
                    water_relay.off()
                    time.sleep(2)
                    water_relay.on()

        if feed_level <= 10:
            print("FEED REFILL REQUIRED")

        if water_level <= 10:
            print("WATER REFILL REQUIRED")
 
        sensors_ref = None

        if not is_pc_device:
            sensors_ref = db.reference(f"sensors/{user_uid}/{device_uid}")
            updatedAt = datetime.now().strftime('%m/%d/%Y %H:%M:%S')

        if sensors_ref:
            sensors_ref.update({
            "feedLevel": new_feed_level,
            "waterLevel": water_level,
            "updatedAt": updatedAt
        })



time.sleep(1)
