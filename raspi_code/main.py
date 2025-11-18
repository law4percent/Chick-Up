from lib.processes import process_a, process_b, process_c
from multiprocessing import Process, Queue, Event
from lib.services import firebase_rtdb, handle_pairing
import os

def main(
        process_a_args: dict,
        process_b_args: dict,
        process_c_args: dict,
        device_uid: str         = "-3GSRmf356dy6GFQSTGIF",
        is_pc_device: bool      = False,
        save_logs: bool         = False,
        logs_path: str          = "logs",
        yolo_path: str          = "YOLO",
    ) -> None:
    
    if save_logs and not os.path.exists(logs_path):
        os.makedirs(logs_path)
        
    if not os.path.exists(yolo_path):
        os.makedirs(yolo_path)
        
    firebase_rtdb.initialize_firebase(save_logs=save_logs)
    user_credentials = handle_pairing.pair_it(device_uid=device_uid, is_pc_device=is_pc_device, save_logs=save_logs)

    # -----------------
    # Multi-processing
    #------------------
    queue_frame                 = Queue(maxsize = 1)
    live_status                 = Event()
    annotated_option            = Event()
    number_of_class_instances   = Queue(maxsize = 1)
    process_b_args["user_credentials"] = user_credentials
    process_c_args["user_credentials"] = user_credentials

    task_A = Process(target=process_a.process_A, args=("Process A", queue_frame, live_status, annotated_option, number_of_class_instances, process_a_args))
    task_B = Process(target=process_b.process_B, args=("Process B", queue_frame, live_status, number_of_class_instances, process_b_args))
    task_C = Process(target=process_c.process_C, args=("Process C", live_status, annotated_option, process_c_args))

    task_A.start()
    task_B.start()
    task_C.start()

    task_A.join()
    task_B.join()
    task_C.join()


if __name__ == "__main__":
    is_pc_device    = True
    save_logs       = False
    
    process_a_args = {
        "confidence": 0.25,
        "yolo_model_path": "YOLO/best.pt",
        "class_list_path": "YOLO/class_list.txt",
        "frame_dimensions": {"width": 640, "height": 480},
        "camera_index": 0,
        "is_pc_device": is_pc_device,
        "save_logs": save_logs
    }
    
    process_b_args = {
        "user_credentials": {},
        "is_pc_device": is_pc_device,
        "save_logs": save_logs
    }
    
    process_c_args = {
        "user_credentials": {},
        "is_pc_device": is_pc_device,
        "save_logs": save_logs
    }
    
    main(
        process_a_args  = process_a_args,
        process_b_args  = process_b_args,
        process_c_args  = process_c_args,
        is_pc_device    = is_pc_device,
        save_logs       = save_logs,
    )
