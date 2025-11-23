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
    
    sensors_ref = db.reference(f"sensors/{user_uid}/{device_uid}")
    
    feed_level_sensor, water_level_sensor = handle_hardware.init_level_sensors(
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
    feed_physical_button, water_physical_button = handle_hardware.init_physical_buttons(
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
    
    while True:
        
        if is_pc_device:
            print(f"{task_name} The device is PC... skip reading raspi pins")
            time.sleep(0.5)
            continue
        
        
        # -------------------------------
        # This handles level sensors
        # -------------------------------
        feed_current_level, water_current_level = handle_hardware.read_level_sensors_data(feed_level_sensor=feed_level_sensor, water_level_sensor=water_level_sensor)
        print(f"{task_name} Current level of feeds  : {feed_current_level}")
        print(f"{task_name} Current level of water  : {water_current_level}")
            
            
               
        # -------------------------------
        # This handles physical buttons
        # -------------------------------
        feed_physical_button_current_status, water_physical_button_current_status = handle_hardware.read_physical_buttons_data(feed_physical_button=feed_physical_button, water_physical_button=water_physical_button)
        print(f"{task_name} Current physical button status of feed  : {feed_physical_button_current_status}")
        print(f"{task_name} Current physical button status of water : {water_physical_button_current_status}")
            
        


        # updatedAt = datetime.now().strftime('%m/%d/%Y %H:%M:%S')
        # sensors_data = {
        #     "feedLevel"     : round(feed_current_level, 2),
        #     "updatedAt"     : updatedAt,
        #     "waterLevel"    : round(water_current_level, 2)
        # }
        # print("Firebase sensors:", sensors_data)
        # sensors_ref.update(sensors_data)

        time.sleep(0.5)
