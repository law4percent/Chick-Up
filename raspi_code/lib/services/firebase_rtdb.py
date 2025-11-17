import os
import firebase_admin
from firebase_admin import credentials, db

_initialized = False


def initialize_firebase(service_account_path=None, database_url=None):
    global _initialized
    if _initialized:
        return

    if not service_account_path:
        service_account_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    if not service_account_path or not os.path.exists(service_account_path):
        raise FileNotFoundError("Service Account JSON invalid or missing.")

    if not database_url:
        database_url = os.environ.get("https://chick-up-1c2df-default-rtdb.asia-southeast1.firebasedatabase.app/")

    if not database_url:
        raise ValueError("Missing FIREBASE_DB_URL environment variable.")

    cred = credentials.Certificate("chick-up-1c2df-firebase-adminsdk-fbsvc-8def884eb7.json")
    firebase_admin.initialize_app(cred, {"databaseURL": database_url})

    _initialized = True
    print("[FIREBASE] ✔ Initialized successfully.")