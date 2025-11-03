"""
    Sample code demonstrating inter-process communication using multiprocessing
"""

from multiprocessing import Process, Event
import time

def task(name, stop_event):
    count = 0
    print(f"{name} started")
    
    while not stop_event.is_set():  # Check the shared event
        print(count)
        time.sleep(1)
        count += 1
        
    print(f"{name} done")

def task2(name, stop_event):
    print(f"{name} started")
    time.sleep(5)  # Simulate some work
    print(f"{name} done")
    stop_event.set()  # Signal the other process to stop

if __name__ == "__main__":
    stop_event = Event()  # Shared event between processes
    
    p1 = Process(target=task, args=("Task 1", stop_event))
    p2 = Process(target=task2, args=("Task 2", stop_event))

    p1.start()
    p2.start()

    p1.join()
    p2.join()

    print("Both tasks done!")
