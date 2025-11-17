import cv2
from lib.services import detection
from multiprocessing import Process, Queue, Event

def process_A(
        task_name: str,
        queue: Queue,
        live_event_status: any,
        with_annotated_live_status: any
    ):
    print(f"{task_name} is starting...")
    
    cap = cv2.VideoCapture("video/chicken3.mp4")
    yolo_model = detection.model
    confidence = 0.25

    while True:
        ret, raw_frame = cap.read()
        frame = cv2.resize(frame, (640, 480))

        if not ret:
            break

        annotated_frame, number_of_chickens = detection.run(raw_frame=raw_frame, yolo_model=yolo_model, confidence=confidence)

        
        if live_event_status.is_set():
            if with_annotated_live_status.is_set():
                frame_array = annotated_frame.tolist()
            else:
                frame_array = raw_frame.tolist()
                
        if live_event_status.is_set():
            if queue.full():
                queue.get()

            queue.put(frame_array)
        
        cv2.imshow("Chicken-Detection", annotated_frame) # diplay the frame or show frame
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()