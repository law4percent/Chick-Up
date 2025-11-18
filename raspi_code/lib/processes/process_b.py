import time
from multiprocessing import Queue

def process_B(
        task_name: str,
        queue_frame: Queue,
        live_status: any,
    ) -> None:
    print(f"{task_name} is starting...")

    while True:
        print(f"{task_name}...")
        time.sleep(3)