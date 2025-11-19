import time
import cv2
import base64
import numpy as np
from multiprocessing import Queue
from lib.services import firebase_rtdb
from firebase_admin import db
from datetime import datetime

def process_B(
        task_name: str,
        queue_frame: Queue,
        live_status: any,
        number_of_class_instances: Queue,
        process_b_args: dict
    ) -> None:

    firebase_rtdb.initialize_firebase(save_logs=process_b_args["save_logs"])
    print(f"{task_name} Running ✅")

    user_uid = process_b_args["user_credentials"]["userUid"]
    linked_uid = process_b_args["user_credentials"]["linkedUid"]

    livestream_ref = db.reference(f"liveStream/{user_uid}/{linked_uid}")
    detection_ref = db.reference(f"detection/{user_uid}/{linked_uid}")

    while True:
        if not live_status.is_set():
            print(f"{task_name} Live status is OFF. Waiting...")
            time.sleep(0.5)
            continue

        if not queue_frame.empty():
            frame = queue_frame.get()
            frame = np.array(frame, dtype=np.uint8)
            
            ret, buffer = cv2.imencode(".jpg", frame)
            if not ret:
                print("Error: Failed to encode frame.")
            else:
                jpg_text = base64.b64encode(buffer).decode("utf-8")
                now = datetime.now()
                lastUpdateAt = now.strftime('%m/%d/%Y at %H:%M:%S')

                livestream_ref.update({
                    "base64": jpg_text,
                    "lastUpdateAt": lastUpdateAt
                })

        if not number_of_class_instances.empty():
            class_counts = number_of_class_instances.get()
            number_of_chickens = class_counts.get("chickens", 0)
            number_of_intruders = class_counts.get("intruders", 0)

            updatedAt = datetime.now().strftime('%m/%d/%Y %H:%M:%S')
            detection_ref.update({
                "numberOfChickens": number_of_chickens,
                "numberOfIntruders": number_of_intruders,
                "updatedAt": updatedAt
            })

        time.sleep(0.5)
