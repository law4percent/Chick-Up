from firebase_admin import db
import os
import logging
from datetime import datetime



def pair_it(
        device_uid: str, 
        is_pc_device: bool      = False, 
        save_logs: bool         = False,
        user_credentials_path   = "raspi_code/credentials/user_credentials.txt",
        required_keys           = {"deviceUid", "linkedUid", "username", "userUid"}
    ) -> dict:

    if is_pc_device:
        testing_credentials = {
            "test_username"     : "law4percent",
            "test_linked_uid"   : "ABCDabcd1234567890",
            "test_user_uid"     : "kP718rjyRXWlDUupBhiQTRAaWKt2",
            "device_uid"        : device_uid
        }
        print("Skipping Device Pairing...")
        print("--------------------------------")
        print("PC mode user credentials Info:")
        print(f"- Username   : {testing_credentials["test_username"]}.")
        print(f"- Link UID   : {testing_credentials["test_linked_uid"]}.")
        print(f"- User UID   : {testing_credentials["test_user_uid"]}.")
        print(f"- Device UID : {testing_credentials["device_uid"]}.")
        print("--------------------------------")

        if os.path.exists(user_credentials_path):
            print("Found existing pairing info file. Reading contents...")
            if save_logs:
                logging.info("Found existing pairing info file. Reading contents...")
            
            user_credentials = _read_txt_to_dict(user_credentials_path)
            _validate_credentials_keys(required_keys=required_keys, user_credentials=user_credentials)
            
        test_cred = {
            "deviceUid" : device_uid,
            "linkedUid" : testing_credentials["test_linked_uid"],
            "username"  : testing_credentials["test_username"],
            "userUid"   : testing_credentials["test_user_uid"]
        }
        _write_user_info_in_txt_file(credentials=test_cred, save_logs=save_logs, user_credentials_path=user_credentials_path)
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


def _validate_credentials_keys(required_keys: set, save_logs: bool, user_credentials: dict) -> None:
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


def _write_user_info_in_txt_file(credentials: dict, save_logs: bool, user_credentials_path: str = "raspi_code/credentials/user_credentials.txt") -> None:
    now = datetime.now()
    created_at = now.strftime('%m/%d/%Y at %H:%M:%S')
    data = (
        f"userUid   : {credentials["userUid"]}\n"
        f"username  : {credentials["username"]}\n"
        f"linkedUid : {credentials["linkedUid"]}\n"
        f"deviceUid : {credentials["deviceUid"]}\n"
        f"createdAt : {created_at}"
    )
    with open(user_credentials_path, "w") as f:
        f.write(data)


def _is_available_for_resetting() -> bool:
    pass


def _collect_device_info_from_db() -> dict:
    pass


def _read_txt_to_dict(user_credentials_path: str) -> dict:
    result = {}
    with open(user_credentials_path, "r") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue  # skip empty lines

            key, value = line.split(":", 1)
            result[key.strip()] = value.strip()

    return result