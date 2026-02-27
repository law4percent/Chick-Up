"""
main.py — System Entry Point

System Flow:
    1. Init LCD + Keypad
    2. AuthService.authenticate()
       - credentials.txt exists → re-validate Firebase → load
       - Missing → LCD menu: (A) Login → pairing flow  (B) Shutdown
    3. Pass credentials to Process A, B, C
    4. Start all processes
"""

import os
from multiprocessing import Process, Queue, Event

from lib.processes import process_a, process_b, process_c
from lib.services.auth import AuthService
from lib.services.hardware.lcd_controller   import LCD_I2C,  LCDSize
from lib.services.hardware.keypad_controller import Keypad4x4
from lib.services.logger import get_logger
from lib.services.utils import normalize_path

from dotenv import load_dotenv
load_dotenv(normalize_path("credentials/.env"))
log = get_logger("main.py")

PRODUCTION_MODE = os.getenv("PRODUCTION_MODE", "").lower() in {"1", "true", "yes"}
DEVICE_UID      = os.getenv("DEVICE_UID")
# ── Config (adjust manually) ──────────────────────────────────────────
TEST_CREDENTIALS = {
    "username"  : "honey",
    "userUid"   : "agjtuFg6YIcJWNfbDsc8QAlMEtj1",
    "deviceUid" : DEVICE_UID
}

def main(**kargs) -> None:
    """
    System entry point.

    Args (via kargs):
        DEVICE_UID       : str
        PRODUCTION_MODE  : bool
        TEST_CREDENTIALS : dict  — only used when PRODUCTION_MODE=False
        process_A_args   : dict
        process_B_args   : dict
        process_C_args   : dict
    """

    # ── Init hardware ─────────────────────────────────────────────────────
    lcd    = LCD_I2C(address=0x27, size=LCDSize.LCD_20x4)
    keypad = Keypad4x4()

    # ── Authenticate ──────────────────────────────────────────────────────
    auth = AuthService(
        device_uid       = kargs["DEVICE_UID"],
        lcd              = lcd,
        keypad           = keypad,
        production_mode  = kargs["PRODUCTION_MODE"],
        test_credentials = kargs.get("TEST_CREDENTIALS")
    )

    user_credentials = auth.authenticate()
    log(
        f"System authenticated\n"
        f"  Username  : {user_credentials['username']}\n"
        f"  User UID  : {user_credentials['userUid']}\n"
        f"  Device UID: {user_credentials['deviceUid']}",
        log_type="info"
    )

    # ── Inject credentials into all process args ──────────────────────────
    kargs["process_A_args"]["USER_CREDENTIAL"] = user_credentials
    kargs["process_B_args"]["USER_CREDENTIAL"] = user_credentials
    kargs["process_C_args"]["USER_CREDENTIAL"] = user_credentials

    # ── Start processes ───────────────────────────────────────────────────
    task_A = Process(target=process_a.process_A, kwargs={"process_A_args": kargs["process_A_args"]})
    task_B = Process(target=process_b.process_B, kwargs={"process_B_args": kargs["process_B_args"]})
    task_C = Process(target=process_c.process_C, kwargs={"process_C_args": kargs["process_C_args"]})

    task_A.start()
    task_B.start()
    task_C.start()

    try:
        task_A.join()
        task_B.join()
        task_C.join()
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt — stopping all processes...")
    finally:
        for task in [task_A, task_B, task_C]:
            if task.is_alive():
                task.terminate()
                task.join()
        lcd.clear()
        keypad.cleanup()


if __name__ == "__main__":
    # ── Shared IPC primitives ─────────────────────────────────────────────
    queue_frame         = Queue(maxsize=1)
    live_status         = Event()
    annotated_option    = Event()
    status_checker      = Event()
    number_of_instances = Queue(maxsize=1)

    status_checker.set()
    live_status.set()
    live_status.clear()

    main(
        PRODUCTION_MODE  = PRODUCTION_MODE,
        DEVICE_UID       = DEVICE_UID,
        TEST_CREDENTIALS = TEST_CREDENTIALS,
        process_A_args   = {
            "TASK_NAME"           : "Process A",
            "queue_frame"         : queue_frame,
            "live_status"         : live_status,
            "annotated_option"    : annotated_option,
            "status_checker"      : status_checker,
            "number_of_instances" : number_of_instances,
            "YOLO_CONFIDENCE"     : 0.25,
            "FRAME_DIMENSION"     : {"width": 1280, "height": 720},
            "IS_WEB_CAM"          : False,
            "CAMERA_INDEX"        : 0,
            "VIDEO_FILE"          : "video/chicken.mp4",
            "SHOW_WINDOW"         : False,
            "USER_CREDENTIAL"     : {},
            "PRODUCTION_MODE"     : PRODUCTION_MODE
        },
        process_B_args   = {
            "TASK_NAME"           : "Process B",
            "status_checker"      : status_checker,
            "queue_frame"         : queue_frame,
            "live_status"         : live_status,
            "number_of_instances" : number_of_instances,
            "USER_CREDENTIAL"     : {}
        },
        process_C_args   = {
            "TASK_NAME"               : "Process C",
            "DISPENSE_COUNTDOWN_TIME" : 1000 * 60,
            "status_checker"          : status_checker,
            "live_status"             : live_status,
            "annotated_option"        : annotated_option,
            "USER_CREDENTIAL"         : {}
        }
    )