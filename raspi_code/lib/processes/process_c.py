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
    
    sensors_ref = db.reference(f"sensors/{user_uid}/{device_uid}")
    
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
                                        is_pc_device=is_pc_device
                                    )


    while True:
        
        if is_pc_device:
            print(f"{task_name} The device is PC... skip reading raspi pins and database data")
            time.sleep(0.5)
            continue
        
        all_pins_data = handle_hardware.read_pins_data(
                            feed_physical_button    = feed_physical_button, 
                            water_physical_button   = water_physical_button,
                            feed_level_sensor       = feed_level_sensor,
                            water_level_sensor      = water_level_sensor,
                            keypad_pins             = keypad_pins,
                            is_pc_device            = is_pc_device,
                            save_logs               = save_logs
                        )
        
        database_data = firebase_rtdb.read_RTDB(database=database,is_pc_device=is_pc_device)
        {
            "df_app_button" : bool,
            "wr_app_button" : bool,
            "feed_schedule" : bool,
            "live_button_status": bool
        }

        # df_app_button      = database.get("df_app_button")
        # wr_app_button      = database.get("wr_app_button")
        # feed_schedule      = database.get("feed_schedule")
        # live_button_status = database.get("live_button_status")

        # print("\n=== Firebase RTDB Read ===")
        # print("df_app_button     :", df_app_button)
        # print("wr_app_button     :", wr_app_button)
        # print("feed_schedule     :", feed_schedule)
        # print("live_button_status:", live_button_status)
        # print("==========================\n")
        


        # updatedAt = datetime.now().strftime('%m/%d/%Y %H:%M:%S')
        # sensors_data = {
        #     "feedLevel"     : round(feed_current_level, 2),
        #     "updatedAt"     : updatedAt,
        #     "waterLevel"    : round(water_current_level, 2)
        # }
        # print("Firebase sensors:", sensors_data)
        # sensors_ref.update(sensors_data)

        time.sleep(0.5)
