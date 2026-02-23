"""
Path: raspi_code/lib/processes/process_a.py
Description:
- Video streaming process with WebRTC support
- Captures video from camera or file, resizes frames, and streams to WebRTC peer
- Displays video in a window with toggle controls
- Logs performance metrics and connection status
"""
import cv2
from lib.services.hardware import camera_controller as camera
from lib.services import webrtc_peer
import logging
import time
import asyncio
from firebase_admin import db, credentials
from lib.services import firebase_rtdb
import threading
import numpy as np

from lib import logger_config

logger = logger_config.setup_logger(name=__name__, level=logging.INFO)

# ========================================
# TURN SERVER CONFIGURATION
# ========================================
TURN_SERVER_URL = "turn:YOUR_PUBLIC_IP:3478"
TURN_USERNAME = "webrtc"
TURN_PASSWORD = "YOUR_STRONG_PASSWORD"
# ========================================

def _check_points(VIDEO_FILE: str, PC_MODE: bool, IS_WEB_CAM: bool, CAMERA_INDEX: int, FRAME_DIMENSION: dict) -> dict:
    """Validate and configure camera settings."""
    config_result = camera.config_camera(PC_MODE, IS_WEB_CAM, VIDEO_FILE, CAMERA_INDEX, FRAME_DIMENSION)
    if config_result["status"] == "error":
        return config_result

    return {
        "status"    : "success",
        "capture"   : config_result["capture"]
    }


def setup_RTDB(user_uid: str, device_uid: str) -> dict:
    """Setup Firebase RTDB references for WebRTC signaling."""
    return {}


class SharedFrameBuffer:
    """Thread-safe buffer to share frames between camera capture and WebRTC streaming."""
    def __init__(self):
        self._frame = None
        self._lock = threading.Lock()
        self._new_frame_available = threading.Event()
        self._update_count = 0
        self._read_count = 0
    
    def update(self, frame):
        """Update the buffer with a new frame."""
        with self._lock:
            self._frame = frame.copy() if frame is not None else None
            self._new_frame_available.set()
            self._update_count += 1
    
    def get(self):
        """Get the latest frame from the buffer."""
        with self._lock:
            self._read_count += 1
            return self._frame.copy() if self._frame is not None else None
    
    def get_stats(self):
        """Get buffer statistics."""
        with self._lock:
            return {
                'updates': self._update_count,
                'reads': self._read_count,
                'has_frame': self._frame is not None
            }
    
    def wait_for_frame(self, timeout=1.0):
        """Wait for a new frame to be available."""
        return self._new_frame_available.wait(timeout)
    
    def clear_event(self):
        """Clear the new frame event."""
        self._new_frame_available.clear()


