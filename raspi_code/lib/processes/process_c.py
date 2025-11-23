from gpiozero import DistanceSensor, Button
import time
from firebase_admin import db
from lib.services import firebase_rtdb
import logging

logging.basicConfig(
    filename='logs/debug.log',
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

sensor_feed = DistanceSensor(echo=5, trigger=3, max_distance=4)
sensor_water = DistanceSensor(echo=7, trigger=6, max_distance=4)

feed_button = Button(20, pull_up=True)
water_button = Button(28, pull_up=True)

def measure_cm(sensor):
    return sensor.distance * 100

def convert_to_percentage(distance_cm, min_dist=10, max_dist=300):
    if distance_cm <= min_dist:
        return 100
    if distance_cm >= max_dist:
        return 0
    
    percent = (max_dist - distance_cm) / (max_dist - min_dist) * 100
    return round(percent, 2)


def process_C(task_name: str, 
              live_status: any, 
              annotated_option: any, 
              process_c_args: dict):

    firebase_rtdb.initialize_firebase(save_logs=process_c_args.get("save_logs"))
    print(f"{task_name} Running ✅")

    user_uid = process_c_args["user_credentials"]["userUid"]

    while True:
        sensors_ref = db.reference(f"sensors/{user_uid}")

        feed_dist = measure_cm(sensor_feed)
        water_dist = measure_cm(sensor_water)

        feedLevel = convert_to_percentage(feed_dist)
        waterLevel = convert_to_percentage(water_dist)

        print(f"Feed Level: {feedLevel}")
        print(f"Water Level: {waterLevel}")
        # mo show ang feed level og water level is low if 0 iya value
        if feedLevel > 0:
            print("Feed level is low")

        if waterLevel > 0:
            print("Water level is low")

        feed_pressed = not feed_button.value
        water_pressed = not water_button.value

        #ari ang mo press ang button nya if greater to 10 or less than 100
        if feed_pressed and 10 <= feedLevel <= 100:
            print("Feed Dispense")

        if water_pressed and 10 <= waterLevel <= 100:
            print("Water Dispense")

        sensors_data = {
            "feedLevel": round(feedLevel, 2),
            "waterLevel": round(waterLevel, 2)
        }
        sensors_ref.update(sensors_data)

        print("Firebase sensors:", sensors_data)

        time.sleep(0.5)
