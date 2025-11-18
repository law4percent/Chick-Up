import cv2
from lib.services import detection
from multiprocessing import Queue, Event
from ultralytics import YOLO
import os
import logging
import time

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
        annotated_option: any,
        number_of_class_instances: Queue,
        process_a_args: dict
    ) -> None:
    print(f"{task_name} is starting...")
    
    # Configuration
    confidence          = process_a_args["confidence"]
    yolo_model_path     = process_a_args["yolo_model_path"]
    class_list_path     = process_a_args["class_list_path"]
    frame_dimensions    = process_a_args["frame_dimensions"]
    is_pc_device        = process_a_args["is_pc_device"]
    camera_index        = process_a_args["camera_index"]
    save_logs           = process_a_args["save_logs"]
    video_path          = process_a_args["video_path"]
    class_list, yolo_model, capture = checkpoints(test_mode=is_pc_device, yolo_model_path=yolo_model_path, class_list_path=class_list_path, video_path=video_path, camera_index=camera_index)

    while True:
        ret, raw_frame = capture.read()

        if not ret:
            if is_pc_device:
                print(f"Process A - Error: Video ended or video is a corrupt file.\nProcess A - Error: Check video here: {video_path}.\nProcess A - Error: Ctrl + C to end the program.")
                if save_logs:
                    logging.error(f"Process A - Video ended or video is a corrupt file.")
                    logging.error(f"Process A - Check video here: {video_path}.")
                    logging.error(f"Process A - Ctrl + C to end the program.")
            else:
                print(f"Process A - Error: Check the hardware camera.")
                if save_logs:
                    logging.error(f"Process A - Error: Check the hardware camera.")
                    
            time.sleep(2)
            continue
        
        raw_frame = cv2.resize(raw_frame, (frame_dimensions["width"], frame_dimensions["height"]))
        annotated_frame, number_of_chickens, number_of_intruders = detection.run(raw_frame=raw_frame, yolo_model=yolo_model, confidence=confidence, class_list=class_list, frame_dimensions=frame_dimensions)
                
        if live_status.is_set():
            if queue_frame.full():
                queue_frame.get()

            if annotated_option.is_set():
                queue_frame.put(annotated_frame)
            else:
                queue_frame.put(raw_frame)

        if number_of_class_instances.full():
            number_of_class_instances.get()
            
            number_of_class_instances.put(
                {
                    "chickens": number_of_chickens,
                    "intruders": number_of_intruders
                }
            )
        
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