import cv2
from lib.services import detection
from multiprocessing import Queue, Event
from ultralytics import YOLO
import os
import logging
import time
import queue 

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
    print(f"{task_name}Running✅")
    
    # Configuration
    confidence          = process_a_args["confidence"]
    yolo_model_path     = process_a_args["yolo_model_path"]
    class_list_path     = process_a_args["class_list_path"]
    frame_dimensions    = process_a_args["frame_dimensions"]
    is_pc_device        = process_a_args["is_pc_device"]
    camera_index        = process_a_args["camera_index"]
    save_logs           = process_a_args["save_logs"]
    video_path          = process_a_args["video_path"]
    use_web_cam         = process_a_args["use_web_cam"]
    
    class_list, yolo_model, capture = checkpoints(task_name=task_name, is_pc_device=is_pc_device, save_logs=save_logs, yolo_model_path=yolo_model_path, class_list_path=class_list_path, video_path=video_path, camera_index=camera_index, use_web_cam=use_web_cam)

    while True:
        ret, raw_frame = capture.read()
        if not ret:
            if is_pc_device:
                print(f"{task_name}Error: Video has ended or video is a corrupted file.")
                print(f"{task_name}Error: Check video here: {video_path}.")
                print(f"{task_name}Error: Ctrl + C to end the program.")
                if save_logs:
                    logging.error(f"{task_name}Video ended or video is a corrupt file.")
                    logging.error(f"{task_name}Check video here: {video_path}.")
                    logging.error(f"{task_name}Ctrl + C to end the program.")
            else:
                print(f"{task_name}Error: Check the hardware camera.")
                if save_logs:
                    logging.error(f"{task_name}Error: Check the hardware camera.")
                    
            time.sleep(2)
            continue
        
        raw_frame = cv2.resize(raw_frame, (frame_dimensions["width"], frame_dimensions["height"]))
        annotated_frame, number_of_chickens, number_of_intruders = detection.run(raw_frame=raw_frame, yolo_model=yolo_model, confidence=confidence, class_list=class_list, frame_dimensions=frame_dimensions)
                
        if live_status.is_set():
            if queue_frame.full():
                try:
                    queue_frame.get_nowait()  # remove old frame
                except queue.Empty:
                    pass

            try:
                if annotated_option.is_set():
                    queue_frame.put_nowait(annotated_frame)
                else:
                    queue_frame.put_nowait(raw_frame)
            except queue.Full:
                pass  # skip frame if queue is full


        # Safely update number_of_class_instances queue
        try:
            if number_of_class_instances.full():
                number_of_class_instances.get_nowait()  # remove old data
        except queue.Empty:
            pass  # queue was unexpectedly empty

        try:
            number_of_class_instances.put_nowait({
                "chickens": number_of_chickens,
                "intruders": number_of_intruders
            })
        except queue.Full:
            pass  # queue is still full, skip this update
        # print(f"{task_name} Repeat✅ - Chickens: {number_of_chickens} | Intruders: {number_of_intruders}")
        
        cv2.imshow("Chicken-Detection", annotated_frame) # diplay the frame or show frame
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    capture.release()
    cv2.destroyAllWindows()


def checkpoints(task_name:str, is_pc_device: bool, save_logs: bool, yolo_model_path: str, class_list_path: str, use_web_cam: bool, video_path: str = "video/chicken.mp4", camera_index: int = 0) -> list:
    class_list = []

    if is_pc_device and not use_web_cam:
        if not os.path.exists(video_path):
            print(f"{task_name}Error: Video file not found at path: {video_path}")
            if save_logs:
                logging.error(f"{task_name}Video file not found at path: {video_path}")
            exit()
            
        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            print(f"{task_name}Error: Could not open video.")
            print(f"{task_name}Error: Try to play the video file separately to check if it's corrupted.")
            print(f"{task_name}Error: Video file location: {video_path}")
            if save_logs:
                logging.error(f"{task_name}Could not open video.")
                logging.error(f"{task_name}Try to play the video file separately to check if it's corrupted.")
                logging.error(f"{task_name}Video file location: {video_path}")
            exit()
    elif is_pc_device and use_web_cam:
        capture = cv2.VideoCapture(camera_index)
        if not capture.isOpened():
            print(f"{task_name}Error: Could not open the camera index {camera_index}.")
            if save_logs:
                logging.error(f"{task_name}Could not open the camera index {camera_index}.")
            exit()
    else:
        capture = cv2.VideoCapture(camera_index)
        if not capture.isOpened():
            print(f"{task_name}Error: Could not open the camera index {camera_index}.")
            if save_logs:
                logging.error(f"{task_name}Could not open the camera index {camera_index}.")
            exit()
    
    if not os.path.exists(yolo_model_path):
        print(f"{task_name}Error: YOLO model not found at path: {yolo_model_path}")
        if save_logs:
            logging.error(f"{task_name}YOLO model not found at path: {yolo_model_path}")
        exit()

    if not os.path.exists(class_list_path):
        print(f"{task_name}Error: Class list file not found at path: {class_list_path}")
        if save_logs:
            logging.error(f"{task_name}Class list file not found at path: {class_list_path}")
        exit()

    with open(class_list_path, 'r') as f:
        class_list = [line.strip() for line in f.readlines()]
    
    yolo_model = YOLO(yolo_model_path)

    return [class_list, yolo_model, capture]