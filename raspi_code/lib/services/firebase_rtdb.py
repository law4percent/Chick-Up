import firebase_admin
from firebase_admin import credentials, db
import logging
import os
from datetime import datetime, timedelta
from . import utils

def initialize_firebase() -> dict:
    SERVICE_ACC_KEY_PATH    = "credentials",
    FILE_NAME               = "serviceAccountKey.json"
    FULL_PATH               = utils.join_path_with_os_adaptability(SERVICE_ACC_KEY_PATH, FILE_NAME, __name__, False)
    
    check_point_result = utils.file_existence_checkpoint(utils)
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
    df_app_button_ref = db.reference(f"buttons/{user_uid}/{device_uid}/feedButton/lastUpdateAt")
    wr_app_button_ref = db.reference(f"buttons/{user_uid}/{device_uid}/waterButton/lastUpdateAt")
    feed_schedule_ref = db.reference(f"schedules/{user_uid}")
    live_button_status_ref = db.reference(f"liveStream/{user_uid}/{device_uid}/liveStreamButton")
    
    return {
        "df_app_button_ref": df_app_button_ref,
        "wr_app_button_ref": wr_app_button_ref,
        "feed_schedule_ref": feed_schedule_ref,
        "live_button_status_ref": live_button_status_ref,
    }


def is_fresh(datetime_string: str, min_to_stop: int) -> bool:
        dt = datetime.strptime(datetime_string, "%m/%d/%Y %H:%M:%S")

        return (datetime.now() - dt) <= timedelta(minutes=min_to_stop)


def is_schedule_triggered(schedule_data: dict) -> bool:
    if not schedule_data:
        return False

    now = datetime.now()
    today_day_index = now.weekday()          # Monday = 0, Sunday = 6
    now_time = now.strftime("%H:%M")

    # Loop over the actual schedule objects
    for schedule in schedule_data.values():
        days = schedule.get("days", [])
        sched_time = schedule.get("time")
        enabled = schedule.get("enabled", False)

        if not enabled:
            continue

        if sched_time != now_time:
            continue

        if today_day_index not in days:
            continue

        return True

    return False


def livestream_on(value) -> bool:
    if value is None:
        return False

    if isinstance(value, bool):
        return value

    v = str(value).strip().lower()
    return v in ["1", "true", "yes", "on"]


def read_RTDB(database: dict) -> dict:

    # Get actual values from RTDB
    df_datetime = database["df_app_button_ref"].get()
    wr_datetime = database["wr_app_button_ref"].get()
    feed_schedule = database["feed_schedule_ref"].get()
    live_status = database["live_button_status_ref"].get()

    return {
        "feed_app_button_current_state": is_fresh(df_datetime, min_to_stop=3),
        "water_app_button_current_state": is_fresh(wr_datetime, min_to_stop=3),
        "feed_schedule_current_state": is_schedule_triggered(feed_schedule),
        "live_button_current_state": livestream_on(live_status),
    }