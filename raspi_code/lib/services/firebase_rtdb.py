import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime, timedelta
import time
from . import utils

def initialize_firebase() -> dict:
    SERVICE_ACC_KEY_PATH    = "credentials",
    FILE_NAME               = "serviceAccountKey.json"
    FULL_PATH               = utils.join_path_with_os_adaptability(SERVICE_ACC_KEY_PATH, FILE_NAME, __name__, False)
    
    check_point_result = utils.file_existence_check_point(FULL_PATH, __name__)
    if check_point_result["status"] == "error":
        return check_point_result

    try:
        cred = credentials.Certificate(FULL_PATH)
        firebase_admin.initialize_app(
            cred,
            {
                'databaseURL': 'https://chick-up-1c2df-default-rtdb.asia-southeast1.firebasedatabase.app/'
            }
        )
        return {"status": "success"}
    except Exception as e:
        return {
            "status": "error",
            "message": f"{e}. Initiallizing Firebase RTDB failed. Source: {__name__}"
        }


def setup_RTDB(user_uid: str, device_uid: str) -> dict:
    df_app_button_ref       = db.reference(f"buttons/{user_uid}/{device_uid}/feedButton/lastUpdateAt")
    wr_app_button_ref       = db.reference(f"buttons/{user_uid}/{device_uid}/waterButton/lastUpdateAt")
    feed_schedule_ref       = db.reference(f"schedules/{user_uid}")
    live_button_status_ref  = db.reference(f"liveStream/{user_uid}/{device_uid}/liveStreamButton")
    user_settings_ref       = db.reference(f"settings/{user_uid}")
    sensors_ref             = db.reference(f"sensors/{user_uid}/{device_uid}")
    
    return {
        "df_app_button_ref"     : df_app_button_ref,
        "wr_app_button_ref"     : wr_app_button_ref,
        "feed_schedule_ref"     : feed_schedule_ref,
        "live_button_status_ref": live_button_status_ref,
        "user_settings_ref"     : user_settings_ref,
        "sensors_ref"           : sensors_ref
    }


# Global tracking for schedule triggers (maintains state between calls)
_last_triggered_schedules = {}


def is_fresh(timestamp_value, min_to_stop: int) -> bool:
    """
    Check if a timestamp is fresh (within min_to_stop minutes)
    Handles both Unix timestamps (from Firebase serverTimestamp) and datetime strings
    
    Args:
        timestamp_value: Either a Unix timestamp (int/float in milliseconds) or datetime string
        min_to_stop: Number of minutes to consider "fresh"
    
    Returns:
        bool: True if timestamp is within the time window
    """
    try:
        # Get current time in milliseconds
        now_ms = time.time() * 1000
        
        # Handle different timestamp formats
        if isinstance(timestamp_value, (int, float)):
            # Firebase serverTimestamp - Unix timestamp in milliseconds
            timestamp_ms = float(timestamp_value)
        elif isinstance(timestamp_value, str):
            # Legacy string format "MM/DD/YYYY HH:MM:SS"
            dt = datetime.strptime(timestamp_value, "%m/%d/%Y %H:%M:%S")
            timestamp_ms = dt.timestamp() * 1000
        else:
            print(f"[ERROR] Unknown timestamp format: {type(timestamp_value)}")
            return False
        
        # Calculate time difference in milliseconds
        time_diff_ms = now_ms - timestamp_ms
        time_diff_minutes = time_diff_ms / (1000 * 60)
        
        is_fresh_result = time_diff_minutes <= min_to_stop
        
        # Optional: Uncomment for debugging
        # print(f"[DEBUG] Checking freshness:")
        # print(f"  Timestamp (ms): {timestamp_ms}")
        # print(f"  Current time (ms): {now_ms}")
        # print(f"  Time difference (minutes): {time_diff_minutes:.2f}")
        # print(f"  Is fresh (< {min_to_stop} min)? {is_fresh_result}")
        
        return is_fresh_result
        
    except Exception as e:
        print(f"[ERROR] is_fresh failed: {e}, value: {timestamp_value}")
        return False


