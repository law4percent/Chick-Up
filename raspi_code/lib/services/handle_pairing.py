from firebase_admin import db
import time
import os
import logging
from datetime import datetime



def pair_it(
        device_uid: str, 
        user_credentials_path: str  = "raspi_code/user_credentials.txt",
        test_username: str      = "law4percent",
        test_linked_uid: str    = "ABCDabcd1234567890",
        test_user_uid: str      = "kP718rjyRXWlDUupBhiQTRAaWKt2",
        testing_mode: bool      = False, 
        save_logs: bool         = False,
    ) -> dict:
    required_keys = {"deviceUid", "linkedUid", "username", "userUid"}

    if testing_mode:
        print("Skipping Device Pairing...")
        print("--------------------------------")
        print("Testing Device Info:")
        print(f"- Username   : {test_username}.")
        print(f"- User UID   : {test_user_uid}.")
        print(f"- Link UID   : {test_linked_uid}.")
        print(f"- Device UID : {device_uid}.")
        print("--------------------------------")

        if os.path.exists(user_credentials_path):
            print("Found existing pairing info file. Reading contents...")
            if save_logs:
                logging.info("Found existing pairing info file. Reading contents...")
            
            user_credentials = _read_txt_to_dict(user_credentials_path)
            if user_credentials.keys() >= required_keys:
                print("Pairing info file contains all required keys.")
                if save_logs:
                    logging.info("Pairing info file contains all required keys.")
                return user_credentials
            else:
                print("Error: Pairing info file is missing some required keys.")
                if save_logs:
                    logging.error("Pairing info file is missing some required keys.")
                exit()

        test_cred = {
            "deviceUid": device_uid,
            "linkedUid": test_linked_uid,
            "username": test_username,
            "userUid": test_user_uid
        }
        _write_user_info_in_txt_file(credentials=test_cred, save_logs=save_logs, pairing_info_path=user_credentials_path)
        print(f"Not found pairing info file. Creating one with testing credentials at '{user_credentials_path}'...")
        print(f"Writing testing credentials pairing info to '{user_credentials_path}'...")
        if save_logs:
            logging.info(f"Not found pairing info file. Creating one with testing credentials at '{user_credentials_path}'...")
            logging.info(f"Writing testing credentials pairing info to '{user_credentials_path}'...")
        return _read_txt_to_dict(user_credentials_path)
    
    """
        credentials = {
            "deviceUid": device_uid,
            "linkedUid": "",
            "username": "",
            "userUid": ""
        }
        # 1. Check pairing_info.txt file. If not exist, create with default values.
        _write_user_info_in_txt_file(credentials=credentials, save_logs=save_logs, pairing_info_path=pairing_info_path)
        # 2. Read pairing_info.txt file and validate contents.
        validate_pairing_info(required_keys=["linkedUid", "username", "userUid", "deviceUid", "createdAt"], save_logs=save_logs, pairing_info_path=pairing_info_path)


        print("Starting Pairing Process...")
    """


def _validate_pairing_info(required_keys: list, save_logs: bool, pairing_info_path: str = "raspi_code/user_credentials") -> bool:
    data = _read_txt_to_dict(pairing_info_path)
    # if 

    if data.get("linkedUid") not in [None, "", "None"]:
        linked_uid = data.get("linkedUid")
        if save_logs:
            print(f"[PAIRING] Linked UID already provided: {linked_uid}")



def _write_user_info_in_txt_file(credentials: dict, save_logs: bool, user_credentials_path: str = "raspi_code/user_credentials") -> None:
    now = datetime.now()
    created_at = now.strftime('%m/%d/%Y at %H:%M:%S')
    data = (
        f"userUid: {credentials["userUid"]}\n"
        f"username: {credentials["username"]}\n"
        f"linkedUid: {credentials["linkedUid"]}\n"
        f"deviceUid: {credentials["deviceUid"]}\n"
        f"createdAt: {created_at}"
    )
    with open(user_credentials_path, "w") as f:
        f.write(data)


def _is_available_for_resetting() -> bool:
    pass


def _collect_device_info_from_db() -> dict:
    pass


def _read_txt_to_dict(pairing_info_path: str) -> dict:
    result = {}
    with open(pairing_info_path, "r") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue  # skip empty lines

            key, value = line.split(":", 1)
            result[key.strip()] = value.strip()

    return result