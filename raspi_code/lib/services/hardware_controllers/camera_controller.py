from picamera2 import Picamera2
from .. import utils
import cv2

def setup_windows(window_name: str = "Chick-Up Streaming", window_visible_state: bool = True):
    window_name = window_name
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    window_visible_state = window_visible_state
    return [window_name, window_visible_state]
  

def clean_up_camera(capture: any, PC_MODE: bool) -> None:
    if PC_MODE:
        capture.release()
    cv2.destroyAllWindows()
    
    
def config_camera(PC_MODE: bool, IS_WEB_CAM: bool, VIDEO_PATH: str, CAMERA_INDEX: int, FRAME_DIMENSION: dict) -> dict:
  if PC_MODE:
    if not IS_WEB_CAM:
      check_point_result = utils.file_existence_check_point(VIDEO_PATH, __name__)
      if check_point_result["status"] == "error":
        return check_point_result
      
      capture = cv2.VideoCapture(VIDEO_PATH)
      if not capture.isOpened():
          return {
            "status"    : "error",
            "message"   : f"Could not open video. Try to play the video file separately to check if it's corrupted. Video file location: {VIDEO_PATH}"
          }
      return {
        "status"    : "success",
        "capture"   : capture
      }
      
    else:
      capture = cv2.VideoCapture(CAMERA_INDEX)
      if not capture.isOpened():
          return {
            "status"    : "error",
            "message"   : f"Could not open the camera index {CAMERA_INDEX}. Source: {__name__}"
          }
      return {
        "status"  : "success",
        "capture" : capture
      }
    
  try:
    picam2 = Picamera2()

    # Create camera configuration
    config = picam2.create_still_configuration(
        main={"size": (FRAME_DIMENSION["width"], FRAME_DIMENSION["height"])},   # HD resolution
        lores={"size": (640, 480)},   # Lower resolution for previews/processing
        display="lores"               # Use the low-res for viewing
    )

    # Apply the configuration
    picam2.configure(config)

    # Optional tuning
    #picam2.set_controls({
    #    "AwbMode": "auto",           # Auto white balance
    #    "ExposureTime": 10000,       # Adjust if needed
    #    "AnalogueGain": 1.0,         # Adjust for brightness
    #})

    return {
      "status"  : "success",
      "capture" : picam2
    }
  except Exception as e:
    return {
      "status"  : "error",
      "message" : f"{e}. Failed to configure raspi-camera. Source: {__name__}"
    }