def is_schedule_triggered(schedule_data: dict) -> bool:
    """
    Check if any schedule should trigger right now.
    Returns True if at least one schedule is triggered.
    
    MAINTAINS ORIGINAL RETURN FORMAT: Returns bool only
    """
    global _last_triggered_schedules
    
    if not schedule_data:
        return False

    # Use system time
    now = datetime.now()
    today_day_index = now.weekday()  # Monday = 0, Sunday = 6
    now_time = now.strftime("%H:%M")
    
    # Optional: Uncomment for debugging
    # print(f"[DEBUG] Schedule check - Current time: {now}, Day: {today_day_index}, Time: {now_time}")
    
    is_triggered = False

    # Loop over the actual schedule objects
    for schedule_id, schedule in schedule_data.items():
        days = schedule.get("days", [])
        sched_time = schedule.get("time")
        enabled = schedule.get("enabled", False)

        # Optional: Uncomment for debugging
        # print(f"[DEBUG] Checking schedule {schedule_id}: enabled={enabled}, time={sched_time}, days={days}")

        if not enabled:
            continue

        # Check if today is in the schedule
        if today_day_index not in days:
            continue

        # Check if current time matches schedule time
        if sched_time != now_time:
            # Reset tracking if we've passed the schedule time
            if schedule_id in _last_triggered_schedules:
                try:
                    sched_dt = datetime.strptime(sched_time, "%H:%M")
                    now_dt = datetime.strptime(now_time, "%H:%M")
                    if now_dt < sched_dt:
                        # New day, reset tracking
                        del _last_triggered_schedules[schedule_id]
                except Exception:
                    pass
            continue

        # Check if we've already triggered this schedule today
        last_trigger = _last_triggered_schedules.get(schedule_id)
        if last_trigger:
            time_since_trigger = (now - last_trigger).total_seconds()
            # Only trigger once per minute (60 seconds cooldown)
            if time_since_trigger < 60:
                continue

        # This schedule should trigger!
        print(f"[INFO] Schedule {schedule_id} triggered at {now_time}")
        is_triggered = True
        _last_triggered_schedules[schedule_id] = now

    return is_triggered


def livestream_on(value) -> bool:
    if value is None:
        return False

    if isinstance(value, bool):
        return value

    v = str(value).strip().lower()
    return v in ["1", "true", "yes", "on"]


def read_RTDB(database_ref: dict) -> dict:
    """
    Read data from Firebase RTDB.
    
    MAINTAINS ORIGINAL RETURN FORMAT - no changes to structure
    Now handles both Firebase serverTimestamp and legacy datetime strings
    """
    # Get actual values from RTDB
    df_datetime     = database_ref["df_app_button_ref"].get()
    wr_datetime     = database_ref["wr_app_button_ref"].get()
    feed_schedule   = database_ref["feed_schedule_ref"].get()
    live_status     = database_ref["live_button_status_ref"].get()
    settings_ref                = database_ref["user_settings_ref"].get()
    feed_threshold_warning      = settings_ref.get("feed", {}).get("thresholdPercent")
    dispense_volume_percent     = settings_ref.get("feed", {}).get("dispenseVolumePercent") # Work in progress
    water_threshold_warning     = settings_ref.get("water", {}).get("thresholdPercent")
    auto_refill_water_enabled   = settings_ref.get("water", {}).get("autoRefillEnabled")

    return {
        "current_feed_app_button_state" : is_fresh(df_datetime, min_to_stop=3),
        "current_water_app_button_state": is_fresh(wr_datetime, min_to_stop=3),
        "current_feed_schedule_state"   : is_schedule_triggered(feed_schedule),
        "current_live_button_state"     : livestream_on(live_status),
        "current_user_settings"         : {
            "feed_threshold_warning"    : feed_threshold_warning,
            "dispense_volume_percent"   : dispense_volume_percent,
            "water_threshold_warning"   : water_threshold_warning,
            "auto_refill_water_enabled" : auto_refill_water_enabled
        }
    }