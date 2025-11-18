import time

def process_C(
        task_name: str,
        live_status: any,
        annotated_option: any
    ):
    print(f"{task_name} is starting...")

    while True:
        print(f"{task_name}...")
        time.sleep(3)