import cv2
from multiprocessing import Event
from lib.services.hardware import camera_controller as camera
import logging
import time
import queue

from lib.services import detection, utils
from lib import logger_config

logger = logger_config.setup_logger(name=__name__, level=logging.DEBUG)


def _check_points(FILE_PATHS: dict, PC_MODE: bool, IS_WEB_CAM: bool, CAMERA_INDEX: int, FRAME_DIMENSION: dict) -> dict:
    count = 0
    for FILE_PATH in FILE_PATHS.values():    
        check_point_result = utils.file_existence_check_point(FILE_PATH, __name__)
        if check_point_result["status"] == "error" and count < 2:
            return check_point_result
        count += 1
    
    capture = None
    VIDEO_PATH = FILE_PATHS["VIDEO_FILE"]
    
    config_result = camera.config_camera(PC_MODE, IS_WEB_CAM, VIDEO_PATH, CAMERA_INDEX, FRAME_DIMENSION)
    if config_result["status"] == "error":
        return config_result
        
    init_result = detection.init_YOLO_detection(FILE_PATHS["CLASS_LIST_FILE"], FILE_PATHS["YOLO_MODEL_FILE"])
    if init_result["status"] == "error":
        return init_result

    return {
        "status"    : "success",
        "class_list": init_result["class_list"],
        "yolo_model": init_result["yolo_model"],
        "capture"   : config_result["capture"]
    }

# ========================= WIP =========================
def process_A(**kwargs) -> None:
    # Configuration
    process_A_args      = kwargs["process_A_args"]
    TASK_NAME           = process_A_args["TASK_NAME"]
    queue_frame         = process_A_args["queue_frame"]
    live_status         = process_A_args["live_status"]
    annotated_option    = process_A_args["annotated_option"]
    number_of_instances = process_A_args["number_of_instances"]
    status_checker      = process_A_args["status_checker"]
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

    check_point_result = _check_points(
        FILE_PATHS      = FILE_PATHS, 
        PC_MODE         = PC_MODE,
        CAMERA_INDEX    = CAMERA_INDEX, 
        IS_WEB_CAM      = IS_WEB_CAM,
        FRAME_DIMENSION = FRAME_DIMENSION
    )
    if check_point_result["status"] == "error":
        if SAVE_LOGS:
            logger.error(f"{TASK_NAME} - {check_point_result["message"]}")
        status_checker.clear()
        exit()
        
    capture     = check_point_result["capture"]
    class_list  = check_point_result["class_list"]
    yolo_model  = check_point_result["yolo_model"]
    
    capture     = None
    if not PC_MODE:
        capture = check_point_result["capture"]
        capture.start()
    else:
        capture = check_point_result["capture"]
        
    window_name, window_visible_state = camera_controller.setup_windows(window_visible_state=SHOW_WINDOW)
    
    ret         = None
    raw_frame   = None
    while True:
        if not status_checker.is_set():
            logger.error(f"{TASK_NAME} - One of the processes got error.")
            exit()
        
        if PC_MODE:
            ret, raw_frame = capture.read()
            if not ret:
                if not IS_WEB_CAM:
                    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                
                if SAVE_LOGS:
                    logging.error(f"{TASK_NAME}Error: Check the hardware camera.")
                status_checker.clear()
                camera_controller.clean_up_camera(capture, PC_MODE)
                exit()
                        
                time.sleep(5)
                continue
        else:
            raw_frame = capture.capture_array()
        
        raw_frame = cv2.resize(raw_frame, (FRAME_DIMENSION["width"], FRAME_DIMENSION["height"]))
        annotated_frame, number_of_chickens, number_of_intruders = detection.run(
            raw_frame       = raw_frame, 
            yolo_model      = yolo_model, 
            confidence      = YOLO_CONFIDENCE, 
            class_list      = class_list, 
            frame_dimension = FRAME_DIMENSION
        )
                
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

        if SHOW_WINDOW:
            if window_visible_state:
                cv2.imshow(window_name, annotated_frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                break

            # Press C → close/hide the window
            elif key == ord('c'):
                if window_visible_state:
                    camera_controller.clean_up_camera(capture, PC_MODE)
                    window_visible_state = False

            # Press W → show the window again
            elif key == ord('w'):
                if not window_visible_state:
                    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                    window_visible_state = True

    camera_controller.clean_up_camera(capture, PC_MODE)