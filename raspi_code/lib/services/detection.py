from ultralytics import YOLO
import cv2

# Load YOLO model
model = YOLO("YOLO/best.pt")
class_list = ["cat", "chicken", "rat", "dog", "snake"]


def get_prediction_boxes(frame: any, confidence: float, yolo_model: any) -> any:
    """Get prediction boxes from the YOLO model."""
    pred = yolo_model.predict(source=[frame], save=False, conf=confidence)
    results = pred[0]
    boxes = results.boxes.data.cpu().numpy()
    return boxes


def detect_object(frame: any, boxes: any, class_list: list) -> list:
    """Draw detected objects and labels on the frame."""
    for box in boxes:
        x1, y1, x2, y2, conf_score, cls = box
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
        conf_score = "%.2f" % conf_score
        class_name = class_list[int(cls)]

        color = (0, 255, 0) if class_name == "chicken" else (0, 0, 255)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, f"{class_name} {conf_score}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    chicken_count   = count_all_chickens(boxes, class_list)
    display_chicken_count(frame, chicken_count)
    return [frame, chicken_count]


def count_all_chickens(boxes, class_list) -> int:
    """Count all chickens detected in the frame."""
    count = 0
    for box in boxes:
        _, _, _, _, _, cls = box
        class_name = class_list[int(cls)]
        if class_name == "chicken":
            count += 1
    return count


def display_chicken_count(frame, count) -> None:
    """Display the chicken count in the upper-left corner of the frame."""
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (230, 60), (0, 0, 0), -1)

    cv2.putText(frame, f"Chickens Detected: {count}",
                (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                (128, 0, 128), 2)


def run(raw_frame: any, yolo_model: any, confidence: float = 0.25) -> list:
    boxes                                   = get_prediction_boxes(raw_frame, yolo_model, confidence=confidence)
    annotated_frame, number_of_chickens     = detect_object(raw_frame, boxes, class_list)
    return [annotated_frame, number_of_chickens]