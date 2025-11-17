import cv2
import numpy as np
import firebase_admin
from firebase_admin import credentials, db
from multiprocessing import Process, Queue
import time

# -----------------------------
# Firebase initialize
# -----------------------------
cred = credentials.Certificate("serviceAccount.json")
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://YOUR_PROJECT.firebaseio.com/"
})

# -----------------------------
# TASK A: Image detection
# -----------------------------
def detection_task(queue):
    print("Task A (Detection) started...")

    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        
        # Simulate heavy detection processing
        time.sleep(0.5)
        
        # Put the result into the queue as matrix array
        frame_array = frame.tolist()   # Convert image → Python list (matrix)

        if queue.full():
            queue.get()                # Remove old frame to avoid blocking

        queue.put(frame_array)

        print("Task A: Frame processed and sent to queue.")

# -----------------------------
# TASK B: Firebase RTDB sender
# -----------------------------
def firebase_task(queue):
    print("Task B (Firebase RTDB) started...")

    ref = db.reference("/livestream/frame")

    while True:
        if not queue.empty():
            frame_data = queue.get()  # matrix array
            
            ref.set(frame_data)       # send to RTDB
            
            print("Task B: Frame uploaded to RTDB.")

        time.sleep(0.1)  # prevent hogging CPU

# -----------------------------
# MAIN PROCESS
# -----------------------------
if __name__ == "__main__":
    queue = Queue(maxsize=1)  # store only latest frame

    p1 = Process(target=detection_task, args=(queue,))
    p2 = Process(target=firebase_task, args=(queue,))

    p1.start()
    p2.start()

    p1.join()
    p2.join()
