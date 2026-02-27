"""
Path: lib/processes/process_a.py
Description:
    Video streaming process with WebRTC + TURN server support.
    Captures video from camera or file, streams via WebRTC peer.
    TURN credentials loaded from .env
"""

import cv2
import time
import asyncio
import threading

from lib.services.hardware import camera_controller as camera
from lib.services           import webrtc_peer, firebase_rtdb
from lib.services.logger    import get_logger

log = get_logger("process_a")


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


# ─────────────────────────── CHECKPOINTS ─────────────────────────────────────

def _check_points(
    IS_WEB_CAM      : bool,
    CAMERA_INDEX    : int,
    FRAME_DIMENSION : dict
) -> dict:
    """Validate and configure camera settings."""
    config_result = camera.config_camera(IS_WEB_CAM, CAMERA_INDEX, FRAME_DIMENSION)
    if config_result["status"] == "error":
        return config_result
    return {
        "status"  : "success",
        "capture" : config_result["capture"]
    }


# ─────────────────────────── PROCESS A ───────────────────────────────────────

def process_A(**kwargs) -> None:
    """
    Main video streaming process with WebRTC + TURN support.

    Expected kwargs["process_A_args"] keys:
        TASK_NAME       : str
        live_status     : multiprocessing.Event
        status_checker  : multiprocessing.Event
        FRAME_DIMENSION : dict  e.g. {"width": 1280, "height": 720}
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

    log(f"{TASK_NAME} - Running ✅", log_type="info")

    # ── Validate camera config ────────────────────────────────────────────
    check_point_result = _check_points(
        CAMERA_INDEX    = CAMERA_INDEX,
        IS_WEB_CAM      = IS_WEB_CAM,
        FRAME_DIMENSION = FRAME_DIMENSION
    )
    if check_point_result["status"] == "error":
        log(f"{TASK_NAME} - {check_point_result['message']}", log_type="error")
        status_checker.clear()
        return

    # ── Init camera ───────────────────────────────────────────────────────
    capture = check_point_result["capture"]
    capture.start()

    window_name, window_visible_state = camera.setup_windows(window_visible_state=SHOW_WINDOW)

    # ── Init Firebase ─────────────────────────────────────────────────────
    init_result = firebase_rtdb.initialize_firebase()
    if init_result["status"] == "error":
        log(f"{TASK_NAME} - {init_result['message']}", log_type="error")
        status_checker.clear()
        camera.clean_up_camera(capture)
        return

    user_uid   = USER_CREDENTIAL["userUid"]
    device_uid = USER_CREDENTIAL["deviceUid"]

    log(f"{TASK_NAME} - WebRTC init: user={user_uid} device={device_uid}", log_type="info")

    # ── Shared frame buffer ───────────────────────────────────────────────
    frame_buffer = SharedFrameBuffer()

    # ── Async event loop ──────────────────────────────────────────────────
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    webrtc_peer_instance = None

    # ── Connection state callback ─────────────────────────────────────────
    def on_connection_state_change(state: str) -> None:
        if state == "connected":
            log(f"{TASK_NAME} - WebRTC connected, streaming active", log_type="info")
            live_status.set()
        elif state in ["disconnected", "failed", "closed"]:
            log(f"{TASK_NAME} - WebRTC {state}", log_type="warn")
            live_status.clear()

    # ── Init WebRTC peer ──────────────────────────────────────────────────
    try:
        webrtc_peer_instance = loop.run_until_complete(
            webrtc_peer.run_webrtc_peer(
                user_uid                  = user_uid,
                device_uid                = device_uid,
                capture                   = capture,
                pc_mode                   = PC_MODE,
                frame_dimension           = FRAME_DIMENSION,
                on_connection_state_change= on_connection_state_change,
                frame_buffer              = frame_buffer,
                turn_server_url           = TURN_SERVER_URL,
                turn_username             = TURN_USERNAME,
                turn_password             = TURN_PASSWORD
            )
        )
        log(f"{TASK_NAME} - WebRTC peer initialized", log_type="info")
    except Exception as e:
        log(f"{TASK_NAME} - Failed to init WebRTC peer: {e}", log_type="error")
        status_checker.clear()
        camera.clean_up_camera(capture, PC_MODE)
        return

    # ── Main streaming loop ───────────────────────────────────────────────
    async def main_streaming_loop():
        nonlocal window_visible_state

        frame_count    = 0
        start_time     = time.time()
        last_fps_log   = start_time

        log(f"{TASK_NAME} - Streaming loop started", log_type="info")

        while status_checker.is_set():

            # Capture frame
            if PC_MODE:
                ret, raw_frame = capture.read()
                if not ret:
                    if not IS_WEB_CAM:
                        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    log(f"{TASK_NAME} - Camera read failed", log_type="error")
                    status_checker.clear()
                    break
            else:
                raw_frame = capture.capture_array()

            # Resize
            raw_frame = cv2.resize(
                raw_frame,
                (FRAME_DIMENSION["width"], FRAME_DIMENSION["height"])
            )

            # Push to buffer
            frame_buffer.update(raw_frame)
            frame_count += 1

            # Optional display window
            if SHOW_WINDOW and window_visible_state:
                cv2.imshow(window_name, raw_frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('c'):
                    cv2.destroyWindow(window_name)
                    window_visible_state = False
                elif key == ord('w') and not window_visible_state:
                    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                    window_visible_state = True

            # FPS log every 60s
            now = time.time()
            if now - last_fps_log >= 60.0:
                fps = frame_count / (now - start_time)
                log(f"{TASK_NAME} - FPS: {fps:.1f} | Frames: {frame_count}", log_type="info")
                last_fps_log = now

            await asyncio.sleep(0.01)

    # ── Run ───────────────────────────────────────────────────────────────
    try:
        loop.run_until_complete(main_streaming_loop())
    except KeyboardInterrupt:
        log(f"{TASK_NAME} - KeyboardInterrupt", log_type="warn")
        status_checker.clear()
    except Exception as e:
        log(f"{TASK_NAME} - Unexpected error: {e}", log_type="error")
        status_checker.clear()
    finally:
        if webrtc_peer_instance:
            try:
                loop.run_until_complete(webrtc_peer_instance.stop())
            except Exception as e:
                log(f"{TASK_NAME} - Error stopping WebRTC peer: {e}", log_type="error")

        clean_result = camera.clean_up_camera(capture, PC_MODE)
        if clean_result["status"] == "error":
            log(f"{TASK_NAME} - {clean_result['message']}", log_type="error")

        try:
            loop.close()
        except Exception:
            pass

        log(f"{TASK_NAME} - Process stopped", log_type="info")