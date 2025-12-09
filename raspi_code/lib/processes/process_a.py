import cv2
from multiprocessing import Queue, Event
from ultralytics import YOLO
import os
import logging
import time
import queue

from lib.services import detection, utils
from lib import logger_config

logger = logger_config.setup_logger(name=__name__, level=logging.DEBUG)

def process_A(**kwargs) -> None:
    # Configuration
    process_A_args      = kwargs["process_A_args"]
    TASK_NAME           = process_A_args["TASK_NAME"]
    queue_frame         = process_A_args["queue_frame"]
    live_status         = process_A_args["live_status"]
    annotated_option    = process_A_args["annotated_option"]
    number_of_instances = process_A_args["number_of_instances"]
    YOLO_CONFIDENCE     = process_A_args["YOLO_CONFIDENCE"]
    FRAME_DIMENSION     = process_A_args["FRAME_DIMENSION"]
    IS_WEB_CAM          = process_A_args["IS_WEB_CAM"]
    PC_MODE             = process_A_args["PC_MODE"]
    CAMERA_INDEX        = process_A_args["CAMERA_INDEX"]
    VIDEO_FILE          = process_A_args["VIDEO_FILE"]
    SAVE_LOGS           = process_A_args["SAVE_LOGS"]
    SHOW_WINDOW         = process_A_args["SHOW_WINDOW"]
    YOLO_MODEL_FILE     = "YOLO/best.pt",
    CLASS_LIST_FILE     = "YOLO/class_list.txt",
    
    print(f"{TASK_NAME} - Running✅")
    logger.info(f"{TASK_NAME} - Running✅")
    
    FILE_PATHS = {
        "YOLO_MODEL_FILE"   : YOLO_MODEL_FILE, 
        "CLASS_LIST_FILE"   : CLASS_LIST_FILE, 
        "VIDEO_FILE"        : VIDEO_FILE
    }
    
    # "status"    : "success",
    # "class_list": init_result["class_list"],
    # "yolo_model": init_result["yolo_model"],
    # "capture"   : capture
    check_point_result = _check_points(
        FILE_PATHS  = FILE_PATHS, 
        PC_MODE     = PC_MODE, 
        SAVE_LOGS   = SAVE_LOGS, 
        CAMERA_INDEX= CAMERA_INDEX, 
        IS_WEB_CAM  = IS_WEB_CAM
    )
    if check_point_result["status"] == "error":
        if SAVE_LOGS:
            logger.error(f"{TASK_NAME} - {check_point_result["message"]}")
        exit()
        
    capture     = check_point_result["capture"]
    class_list  = check_point_result["class_list"]
    yolo_model  = check_point_result["yolo_model"]
    window_name, window_visible_state = setup_windows()
    
    while True:
        try:
            ret, raw_frame = capture.read()
            if not ret:
                if PC_MODE:
                    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    print(f"{TASK_NAME}Error: Video has ended or video is a corrupted file.")
                    print(f"{TASK_NAME}Error: Check video here: {VIDEO_FILE}.")
                    print(f"{TASK_NAME}Error: Ctrl + C to end the program.")
                    if SAVE_LOGS:
                        logging.error(f"{TASK_NAME}Video ended or video is a corrupt file.")
                        logging.error(f"{TASK_NAME}Check video here: {VIDEO_FILE}.")
                        logging.error(f"{TASK_NAME}Ctrl + C to end the program.")
                else:
                    print(f"{TASK_NAME}Error: Check the hardware camera.")
                    if SAVE_LOGS:
                        logging.error(f"{TASK_NAME}Error: Check the hardware camera.")
                        
                time.sleep(2)
                continue
            
            raw_frame = cv2.resize(raw_frame, (FRAME_DIMENSION["width"], FRAME_DIMENSION["height"]))
            annotated_frame, number_of_chickens, number_of_intruders = detection.run(
                raw_frame=raw_frame, 
                yolo_model=yolo_model, 
                confidence=YOLO_CONFIDENCE, 
                class_list=class_list, 
                frame_dimensions=FRAME_DIMENSION)
                    
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

            try:
                if number_of_instances.full():
                    number_of_instances.get_nowait()  # remove old data
            except queue.Empty:
                pass  # queue was unexpectedly empty

            try:
                number_of_instances.put_nowait({
                    "chickens": number_of_chickens,
                    "intruders": number_of_intruders
                })
            except queue.Full:
                pass  # queue is still full, skip this update

            if PC_MODE and SHOW_WINDOW:

                if window_visible_state:
                    cv2.imshow(window_name, annotated_frame)

                key = cv2.waitKey(1) & 0xFF

                if key == ord('q'):
                    break

                # Press C → close/hide the window
                elif key == ord('c'):
                    if window_visible_state:
                        cv2.destroyAllWindows()
                        window_visible_state = False

                # Press W → show the window again
                elif key == ord('w'):
                    if not window_visible_state:
                        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                        window_visible_state = True

        except Exception as e:
            print(f"{TASK_NAME} Error occurred: {e}")
            time.sleep(2)

    capture.release()
    cv2.destroyAllWindows()


def setup_windows(window_name: str = "Chick-Up Streaming", window_visible_state: bool = True):
    window_name = window_name
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    window_visible_state = window_visible_state
    return [window_name, window_visible_state]


def _init_YOLO_detection(CLASS_LIST_FILE: str, YOLO_MODEL_FILE: str) -> dict:
    class_list = []
    with open(CLASS_LIST_FILE, 'r') as f:
        class_list = [line.strip() for line in f.readlines()]
    
    try:    
        yolo_model = YOLO(YOLO_MODEL_FILE)
        return {
            "status"    : "success",
            "class_list": class_list,
            "yolo_model": yolo_model
        }
    except Exception as e:
        return {
            "status"    : "error",
            "message"   : "{e}. Failed to load"
        }


def _check_points(FILE_PATHS: dict, PC_MODE: bool, SAVE_LOGS: bool, IS_WEB_CAM: bool, CAMERA_INDEX: int) -> dict:
    for FILE_PATH in FILE_PATHS.values():    
        check_point_result = utils.file_existence_check_point(FILE_PATH, __name__)
        if check_point_result["status"] == "error":
            return check_point_result
    
    capture = None
    VIDEO_PATH = FILE_PATHS["VIDEO_PATH"]
    
    if PC_MODE and not IS_WEB_CAM:
        capture = cv2.VideoCapture(VIDEO_PATH)
        if not capture.isOpened():
            return {
                "status"    : "error",
                "message"   : f"Could not open video. Try to play the video file separately to check if it's corrupted. Video file location: {video_path}"
            }
            
    elif PC_MODE and IS_WEB_CAM:
        capture = cv2.VideoCapture(CAMERA_INDEX)
        if not capture.isOpened():
            return {
                "status"    : "error",
                "message"   : f"Could not open the camera index {CAMERA_INDEX}. Source: {__name__}"
            }
          
    # =============== WIP: Change this to RASPI CAMERA ===============
    else: 
        capture = cv2.VideoCapture(CAMERA_INDEX)
        if not capture.isOpened():
            return {
                "status"    : "error",
                "message"   : f"Could not open the camera index {CAMERA_INDEX}. Source: {__name__}"
            }
        
    init_result = _init_YOLO_detection(FILE_PATHS["CLASS_LIST_FILE"], FILE_PATHS["YOLO_MODEL_FILE"])
    if init_result["status"] == "error":
        return init_result

    return {
        "status"    : "success",
        "class_list": init_result["class_list"],
        "yolo_model": init_result["yolo_model"],
        "capture"   : capture
    }