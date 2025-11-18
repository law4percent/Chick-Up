import time
from multiprocessing import Queue

# "Process C", live_status, annotated_option, process_c_args
def process_C(
        task_name: str,
        live_status: any,
        annotated_option: any,
        process_c_args: dict
    ):
    print(f"{task_name} is starting...")

    while True:
        print(f"{task_name}...")
        time.sleep(3)