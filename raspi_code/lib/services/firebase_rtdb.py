import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime, timedelta
import pytz  # Add this to requirements.txt if not present
from . import utils

# Define Philippine timezone
PH_TIMEZONE = pytz.timezone('Asia/Manila')

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


def get_current_time_ph() -> datetime:
    """Get current time in Philippine timezone"""
    return datetime.now(PH_TIMEZONE)


# Global tracking for schedule triggers (maintains state between calls)
_last_triggered_schedules = {}


def is_fresh(datetime_string: str, min_to_stop: int) -> bool:
    """
    Check if a timestamp is fresh (within min_to_stop minutes)
    Uses Philippine timezone for consistency
    """
    try:
        # Parse the datetime string (assuming it's in PH time)
        dt = datetime.strptime(datetime_string, "%m/%d/%Y %H:%M:%S")
        # Make it timezone-aware (PH timezone)
        dt_ph = PH_TIMEZONE.localize(dt)
        
        # Get current time in PH timezone
        now_ph = get_current_time_ph()
        
        # Calculate difference
        time_diff = now_ph - dt_ph
        
        # Optional: Uncomment for debugging
        # print(f"[DEBUG] Checking freshness:")
        # print(f"  Button timestamp: {dt_ph}")
        # print(f"  Current time (PH): {now_ph}")
        # print(f"  Time difference: {time_diff}")
        # print(f"  Is fresh (< {min_to_stop} min)? {time_diff <= timedelta(minutes=min_to_stop)}")
        
        return time_diff <= timedelta(minutes=min_to_stop)
    except Exception as e:
        print(f"[ERROR] is_fresh failed: {e}")
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

    # Use Philippine timezone
    now = get_current_time_ph()
    today_day_index = now.weekday()  # Monday = 0, Sunday = 6
    now_time = now.strftime("%H:%M")
    
    # Optional: Uncomment for debugging
    # print(f"[DEBUG] Schedule check - Current PH time: {now}, Day: {today_day_index}, Time: {now_time}")
    
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