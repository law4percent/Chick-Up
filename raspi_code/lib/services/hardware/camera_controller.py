import cv2
import logging
from .. import utils

# Optional import to prevent PC crashes
try:
    from picamera2 import Picamera2
    HAS_PICAMERA = True
except (ImportError, RuntimeError):
    HAS_PICAMERA = False

logger = logging.getLogger(__name__)

def setup_windows(window_name: str = "Chick-Up Streaming", window_visible_state: bool = True) -> list:
    """Initializes a window if visible state is true."""
    if window_visible_state:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    return [window_name, window_visible_state]

def clean_up_camera(capture: any, PC_MODE: bool) -> dict:
    """Properly release or stop the camera depending on the mode."""
    try:
        if PC_MODE:
            if capture and capture.isOpened():
                capture.release()
        else:
            if capture:
                capture.stop()
                capture.close()
        cv2.destroyAllWindows()
        return {"status": "success"}
    except Exception as e:
        cv2.destroyAllWindows()
        return {
            "status"  : "error",
            "message" : f"{e} Error cleaning up camera. Source: {__name__}"
        }

def config_camera(PC_MODE: bool, IS_WEB_CAM: bool, VIDEO_PATH: str, CAMERA_INDEX: int, FRAME_DIMENSION: dict) -> dict:
    # --- PC MODE OR USB WEBCAM ---
    if PC_MODE or IS_WEB_CAM:
        source = VIDEO_PATH if (not IS_WEB_CAM and VIDEO_PATH) else CAMERA_INDEX
        
        if not IS_WEB_CAM:
            check_result = utils.file_existence_check_point(VIDEO_PATH, __name__)
            if check_result["status"] == "error":
                return check_result

        capture = cv2.VideoCapture(source)
        if not capture.isOpened():
            return {
                "status": "error",
                "message": f"Could not open source {source}. Source: {__name__}"
            }
        
        # Helper: add capture_array method to cv2 object to match Picamera2 API
        # This makes process_a.py code simpler
        def capture_array_shim():
            ret, frame = capture.read()
            return frame if ret else None
        
        capture.capture_array = capture_array_shim
        
        return {"status": "success", "capture": capture}

    # --- RASPBERRY PI NATIVE MODE ---
    if not HAS_PICAMERA:
        return {
            "status": "error", 
            "message": "Picamera2 not installed or not running on Raspberry Pi."
        }

    try:
        picam2 = Picamera2()
        
        # Use video_configuration for streaming (better than still_configuration)
        config = picam2.create_video_configuration(
            main={"size": (FRAME_DIMENSION["width"], FRAME_DIMENSION["height"]), "format": "BGR888"},
        )
        
        picam2.configure(config)
        picam2.start() # CRITICAL: Camera won't output frames without this

        return {
            "status"  : "success",
            "capture" : picam2
        }
    except Exception as e:
        return {
            "status"  : "error",
            "message" : f"{e}. Failed to configure raspi-camera. Source: {__name__}"
        }