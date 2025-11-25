import firebase_admin
from firebase_admin import credentials, db
import logging
import os

logging.basicConfig(
    filename='logs/debug.log',     # log file name
    filemode='a',              # 'a' to append, 'w' to overwrite
    level=logging.INFO,        # minimum level to log
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def initialize_firebase(
        service_acc_key_path: str   = "credentials",
        file_name: str              = "serviceAccountKey.json",
        save_logs: bool             = False
    ) -> None:
    service_acc_key_full_path = os.path.join(service_acc_key_path, file_name)
    if not os.path.exists(service_acc_key_full_path):
        print(f"Error: No such file {file_name} in {service_acc_key_path} folder.")
        if save_logs:
            logging.error(f"Error: No such file or directory of {service_acc_key_full_path}.")
        exit()

    cred = credentials.Certificate(service_acc_key_full_path)
    firebase_admin.initialize_app(
        cred,
        {
            'databaseURL': 'https://chick-up-1c2df-default-rtdb.asia-southeast1.firebasedatabase.app/'
        }
    )
def setup_RTDB(database_tag:any, is_pc_device: bool) -> list:
    if is_pc_device:
        print("Pass, no initializing database...")
        return None

    ref = db.reference("")
    database_tag = ref.get()

    return database_tag
def read_RTDB(database: any) -> dict:
    
    return {
        "df_app_button": database.get("df_app_button"),
        "wr_app_button": database.get("wr_app_button"),
        "feed_schedule": database.get("feed_schedule"),
        "live_button_status": database.get("live_button_status")
    }
