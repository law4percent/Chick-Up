from ultralytics import YOLO
import cv2
import os
import logging

logging.basicConfig(
    filename='logs/debug.log',     # log file name
    filemode='a',              # 'a' to append, 'w' to overwrite
    level=logging.INFO,        # minimum level to log
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def run(raw_frame: any, frame_dimensions: dict, yolo_model: any, class_list: list, confidence: float = 0.25) -> list:
    boxes = _get_prediction_boxes(raw_frame=raw_frame, yolo_model=yolo_model, confidence=confidence)
    return _detect_object(frame=raw_frame, boxes=boxes, class_list=class_list, frame_dimensions=frame_dimensions)


def _get_prediction_boxes(raw_frame: any, confidence: float, yolo_model: any) -> any:
    """Get prediction boxes from the YOLO model."""
    pred    = yolo_model.predict(source=[raw_frame], save=False, conf=confidence)
    results = pred[0]
    boxes   = results.boxes.data.cpu().numpy()
    return boxes


def _detect_object(frame: any, boxes: any, class_list: list, frame_dimensions: dict) -> list:
    """Draw detected objects and labels on the frame."""
    number_of_chickens = 0
    number_of_intruders = 0

    for box in boxes:
        x1, y1, x2, y2, conf_score, cls = box
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
        conf_score = "%.2f" % conf_score
        class_name = class_list[int(cls)]
        
        if class_name in class_list:
            if class_name == "chicken":
                color = (0, 255, 0)
                number_of_chickens += 1
            else:
                color = (0, 0, 255)
                number_of_intruders += 1

            frame = _annotate_all_objects(frame, class_name, conf_score, (x1, y1), (x2, y2), color)

    # chicken_count   = count_all_chickens(boxes, class_list)
    frame = _display_chicken_count(frame, number_of_chickens, frame_dimensions)
    frame = _display_intruder_count(frame, number_of_intruders, frame_dimensions)
    return [frame, number_of_chickens, number_of_intruders]


def _annotate_all_objects(frame, class_name, conf_score, top_left, bottom_right, color) -> any:
    """Annotate detected objects on the frame."""
    cv2.rectangle(frame, top_left, bottom_right, color, 2)
    cv2.putText(frame, f"{class_name} {conf_score}", (top_left[0], top_left[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    return frame


def _display_intruder_count(frame: any, number_of_intruders: int, frame_dimensions: dict) -> any:
    """Display the intruder count in the upper-right corner of the frame."""
    overlay = frame.copy()
    width = frame_dimensions['width']
    cv2.rectangle(overlay, (width - 230, 10), (width - 10, 60), (0, 0, 0), -1)
    cv2.putText(frame, f"Intruders Detected: {number_of_intruders}", (width - 220, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    return frame


def _display_chicken_count(frame: any, number_of_chicken: int, frame_dimensions: dict) -> any:
    """Display the chicken count in the upper-left corner of the frame."""
    overlay = frame.copy()
    width = frame_dimensions['width']
    cv2.rectangle(overlay, (width - 430, 10), (width - 240, 60), (0, 0, 0), -1)
    cv2.putText(frame, f"Chickens Detected: {number_of_chicken}", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (128, 0, 128), 2)
    return frame