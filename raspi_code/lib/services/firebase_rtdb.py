import firebase_admin
from firebase_admin import credentials, db

def initialize_firebase(status: str):
    """
    Initializes Firebase Realtime Database based on the given status..
    """
    status = status.lower()

    if status == "on":
        try:
            service_acc_key_path = "credentials/serviceAccountKey.json"

            cred = credentials.Certificate(service_acc_key_path)

            firebase_admin.initialize_app(
                cred,
                {
                    'databaseURL': 'https://chick-up-1c2df-default-rtdb.asia-southeast1.firebasedatabase.app/'
                }
            )

            print("Firebase initialized successfully.")

        except Exception as e:
            print(f"Error in initializing Firebase: {e} - Check service account file and database URL.")

    elif status == "off":
        print("Firebase initialization skipped. Status is off.")

    else:
        print(f"Invalid status provided: {status}. Please use 'on' or 'off'.")
