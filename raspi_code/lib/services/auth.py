"""
Authentication Module
Loc: lib/services/auth.py

Pairing Flow:
    1. Boot → check if credentials/credentials.txt exists
       - Exists   → re-validate against Firebase → load credentials
       - Missing  → show LCD menu: (A) Login  (B) Shutdown

    2. Login:
       - Generate unique 6-char alphanumeric code
       - Write to Firebase: /device_code/{code}/
       - Show code on LCD
       - Poll Firebase: wait for app to pair (app writes userUid + username under the code)
       - Code expires in 60 seconds → if timeout, return to menu
       - On success → save credentials/credentials.txt → return credentials

    3. Every boot (credentials.txt exists):
       - Re-validate userUid + deviceUid against Firebase
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
from datetime import datetime
from typing import Optional

from firebase_admin import db

from lib.services import utils, firebase_rtdb
from lib.services.firebase_rtdb import FirebaseInitError as FirebaseRTDBInitError
from lib.services.hardware.lcd_controller   import LCD_I2C,  LCDSize
from lib.services.hardware.keypad_controller import Keypad4x4


# ─────────────────────────── CONSTANTS ───────────────────────────────────────

CREDENTIALS_DIR      = "credentials"
CREDENTIALS_FILENAME = "user_credentials.txt"
CODE_EXPIRY_SECONDS  = 60
CODE_POLL_INTERVAL   = 2
REQUIRED_KEYS        = {"userUid", "username", "deviceUid", "createdAt"}


# ─────────────────────────── EXCEPTIONS ──────────────────────────────────────

class AuthError(Exception):
    """Base exception for authentication errors."""
    pass

class FirebaseInitError(AuthError):
    """Raised when Firebase fails to initialize."""
    pass

class CredentialsError(AuthError):
    """Raised when credentials are missing, invalid, or cannot be saved."""
    pass

class PairingError(AuthError):
    """Raised when a pairing flow step fails (Firebase write, poll error, etc.)."""
    pass

class ValidationError(AuthError):
    """Raised when saved credentials fail Firebase re-validation."""
    pass


# ─────────────────────────── AUTH CLASS ──────────────────────────────────────

class AuthService:
    """
    Handles Raspberry Pi device authentication and pairing.

    Responsibilities:
    - First-time pairing via 6-char device code shown on LCD
    - Re-validation of saved credentials against Firebase on every boot
    - Clean shutdown via keypad menu
    - Saving / loading credentials to local txt file

    This class raises exceptions — all logging is handled by the caller.

    Example usage:
        auth = AuthService(
            device_uid = "DEV_001",
            lcd        = lcd,
            keypad     = keypad
        )
        credentials = auth.authenticate()
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

        self._cred_path = utils.join_and_ensure_path(
            target_directory  = CREDENTIALS_DIR,
            filename          = CREDENTIALS_FILENAME,
            source            = __name__,
            create_if_missing = True
        )

    # ─────────────────────────── PUBLIC ENTRY POINT ──────────────────────────

    def authenticate(self) -> dict:
        """
        Main authentication entry point. Called once at boot from main.py.

        Returns:
            dict with keys: username, userUid, deviceUid, createdAt

        Raises:
            FirebaseInitError:  Firebase failed to initialize.
            CredentialsError:   Credentials file is corrupt or unreadable.
            PairingError:       Pairing flow encountered a Firebase error.
            SystemExit:         User chose Shutdown from the LCD menu.
        """
        # ── DEV / PC mode: bypass pairing entirely ────────────────────────
        if not self.production_mode:
            credentials = self.test_credentials.copy()
            credentials["createdAt"] = datetime.now().strftime("%m/%d/%Y at %H:%M:%S")
            self._save_credentials(credentials)
            return credentials

        # ── Initialize Firebase ───────────────────────────────────────────
        try:
            firebase_rtdb.initialize_firebase()
        except FirebaseRTDBInitError as e:
            raise FirebaseInitError(str(e)) from e

        # ── credentials.txt exists → re-validate ─────────────────────────
        if os.path.exists(self._cred_path):
            self.lcd.show(["Validating...", "Please wait"], duration=1)

            saved = self._load_credentials()
            if saved and self._validate_against_firebase(saved):
                self.lcd.show([
                    "Welcome back!",
                    f"{saved['username']}",
                    f"Device: {saved['deviceUid']}"
                ], duration=2)
                return saved
            else:
                os.remove(self._cred_path)
                self.lcd.show(["Auth invalid", "Re-pairing..."], duration=2)

        # ── No valid credentials → show pairing menu ──────────────────────
        return self._show_pairing_menu()

    # ─────────────────────────── PAIRING MENU ────────────────────────────────

    def _show_pairing_menu(self) -> dict:
        """
        Cursor-based LCD menu — navigated with the keypad.

        Keys:
            2       → move cursor UP
            8       → move cursor DOWN
            A       → confirm selection
            (any)   → ignored

        Menu items:
            0: Login     → start pairing flow
            1: Shutdown  → clean shutdown

        The LCD is 16×2. Layout with cursor on item 0:
            Line 0: "> Login         "
            Line 1: "  Shutdown      "

        When cursor moves to item 1:
            Line 0: "  Login         "
            Line 1: "> Shutdown      "
        """
        MENU_ITEMS = ["Login", "Shutdown"]
        cursor     = 0                       # index of currently highlighted item
        NUM_ITEMS  = len(MENU_ITEMS)
        VISIBLE    = 2                        # LCD rows

        def _render(cur: int) -> None:
            lines = []
            # Show the window of items that keeps the cursor visible
            # For a 2-row LCD and 2 items this is simply items[0] and items[1]
            start = max(0, min(cur, NUM_ITEMS - VISIBLE))
            for i in range(start, start + VISIBLE):
                prefix = "> " if i == cur else "  "
                label  = MENU_ITEMS[i] if i < NUM_ITEMS else ""
                lines.append(f"{prefix}{label:<14}")  # 2 + 14 = 16 chars
            self.lcd.show(lines)

        # Initial render
        _render(cursor)

        while True:
            key = self.keypad.wait_for_key(valid_keys=["2", "8", "A"])

            if key == "2":
                # Scroll UP — wrap around
                cursor = (cursor - 1) % NUM_ITEMS
                _render(cursor)

            elif key == "8":
                # Scroll DOWN — wrap around
                cursor = (cursor + 1) % NUM_ITEMS
                _render(cursor)

            elif key == "A":
                selected = MENU_ITEMS[cursor]

                if selected == "Login":
                    result = self._pairing_flow()
                    if result:
                        return result
                    # Pairing failed/expired → redraw menu and wait again
                    _render(cursor)

                elif selected == "Shutdown":
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
        5. On success → save credentials → return credentials
        6. On timeout / cancel → return None (caller loops back to menu)

        Raises:
            PairingError: If the Firebase write at step 2 fails.
        """
        # ── Step 1: Generate unique code ──────────────────────────────────
        code = self._generate_device_code()

        # ── Step 2: Write to Firebase ─────────────────────────────────────
        now_ms = int(time.time() * 1000)
        try:
            code_ref = db.reference(f"device_code/{code}")
            code_ref.set({
                "deviceUid" : self.device_uid,
                "createdAt" : now_ms,
                "status"    : "pending"
            })
        except Exception as e:
            raise PairingError(
                f"Failed to write device code to Firebase: {e}. Source: {__name__}"
            ) from e

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
            elapsed   = time.time() - start_time
            remaining = int(CODE_EXPIRY_SECONDS - elapsed)

            # Non-blocking cancel check
            key = self.keypad.read_key(with_debounce=True)
            if key == "*":
                self._expire_code(code)
                self.lcd.show(["Pairing cancelled"], duration=2)
                return None

            # Timeout
            if elapsed >= CODE_EXPIRY_SECONDS:
                self._expire_code(code)
                self.lcd.show(["Code expired!", "Press A to retry"], duration=3)
                return None

            # Countdown display
            self.lcd.write_at(0, 2, f"Expires in {remaining:2d}s  ")

            # Poll for pairing completion
            try:
                data = code_ref.get()
                if data and data.get("status") == "paired":
                    user_uid = data.get("userUid", "").strip()
                    username = data.get("username", "").strip()

                    if not user_uid or not username:
                        self._expire_code(code)
                        raise PairingError(
                            "Pairing status is 'paired' but userUid or username is missing "
                            f"in Firebase. Code: {code}. Source: {__name__}"
                        )

                    # ── Step 5: Save and return credentials ───────────────
                    credentials = {
                        "username"  : username,
                        "userUid"   : user_uid,
                        "deviceUid" : self.device_uid,
                    }
                    self._save_credentials(credentials)
                    self._expire_code(code)

                    self.lcd.show([
                        "Paired!",
                        f"Hi, {username}!",
                        f"Device: {self.device_uid}",
                        "Starting system..."
                    ], duration=3)

                    return self._load_credentials()

            except PairingError:
                raise
            except Exception as e:
                # Firebase poll errors are transient — surface as PairingError
                # so the caller can log and decide whether to retry or abort
                raise PairingError(
                    f"Firebase poll error during pairing: {e}. Source: {__name__}"
                ) from e

            time.sleep(CODE_POLL_INTERVAL)

    # ─────────────────────────── FIREBASE VALIDATION ─────────────────────────

    def _validate_against_firebase(self, credentials: dict) -> bool:
        """
        Re-validate saved credentials against Firebase.
        Checks /users/{userUid} exists and deviceUid matches .env.

        Returns:
            True  → valid
            False → invalid (caller should delete and re-pair)

        Raises:
            ValidationError: If the Firebase call itself fails unexpectedly.
        """
        user_uid   = credentials.get("userUid", "")
        device_uid = credentials.get("deviceUid", "")

        if not user_uid or not device_uid:
            return False

        if device_uid != self.device_uid:
            return False

        try:
            user_data = db.reference(f"users/{user_uid}").get()
            return bool(user_data)
        except Exception as e:
            raise ValidationError(
                f"Firebase validation call failed: {e}. Source: {__name__}"
            ) from e

    # ─────────────────────────── FILE I/O ────────────────────────────────────

    def _save_credentials(self, credentials: dict) -> None:
        """
        Save credentials dict to local txt file.

        Raises:
            CredentialsError: If the file cannot be written.
        """
        try:
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
        except Exception as e:
            raise CredentialsError(
                f"Failed to save credentials to {self._cred_path}: {e}. Source: {__name__}"
            ) from e

    def _load_credentials(self) -> Optional[dict]:
        """
        Load credentials from local txt file.

        Returns:
            dict with credentials, or None if file is missing / keys incomplete.

        Raises:
            CredentialsError: If the file exists but cannot be parsed.
        """
        if not os.path.exists(self._cred_path):
            return None

        try:
            credentials = {}
            with open(self._cred_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    key, value = line.split(":", 1)
                    credentials[key.strip()] = value.strip()
        except Exception as e:
            raise CredentialsError(
                f"Failed to parse credentials file {self._cred_path}: {e}. Source: {__name__}"
            ) from e

        missing = REQUIRED_KEYS - set(credentials.keys())
        if missing:
            return None

        return credentials

    # ─────────────────────────── HELPERS ─────────────────────────────────────

    def logout(self, credentials: dict) -> None:
        """
        Delete local credentials and clean up Firebase.
        Called by main.py after both processes have been stopped.

        Args:
            credentials: The credentials dict that was active — used to
                         remove users/{userUid}/linkedDevice from Firebase.
        """
        # Delete local credentials file
        if os.path.exists(self._cred_path):
            try:
                os.remove(self._cred_path)
            except Exception as e:
                self.lcd.show(["Logout failed", str(e)[:16]], duration=2)
                return

        # Best-effort: remove linkedDevice from Firebase so the app
        # immediately shows the device as unpaired
        try:
            db.reference(f"users/{credentials['userUid']}/linkedDevice").delete()
        except Exception:
            pass  # Non-critical

        self.lcd.show(["Logged out!", "Pairing menu..."], duration=2)

    def _generate_device_code(self) -> str:
        """
        Generate a unique 6-character alphanumeric code (uppercase).
        Checks Firebase to avoid collisions; falls back gracefully if check fails.
        """
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choices(chars, k=6))
            try:
                existing = db.reference(f"device_code/{code}").get()
                if not existing:
                    return code
            except Exception:
                return code  # Firebase check failed — use code anyway

    def _expire_code(self, code: str) -> None:
        """
        Mark device code as expired in Firebase.
        Silent on failure — best-effort cleanup only.
        """
        try:
            db.reference(f"device_code/{code}/status").set("expired")
        except Exception:
            pass  # Non-critical; caller does not need to know

    def __repr__(self) -> str:
        return f"AuthService(device_uid={self.device_uid}, production={self.production_mode})"