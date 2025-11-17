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
        
    firebase_rtdb.initialize_firebase(testing_mode=testing_mode, show_logs=show_logs)
    handle_pairing.pair_it(testing_mode=testing_mode, show_logs=show_logs)

    task_A = Process(target=process_a, args=("Process A", Queue(maxsize = 1), Event()))
    task_B = Process(target=process_b, args=("Process B", Queue(maxsize = 1), Event()))
    task_C = Process(target=process_c, args=("Process C", Event()))

    task_A.start()
    task_B.start()
    task_C.start()

    # firebase_rtdb.initialize_firebase("on")
    # linked_id = handle_hardware.require_valid_pairing(device_id)

    # print("Pairing success:", linked_id)

    # cap = cv2.VideoCapture("video/chicken3.mp4")
    # yolo_model = detection.model
    # class_list = detection.class_list

    # while True:
    #     ret, frame = cap.read()
    #     frame = cv2.resize(frame, (640, 480))

    #     if not ret:
    #         break

    #     boxes = detection.get_prediction_boxes(frame, yolo_model, confidence=0.25)
    #     chicken_count = detection.count_all_chickens(boxes, class_list)
    #     with_boxes_frame = detection.detect_object(frame, boxes, class_list)
    #     detection.display_chicken_count(frame, chicken_count)

    #     cv2.imshow("Chicken-Detection", with_boxes_frame) # diplay the frame or show frame
    #     if cv2.waitKey(1) & 0xFF == ord('q'):
    #         break

    # cap.release()
    # cv2.destroyAllWindows()
    

if __name__ == "__main__":
    main(
        testing_mode = True,
        show_logs = False
    )
