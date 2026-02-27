"""
Camera Controller Module
Loc: lib/services/hardware/camera_controller.py

Supports:
- PC mode (cv2.VideoCapture from file or webcam)
- Raspberry Pi native mode (Picamera2)

This module raises exceptions only — no logging.
All logging is handled by the calling process.
"""

import cv2
from typing import Any

from lib.services import utils

# Optional import — prevents crash on PC/dev environments
try:
    from picamera2 import Picamera2
    HAS_PICAMERA = True
except (ImportError, RuntimeError):
    HAS_PICAMERA = False


# ─────────────────────────── EXCEPTIONS ──────────────────────────────────────

class CameraError(Exception):
    """Base exception for camera errors"""
    pass

class CameraConfigError(CameraError):
    """Raised when camera configuration fails"""
    pass

class CameraCleanupError(CameraError):
    """Raised when camera cleanup fails"""
    pass

class CameraNotAvailableError(CameraError):
    """Raised when required camera hardware is not available"""
    pass


# ─────────────────────────── WINDOW SETUP ────────────────────────────────────

def setup_windows(
    window_name          : str  = "Chick-Up Streaming",
    window_visible_state : bool = True
) -> list:
    """
    Initialize a display window if visible state is True.

    Args:
        window_name:          OpenCV window name
        window_visible_state: Show window on init

    Returns:
        [window_name, window_visible_state]
    """
    if window_visible_state:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    return [window_name, window_visible_state]


# ─────────────────────────── CLEANUP ─────────────────────────────────────────

def clean_up_camera(capture: Any, PC_MODE: bool) -> dict:
    """
    Properly release or stop the camera depending on mode.

    Args:
        capture: cv2.VideoCapture or Picamera2 instance
        PC_MODE: True = cv2, False = Picamera2

    Returns:
        {"status": "success"} or {"status": "error", "message": str}

    Note:
        Returns a dict instead of raising so the finally block in the
        calling process always completes even on camera errors.
    """
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
            "message" : f"Error cleaning up camera: {e}. Source: {__name__}"
        }


# ─────────────────────────── CONFIG ──────────────────────────────────────────

def config_camera(
    PC_MODE         : bool,
    IS_WEB_CAM      : bool,
    VIDEO_PATH      : str,
    CAMERA_INDEX    : int,
    FRAME_DIMENSION : dict
) -> dict:
    """
    Configure and return the appropriate camera capture object.

    Args:
        PC_MODE:         True = use cv2 (video file or webcam)
        IS_WEB_CAM:      True = use webcam index, False = use VIDEO_PATH
        VIDEO_PATH:      Path to video file (used when PC_MODE=True, IS_WEB_CAM=False)
        CAMERA_INDEX:    Camera index for webcam (used when IS_WEB_CAM=True)
        FRAME_DIMENSION: {"width": int, "height": int}

    Returns:
        {"status": "success", "capture": <capture object>}
        {"status": "error",   "message": str}

    Note:
        Returns a dict instead of raising so process_a.py can handle
        the error gracefully and log it with context.

    The returned capture object always has a capture_array() method
    so process_a.py can use a unified API regardless of camera type.
    """

    # ── PC MODE or USB WEBCAM ─────────────────────────────────────────────
    if PC_MODE or IS_WEB_CAM:
        source = VIDEO_PATH if (not IS_WEB_CAM and VIDEO_PATH) else CAMERA_INDEX

        # Validate video file exists
        if not IS_WEB_CAM and VIDEO_PATH:
            check_result = utils.file_existence_check_point(VIDEO_PATH, __name__)
            if check_result["status"] == "error":
                return check_result

        capture = cv2.VideoCapture(source)
        if not capture.isOpened():
            return {
                "status"  : "error",
                "message" : f"Could not open source '{source}'. Source: {__name__}"
            }

        # Shim: add capture_array() to match Picamera2 API
        # Allows process_a.py to use a single unified call regardless of mode
        def capture_array_shim():
            ret, frame = capture.read()
            return frame if ret else None

        capture.capture_array = capture_array_shim

        return {"status": "success", "capture": capture}

    # ── RASPBERRY PI NATIVE MODE ──────────────────────────────────────────
    if not HAS_PICAMERA:
        return {
            "status"  : "error",
            "message" : "Picamera2 not available. Not running on Raspberry Pi or not installed."
        }

    try:
        picam2  = Picamera2()
        config  = picam2.create_video_configuration(
            main={"size": (FRAME_DIMENSION["width"], FRAME_DIMENSION["height"]), "format": "BGR888"}
        )
        picam2.configure(config)
        picam2.start()

        return {"status": "success", "capture": picam2}

    except Exception as e:
        return {
            "status"  : "error",
            "message" : f"Failed to configure Picamera2: {e}. Source: {__name__}"
        }