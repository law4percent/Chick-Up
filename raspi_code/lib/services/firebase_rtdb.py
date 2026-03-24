"""
Firebase RTDB Module
Loc: lib/services/firebase_rtdb.py

Class-based wrapper for Firebase Realtime Database operations.

Logging contract:
    This is a service module — it raises exceptions only.
    All logging is handled by the calling process.
"""

import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
import time
from typing import Optional

from . import utils


# ─────────────────────────── EXCEPTIONS ──────────────────────────────────────

class FirebaseError(Exception):
    """Base exception for all Firebase RTDB errors."""
    pass

class FirebaseInitError(FirebaseError):
    """Raised when Firebase app initialization fails."""
    pass

class FirebaseReadError(FirebaseError):
    """Raised when a Firebase RTDB read operation fails."""
    pass

class FirebaseWriteError(FirebaseError):
    """Raised when a Firebase RTDB write operation fails."""
    pass


# ─────────────────────────── FIREBASE RTDB CLASS ─────────────────────────────

class FirebaseRTDB:
    """
    Firebase Realtime Database service wrapper.

    Handles:
    - Firebase app initialization (singleton-safe)
    - RTDB reference setup per user/device
    - Reading and interpreting RTDB data
    - Schedule trigger logic with cooldown tracking
    - Timestamp freshness checks

    This class raises exceptions — all logging is handled by the caller.

    Example usage:
        firebase = FirebaseRTDB()
        firebase.initialize()

        refs = firebase.setup_refs(
            user_uid   = "agjtuFg6YIcJWNfbDsc8QAlMEtj1",
            device_uid = "DEV_001"
        )

        state = firebase.read(refs, min_to_stop=1)
        print(state["current_live_button_state"])
        print(state["current_feed_schedule_state"])
    """

    SERVICE_ACC_KEY_PATH = "credentials"
    SERVICE_ACC_KEY_FILE = "serviceAccountKey.json"
    DATABASE_URL         = "https://chick-up-1c2df-default-rtdb.asia-southeast1.firebasedatabase.app/"

    def __init__(self):
        self._initialized              = False
        self._last_triggered_schedules = {}

    # ─────────────────────────── INIT ────────────────────────────────────────

    def initialize(self) -> None:
        """
        Initialize Firebase app. Safe to call multiple times — only inits once.

        Raises:
            FirebaseInitError: If the service account key is missing or
                               Firebase initialization fails.
        """
        if self._initialized or len(firebase_admin._apps) > 0:
            self._initialized = True
            return

        try:
            full_path = utils.join_and_ensure_path(
                target_directory   = self.SERVICE_ACC_KEY_PATH,
                filename           = self.SERVICE_ACC_KEY_FILE,
                source             = __name__,
                create_if_missing  = False
            )
            utils.ensure_file_exists(full_path, source=__name__)
        except (utils.PathError, utils.FileError) as e:
            raise FirebaseInitError(
                f"Service account key not found: {e}. Source: {__name__}"
            ) from e

        try:
            cred = credentials.Certificate(full_path)
            firebase_admin.initialize_app(cred, {"databaseURL": self.DATABASE_URL})
            self._initialized = True
        except Exception as e:
            raise FirebaseInitError(
                f"Firebase initialization failed: {e}. Source: {__name__}"
            ) from e

    # ─────────────────────────── REFS SETUP ──────────────────────────────────

    def setup_refs(self, user_uid: str, device_uid: str) -> dict:
        """
        Build Firebase RTDB references for a specific user/device.

        Args:
            user_uid:   Firebase user UID
            device_uid: Device UID from .env

        Returns:
            Dict of database references.
        """
        return {
            "df_app_button_ref"        : db.reference(f"buttons/{user_uid}/{device_uid}/feedButton/lastUpdateAt"),
            "wr_app_button_ref"        : db.reference(f"buttons/{user_uid}/{device_uid}/waterButton/lastUpdateAt"),
            "feed_schedule_ref"        : db.reference(f"schedules/{user_uid}"),
            "live_button_status_ref"   : db.reference(f"liveStream/{user_uid}/{device_uid}/liveStreamButton"),
            "user_settings_ref"        : db.reference(f"settings/{user_uid}"),
            "sensors_ref"              : db.reference(f"sensors/{user_uid}/{device_uid}"),
            "dispense_countdown_ref"   : db.reference(f"settings/{user_uid}/feed/dispenseCountdownMs"),
        }

    # ─────────────────────────── READ ────────────────────────────────────────

    def read(self, database_ref: dict, min_to_stop: int = 1) -> dict:
        """
        Read all relevant state from Firebase RTDB in one call.

        Args:
            database_ref: Dict of references from setup_refs()
            min_to_stop:  Minutes window to consider a button press "fresh"

        Returns:
            Dict with current states.

        Raises:
            FirebaseReadError: If any Firebase read operation fails.
        """
        try:
            df_datetime   = database_ref["df_app_button_ref"].get()
            wr_datetime   = database_ref["wr_app_button_ref"].get()
            feed_schedule = database_ref["feed_schedule_ref"].get()
            live_status   = database_ref["live_button_status_ref"].get()
            settings      = database_ref["user_settings_ref"].get() or {}
        except Exception as e:
            raise FirebaseReadError(
                f"Firebase RTDB read failed: {e}. Source: {__name__}"
            ) from e

        feed_settings  = settings.get("feed",  {})
        water_settings = settings.get("water", {})

        raw_countdown = feed_settings.get("dispenseCountdownMs")
        countdown_ms  = int(raw_countdown) if isinstance(raw_countdown, (int, float)) and raw_countdown > 0 else None

        return {
            "current_feed_app_button_state" : self.is_fresh(df_datetime,  min_to_stop=min_to_stop),
            "current_water_app_button_state": self.is_fresh(wr_datetime,  min_to_stop=min_to_stop),
            # Raw timestamps — used by process_b to detect new presses vs re-reads
            # of the same timestamp that is still within the is_fresh() window.
            "raw_feed_timestamp"            : df_datetime,
            "raw_water_timestamp"           : wr_datetime,
            "current_feed_schedule_state"   : self.is_schedule_triggered(feed_schedule),
            "current_live_button_state"     : self.livestream_on(live_status),
            "current_user_settings"         : {
                "feed_threshold_warning"    : feed_settings.get("thresholdPercent"),
                "dispense_volume_percent"   : feed_settings.get("dispenseVolumePercent"),
                "water_threshold_warning"   : water_settings.get("thresholdPercent"),
                "auto_refill_water_enabled" : water_settings.get("autoRefillEnabled"),
                "dispense_countdown_ms"     : countdown_ms,
                "kg_per_dispense"           : feed_settings.get("kgPerDispense"),
            }
        }

    # ─────────────────────────── HELPERS ─────────────────────────────────────

    def is_fresh(self, timestamp_value, min_to_stop: int) -> bool:
        """
        Check if a timestamp is within min_to_stop minutes of now.
        Handles Unix ms timestamps (int/float) and legacy datetime strings
        ("MM/DD/YYYY HH:MM:SS").

        Returns False silently on any unrecognised input or parse failure.
        """
        try:
            now_ms = time.time() * 1000

            if isinstance(timestamp_value, (int, float)):
                timestamp_ms = float(timestamp_value)
            elif isinstance(timestamp_value, str):
                dt           = datetime.strptime(timestamp_value, "%m/%d/%Y %H:%M:%S")
                timestamp_ms = dt.timestamp() * 1000
            else:
                return False

            return (now_ms - timestamp_ms) / (1000 * 60) <= min_to_stop

        except Exception:
            return False

    def is_schedule_triggered(self, schedule_data: dict) -> bool:
        """
        Check if any enabled schedule should trigger right now.
        Includes a 60-second cooldown to prevent duplicate triggers.

        Returns False silently on bad/missing data.
        """
        if not schedule_data:
            return False

        now             = datetime.now()
        today_day_index = now.weekday()   # Monday=0, Sunday=6
        now_time        = now.strftime("%H:%M")
        is_triggered    = False

        for schedule_id, schedule in schedule_data.items():
            days       = schedule.get("days", [])
            sched_time = schedule.get("time")
            enabled    = schedule.get("enabled", False)

            if not enabled:
                continue
            if today_day_index not in days:
                continue

            if sched_time != now_time:
                # Reset tracking once we've passed the scheduled time
                if schedule_id in self._last_triggered_schedules:
                    try:
                        if datetime.strptime(now_time, "%H:%M") < datetime.strptime(sched_time, "%H:%M"):
                            del self._last_triggered_schedules[schedule_id]
                    except Exception:
                        pass
                continue

            # 60-second cooldown guard
            last_trigger = self._last_triggered_schedules.get(schedule_id)
            if last_trigger and (now - last_trigger).total_seconds() < 60:
                continue

            is_triggered = True
            self._last_triggered_schedules[schedule_id] = now

        return is_triggered

    def livestream_on(self, value) -> bool:
        """
        Interpret a Firebase liveStreamButton value as bool.
        Returns False on None or unrecognised values.
        """
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def __repr__(self) -> str:
        return f"FirebaseRTDB(initialized={self._initialized})"


