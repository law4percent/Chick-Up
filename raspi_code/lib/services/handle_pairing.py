from firebase_admin import db
import os
import logging
from datetime import datetime

logging.basicConfig(
    filename='logs/debug.log',     # log file name
    filemode='a',              # 'a' to append, 'w' to overwrite
    level=logging.INFO,        # minimum level to log
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def pair_it(
        device_uid: str, 
        is_pc_device: bool           = False, 
        save_logs: bool              = False,
        user_credentials_path: str   = "credentials",
        file_name: str               = "user_credentials.txt",
        required_keys: str           = {"deviceUid", "linkedUid", "username", "userUid", "createdAt"}
    ) -> dict | None:
    
    # Use forward slash for path segments. os.path.join handles conversion for the OS.
    cred_full_path = os.path.join(user_credentials_path, file_name)
    
    if is_pc_device:
        testing_credentials = {
            "test_username"     : "law4percent",
            "test_linked_uid"   : "ABCDabcd1234567890",
            "test_user_uid"     : "kP718rjyRXWlDUupBhiQTRAaWKt2",
            "device_uid"        : device_uid
        }
        print("Skipping device pairing in PC mode.")
        print(f"Checking if {file_name} file is existing at {cred_full_path}...")
        if save_logs:
            logging.info("Skipping device pairing in PC mode.")
            logging.info(f"Checking if {file_name} file is existing at {cred_full_path}...")
        
        if not os.path.exists(cred_full_path):
            print(f"Warning: The '{file_name}' file does not exist.")
            print(f"Writing {file_name} file at '{cred_full_path}'...")
            if save_logs:
                logging.warning(f"The '{file_name}' file does not exist.")
                logging.info(f"Writing {file_name} file at '{cred_full_path}'...")
            
            test_cred = {
                "deviceUid" : device_uid,
                "linkedUid" : testing_credentials["test_linked_uid"],
                "username"  : testing_credentials["test_username"],
                "userUid"   : testing_credentials["test_user_uid"]
            } 
            
            _write_user_info_in_txt_file(
                credentials=test_cred, 
                save_logs=save_logs, 
                user_credentials_full_path=cred_full_path
            )
            
            # Wait for the file to be created before reading
            user_credentials = _read_txt_to_dict(cred_full_path)
            print("--------------------------------")
            print("PC mode user credentials info:")
            print(f"- Username   : {user_credentials["username"]}")
            print(f"- Link UID   : {user_credentials["linkedUid"]}")
            print(f"- User UID   : {user_credentials["userUid"]}")
            print(f"- Device UID : {user_credentials["deviceUid"]}")
            print("--------------------------------")
            print("Writing done.✅")
            if save_logs:
                logging.info("--------------------------------")
                logging.info("PC mode user credentials info:")
                logging.info(f"- Username   : {user_credentials["username"]}")
                logging.info(f"- Link UID   : {user_credentials["linkedUid"]}")
                logging.info(f"- User UID   : {user_credentials["userUid"]}")
                logging.info(f"- Device UID : {user_credentials["deviceUid"]}")
                logging.info("--------------------------------")
                logging.info("Writing done.✅")
            return user_credentials
        else:
            print(f"{file_name} file found.✅")
            if save_logs:
                logging.info(f"{file_name} file found.✅")
                
            user_credentials = _read_txt_to_dict(cred_full_path)
            _validate_credentials_keys(required_keys=required_keys, save_logs=save_logs, user_credentials=user_credentials, file_name=file_name)
            
            print("--------------------------------")
            print("PC mode user credentials Info:")
            print(f"- Username   : {user_credentials["username"]}")
            print(f"- Link UID   : {user_credentials["linkedUid"]}")
            print(f"- User UID   : {user_credentials["userUid"]}")
            print(f"- Device UID : {user_credentials["deviceUid"]}")
            print(f"This file was created on {user_credentials["createdAt"]}.")
            print("--------------------------------")
            if save_logs:
                logging.info("--------------------------------")
                logging.info("PC mode user credentials Info:")
                logging.info(f"- Username   : {user_credentials["username"]}")
                logging.info(f"- Link UID   : {user_credentials["linkedUid"]}")
                logging.info(f"- User UID   : {user_credentials["userUid"]}")
                logging.info(f"- Device UID : {user_credentials["deviceUid"]}")
                logging.info(f"This file was created on {user_credentials["createdAt"]}.")
                logging.info("--------------------------------")
            return user_credentials
        
    # print("Pairing device to app...")
    # ... (Rest of the logic for non-PC devices) ...
    
    # If the file exists, read and validate it
    # user_credentials = _read_txt_to_dict(cred_full_path)
    # if user_credentials:
    #     _validate_credentials_keys(required_keys=required_keys, save_logs=save_logs, user_credentials=user_credentials)
    
    # return user_credentials


def _validate_credentials_keys(required_keys: set, save_logs: bool, user_credentials: dict, file_name: str) -> None:
    print("Validating credential keys...")
    if save_logs:
        logging.info("Validating credential keys...")
    
    if user_credentials.keys() >= required_keys:
        print(f"{file_name} contains all required keys. ✅")
        if save_logs:
            logging.info(f"{file_name} contains all required keys. ✅")
        return
    
    print("Error: Pairing info file is missing some required keys.")
    if save_logs:
        logging.error("Pairing info file is missing some required keys.")
    exit()


def _write_user_info_in_txt_file(credentials: dict, save_logs: bool, user_credentials_full_path: str) -> None:
    """Writes credentials to a file, ensuring the directory exists."""
    now = datetime.now()
    created_at = now.strftime('%m/%d/%Y at %H:%M:%S')
    data = (
        f"userUid   : {credentials["userUid"]}\n"
        f"username  : {credentials["username"]}\n"
        f"linkedUid : {credentials["linkedUid"]}\n"
        f"deviceUid : {credentials["deviceUid"]}\n"
        f"createdAt : {created_at}"
    )
    
    with open(user_credentials_full_path, "w") as f:
        f.write(data)


def _read_txt_to_dict(user_credentials_path: str) -> dict:
    user_credentials = {}
    with open(user_credentials_path, "r") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue  # skip empty lines

            # Split only on the first colon to handle potential colons in the value
            key, value = line.split(":", 1)
            user_credentials[key.strip()] = value.strip()
    return user_credentials


def _is_available_for_resetting() -> bool:
    pass


def _collect_device_info_from_db() -> dict:
    pass