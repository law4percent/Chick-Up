import time
from firebase_admin import db
from datetime import datetime
from lib.services import firebase_rtdb
from lib.services import handle_hardware
import logging

logging.basicConfig(
    filename='logs/debug.log',     # log file name
    filemode='a',              # 'a' to append, 'w' to overwrite
    level=logging.INFO,        # minimum level to log
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def process_C(
        task_name: str,
        live_status: any,
        annotated_option: any,
        process_c_args: dict
    ):

    firebase_rtdb.initialize_firebase(save_logs=process_c_args.get("save_logs", False))
    print(f"{task_name} Running ✅")

    user_uid = process_c_args["user_credentials"]["userUid"]
    linked_uid = process_c_args["user_credentials"]["linkedUid"]

    is_pc_device = process_c_args.get("is_pc_device", True)

    live_status.set() 

    while True:

        if not live_status.is_set():
            print(f"{task_name} Live status is OFF. Waiting...")
            time.sleep(0.5)
            continue

        if is_pc_device:

            sensors_ref = db.reference(f"sensors/{user_uid}/{linked_uid}")
            snapshot = sensors_ref.get() or {}

            df_button_status = snapshot.get("df_system_button_status", False)
            wr_button_status = snapshot.get("wr_system_button_status", False)
            keypad_data = snapshot.get("keypad_data", "")
            hw_sensors_data = snapshot.get("sensors_data", {"df": {}, "wf": {}})

        else:

            (
                df_button_status,
                wr_button_status,
                keypad_data,
                hw_sensors_data
            ) = handle_hardware.read_pins_data(
                dispense_feed_pin=process_c_args["dispense_feed_pin"],
                water_refill_pin=process_c_args["water_refill_pin"],
                keypad_pins=process_c_args["keypad_pins"],
                df_level_sensor_pins=process_c_args["df_level_sensor_pins"],
                wf_level_sensor_pins=process_c_args["wf_level_sensor_pins"]
            )

        sensors_ref = db.reference(f"sensors/{user_uid}/{linked_uid}")
        sensors_snapshot = sensors_ref.get() or {}

        feedLevel = sensors_snapshot.get("feedLevel", 0)
        waterLevel = sensors_snapshot.get("waterLevel", 0)
        updatedAt = sensors_snapshot.get("updatedAt", 0)
        lastFeedDispense = sensors_snapshot.get("lastFeedDispense", {})
        lastWaterDispense = sensors_snapshot.get("lastWaterDispense", {})

        sensors_data = {
            "feedLevel": feedLevel,
            "waterLevel": waterLevel,
            "updatedAt": updatedAt,
            "lastFeedDispense": lastFeedDispense,
            "lastWaterDispense": lastWaterDispense
        }

        print("Firebase sensors:", sensors_data)

        time.sleep(process_c_args.get("read_delay", 0.2))
