"""
Path: lib/processes/process_a.py
Description:
    Video streaming process — WebRTC + TURN server.
    Captures from webcam or Picamera2, streams via WebRTC peer.
    No local display. No annotation. Pure streaming only.
"""

import cv2
import time
import asyncio
import threading

from lib.services.hardware import camera_controller as camera
from lib.services.hardware.camera_controller import CameraError
from lib.services.webrtc_peer import run_webrtc_peer, WebRTCStartError, WebRTCStopError
from lib.services import firebase_rtdb
from lib.services.firebase_rtdb import FirebaseInitError
from lib.services.logger import get_logger

log = get_logger("process_a.py")


# ─────────────────────────── SHARED FRAME BUFFER ─────────────────────────────

class SharedFrameBuffer:
    """Thread-safe buffer to share frames between camera capture and WebRTC."""

    def __init__(self):
        self._frame     = None
        self._lock      = threading.Lock()
        self._new_frame = threading.Event()

    def update(self, frame) -> None:
        with self._lock:
            self._frame = frame.copy() if frame is not None else None
            self._new_frame.set()

    def get(self):
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def wait_for_frame(self, timeout: float = 1.0) -> bool:
        return self._new_frame.wait(timeout)

    def clear_event(self) -> None:
        self._new_frame.clear()


# ─────────────────────────── PROCESS A ───────────────────────────────────────

def process_A(**kwargs) -> None:
    """
    Main video streaming process — WebRTC + TURN support.

    Expected kwargs["process_A_args"] keys:
        TASK_NAME       : str
        live_status     : multiprocessing.Event
        status_checker  : multiprocessing.Event
        FRAME_DIMENSION : dict  {"width": int, "height": int}
        IS_WEB_CAM      : bool
        CAMERA_INDEX    : int
        USER_CREDENTIAL : dict  {userUid, deviceUid, ...}
        TURN_SERVER_URL : str
        TURN_USERNAME   : str
        TURN_PASSWORD   : str
    """
    args            = kwargs["process_A_args"]
    TASK_NAME       = args["TASK_NAME"]
    live_status     = args["live_status"]
    status_checker  = args["status_checker"]
    FRAME_DIMENSION = args["FRAME_DIMENSION"]
    IS_WEB_CAM      = args["IS_WEB_CAM"]
    CAMERA_INDEX    = args["CAMERA_INDEX"]
    USER_CREDENTIAL = args["USER_CREDENTIAL"]
    TURN_SERVER_URL = args["TURN_SERVER_URL"]
    TURN_USERNAME   = args["TURN_USERNAME"]
    TURN_PASSWORD   = args["TURN_PASSWORD"]

    log(details=f"{TASK_NAME} - Running", log_type="info")

    # ── Init camera ───────────────────────────────────────────────────────
    try:
        capture = camera.config_camera(
            IS_WEB_CAM      = IS_WEB_CAM,
            CAMERA_INDEX    = CAMERA_INDEX,
            FRAME_DIMENSION = FRAME_DIMENSION
        )
    except CameraError as e:
        log(details=f"{TASK_NAME} - Camera init failed: {e}", log_type="error")
        status_checker.clear()
        return

    # ── Init Firebase ─────────────────────────────────────────────────────
    try:
        firebase_rtdb.initialize_firebase()
    except FirebaseInitError as e:
        log(details=f"{TASK_NAME} - Firebase init failed: {e}", log_type="error")
        status_checker.clear()
        _safe_cleanup(capture, IS_WEB_CAM, TASK_NAME)
        return

    user_uid   = USER_CREDENTIAL["userUid"]
    device_uid = USER_CREDENTIAL["deviceUid"]

    # ── Shared frame buffer ───────────────────────────────────────────────
    frame_buffer = SharedFrameBuffer()

    # ── Async event loop ──────────────────────────────────────────────────
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    webrtc_peer_instance = None

    # ── Connection state callback ─────────────────────────────────────────
    def on_connection_state_change(state: str) -> None:
        if state == "connected":
            live_status.set()
        elif state in ["disconnected", "failed", "closed"]:
            log(details=f"{TASK_NAME} - WebRTC state: {state}", log_type="warning")
            live_status.clear()

    # ── Init WebRTC peer ──────────────────────────────────────────────────
    try:
        webrtc_peer_instance = loop.run_until_complete(
            run_webrtc_peer(
                user_uid                   = user_uid,
                device_uid                 = device_uid,
                capture                    = capture,
                frame_dimension            = FRAME_DIMENSION,
                on_connection_state_change = on_connection_state_change,
                frame_buffer               = frame_buffer,
                turn_server_url            = TURN_SERVER_URL,
                turn_username              = TURN_USERNAME,
                turn_password              = TURN_PASSWORD
            )
        )
    except WebRTCStartError as e:
        log(details=f"{TASK_NAME} - WebRTC peer init failed: {e}", log_type="error")
        status_checker.clear()
        _safe_cleanup(capture, IS_WEB_CAM, TASK_NAME)
        return

    # ── Main streaming loop ───────────────────────────────────────────────
    async def _streaming_loop():
        frame_count  = 0
        start_time   = time.time()
        last_fps_log = start_time

        while status_checker.is_set():
            raw_frame = capture.capture_array()

            if raw_frame is None:
                log(details=f"{TASK_NAME} - Camera returned empty frame", log_type="warning")
                status_checker.clear()
                break

            raw_frame = cv2.resize(
                raw_frame,
                (FRAME_DIMENSION["width"], FRAME_DIMENSION["height"])
            )

            frame_buffer.update(raw_frame)
            frame_count += 1

            # FPS log every 60 seconds
            now = time.time()
            if now - last_fps_log >= 60.0:
                fps = frame_count / (now - start_time)
                log(details=f"{TASK_NAME} - FPS: {fps:.1f} | Frames: {frame_count}", log_type="info")
                last_fps_log = now

            await asyncio.sleep(0.01)

    # ── Run ───────────────────────────────────────────────────────────────
    try:
        loop.run_until_complete(_streaming_loop())
    except KeyboardInterrupt:
        log(details=f"{TASK_NAME} - KeyboardInterrupt received", log_type="warning")
        status_checker.clear()
    except Exception as e:
        log(details=f"{TASK_NAME} - Unexpected error in streaming loop: {e}", log_type="error")
        status_checker.clear()
    finally:
        if webrtc_peer_instance:
            try:
                loop.run_until_complete(webrtc_peer_instance.stop())
            except WebRTCStopError as e:
                log(details=f"{TASK_NAME} - WebRTC stop error: {e}", log_type="warning")

        _safe_cleanup(capture, IS_WEB_CAM, TASK_NAME)

        try:
            loop.close()
        except Exception:
            pass

        log(details=f"{TASK_NAME} - Process stopped", log_type="info")


# ─────────────────────────── HELPERS ─────────────────────────────────────────

def _safe_cleanup(capture, IS_WEB_CAM: bool, task_name: str) -> None:
    """Attempt camera cleanup and log on failure."""
    try:
        camera.clean_up_camera(capture, IS_WEB_CAM)
    except Exception as e:
        log(details=f"{task_name} - Camera cleanup failed: {e}", log_type="warning")