"""
Camera Controller Module
Loc: lib/services/hardware/camera_controller.py

Supports:
- Webcam mode  (cv2.VideoCapture via CAMERA_INDEX)
- Raspberry Pi native mode (Picamera2)

This module raises exceptions only — no logging, no dict returns.
All logging is handled by the calling process.
"""

import cv2
from typing import Any

# Optional import — prevents crash on dev environments without Picamera2
try:
    from picamera2 import Picamera2
    HAS_PICAMERA = True
except (ImportError, RuntimeError):
    HAS_PICAMERA = False


# ─────────────────────────── EXCEPTIONS ──────────────────────────────────────

class CameraError(Exception):
    """Base exception for all camera errors."""
    pass

class CameraConfigError(CameraError):
    """Raised when camera configuration or open fails."""
    pass

class CameraCleanupError(CameraError):
    """Raised when camera cleanup fails."""
    pass

class CameraNotAvailableError(CameraError):
    """Raised when required camera hardware is not available."""
    pass


# ─────────────────────────── CONFIG ──────────────────────────────────────────

def config_camera(
    IS_WEB_CAM      : bool,
    CAMERA_INDEX    : int,
    FRAME_DIMENSION : dict
) -> Any:
    """
    Configure and return the appropriate camera capture object.

    Two supported modes:
        IS_WEB_CAM=True  → cv2.VideoCapture(CAMERA_INDEX)
        IS_WEB_CAM=False → Picamera2 (Raspberry Pi native)

    The returned capture object always exposes a capture_array() method
    so the calling process can use a unified API regardless of camera type.

    Args:
        IS_WEB_CAM:      True = USB/webcam, False = Picamera2
        CAMERA_INDEX:    Camera index (used only when IS_WEB_CAM=True)
        FRAME_DIMENSION: {"width": int, "height": int}

    Returns:
        capture object (cv2.VideoCapture or Picamera2)

    Raises:
        CameraConfigError:        Camera failed to open or configure.
        CameraNotAvailableError:  Picamera2 not installed / not on Pi.
    """

    # ── WEBCAM MODE ───────────────────────────────────────────────────────
    if IS_WEB_CAM:
        capture = cv2.VideoCapture(CAMERA_INDEX)
        if not capture.isOpened():
            raise CameraConfigError(
                f"Could not open webcam at index {CAMERA_INDEX}. Source: {__name__}"
            )

        # Shim: expose capture_array() to match Picamera2 API
        def _capture_array_shim():
            ret, frame = capture.read()
            if not ret:
                return None
            return frame

        capture.capture_array = _capture_array_shim
        return capture

    # ── RASPBERRY PI NATIVE MODE ──────────────────────────────────────────
    if not HAS_PICAMERA:
        raise CameraNotAvailableError(
            "Picamera2 is not available. Not running on Raspberry Pi or not installed. "
            f"Source: {__name__}"
        )

    try:
        picam2 = Picamera2()
        config = picam2.create_video_configuration(
            main={
                "size"  : (FRAME_DIMENSION["width"], FRAME_DIMENSION["height"]),
                "format": "BGR888"
            }
        )
        picam2.configure(config)
        picam2.start()
        return picam2

    except Exception as e:
        raise CameraConfigError(
            f"Failed to configure Picamera2: {e}. Source: {__name__}"
        ) from e


# ─────────────────────────── CLEANUP ─────────────────────────────────────────

def clean_up_camera(capture: Any, IS_WEB_CAM: bool) -> None:
    """
    Properly release or stop the camera depending on mode.

    Args:
        capture:    cv2.VideoCapture or Picamera2 instance
        IS_WEB_CAM: True = cv2.VideoCapture, False = Picamera2

    Raises:
        CameraCleanupError: If releasing/stopping the camera fails.

    Note:
        cv2.destroyAllWindows() is always called even on error.
    """
    try:
        if IS_WEB_CAM:
            if capture and capture.isOpened():
                capture.release()
        else:
            if capture:
                capture.stop()
                capture.close()
    except Exception as e:
        raise CameraCleanupError(
            f"Error cleaning up camera: {e}. Source: {__name__}"
        ) from e
    finally:
        cv2.destroyAllWindows()