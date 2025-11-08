from lib.services import detection
import cv2


def main():
    cap = cv2.VideoCapture("video/chicken3.mp4")
    yolo_model = detection.model
    class_list = detection.class_list

    while True:
        ret, frame = cap.read()
        frame = cv2.resize(frame, (640, 480))

        if not ret:
            break

        boxes = detection.get_prediction_boxes(frame, yolo_model, confidence=0.25)
        chicken_count = detection.count_all_chickens(boxes, class_list)
        with_boxes_frame = detection.detect_object(frame, boxes, class_list)
        detection.display_chicken_count(frame, chicken_count)

        cv2.imshow("Chicken-Detection", with_boxes_frame) # diplay the frame or show frame
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    

if __name__ == "__main__":
    main()