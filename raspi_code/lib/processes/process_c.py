import time
from firebase_admin import db
from datetime import datetime
from lib.services import firebase_rtdb
from lib.services import handle_hardware
import logging

logging.basicConfig(
    filename='logs/debug.log',
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def process_C(
        task_name: str,
        live_status: any,
        annotated_option: any,
        process_c_args: dict
    ):

    firebase_rtdb.initialize_firebase(save_logs=process_c_args.get("save_logs"))
    print(f"{task_name} Running ✅")

    user_uid = process_c_args["user_credentials"]["userUid"]
    linked_uid = process_c_args["user_credentials"]["linkedUid"]
    is_pc_device = process_c_args.get("is_pc_device", True)

    isFeedRefill = False
    isWaterRefill = False

    live_status.set()

    while True:

        if not live_status.is_set():
            print(f"{task_name} Live status is OFF. Waiting...")
            time.sleep(0.5)
            continue

        if is_pc_device:

            linked_ref = db.reference(f"linked/{user_uid}/{linked_uid}")
            linked_data = linked_ref.get() or {}

            manual_mode = linked_data.get("manual_mode", {})
            df_button_status = manual_mode.get("df_system_button_status", False)
            keypad_data = manual_mode.get("keypad_data", "")

            wr_button_status = linked_data.get("wr_system_button_status", False)

            sensors_data = linked_data.get("sensors_data", {})
            feedLevel = sensors_data.get("feedLevel", 0)
            waterLevel = sensors_data.get("waterLevel", 0)
            updatedAt = sensors_data.get("updatedAt", 0)

            hw_sensors_data = {
                "df": {"low": False},
                "wf": {"low": False}
            }

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

            sensors_ref = db.reference(f"sensors/{user_uid}")
            sensors = sensors_ref.get() or {}
            feedLevel = sensors.get("feedLevel", 0)
            waterLevel = sensors.get("waterLevel", 0)
            updatedAt = sensors.get("updatedAt", 0)

        ultrasonicA_low = hw_sensors_data["df"].get("low", False)
        ultrasonicB_low = hw_sensors_data["wf"].get("low", False)

        if ultrasonicA_low:
            print("Feed level LOW")

            if df_button_status:
                isFeedRefill = True
                print("Feed refill STARTED")

        if isFeedRefill and not ultrasonicA_low:
            isFeedRefill = False
            print("Feed refill STOPPED")

        if ultrasonicB_low:
            print("Water level LOW")

            if wr_button_status:
                isWaterRefill = True
                print("Water refill STARTED")

        if isWaterRefill and not ultrasonicB_low:
            isWaterRefill = False
            print("Water refill STOPPED")

        sensors_ref = db.reference(f"sensors/{user_uid}")
        sensors_ref.update({
            "isFeedRefill": isFeedRefill,
            "isWaterRefill": isWaterRefill,
            "updatedAt": datetime.now().timestamp()
        })

        print("Show data:", {
            "feedLevel": feedLevel,
            "waterLevel": waterLevel,
            "isWaterRefill": isWaterRefill,
            "isFeedRefill": isFeedRefill,
            "df_button": df_button_status,
            "wr_button": wr_button_status,
            "keypad": keypad_data
        })

        time.sleep(0.5)
