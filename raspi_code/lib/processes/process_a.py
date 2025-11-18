import cv2
from lib.services import detection
from multiprocessing import Process, Queue, Event
import base64
from ultralytics import YOLO
import os
import logging

logging.basicConfig(
    filename='logs/debug.log',     # log file name
    filemode='a',              # 'a' to append, 'w' to overwrite
    level=logging.INFO,        # minimum level to log
    format='%(asctime)s - %(levelname)s - %(message)s'
)


"""
    For Reference
    
    def send_frame_to_firebase(frame):
        # Encode frame to JPEG
        ret, buffer = cv2.imencode('.jpg', frame)

        # Convert to Base64 string
        jpg_as_text = base64.b64encode(buffer).decode('utf-8')

        # Upload to RTDB
        db.reference("live_frame").set(jpg_as_text)
"""


def process_A(
        task_name: str,
        queue_frame: Queue,
        live_status: any,
        annotated_option: any
    ) -> None:
    print(f"{task_name} is starting...")
    
    # Configuration
    confidence          = 0.25
    yolo_model_path     = "YOLO/best.pt"
    class_list_path     = "YOLO/class_list.txt"
    frame_dimensions    = {"width": 640, "height": 480}
    test_mode           = True
    camera_index        = 0
    class_list, yolo_model, capture = checkpoints(test_mode = test_mode, yolo_model_path = yolo_model_path, class_list_path = class_list_path, camera_index = camera_index)

    while True:
        ret, raw_frame = capture.read()
        frame = cv2.resize(frame, (frame_dimensions["width"], frame_dimensions["height"]))

        if not ret:
            break

        annotated_frame, number_of_chickens, number_of_intruders = detection.run(raw_frame=raw_frame, yolo_model=yolo_model, confidence=confidence, class_list=class_list, frame_dimensions=frame_dimensions)

        
        if live_status.is_set():
            if annotated_option.is_set():
                frame_array = annotated_frame.tolist()
            else:
                frame_array = raw_frame.tolist()
                
        if live_status.is_set():
            if queue_frame.full():
                queue_frame.get()

            queue_frame.put(frame_array)
        
        cv2.imshow("Chicken-Detection", annotated_frame) # diplay the frame or show frame
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    capture.release()
    cv2.destroyAllWindows()

def checkpoints(test_mode: bool, yolo_model_path: str, class_list_path: str, video_path: str = "video/chicken.mp4", camera_index: int = 0) -> list:
    class_list = []

    if test_mode:
        if not os.path.exists(video_path):
            print(f"Error: Test video not found at path: {video_path}")
            logging.error(f"Test video not found at path: {video_path}")
            exit()
        print("Test mode enabled. Using test video.")
        logging.info("Test mode enabled. Using test video.")
        capture = cv2.VideoCapture("video/chicken.mp4")
        if not capture.isOpened():
            print(f"Error: Could not open video. Try to play the video file separately to check if it's corrupted.\nVideo file location: {video_path}")
            logging.error(f"Could not open video. Try to play the video file separately to check if it's corrupted.\nVideo file location: {video_path}")
            exit()
    else:
        capture = cv2.VideoCapture(camera_index)
        if not capture.isOpened():
            print(f"Error: Could not open the camera index {camera_index}.")
            logging.error(f"Could not open the camera index {camera_index}.")
            exit()
    
    if not os.path.exists(yolo_model_path):
        print(f"Error: YOLO model not found at path: {yolo_model_path}")
        logging.error(f"YOLO model not found at path: {yolo_model_path}")
        exit()

    if not os.path.exists(class_list_path):
        print(f"Error: Class list file not found at path: {class_list_path}")
        logging.error(f"Class list file not found at path: {class_list_path}")
        exit()

    with open(class_list_path, 'r') as f:
        class_list = [line.strip() for line in f.readlines()]
    
    yolo_model = YOLO(yolo_model_path)

    return [class_list, yolo_model, capture]