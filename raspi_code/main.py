from lib.processes import process_a, process_b, process_c
from multiprocessing import Process, Queue, Event
from lib.services import firebase_rtdb, handle_pairing
import os

def main(
        testing_mode: bool  = False,
        show_logs: bool     = False,
        logs_path: str      = "logs",
        yolo_path: str      = "YOLO"
    ) -> None:
    if show_logs and not os.path.exists(logs_path):
        os.makedirs(logs_path)
        
    if not os.path.exists(yolo_path):
        os.makedirs(yolo_path)
        
    firebase_rtdb.initialize_firebase(show_logs=show_logs)
    handle_pairing.pair_it(testing_mode=testing_mode, show_logs=show_logs)

    # Multi-processing
    task_A = Process(target=process_a, args=("Process A", Queue(maxsize = 1), Event(), Event()))
    task_B = Process(target=process_b, args=("Process B", Queue(maxsize = 1), Event()))
    task_C = Process(target=process_c, args=("Process C", Event(), Event()))

    task_A.start()
    task_B.start()
    task_C.start()

if __name__ == "__main__":
    main(
        testing_mode = True,
        show_logs = False
    )
