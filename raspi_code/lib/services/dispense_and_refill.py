from multiprocessing import Process, Event
import time

def button_task(name, stop_event):
    print(f"{name} started")
    while True:
        print("Click button now!")
        time.sleep(1) # delay(1000);

def detection_task(name, stop_event):
    print(f"{name} started")
    while True:
        print("Detecting...")
        time.sleep(5) # delay(1000);

if __name__ == "__main__":
    stop_event = Event()  # Shared event between processes
    
    p1 = Process(target=button_task, args=("Button Task", stop_event))
    p2 = Process(target=detection_task, args=("Detection Task", stop_event))

    p1.start()
    p2.start()

    p1.join()
    p2.join()

    print("Both tasks done!")
