from firebase_admin import db
import os
import logging
from datetime import datetime

def pair_it(
        device_uid: str, 
        is_pc_device: bool           = False, 
        save_logs: bool              = False,
        user_credentials_path: str   = "credentials", # Changed backslash to forward slash for better cross-platform compatibility
        file_name: str               = "user_credentials.txt",
        required_keys: str           = {"deviceUid", "linkedUid", "username", "userUid"}
    ) -> dict:
    
    # Use forward slash for path segments. os.path.join handles conversion for the OS.
    cred_full_path = os.path.join(user_credentials_path, file_name) 
    
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
        print(f"- Username   : {testing_credentials["test_username"]}")
        print(f"- Link UID   : {testing_credentials["test_linked_uid"]}")
        print(f"- User UID   : {testing_credentials["test_user_uid"]}")
        print(f"- Device UID : {testing_credentials["device_uid"]}")
        print("--------------------------------")

        if not os.path.exists(cred_full_path):
            print(f"The path '{cred_full_path}' does not exist.")
            if save_logs:
                logging.error(f"The path '{cred_full_path}' does not exist.")
            
            test_cred = {
                "deviceUid" : device_uid,
                "linkedUid" : testing_credentials["test_linked_uid"],
                "username"  : testing_credentials["test_username"],
                "userUid"   : testing_credentials["test_user_uid"]
            }
            
            print(f"Not found pairing info file. Creating one with testing credentials at '{cred_full_path}'...")
            print(f"Writing testing credentials pairing info to '{cred_full_path}'...")
            if save_logs:
                logging.info(f"Not found pairing info file. Creating one with testing credentials at '{cred_full_path}'...")
                logging.info(f"Writing testing credentials pairing info to '{cred_full_path}'...")
            
            _write_user_info_in_txt_file(
                credentials=test_cred, 
                save_logs=save_logs, 
                user_credentials_full_path=cred_full_path
            )
            
            # Wait for the file to be created before reading
            return _read_txt_to_dict(cred_full_path)
        
        
    # ... (Rest of the logic for non-PC devices) ...
    
    # If the file exists, read and validate it
    user_credentials = _read_txt_to_dict(cred_full_path)
    if user_credentials:
        _validate_credentials_keys(required_keys=required_keys, save_logs=save_logs, user_credentials=user_credentials)
    
    return user_credentials


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
    
    # ** THE CRITICAL CORRECTION **
    # 1. Get the directory path from the full path
    dir_path = os.path.dirname(user_credentials_full_path)
    
    # 2. Create all intermediate directories if they don't exist
    # exist_ok=True prevents an error if the directory already exists.
    os.makedirs(dir_path, exist_ok=True) 
    
    # 3. Open the file for writing
    try:
        with open(user_credentials_full_path, "w") as f:
            f.write(data)
        print(f"Successfully wrote credentials to {user_credentials_full_path}")
    except IOError as e:
        print(f"Error writing file: {e}")
        if save_logs:
            logging.error(f"Failed to write credentials file: {e}")


def _read_txt_to_dict(user_credentials_path: str) -> dict:
    result = {}
    try:
        with open(user_credentials_path, "r") as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue  # skip empty lines

                # Split only on the first colon to handle potential colons in the value
                key, value = line.split(":", 1)
                result[key.strip()] = value.strip()
        return result
    except FileNotFoundError:
        print(f"Error: Credentials file not found at {user_credentials_path}")
        # Consider logging this error if appropriate
        return {} # Return empty dict if file is not found


def _is_available_for_resetting() -> bool:
    pass


def _collect_device_info_from_db() -> dict:
    pass