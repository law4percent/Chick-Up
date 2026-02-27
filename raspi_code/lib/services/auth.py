"""
Authentication Module
Loc: lib/services/auth.py

Pairing Flow:
    1. Boot → check if credentials.txt exists
       - Exists   → re-validate against Firebase → load credentials
       - Missing  → show LCD menu: (A) Login  (B) Shutdown

    2. Login:
       - Generate unique 6-char alphanumeric code
       - Write to Firebase: /device_code/{code}/{device_credentials}/
       - Show code on LCD
       - Poll Firebase: wait for app to pair (app writes userUid + username under the code)
       - Code expires in 60 seconds → if timeout, return to menu
       - On success → save credentials.txt → return credentials

    3. Every boot (credentials.txt exists):
       - Re-validate userUid + deviceUid exist in Firebase
       - If invalid → delete credentials.txt → restart pairing flow
       - If valid   → return credentials

    4. Shutdown:
       - Calls os.shutdown cleanly

Firebase structure written by this module:
    /device_code/{code}/
        deviceUid   : str
        createdAt   : int  (Unix ms)
        status      : "pending" | "paired" | "expired"

Firebase structure written by the APP (read by this module):
    /device_code/{code}/
        userUid     : str
        username    : str
        status      : "paired"
"""

import os
import time
import random
import string
import logging
from datetime import datetime
from typing import Optional

from firebase_admin import db

from lib.services import utils, firebase_rtdb
from lib.services.hardware.lcd_controller  import LCD_I2C,  LCDSize
from lib.services.hardware.keypad_controller import Keypad4x4
from lib import logger_config

logger = logger_config.setup_logger(name=__name__, level=logging.DEBUG)

# ─────────────────────────── CONSTANTS ───────────────────────────────────────

CREDENTIALS_DIR      = "credentials"
CREDENTIALS_FILENAME = "user_credentials.txt"
CODE_EXPIRY_SECONDS  = 60       # 1 minute
CODE_POLL_INTERVAL   = 2        # seconds between Firebase polls
REQUIRED_KEYS        = {"userUid", "username", "deviceUid", "createdAt"}


# ─────────────────────────── AUTH CLASS ──────────────────────────────────────

