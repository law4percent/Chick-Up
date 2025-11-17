import firebase_admin
from firebase_admin import credentials, db
import logging

# Configure logging
logging.basicConfig(
    filename='logs/keypad.log',     # log file name
    filemode='a',              # 'a' to append, 'w' to overwrite
    level=logging.INFO,        # minimum level to log
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def initialize_firebase(
        service_acc_key_path: str   = "credentials/serviceAccountKey.json",
        testing_mode: bool          = False, 
        show_logs: bool             = False
    ) -> None:
    """
        Initializes Firebase Realtime Database
    """

    try:
        service_acc_key_path = "credentials/serviceAccountKey.json"
        cred = credentials.Certificate(service_acc_key_path)
        firebase_admin.initialize_app(
            cred,
            {
                'databaseURL': 'https://chick-up-1c2df-default-rtdb.asia-southeast1.firebasedatabase.app/'
            }
        )

        if show_logs:
            logging.info("Firebase initialized successfully.")
        print("Firebase initialized successfully.")

    except Exception as e:
        print(f"Error in initializing Firebase: {e} - Check service account file and database URL.")
        if show_logs:
            logging.error(f"Error in initializing Firebase: {e} - Check service account file and database URL.")