"""
Firebase RTDB Module
Loc: lib/services/firebase_rtdb.py

Class-based wrapper for Firebase Realtime Database operations.
All return formats preserved from original to avoid breaking other modules.
"""

import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
import time
import logging
from typing import Optional

from . import utils
from lib import logger_config

logger = logger_config.setup_logger(name=__name__, level=logging.DEBUG)


class FirebaseRTDB:
    """
    Firebase Realtime Database service wrapper.

    Handles:
    - Firebase app initialization (singleton-safe)
    - RTDB reference setup per user/device
    - Reading and interpreting RTDB data
    - Schedule trigger logic with cooldown tracking
    - Timestamp freshness checks

    Example usage:
        firebase = FirebaseRTDB()

        # Initialize once at startup
        result = firebase.initialize()
        if result["status"] == "error":
            print(result["message"])
            exit()

        # Setup references for a specific user/device
        refs = firebase.setup_refs(
            user_uid   = "agjtuFg6YIcJWNfbDsc8QAlMEtj1",
            device_uid = "DEV_001"
        )

        # Read all relevant RTDB state in one call
        state = firebase.read(refs, min_to_stop=1)
        print(state["current_live_button_state"])
        print(state["current_feed_schedule_state"])
    """

    SERVICE_ACC_KEY_PATH = "credentials"
    SERVICE_ACC_KEY_FILE = "serviceAccountKey.json"
    DATABASE_URL         = "https://chick-up-1c2df-default-rtdb.asia-southeast1.firebasedatabase.app/"

    def __init__(self):
        self._initialized             = False
        self._last_triggered_schedules = {}

    # ─────────────────────────── INIT ────────────────────────────────────────

    def initialize(self) -> dict:
        """
        Initialize Firebase app (safe to call multiple times — only inits once).

        Returns:
            {"status": "success"} or {"status": "error", "message": str}
        """
        # Already initialized (firebase_admin singleton)
        if self._initialized or len(firebase_admin._apps) > 0:
            self._initialized = True
            return {"status": "success"}

        full_path = utils.join_path_with_os_adaptability(
            self.SERVICE_ACC_KEY_PATH,
            self.SERVICE_ACC_KEY_FILE,
            __name__,
            False
        )

        check = utils.file_existence_check_point(full_path, __name__)
        if check["status"] == "error":
            return check

        try:
            cred = credentials.Certificate(full_path)
            firebase_admin.initialize_app(cred, {"databaseURL": self.DATABASE_URL})
            self._initialized = True
            logger.info("Firebase RTDB initialized successfully.")
            return {"status": "success"}
        except Exception as e:
            return {
                "status" : "error",
                "message": f"{e}. Initializing Firebase RTDB failed. Source: {__name__}"
            }

    # ─────────────────────────── REFS SETUP ──────────────────────────────────

    def setup_refs(self, user_uid: str, device_uid: str) -> dict:
        """
        Build Firebase RTDB references for a specific user/device.

        Args:
            user_uid:   Firebase user UID
            device_uid: Device UID from .env

        Returns:
            Dict of database references (same format as original setup_RTDB)
        """
        return {
            "df_app_button_ref"      : db.reference(f"buttons/{user_uid}/{device_uid}/feedButton/lastUpdateAt"),
            "wr_app_button_ref"      : db.reference(f"buttons/{user_uid}/{device_uid}/waterButton/lastUpdateAt"),
            "feed_schedule_ref"      : db.reference(f"schedules/{user_uid}"),
            "live_button_status_ref" : db.reference(f"liveStream/{user_uid}/{device_uid}/liveStreamButton"),
            "user_settings_ref"      : db.reference(f"settings/{user_uid}"),
            "sensors_ref"            : db.reference(f"sensors/{user_uid}/{device_uid}"),
        }

    # ─────────────────────────── READ ────────────────────────────────────────

    def read(self, database_ref: dict, min_to_stop: int = 1) -> dict:
        """
        Read all relevant state from Firebase RTDB.

        Args:
            database_ref: Dict of references from setup_refs()
            min_to_stop:  Minutes window to consider a button press "fresh"

        Returns:
            Dict with current states (same format as original read_RTDB)
        """
        df_datetime   = database_ref["df_app_button_ref"].get()
        wr_datetime   = database_ref["wr_app_button_ref"].get()
        feed_schedule = database_ref["feed_schedule_ref"].get()
        live_status   = database_ref["live_button_status_ref"].get()
        settings      = database_ref["user_settings_ref"].get() or {}

        feed_settings  = settings.get("feed",  {})
        water_settings = settings.get("water", {})

        return {
            "current_feed_app_button_state" : self.is_fresh(df_datetime,  min_to_stop=min_to_stop),
            "current_water_app_button_state": self.is_fresh(wr_datetime,  min_to_stop=min_to_stop),
            "current_feed_schedule_state"   : self.is_schedule_triggered(feed_schedule),
            "current_live_button_state"     : self.livestream_on(live_status),
            "current_user_settings"         : {
                "feed_threshold_warning"    : feed_settings.get("thresholdPercent"),
                "dispense_volume_percent"   : feed_settings.get("dispenseVolumePercent"),
                "water_threshold_warning"   : water_settings.get("thresholdPercent"),
                "auto_refill_water_enabled" : water_settings.get("autoRefillEnabled"),
            }
        }

    # ─────────────────────────── HELPERS ─────────────────────────────────────

    def is_fresh(self, timestamp_value, min_to_stop: int) -> bool:
        """
        Check if a timestamp is within min_to_stop minutes of now.
        Handles both Unix ms timestamps (Firebase serverTimestamp) and
        legacy datetime strings ("MM/DD/YYYY HH:MM:SS").

        Args:
            timestamp_value: Unix ms int/float or datetime string
            min_to_stop:     Minutes window to consider fresh

        Returns:
            bool
        """
        try:
            now_ms = time.time() * 1000

            if isinstance(timestamp_value, (int, float)):
                timestamp_ms = float(timestamp_value)
            elif isinstance(timestamp_value, str):
                dt = datetime.strptime(timestamp_value, "%m/%d/%Y %H:%M:%S")
                timestamp_ms = dt.timestamp() * 1000
            else:
                logger.error(f"Unknown timestamp format: {type(timestamp_value)}")
                return False

            diff_minutes = (now_ms - timestamp_ms) / (1000 * 60)
            return diff_minutes <= min_to_stop

        except Exception as e:
            logger.error(f"is_fresh failed: {e}, value: {timestamp_value}")
            return False

    def is_schedule_triggered(self, schedule_data: dict) -> bool:
        """
        Check if any schedule should trigger right now.
        Includes 60-second cooldown to prevent duplicate triggers.

        Args:
            schedule_data: Dict of schedule objects from Firebase

        Returns:
            bool: True if at least one schedule triggers
        """
        if not schedule_data:
            return False

        now              = datetime.now()
        today_day_index  = now.weekday()   # Monday=0, Sunday=6
        now_time         = now.strftime("%H:%M")
        is_triggered     = False

        for schedule_id, schedule in schedule_data.items():
            days       = schedule.get("days", [])
            sched_time = schedule.get("time")
            enabled    = schedule.get("enabled", False)

            if not enabled:
                continue
            if today_day_index not in days:
                continue
            if sched_time != now_time:
                # Reset tracking if we've passed the schedule time
                if schedule_id in self._last_triggered_schedules:
                    try:
                        sched_dt = datetime.strptime(sched_time, "%H:%M")
                        now_dt   = datetime.strptime(now_time,   "%H:%M")
                        if now_dt < sched_dt:
                            del self._last_triggered_schedules[schedule_id]
                    except Exception:
                        pass
                continue

            # 60-second cooldown guard
            last_trigger = self._last_triggered_schedules.get(schedule_id)
            if last_trigger:
                if (now - last_trigger).total_seconds() < 60:
                    continue

            logger.info(f"Schedule {schedule_id} triggered at {now_time}")
            is_triggered = True
            self._last_triggered_schedules[schedule_id] = now

        return is_triggered

    def livestream_on(self, value) -> bool:
        """
        Interpret Firebase liveStreamButton value as bool.

        Args:
            value: Any Firebase value

        Returns:
            bool
        """
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ["1", "true", "yes", "on"]

    def __repr__(self) -> str:
        return f"FirebaseRTDB(initialized={self._initialized})"


# ─────────────────────────── MODULE-LEVEL SINGLETON ──────────────────────────
# Preserved from original for backwards compatibility with existing callers.

_firebase = FirebaseRTDB()


def initialize_firebase() -> dict:
    """Module-level wrapper — backwards compatible with original."""
    return _firebase.initialize()


def setup_RTDB(user_uid: str, device_uid: str) -> dict:
    """Module-level wrapper — backwards compatible with original."""
    return _firebase.setup_refs(user_uid, device_uid)


def read_RTDB(database_ref: dict, min_to_stop: int = 1) -> dict:
    """Module-level wrapper — backwards compatible with original."""
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