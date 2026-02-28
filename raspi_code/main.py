"""
main.py — System Entry Point

System Flow:
    1. Init LCD + Keypad
    2. AuthService.authenticate()
       - credentials/credentials.txt exists → re-validate Firebase → load
       - Missing → LCD menu: (A) Login → pairing flow  (B) Shutdown
    3. Pass credentials to Process A and Process B
    4. Start all processes
"""

import os
from multiprocessing import Process, Event

from lib.processes import process_a, process_b
from lib.services.auth import (
    AuthService,
    FirebaseInitError,
    CredentialsError,
    PairingError,
    ValidationError,
)
from lib.services.hardware.lcd_controller    import LCD_I2C, LCDSize
from lib.services.hardware.keypad_controller import Keypad4x4
from lib.services.logger import get_logger
from lib.services.utils  import normalize_path

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
    "deviceUid" : DEVICE_UID,
}
TURN_SERVER_URL = os.getenv("TURN_SERVER_URL")
TURN_USERNAME   = os.getenv("TURN_USERNAME")
TURN_PASSWORD   = os.getenv("TURN_PASSWORD")


log(f'CAMERA_INDEX raw: {repr(os.getenv('CAMERA_INDEX'))}', log_type="debug")
log(f'TURN_SERVER_URL:  {repr(os.getenv('TURN_SERVER_URL'))}', log_type="debug")
log(f'TURN_USERNAME:    {repr(os.getenv('TURN_USERNAME'))}', log_type="debug")
log(f'TURN_PASSWORD:    {repr(os.getenv('TURN_PASSWORD'))}', log_type="debug")


def main(**kargs) -> None:
    """
    System entry point.

    Args (via kargs):
        process_A_args : dict
        process_B_args : dict
    """

    # ── Init hardware ─────────────────────────────────────────────────────
    try:
        lcd    = LCD_I2C(address=0x27, size=LCDSize.LCD_16x2)
        keypad = Keypad4x4()
    except Exception as e:
        log(details=f"Hardware init failed: {e}", log_type="error")
        return

    # ── Authenticate ──────────────────────────────────────────────────────
    auth = AuthService(
        device_uid       = DEVICE_UID,
        lcd              = lcd,
        keypad           = keypad,
        production_mode  = PRODUCTION_MODE,
        test_credentials = TEST_CREDENTIALS,
    )

    try:
        user_credentials = auth.authenticate()
    except FirebaseInitError as e:
        log(details=f"Firebase init error during auth: {e}", log_type="error")
        return
    except CredentialsError as e:
        log(details=f"Credentials error during auth: {e}", log_type="error")
        return
    except PairingError as e:
        log(details=f"Pairing error during auth: {e}", log_type="error")
        return
    except ValidationError as e:
        log(details=f"Validation error during auth: {e}", log_type="warning")
        return
    except SystemExit:
        return
    except Exception as e:
        log(details=f"Unexpected error during auth: {e}", log_type="error")
        return

    log(
        details=(
            f"System authenticated — "
            f"username={user_credentials['username']} "
            f"userUid={user_credentials['userUid']} "
            f"deviceUid={user_credentials['deviceUid']}"
        ),
        log_type="info"
    )

    # ── Inject credentials ────────────────────────────────────────────────
    kargs["process_A_args"]["USER_CREDENTIAL"] = user_credentials
    kargs["process_B_args"]["USER_CREDENTIAL"] = user_credentials

    # ── Start processes ───────────────────────────────────────────────────
    task_A = Process(target=process_a.process_A, kwargs={"process_A_args": kargs["process_A_args"]})
    task_B = Process(target=process_b.process_B, kwargs={"process_B_args": kargs["process_B_args"]})

    task_A.start()
    task_B.start()

    try:
        task_A.join()
        task_B.join()
    except KeyboardInterrupt:
        log(details="KeyboardInterrupt — stopping all processes", log_type="warning")
    finally:
        for task in [task_A, task_B]:
            if task.is_alive():
                task.terminate()
                task.join()
        lcd.clear()
        keypad.cleanup()


if __name__ == "__main__":
    # ── Shared IPC primitives ─────────────────────────────────────────────
    live_status    = Event()
    status_checker = Event()

    status_checker.set()
    live_status.clear()

    main(
        process_A_args = {
            "TASK_NAME"       : "Process A",
            "live_status"     : live_status,
            "status_checker"  : status_checker,
            "FRAME_DIMENSION" : {"width": FRAME_WIDTH, "height": FRAME_HEIGHT},
            "IS_WEB_CAM"      : IS_WEB_CAM,
            "CAMERA_INDEX"    : CAMERA_INDEX,
            "USER_CREDENTIAL" : {},
            "TURN_SERVER_URL" : TURN_SERVER_URL,
            "TURN_USERNAME"   : TURN_USERNAME,
            "TURN_PASSWORD"   : TURN_PASSWORD,
        },
        process_B_args = {
            "TASK_NAME"      : "Process B",
            "status_checker" : status_checker,
            "live_status"    : live_status,
            "USER_CREDENTIAL": {},
            "LCD_I2C_ADDR"   : 0x27,
            # DISPENSE_COUNTDOWN_TIME is intentionally omitted here.
            # Process B reads it from Firebase settings/{userUid}/feed/dispenseCountdownMs
            # after auth. Falls back to local cache, then to 60 000 ms default.
        },
    )