class AuthService:
    """
    Handles Raspberry Pi device authentication and pairing.

    Responsibilities:
    - First-time pairing via 6-char device code shown on LCD
    - Re-validation of saved credentials against Firebase on every boot
    - Clean shutdown via keypad menu
    - Saving / loading credentials to local txt file

    Example usage:
        from lib.services.auth import AuthService
        from lib.services.hardware.lcd_controller import LCD_I2C, LCDSize
        from lib.services.hardware.keypad_controller import Keypad4x4

        lcd    = LCD_I2C(address=0x27, size=LCDSize.LCD_20x4)
        keypad = Keypad4x4()

        auth = AuthService(
            device_uid = "DEV_001",
            lcd        = lcd,
            keypad     = keypad
        )

        credentials = auth.authenticate()
        print(credentials)
        # {
        #   "username"  : "honey",
        #   "userUid"   : "agjtuFg6YIcJWNfbDsc8QAlMEtj1",
        #   "deviceUid" : "DEV_001",
        #   "createdAt" : "02/26/2026 at 11:00:00"
        # }
    """

    def __init__(
        self,
        device_uid      : str,
        lcd             : LCD_I2C,
        keypad          : Keypad4x4,
        production_mode : bool = True,
        test_credentials: Optional[dict] = None
    ):
        """
        Args:
            device_uid:       Unique device ID from .env
            lcd:              Initialized LCD_I2C instance
            keypad:           Initialized Keypad4x4 instance
            production_mode:  False = skip pairing, use test_credentials directly
            test_credentials: Used only when production_mode=False
        """
        self.device_uid       = device_uid
        self.lcd              = lcd
        self.keypad           = keypad
        self.production_mode  = production_mode
        self.test_credentials = test_credentials

        self._cred_path = utils.join_path_with_os_adaptability(
            CREDENTIALS_DIR, CREDENTIALS_FILENAME, __name__
        )

    # ─────────────────────────── PUBLIC ENTRY POINT ──────────────────────────

    def authenticate(self) -> dict:
        """
        Main authentication entry point. Called once at boot from main.py.

        Returns:
            dict with keys: username, userUid, deviceUid, createdAt

        Raises:
            SystemExit if user chooses Shutdown or fatal error occurs
        """
        # ── DEV / PC mode: bypass pairing entirely ────────────────────────
        if not self.production_mode:
            logger.info("DEV MODE: Skipping pairing, using test credentials.")
            credentials = self.test_credentials.copy()
            credentials["createdAt"] = datetime.now().strftime("%m/%d/%Y at %H:%M:%S")
            self._save_credentials(credentials)
            return credentials

        # ── Initialize Firebase ───────────────────────────────────────────
        init_result = firebase_rtdb.initialize_firebase()
        if init_result["status"] == "error":
            logger.error(f"Firebase init failed: {init_result['message']}")
            self.lcd.show(["Firebase Error", "Check network", "Shutting down..."], duration=3)
            os.system("sudo shutdown -h now")
            raise SystemExit

        # ── credentials.txt exists → re-validate ─────────────────────────
        if os.path.exists(self._cred_path):
            logger.info("credentials.txt found. Re-validating against Firebase...")
            self.lcd.show(["Validating...", "Please wait"], duration=1)

            saved = self._load_credentials()
            if saved and self._validate_against_firebase(saved):
                logger.info(f"Re-validation successful: {saved['username']}")
                self.lcd.show([
                    "Welcome back!",
                    f"{saved['username']}",
                    f"Device: {saved['deviceUid']}"
                ], duration=2)
                return saved
            else:
                logger.warning("Re-validation failed. Deleting credentials and re-pairing.")
                os.remove(self._cred_path)
                self.lcd.show(["Auth invalid", "Re-pairing...", ""], duration=2)

        # ── No valid credentials → show pairing menu ──────────────────────
        return self._show_pairing_menu()

    # ─────────────────────────── PAIRING MENU ────────────────────────────────

    def _show_pairing_menu(self) -> dict:
        """
        Show LCD menu:
            Line 0: CHICK-UP SYSTEM
            Line 1: ================
            Line 2: A. Login
            Line 3: B. Shutdown
        """
        while True:
            self.lcd.show([
                " CHICK-UP SYSTEM",
                "================",
                "A. Login",
                "B. Shutdown"
            ])

            logger.info("Waiting for user to press A (Login) or B (Shutdown)...")
            key = self.keypad.wait_for_key(valid_keys=["A", "B"])

            if key == "A":
                result = self._pairing_flow()
                if result:
                    return result
                # If pairing failed/expired, loop back to menu

            elif key == "B":
                logger.info("User selected Shutdown.")
                self.lcd.show(["Shutting down...", "Goodbye!"], duration=2)
                self.lcd.clear()
                os.system("sudo shutdown -h now")
                raise SystemExit

    # ─────────────────────────── PAIRING FLOW ────────────────────────────────

    def _pairing_flow(self) -> Optional[dict]:
        """
        Full pairing sequence:
        1. Generate 6-char code
        2. Write to Firebase /device_code/{code}/
        3. Show code on LCD
        4. Poll Firebase for app to complete pairing
        5. On success → save credentials.txt → return credentials
        6. On timeout/error → return None (goes back to menu)
        """
        # ── Step 1: Generate unique code ──────────────────────────────────
        code = self._generate_device_code()
        logger.info(f"Generated device code: {code}")

        # ── Step 2: Write to Firebase ─────────────────────────────────────
        now_ms = int(time.time() * 1000)
        try:
            code_ref = db.reference(f"device_code/{code}")
            code_ref.set({
                "deviceUid" : self.device_uid,
                "createdAt" : now_ms,
                "status"    : "pending"
            })
            logger.info(f"Device code written to Firebase: device_code/{code}")
        except Exception as e:
            logger.error(f"Failed to write device code to Firebase: {e}")
            self.lcd.show(["Firebase Error", "Cannot pair", "Try again"], duration=3)
            return None

        # ── Step 3: Show code on LCD ──────────────────────────────────────
        self.lcd.show([
            "Enter code in app:",
            f">>> {code} <<<",
            "Expires in 60s",
            "* to cancel"
        ])

        # ── Step 4: Poll Firebase ─────────────────────────────────────────
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            remaining = int(CODE_EXPIRY_SECONDS - elapsed)

            # Check for cancel key (non-blocking)
            key = self.keypad.read_key(with_debounce=True)
            if key == "*":
                logger.info("User cancelled pairing.")
                self._expire_code(code)
                self.lcd.show(["Pairing cancelled"], duration=2)
                return None

            # Check timeout
            if elapsed >= CODE_EXPIRY_SECONDS:
                logger.warning(f"Device code {code} expired.")
                self._expire_code(code)
                self.lcd.show(["Code expired!", "Press A to retry"], duration=3)
                return None

            # Update countdown on LCD
            self.lcd.write_at(0, 2, f"Expires in {remaining:2d}s  ")

            # Poll Firebase for pairing completion
            try:
                data = code_ref.get()
                if data and data.get("status") == "paired":
                    user_uid = data.get("userUid", "").strip()
                    username = data.get("username", "").strip()

                    if not user_uid or not username:
                        logger.error("Paired but missing userUid or username in Firebase.")
                        self._expire_code(code)
                        self.lcd.show(["Pairing error", "Missing data", "Try again"], duration=3)
                        return None

                    # ── Step 5: Save credentials ──────────────────────────
                    credentials = {
                        "username"  : username,
                        "userUid"   : user_uid,
                        "deviceUid" : self.device_uid,
                    }
                    self._save_credentials(credentials)

                    # Clean up Firebase code
                    self._expire_code(code)

                    logger.info(f"Pairing successful! User: {username} ({user_uid})")
                    self.lcd.show([
                        "Paired!",
                        f"Hi, {username}!",
                        f"Device: {self.device_uid}",
                        "Starting system..."
                    ], duration=3)

                    return self._load_credentials()

            except Exception as e:
                logger.error(f"Firebase poll error: {e}")

            time.sleep(CODE_POLL_INTERVAL)

    # ─────────────────────────── FIREBASE VALIDATION ─────────────────────────

    def _validate_against_firebase(self, credentials: dict) -> bool:
        """
        Re-validate saved credentials against Firebase.
        Checks that userUid exists under /users/{userUid}
        and deviceUid matches.

        Returns:
            True if valid, False otherwise
        """
        try:
            user_uid   = credentials.get("userUid", "")
            device_uid = credentials.get("deviceUid", "")

            if not user_uid or not device_uid:
                return False

            # Check user exists in Firebase
            user_ref = db.reference(f"users/{user_uid}")
            user_data = user_ref.get()

            if not user_data:
                logger.warning(f"userUid {user_uid} not found in Firebase.")
                return False

            # Check deviceUid matches
            if device_uid != self.device_uid:
                logger.warning(f"deviceUid mismatch: saved={device_uid}, env={self.device_uid}")
                return False

            return True

        except Exception as e:
            logger.error(f"Firebase validation error: {e}")
            return False

    # ─────────────────────────── FILE I/O ────────────────────────────────────

    def _save_credentials(self, credentials: dict) -> None:
        """Save credentials dict to local txt file."""
        os.makedirs(CREDENTIALS_DIR, exist_ok=True)
        created_at = datetime.now().strftime("%m/%d/%Y at %H:%M:%S")
        content = (
            f"username: {credentials['username']}\n"
            f"userUid: {credentials['userUid']}\n"
            f"deviceUid: {credentials['deviceUid']}\n"
            f"createdAt: {created_at}"
        )
        with open(self._cred_path, "w") as f:
            f.write(content)
        logger.info(f"Credentials saved to {self._cred_path}")

    def _load_credentials(self) -> Optional[dict]:
        """
        Load credentials from local txt file.

        Returns:
            dict with credentials, or None if file missing/invalid
        """
        try:
            credentials = {}
            with open(self._cred_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    key, value = line.split(":", 1)
                    credentials[key.strip()] = value.strip()

            # Validate all required keys present
            missing = REQUIRED_KEYS - set(credentials.keys())
            if missing:
                logger.error(f"credentials.txt missing keys: {missing}")
                return None

            return credentials

        except FileNotFoundError:
            logger.warning("credentials.txt not found.")
            return None
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            return None

    # ─────────────────────────── HELPERS ─────────────────────────────────────

    def _generate_device_code(self) -> str:
        """Generate a unique 6-character alphanumeric code (uppercase)."""
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choices(chars, k=6))
            # Verify it doesn't already exist in Firebase
            try:
                existing = db.reference(f"device_code/{code}").get()
                if not existing:
                    return code
            except Exception:
                return code  # If Firebase check fails, use code anyway

    def _expire_code(self, code: str) -> None:
        """Mark device code as expired in Firebase."""
        try:
            db.reference(f"device_code/{code}/status").set("expired")
            logger.info(f"Device code {code} marked as expired.")
        except Exception as e:
            logger.warning(f"Could not expire code {code}: {e}")

    def __repr__(self) -> str:
        return f"AuthService(device_uid={self.device_uid}, production={self.production_mode})"


