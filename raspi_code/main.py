from lib.processes import process_a, process_b, process_c
from multiprocessing import Process, Queue, Event
from lib.services import firebase_rtdb, handle_pairing, handle_internet, utils
import os
from lib import logger_config
import logging

logger = logger_config.setup_logger(name=__name__, level=logging.DEBUG)

def main(**kargs) -> None:
    # Initial code for checking the internet
    # if not handle_internet.check_external_connection(TARGET_HOST, TARGET_PORT, TIMEOUT_SECONDS):
    #     pass
        
    
    # In AUTHENTICATION FEATURE the will be ask by the system for username
    # Then once obtained the system will get the userUid from RTDB
    # Then save the as a file as user_credentials.txt
    #   Data Format:
    #       userUid   : kP718rjyRXWlDUupBhiQTRAaWKt2
    #       username  : law4percent
    #       deviceUid : -3GSRmf356dy6GFQSTGIF
    #       createdAt : 11/24/2025 at 00:17:48
    user_credentials = handle_pairing.pair_it(
        DEVICE_UID      = kargs["DEVICE_UID"], 
        PRODUCTION_MODE = kargs["PRODUCTION_MODE"], 
        SAVE_LOGS       = kargs["SAVE_LOGS"],
        TEST_CREDENTIALS= kargs["TEST_CREDENTIALS"]
    )

    # -----------------
    # Multi-processing
    #------------------
    
    
    
    # process_b_args["user_credentials"] = user_credentials
    # process_c_args["user_credentials"] = user_credentials

    task_A = Process(
        target = process_a.process_A, 
        kwargs = {"process_A_args": kargs["process_A_args"]}
    )
    task_B = Process(
        target = process_b.process_B, 
        kwargs = {"process_B_args": kargs["process_B_args"]}
    )
    task_C = Process(
        target = process_c.process_C, 
        kwargs = {"process_C_args": kargs["process_C_args"]}
    )

    task_A.start()
    task_B.start()
    task_C.start()

    task_A.join()
    task_B.join()
    task_C.join()


if __name__ == "__main__":
    # ===== MANUALLY TO ADJUST =====
    PRODUCTION_MODE     = False
    PC_MODE             = False
    SAVE_LOGS           = True
    DEVICE_UID          = "DEV_001"
    TEST_CREDENTIALS    = {
        "username"  : "law4percent",
        "userUid"   : "kP718rjyRXWlDUupBhiQTRAaWKt2",
        "deviceUid" : DEVICE_UID
    }
    
    queue_frame         = Queue(maxsize = 1)
    live_status         = Event()
    annotated_option    = Event()
    number_of_instances = Queue(maxsize = 1)
    
    main(
        PRODUCTION_MODE = PRODUCTION_MODE,
        SAVE_LOGS       = SAVE_LOGS,
        DEVICE_UID      = DEVICE_UID,
        TEST_CREDENTIALS= TEST_CREDENTIALS,
        process_A_args  = {
            "TASK_NAME"         : "Process A",
            "USER_CREDENTIAL"   : {},
            "queue_frame"       : queue_frame,
            "live_status"       : live_status,
            "annotated_option"  : annotated_option,
            "YOLO_CONFIDENCE"   : 0.25,
            "FRAME_DIMENSION"   : {"width": 640, "height": 480},
            "IS_WEB_CAM"        : False, # <==== need to find
            "PC_MODE"           : PC_MODE,
            "CAMERA_INDEX"      : 0,
            "VIDEO_FILE"        : "video/chicken.mp4",
            "SAVE_LOGS"         : SAVE_LOGS,
            "SHOW_WINDOW"       : True
        },
        # ("Process B:", queue_frame, live_status, number_of_class_instances, process_b_args))
        process_B_args  = {
            "user_credentials"  : {},
            "is_pc_device"      : PC_MODE,
            "save_logs"         : SAVE_LOGS
        },
        # ("Process C:", live_status, annotated_option, process_c_args))
        process_C_args  = {
            "user_credentials"  : {},
            "is_pc_device"      : PC_MODE,
            "save_logs"         : SAVE_LOGS
        }
    )
    