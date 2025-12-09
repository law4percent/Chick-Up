from firebase_admin import db
from datetime import datetime
import time

from lib.services import utils, handle_hardware, firebase_rtdb
from lib import logger_config
import logging

logger = logger_config.setup_logger(name=__name__, level=logging.DEBUG)


def _write_credentials_to_file(CREDENTIALS: dict, FULL_PATH: str) -> None:
    """Writes credentials to a file, ensuring the directory exists."""
    now = datetime.now()
    created_at = now.strftime('%m/%d/%Y at %H:%M:%S')
    data = (
        f"username  : {CREDENTIALS["username"]}\n"
        f"userUid   : {CREDENTIALS["userUid"]}\n"
        f"deviceUid : {CREDENTIALS["deviceUid"]}\n"
        f"createdAt : {created_at}"
    )
    
    with open(FULL_PATH, "w") as f:
        f.write(data)
    

def _read_txt_and_return_dict(user_credentials_path: str) -> dict:
    user_credentials = {}
    with open(user_credentials_path, "r") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue  # skip empty lines

            # Split only on the first colon to handle potential colons in the value
            key, value = line.split(":", 1)
            user_credentials[key.strip()] = value.strip()
    
    return {
        "status"            : "success",
        "user_credentials"  : user_credentials
    }
        
        

# ====================== WIP: NOT YET FINISHED ======================
def _ask_user_for_username_to_get_userUid(SAVE_LOGS) -> dict:
    init_result = firebase_rtdb.initialize_firebase(save_logs=SAVE_LOGS)
    if init_result["status"] == "error":
        return init_result
    
    while True:
        time.sleep(0.1)
        
        # Ask for username
        key = handle_hardware.read_keypad_data()
        if key == None:
            continue
        
        if key == '#': # meaning erase the last single character input
            pass 
            
        """
        Keypad Rule
        1: abc1, 2: def2, 3: ghi3
        4: jkl4, 5: lmn5, 6: opq6
        7: rst7, 8: uvw8, 9: xyz9
        *: DONE, 0: *#0,  #: ERASE   
        """
        
        # Fetch usernames/ from RTDB Firebase, and pick the same input username, then get userUid 
        
        userUid     = ""
        username    = ""
        return {
            "userUid"   : userUid,
            "username"  : username
        }
    
    
def _validate_essenstial_keys(user_credentials) -> dict:
    REQUIRED_KEYS = {"userUid", "username", "deviceUid", "createdAt"}
    
    for key in REQUIRED_KEYS:
        if key not in user_credentials:
            return {
                "status"    : "error",
                "message"   : f"Missing key: {key}. Check your user_credentials.txt file. Source: {__name__}"
            }
        
    return {"status": "success"}


# ====================== WIP: NOT YET FINISHED ======================
def pair_it(
        DEVICE_UID: str,    
        PRODUCTION_MODE: bool,
        SAVE_LOGS: bool,
        TEST_CREDENTIALS: dict
    ) -> dict:
    """
        Args:
            device_uid      = kargs["DEVICE_UID"], 
            is_pc_device    = kargs["PRODUCTION_MODE"], 
            save_logs       = kargs["SAVE_LOGS"]
            
        Returns:
            Dict of credentials
    """
    FILE_NAME           = "user_credentials.txt"
    TARGET_PATH         = "credentials"
    USER_CRED_FULL_PATH = utils.join_path_with_os_adaptability(TARGET_PATH, FILE_NAME, __name__)
    
    if not PRODUCTION_MODE:        
        _write_credentials_to_file(
            CREDENTIALS = TEST_CREDENTIALS,
            FULL_PATH   = USER_CRED_FULL_PATH
        )
        user_credentials = _read_txt_and_return_dict(USER_CRED_FULL_PATH)
        print(
            "Info: --------------------------------\n"
            "Info: PC mode user credentials info:\n"
            f"Info: - Username   : {user_credentials["username"]}\n"
            f"Info: - User UID   : {user_credentials["userUid"]}\n"
            f"Info: - Device UID : {user_credentials["deviceUid"]}\n"
            "Info: --------------------------------"
        )
        if SAVE_LOGS:
            logging.info(            
                "Info: --------------------------------\n"
                "Info: PC mode user credentials info:\n"
                f"Info: - Username   : {user_credentials["username"]}\n"
                f"Info: - User UID   : {user_credentials["userUid"]}\n"
                f"Info: - Device UID : {user_credentials["deviceUid"]}\n"
                "Info: --------------------------------"
            )
        return user_credentials
    
    
    # Check the file existence else create one with empty data
    check_point_result = utils.file_existence_checkpoint(USER_CRED_FULL_PATH, __name__)
    if check_point_result["status"] == "error":
       ask_result = _ask_user_for_username_to_get_userUid()
       CREDENTIALS  = {
            "username"  : "law4percent",
            "userUid"   : ask_result["userUid"],
            "deviceUid" : DEVICE_UID
        }
       user_credentials = _write_credentials_to_file(
            CREDENTIALS = TEST_CREDENTIALS,
            FULL_PATH   = USER_CRED_FULL_PATH
        )
        
    validation_result = _validate_essenstial_keys(user_credentials)
    if validation_result["status"] == "error":
        if SAVE_LOGS:
            logger.error(validation_result["message"])
        exit()
    
    user_credentials = _read_txt_and_return_dict(USER_CRED_FULL_PATH)
    print(
        "Info: --------------------------------\n"
        "Info: PC mode user credentials info:\n"
        f"Info: - Username   : {user_credentials["username"]}\n"
        f"Info: - User UID   : {user_credentials["userUid"]}\n"
        f"Info: - Device UID : {user_credentials["deviceUid"]}\n"
        "Info: --------------------------------"
    )
    if SAVE_LOGS:
        logging.info(            
            "Info: --------------------------------\n"
            "Info: PC mode user credentials info:\n"
            f"Info: - Username   : {user_credentials["username"]}\n"
            f"Info: - User UID   : {user_credentials["userUid"]}\n"
            f"Info: - Device UID : {user_credentials["deviceUid"]}\n"
            "Info: --------------------------------"
        )
    return user_credentials