# ─────────────────────────── USAGE EXAMPLES ──────────────────────────────────

if __name__ == "__main__":
    from lib.services.hardware.lcd_controller   import LCD_I2C, LCDSize
    from lib.services.hardware.keypad_controller import Keypad4x4

    # ── Hardware init ─────────────────────────────────────────────────────
    lcd    = LCD_I2C(address=0x27, size=LCDSize.LCD_20x4)
    keypad = Keypad4x4()

    # ── PRODUCTION MODE (real pairing) ────────────────────────────────────
    auth = AuthService(
        device_uid      = os.getenv("DEVICE_UID", "DEV_001"),
        lcd             = lcd,
        keypad          = keypad,
        production_mode = True
    )
    credentials = auth.authenticate()
    print(f"Authenticated as: {credentials['username']}")
    print(f"User UID:         {credentials['userUid']}")
    print(f"Device UID:       {credentials['deviceUid']}")
    print(f"Created At:       {credentials['createdAt']}")

    # ── DEV / PC MODE (skip pairing) ──────────────────────────────────────
    auth_dev = AuthService(
        device_uid       = "DEV_001",
        lcd              = lcd,
        keypad           = keypad,
        production_mode  = False,
        test_credentials = {
            "username"  : "honey",
            "userUid"   : "agjtuFg6YIcJWNfbDsc8QAlMEtj1",
            "deviceUid" : "DEV_001"
        }
    )
    dev_credentials = auth_dev.authenticate()
    print(f"DEV credentials: {dev_credentials}")