import cv2


def run(raw_frame: any, frame_dimension: dict, yolo_model: any, class_list: list, confidence: float = 0.25) -> list:
    boxes = _get_prediction_boxes(raw_frame=raw_frame, yolo_model=yolo_model, confidence=confidence)
    return _detect_object(frame=raw_frame, boxes=boxes, class_list=class_list, frame_dimensions=frame_dimension)


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
                color = (50, 255, 50)
                number_of_chickens += 1
            else:
                color = (0, 0, 255)
                number_of_intruders += 1

            _annotate_all_objects(frame, class_name, conf_score, (x1, y1), (x2, y2), color)

    cv2.rectangle(frame, (15, 15), (250, 30+15+30+15), (111, 111, 11), -1)
    alpha = 0.5
    _display_chicken_count(frame, number_of_chickens, font_size=0.6)
    _display_intruder_count(frame, number_of_intruders, font_size=0.6)
    frame = cv2.addWeighted(frame, alpha, frame, 1 - alpha, 0)
    return [frame, number_of_chickens, number_of_intruders]


def _annotate_all_objects(frame, class_name, conf_score, top_left, bottom_right, color) -> None:
    """Annotate detected objects on the frame."""
    cv2.rectangle(frame, top_left, bottom_right, color, 2)
    cv2.putText(frame, f"{class_name} {conf_score}", (top_left[0], top_left[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


def _display_intruder_count(frame: any, number_of_intruders: int, font_size: float) -> None:
    """Display the intruder count in the upper-right corner of the frame."""
    cv2.putText(frame, f"Intruders Detected:", (30, 30+15+30), cv2.FONT_HERSHEY_SIMPLEX, font_size, (250, 250, 250), 2)
    cv2.putText(frame, f"                    {number_of_intruders}", (20+5, 30+15+30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)


def _display_chicken_count(frame: any, number_of_chicken: int, font_size: float) -> None:
    """Display the chicken count in the upper-left corner of the frame."""
    cv2.putText(frame, f"Chickens Detected:", (30, 30+15), cv2.FONT_HERSHEY_SIMPLEX, font_size, (250, 250, 250), 2)
    cv2.putText(frame, f"                    {number_of_chicken}", (20+5, 30+15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (50, 255, 50), 2)