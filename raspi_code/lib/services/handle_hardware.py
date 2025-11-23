from firebase_admin import db
import logging

logging.basicConfig(
    filename='logs/debug.log',
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def read_pins_data(
        dispense_feed_pin: int,
        water_refill_pin: int,
        df_level_sensor_pins: dict,
        wf_level_sensor_pins: dict,
        is_pc_device: bool = False,
        linked_uid: str = None,
        save_logs: bool = False
    ) -> dict:
    
    if is_pc_device:
        if not linked_uid:
            print("Error: linked_uid is required in PC mode.")
            logging.error("linked_uid is required in PC mode.")
            return None

        print("Info: Using PC-mode hardware reading...")
        if save_logs:
            logging.info("PC-mode hardware reading enabled.")

        sensors_data_path = f"sensors/{linked_uid}"
        buttons_data_path = f"buttons/{linked_uid}"

        sensors = db.reference(sensors_data_path).get() or {}
        buttons = db.reference(buttons_data_path).get() or {}

        hw = {
            "df_level_sensor_pins": sensors.get("feedLevel", df_level_sensor_pins),
            "wf_level_sensor_pins": sensors.get("waterLevel", wf_level_sensor_pins),
            "dispense_feed_pin": buttons.get("feedButton", dispense_feed_pin),
            "water_refill_pin": buttons.get("waterButton", water_refill_pin)
        }

        print("Info: --------------------------------")
        print("Info: PC-mode hardware values:")
        for k, v in hw.items():
            print(f"Info: - {k}: {v}")
        print("Info: --------------------------------")

        if save_logs:
            logging.info("--------------------------------")
            logging.info("PC-mode hardware values:")
            logging.info(str(hw))
            logging.info("--------------------------------")

        return hw

    print("Error: Real hardware mode not available. Use PC mode only.")
    logging.error("Attempted to use hardware mode but GPIO code removed.")
    return None
