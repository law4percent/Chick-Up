import time
import cv2
import base64
import numpy as np
from multiprocessing import Queue
from lib.services.firebase_rtdb import db

def process_B(
        task_name: str,
        queue_frame: Queue,
        live_status: any,
        live_uid: str = "kP718rjyRXWLDUupBhiQTRAaWKt2"
    ) -> None:
    print(f"{task_name} is starting...")

    while True:

        if live_status.is_set():
            time.sleep(0.5)
            continue

        if queue_frame.empty():
            time.sleep(0.5)
            continue

        frame_list = queue_frame.get()

        frame = np.array(frame_list, dtype=np.uint8)
        
        ret, buffer = cv2.imencode(".jpg", frame)
        if not ret:
            print("Error: Failed to encode frame.")
            continue


        jpg_text = base64.b64encode(buffer).decode("utf-8")

        db.reference(f"live/{live_uid}/frameListFormat").set(jpg_text)

        print(f"Uploaded frame to live/{live_uid}")

        time.sleep(0.5)