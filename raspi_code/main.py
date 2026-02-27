"""
main.py — System Entry Point

System Flow:
    1. Init LCD + Keypad
    2. AuthService.authenticate()
       - credentials/credentials.txt exists → re-validate Firebase → load
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
CAMERA_INDEX    = int(os.getenv("CAMERA_INDEX"))
IS_WEB_CAM      = os.getenv("IS_WEB_CAM", "").lower() in {"1", "true", "yes"}
FRAME_WIDTH     = int(os.getenv("FRAME_WIDTH"))
FRAME_HEIGHT    = int(os.getenv("FRAME_HEIGHT"))
TEST_USER_UID   = os.getenv("TEST_USER_UID")
TEST_USERNAME   = os.getenv("TEST_USERNAME")
TEST_CREDENTIALS = {
    "username"  : TEST_USERNAME,
    "userUid"   : TEST_USER_UID,
    "deviceUid" : DEVICE_UID
}

def main(**kargs) -> None:
    """
    System entry point.

    Args (via kargs):
        process_A_args   : dict
        process_B_args   : dict
        process_C_args   : dict
    """

    try:
        # ── Init hardware ─────────────────────────────────────────────────────
        lcd    = LCD_I2C(address=0x27, size=LCDSize.LCD_16x2)
        keypad = Keypad4x4()

        # ── Authenticate ──────────────────────────────────────────────────────
        auth = AuthService(
            device_uid       = DEVICE_UID,
            lcd              = lcd,
            keypad           = keypad,
            production_mode  = PRODUCTION_MODE,
            test_credentials = TEST_CREDENTIALS
        )
    except Exception as e:
        log(f"Error occur during Initializing: {e}", log_type="error")

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
        log("KeyboardInterrupt — stopping all processes...", log_type="info")
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

    status_checker.set()
    live_status.set()
    live_status.clear()

    main(
        process_A_args   = {
            "TASK_NAME"           : "Process A",
            "queue_frame"         : queue_frame,
            "live_status"         : live_status,
            "status_checker"      : status_checker,
            "FRAME_DIMENSION"     : {"width": FRAME_WIDTH, "height": FRAME_HEIGHT},
            "IS_WEB_CAM"          : IS_WEB_CAM,
            "CAMERA_INDEX"        : CAMERA_INDEX,
            "USER_CREDENTIAL"     : {},
            "PRODUCTION_MODE"     : PRODUCTION_MODE
        },
        process_B_args   = {
            "TASK_NAME"           : "Process B",
            "status_checker"      : status_checker,
            "queue_frame"         : queue_frame,
            "live_status"         : live_status,
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