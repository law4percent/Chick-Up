import time
import cv2
import base64
from lib.services import firebase_rtdb
from firebase_admin import db
from datetime import datetime

import logging
from lib import logger_config

logger = logger_config.setup_logger(name=__name__, level=logging.DEBUG)

def process_B(**kwargs) -> None:
    process_B_args      = kwargs["process_B_args"]
    TASK_NAME           = process_B_args["TASK_NAME"]
    status_checker      = process_B_args["status_checker"]
    queue_frame         = process_B_args["queue_frame"]
    live_status         = process_B_args["live_status"]
    number_of_instances = process_B_args["number_of_instances"]
    USER_CREDENTIAL     = process_B_args["USER_CREDENTIAL"]
    PC_MODE             = process_B_args["PC_MODE"]
    SAVE_LOGS           = process_B_args["SAVE_LOGS"]
    
    print(f"{TASK_NAME} - Running✅")
    logger.info(f"{TASK_NAME} - Running✅")
    
    init_result = firebase_rtdb.initialize_firebase()
    if init_result["status"] == "error":
        status_checker.clear()
        if SAVE_LOGS:
            logger.error(f"{TASK_NAME} - {init_result["message"]}. Source: {__name__}")
        exit()

    user_uid    = USER_CREDENTIAL["userUid"]
    device_uid  = USER_CREDENTIAL["deviceUid"]
    
    livestream_ref  = db.reference(f"liveStream/{user_uid}/{device_uid}")
    detection_ref   = db.reference(f"detection/{user_uid}/{device_uid}")

    try:
        while True:
            if not status_checker.is_set():
                if SAVE_LOGS:
                    logger.error(f"{TASK_NAME} - One of the processes got error.")
                exit()
            
            if not live_status.is_set():
                time.sleep(0.1)
                continue

            if not queue_frame.empty():
                frame = queue_frame.get()
                
                ret, buffer = cv2.imencode(".jpg", frame)
                if not ret:
                    print("Error: Failed to encode frame.")
                else:
                    jpg_text = base64.b64encode(buffer).decode("utf-8")
                    now = datetime.now()
                    lastUpdateAt = now.strftime('%m/%d/%Y %H:%M:%S')

                    try:
                        livestream_ref.update({
                            "base64": jpg_text,
                            "lastUpdateAt": lastUpdateAt,
                        })
                    except Exception as e:
                        if SAVE_LOGS:
                            logger.warning(f"{TASK_NAME} - {e}. Skip update base64 image to database. No internet.")


            if not number_of_instances.empty():
                class_counts = number_of_instances.get()
                number_of_chickens = class_counts.get("chickens", 0)
                number_of_intruders = class_counts.get("intruders", 0)

                try:
                    updatedAt = datetime.now().strftime('%m/%d/%Y %H:%M:%S')
                    detection_ref.update({
                        "numberOfChickens": number_of_chickens,
                        "numberOfIntruders": number_of_intruders,
                        "updatedAt": updatedAt
                    })
                except Exception as e:
                    if SAVE_LOGS:
                        logger.warning(f"{TASK_NAME} - {e}. Skip update numberOfChickens and numberOfIntruders to database. No internet.")


            time.sleep(0.1)
            
    except KeyboardInterrupt:
        logger.warning(f"{TASK_NAME} - Keyboard interrupt detected at {__name__}")
        status_checker.clear()