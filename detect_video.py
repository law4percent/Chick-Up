from ultralytics import YOLO
import cv2

model = YOLO("runs-20251028T012737Z-1-001/runs/detect/train/weights/best.pt")
  
video_path = "chicken3.mp4"   # change this to your video name or path

results = model.predict(
    source=video_path,
    save=True,     
    save_txt=False,     
    imgsz=640,
    conf=0.5
)

