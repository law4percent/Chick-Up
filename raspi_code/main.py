from lib.processes import process_a, process_b, process_c
from multiprocessing import Process, Queue, Event
from lib.services import handle_pairing
from lib import logger_config
import logging

logger = logger_config.setup_logger(name=__name__, level=logging.DEBUG)

def main(**kargs) -> None:
    user_credentials = handle_pairing.pair_it(
        DEVICE_UID      = kargs["DEVICE_UID"], 
        PRODUCTION_MODE = kargs["PRODUCTION_MODE"], 
        SAVE_LOGS       = kargs["SAVE_LOGS"],
        TEST_CREDENTIALS= kargs["TEST_CREDENTIALS"]
    )
    kargs["process_B_args"]["USER_CREDENTIAL"] = user_credentials["user_credentials"]
    kargs["process_C_args"]["USER_CREDENTIAL"] = user_credentials["user_credentials"]

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
        "username"  : "honey",
        "userUid"   : "agjtuFg6YIcJWNfbDsc8QAlMEtj1",
        "deviceUid" : DEVICE_UID
    }
    
    queue_frame         = Queue(maxsize = 1)
    live_status         = Event()
    annotated_option    = Event()
    status_checker      = Event()
    number_of_instances = Queue(maxsize = 1)
    status_checker.set()
    live_status.set()
    live_status.clear()
    
    main(
        PRODUCTION_MODE = PRODUCTION_MODE,
        SAVE_LOGS       = SAVE_LOGS,
        DEVICE_UID      = DEVICE_UID,
        TEST_CREDENTIALS= TEST_CREDENTIALS,
        process_A_args  = {
            "TASK_NAME"             : "Process A",
            "queue_frame"           : queue_frame,
            "live_status"           : live_status,
            "annotated_option"      : annotated_option,
            "status_checker"        : status_checker,
            "number_of_instances"   : number_of_instances,
            "YOLO_CONFIDENCE"       : 0.25,
            "FRAME_DIMENSION"       : {"width": 1280, "height": 720}, # RECOMMEND ==> {"width": 640, "height": 480}
            "IS_WEB_CAM"            : False,
            "PC_MODE"               : PC_MODE,
            "CAMERA_INDEX"          : 0,
            "VIDEO_FILE"            : "video/chicken.mp4",
            "SAVE_LOGS"             : SAVE_LOGS,
            "SHOW_WINDOW"           : True,
            "PRODUCTION_MODE"       : PRODUCTION_MODE
        },
        process_B_args  = {
            "TASK_NAME"             : "Process B",
            "status_checker"        : status_checker,
            "queue_frame"           : queue_frame,
            "live_status"           : live_status,
            "number_of_instances"   : number_of_instances,
            "USER_CREDENTIAL"       : {},
            "PC_MODE"               : PC_MODE,
            "SAVE_LOGS"             : SAVE_LOGS
        },
        process_C_args  = {
            "TASK_NAME"                 : "Process C",
            "DISPENSE_COUNTDOWN_TIME"   : 5000,
            "status_checker"            : status_checker,
            "live_status"               : live_status,
            "annotated_option"          : annotated_option,
            "USER_CREDENTIAL"           : {},
            "PC_MODE"                   : PC_MODE,
            "SAVE_LOGS"                 : SAVE_LOGS
        }
    )
    