'''
    Phase 3
'''
from ultralytics import YOLO
import cv2

model = YOLO("YOLO/best.pt")
class_list = ["cat", "chicken", "dog", "rat", "snake"]

def get_prediction_boxes(frame, yolo_model, confidence):
    """Get prediction boxes from the YOLO model."""
    pred = yolo_model.predict(source=[frame], save=False, conf=confidence)
    results = pred[0]
    boxes = results.boxes.data.numpy()
    return boxes

def detect_object(frame, boxes, class_list):
    """Track detected objects in defined zones."""

    for idx, box in enumerate(boxes):
        x1, y1, x2, y2, conf_score, cls = box
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
        conf_score = "%.2f" % conf_score
        cls_center_x = int(x1 + x2) // 2
        cls_center_y = int(y1 + y2) // 2
        cls_center_pnt = (cls_center_x, cls_center_y)
        class_name = class_list[int(cls)]
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.circle(frame, cls_center_pnt, 2, (0, 0, 255), -1)
        cv2.putText(frame, f"{class_name} {conf_score}", (x1, y1 - 10),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    return frame