"""
main.py — System Entry Point

System Flow:
    1. Init LCD + Keypad (once — hardware never re-initialized)
    2. AuthService.authenticate()
       - credentials/user_credentials.txt exists → re-validate → load
       - Missing → cursor-menu: Login (pair) or Shutdown
    3. Start Process A + Process B
    4. Wait for processes to finish OR for logout_requested Event
       - logout_requested → terminate processes → call auth.logout() → loop to step 2
       - normal exit → clean shutdown

Logout flow (while running):
    - User holds D key on keypad for 3 seconds inside Process B
    - Process B sets logout_requested Event and exits its loop
    - main.py sees the event, terminates both processes
    - Calls auth.logout() — deletes user_credentials.txt, cleans Firebase
    - Loops back to authenticate() — cursor menu reappears on LCD
"""

import os
import signal
import sys
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

PRODUCTION_MODE  = os.getenv("PRODUCTION_MODE", "").lower() in {"1", "true", "yes"}
DEVICE_UID       = os.getenv("DEVICE_UID")
CAMERA_INDEX     = int(os.getenv("CAMERA_INDEX"))
IS_WEB_CAM       = os.getenv("IS_WEB_CAM", "").lower() in {"1", "true", "yes"}
FRAME_WIDTH      = int(os.getenv("FRAME_WIDTH"))
FRAME_HEIGHT     = int(os.getenv("FRAME_HEIGHT"))
TEST_USER_UID    = os.getenv("TEST_USER_UID")
TEST_USERNAME    = os.getenv("TEST_USERNAME")
TEST_CREDENTIALS = {
    "username"  : TEST_USERNAME,
    "userUid"   : TEST_USER_UID,
    "deviceUid" : DEVICE_UID,
}
TURN_SERVER_URL  = os.getenv("TURN_SERVER_URL")
TURN_USERNAME    = os.getenv("TURN_USERNAME")
TURN_PASSWORD    = os.getenv("TURN_PASSWORD")


def _stop_processes(task_A: Process, task_B: Process) -> None:
    """Terminate both processes and wait for them to exit."""
    for task in [task_A, task_B]:
        if task.is_alive():
            task.terminate()
            task.join(timeout=5)
            if task.is_alive():
                task.kill()
                task.join()


def main() -> None:
    """
    System entry point — outer loop handles logout and re-authentication.
    """

    # ── Init hardware once ────────────────────────────────────────────────
    try:
        lcd    = LCD_I2C(address=0x27, size=LCDSize.LCD_16x2)
        keypad = Keypad4x4()
    except Exception as e:
        log(details=f"Hardware init failed: {e}", log_type="error")
        return

    # ── SIGTERM / SIGINT handler ──────────────────────────────────────────
    # FIX: systemd sends SIGTERM when the service is stopped or restarted.
    # Without this handler Python exits immediately without calling cleanup(),
    # leaving all GPIO pins in their last state. On the next start, the pins
    # are in an undefined state and the keypad reads ghost presses.
    #
    # This handler ensures lcd.clear() and keypad.cleanup() always run on
    # both `systemctl stop` (SIGTERM) and Ctrl-C (SIGINT).
    def _handle_exit(sig, frame):
        log(details=f"Signal {sig} received — cleaning up and exiting", log_type="info")
        try:
            lcd.clear()
        except Exception:
            pass
        try:
            keypad.cleanup()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_exit)
    signal.signal(signal.SIGINT,  _handle_exit)

    auth = AuthService(
        device_uid       = DEVICE_UID,
        lcd              = lcd,
        keypad           = keypad,
        production_mode  = PRODUCTION_MODE,
        test_credentials = TEST_CREDENTIALS,
    )

    # ── Auth + run loop ───────────────────────────────────────────────────
    while True:

        # ── Step 1: Authenticate ──────────────────────────────────────────
        try:
            user_credentials = auth.authenticate()
        except FirebaseInitError as e:
            log(details=f"Firebase init error during auth: {e}", log_type="error")
            lcd.show(["Firebase error", "Check network"], duration=3)
            break
        except CredentialsError as e:
            log(details=f"Credentials error during auth: {e}", log_type="error")
            break
        except PairingError as e:
            log(details=f"Pairing error during auth: {e}", log_type="error")
            lcd.show(["Pairing failed", "Try again"], duration=3)
            continue
        except ValidationError as e:
            log(details=f"Validation error during auth: {e}", log_type="warning")
            continue
        except SystemExit:
            log(details="Shutdown requested from LCD menu", log_type="info")
            break
        except Exception as e:
            log(details=f"Unexpected auth error: {e}", log_type="error")
            break

        log(
            details=(
                f"Authenticated — "
                f"username={user_credentials['username']} "
                f"userUid={user_credentials['userUid']} "
                f"deviceUid={user_credentials['deviceUid']}"
            ),
            log_type="info"
        )

        # ── Step 2: Shared IPC primitives (recreated each session) ────────
        live_status       = Event()
        status_checker    = Event()
        logout_requested  = Event()

        status_checker.set()
        live_status.clear()
        logout_requested.clear()

        # ── Step 3: Start processes ───────────────────────────────────────
        task_A = Process(
            target=process_a.process_A,
            kwargs={"process_A_args": {
                "TASK_NAME"       : "Process A",
                "live_status"     : live_status,
                "status_checker"  : status_checker,
                "FRAME_DIMENSION" : {"width": FRAME_WIDTH, "height": FRAME_HEIGHT},
                "IS_WEB_CAM"      : IS_WEB_CAM,
                "CAMERA_INDEX"    : CAMERA_INDEX,
                "USER_CREDENTIAL" : user_credentials,
                "TURN_SERVER_URL" : TURN_SERVER_URL,
                "TURN_USERNAME"   : TURN_USERNAME,
                "TURN_PASSWORD"   : TURN_PASSWORD,
            }}
        )

        task_B = Process(
            target=process_b.process_B,
            kwargs={"process_B_args": {
                "TASK_NAME"        : "Process B",
                "status_checker"   : status_checker,
                "live_status"      : live_status,
                "logout_requested" : logout_requested,
                "USER_CREDENTIAL"  : user_credentials,
                "LCD_I2C_ADDR"     : 0x27,
            }}
        )

        task_A.start()
        task_B.start()

        # ── Step 4: Wait — monitor for logout or normal exit ──────────────
        try:
            while task_A.is_alive() or task_B.is_alive():
                if logout_requested.is_set():
                    log(details="Logout requested — stopping processes", log_type="info")
                    break
                task_A.join(timeout=0.5)
                task_B.join(timeout=0.5)

        except KeyboardInterrupt:
            # KeyboardInterrupt is now handled by the SIGINT signal handler
            # above, but keep this as a fallback for edge cases.
            log(details="KeyboardInterrupt — stopping", log_type="warning")
            _stop_processes(task_A, task_B)
            break

        # ── Step 5: Stop processes cleanly ───────────────────────────────
        _stop_processes(task_A, task_B)

        # ── Step 6: Handle logout vs normal exit ─────────────────────────
        if logout_requested.is_set():
            log(details="Processing logout", log_type="info")
            auth.logout(user_credentials)
            continue
        else:
            log(details="All processes stopped — exiting", log_type="info")
            break

    # ── Final cleanup ─────────────────────────────────────────────────────
    # Reached on clean break from the while loop (not SIGTERM — that is
    # handled by _handle_exit above).
    try:
        lcd.clear()
    except Exception:
        pass
    try:
        keypad.cleanup()
    except Exception:
        pass


if __name__ == "__main__":
    main()