def process_A(**kwargs) -> None:
    """Main video streaming process with WebRTC support."""
    # Configuration
    process_A_args      = kwargs["process_A_args"]
    TASK_NAME           = process_A_args["TASK_NAME"]
    live_status         = process_A_args["live_status"]
    status_checker      = process_A_args["status_checker"]
    FRAME_DIMENSION     = process_A_args["FRAME_DIMENSION"]
    IS_WEB_CAM          = process_A_args["IS_WEB_CAM"]
    PC_MODE             = process_A_args["PC_MODE"]
    CAMERA_INDEX        = process_A_args["CAMERA_INDEX"]
    VIDEO_FILE          = process_A_args["VIDEO_FILE"]
    SAVE_LOGS           = process_A_args["SAVE_LOGS"]
    SHOW_WINDOW         = process_A_args["SHOW_WINDOW"]
    USER_CREDENTIAL     = process_A_args["USER_CREDENTIAL"]
    
    print(f"{TASK_NAME} - Running✅")
    if SAVE_LOGS:
        logger.info(f"{TASK_NAME} - Running")

    # Validate configuration
    check_point_result = _check_points(
        VIDEO_FILE      = VIDEO_FILE, 
        PC_MODE         = PC_MODE,
        CAMERA_INDEX    = CAMERA_INDEX, 
        IS_WEB_CAM      = IS_WEB_CAM,
        FRAME_DIMENSION = FRAME_DIMENSION
    )
    if check_point_result["status"] == "error":
        if SAVE_LOGS:
            logger.error(f"{TASK_NAME} - {check_point_result['message']}")
        status_checker.clear()
        exit()
        
    # Initialize camera
    capture = None
    if not PC_MODE:
        capture = check_point_result["capture"]
        capture.start()
    else:
        capture = check_point_result["capture"]
        
    # Setup display window
    window_name, window_visible_state = camera.setup_windows(window_visible_state=SHOW_WINDOW)

    # Initialize Firebase
    init_result = firebase_rtdb.initialize_firebase()
    if init_result["status"] == "error":
        status_checker.clear()
        if SAVE_LOGS:
            logger.error(f"{TASK_NAME} - {init_result['message']}. Source: {__name__}")
        if not PC_MODE:
            try:
                import RPi.GPIO as GPIO
                GPIO.cleanup()
            except:
                pass
        exit()
    
    user_uid    = USER_CREDENTIAL["userUid"]
    device_uid  = USER_CREDENTIAL["deviceUid"]
    
    logger.info(f"Initializing WebRTC for user={user_uid}, device={device_uid}")
    
    # Create shared frame buffer
    frame_buffer = SharedFrameBuffer()
    
    # Create event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # WebRTC peer instance
    webrtc_peer_instance = None
    
    # Connection state callback
    def on_connection_state_change(state):
        """Callback for WebRTC connection state changes."""
        logger.info(f"WebRTC connection state: {state}")
        
        if state == "connected":
            logger.info("WebRTC connected - streaming active")
            live_status.set()
        elif state in ["disconnected", "failed", "closed"]:
            logger.info(f"WebRTC {state}")
            live_status.clear()
    
    # Initialize WebRTC peer
    try:
        webrtc_peer_instance = loop.run_until_complete(
            webrtc_peer.run_webrtc_peer(
                user_uid=user_uid,
                device_uid=device_uid,
                capture=capture,
                pc_mode=PC_MODE,
                frame_dimension=FRAME_DIMENSION,
                on_connection_state_change=on_connection_state_change,
                frame_buffer=frame_buffer,
                turn_server_url=TURN_SERVER_URL,
                turn_username=TURN_USERNAME,
                turn_password=TURN_PASSWORD
            )
        )
        
        logger.info("WebRTC peer initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize WebRTC peer: {e}")
        status_checker.clear()
        clean_result = camera.clean_up_camera(capture, PC_MODE)
        exit()
    
    # MAIN STREAMING LOOP
    async def main_streaming_loop():
        """Main async loop for frame capture and display."""
        nonlocal window_visible_state
        
        frame_count = 0
        start_time = time.time()
        last_fps_log = start_time
        
        logger.info("Main streaming loop started")
        
        while status_checker.is_set():
            # Single capture point
            if PC_MODE:
                ret, raw_frame = capture.read()
                if not ret:
                    if not IS_WEB_CAM:
                        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    logger.error("Failed to read from camera")
                    status_checker.clear()
                    break
            else:
                raw_frame = capture.capture_array()
            
            # Resize
            raw_frame = cv2.resize(raw_frame, (FRAME_DIMENSION["width"], FRAME_DIMENSION["height"]))
            
            # Update shared buffer
            frame_buffer.update(raw_frame)
            frame_count += 1
            
            # Display window
            if SHOW_WINDOW and window_visible_state:
                cv2.imshow(window_name, raw_frame)
                
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('c'):
                    cv2.destroyWindow(window_name)
                    window_visible_state = False
                    logger.info("Window hidden")
                
                elif key == ord('w'):
                    if not window_visible_state:
                        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                        window_visible_state = True
                        logger.info("Window shown")
            
            # FPS logging (every 30 seconds)
            current_time = time.time()
            if current_time - last_fps_log >= 30.0:
                elapsed = current_time - start_time
                fps = frame_count / elapsed
                logger.info(f"Capture stats - FPS: {fps:.1f}, Total frames: {frame_count}")
                last_fps_log = current_time
            
            # Hand control to WebRTC
            await asyncio.sleep(0.01)
    
    try:
        # Run the main loop
        loop.run_until_complete(main_streaming_loop())
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt detected")
        status_checker.clear()
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        status_checker.clear()
    
    finally:
        # Cleanup WebRTC peer
        if webrtc_peer_instance:
            try:
                loop.run_until_complete(webrtc_peer_instance.stop())
                logger.info("WebRTC peer stopped")
            except Exception as e:
                logger.error(f"Error stopping WebRTC peer: {e}")
        
        # Cleanup camera
        clean_result = camera.clean_up_camera(capture, PC_MODE)
        if clean_result["status"] == "error":
            logger.error(f"{clean_result['message']}")
        
        # Close event loop
        try:
            loop.close()
        except:
            pass
        
        logger.info(f"{TASK_NAME} - Process stopped")