# ─────────────────────────── MODULE-LEVEL SINGLETON ──────────────────────────
# Backwards-compatible wrappers — callers use these directly.

_firebase = FirebaseRTDB()


def initialize_firebase() -> None:
    """
    Initialize Firebase. Raises FirebaseInitError on failure.
    Module-level wrapper around FirebaseRTDB.initialize().
    """
    _firebase.initialize()


def setup_RTDB(user_uid: str, device_uid: str) -> dict:
    """Module-level wrapper — backwards compatible with original."""
    return _firebase.setup_refs(user_uid, device_uid)


def read_RTDB(database_ref: dict, min_to_stop: int = 1) -> dict:
    """
    Read RTDB state. Raises FirebaseReadError on failure.
    Module-level wrapper around FirebaseRTDB.read().
    """
    return _firebase.read(database_ref, min_to_stop)


def is_fresh(timestamp_value, min_to_stop: int) -> bool:
    """Module-level wrapper — backwards compatible with original."""
    return _firebase.is_fresh(timestamp_value, min_to_stop)


def is_schedule_triggered(schedule_data: dict) -> bool:
    """Module-level wrapper — backwards compatible with original."""
    return _firebase.is_schedule_triggered(schedule_data)


def livestream_on(value) -> bool:
    """Module-level wrapper — backwards compatible with original."""
    return _firebase.livestream_on(value)