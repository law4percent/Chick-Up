"""
Docstring for raspi_code.lib.processes.process_a
Path: raspi_code/lib/processes/process_a.py
Description: This module contains the implementation of process_A which captures video frames from a camera or video file,
             processes them with WebRTC streaming functionality for low-latency video transmission.

Updated: Now uses WebRTC for real-time streaming instead of queue-based base64 encoding.
"""
import cv2
from lib.services.hardware import camera_controller as camera
from lib.services import webrtc_peer
import logging
import time
import asyncio
from firebase_admin import db, credentials
from lib.services import firebase_rtdb

from lib import logger_config

logger = logger_config.setup_logger(name=__name__, level=logging.DEBUG)


def _check_points(VIDEO_PATH: str, PC_MODE: bool, IS_WEB_CAM: bool, CAMERA_INDEX: int, FRAME_DIMENSION: dict) -> dict:
    """Validate and configure camera settings."""
    config_result = camera.config_camera(PC_MODE, IS_WEB_CAM, VIDEO_PATH, CAMERA_INDEX, FRAME_DIMENSION)
    if config_result["status"] == "error":
        return config_result

    return {
        "status"    : "success",
        "capture"   : config_result["capture"]
    }


def setup_RTDB(user_uid: str, device_uid: str) -> dict:
    """
    Setup Firebase RTDB references for WebRTC signaling.
    Returns references needed for the application.
    """
    # WebRTC signaling references are handled by webrtc_peer module
    # Add any additional references needed here
    return {}


def process_A(**kwargs) -> None:
    """
    Main process for video capture and WebRTC streaming.
    
    This process:
    1. Initializes camera capture
    2. Sets up WebRTC peer for low-latency streaming
    3. Monitors streaming status from Firebase
    4. Manages window display (optional)
    """
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
        logger.info(f"{TASK_NAME} - Running✅")

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
        
    # Setup display window (optional)
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
    
    # Create event loop for asyncio (WebRTC requires async)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # WebRTC peer instance
    webrtc_peer_instance = None
    
    # Connection state callback
    def on_connection_state_change(state):
        """Callback for WebRTC connection state changes."""
        if SAVE_LOGS:
            logger.info(f"{TASK_NAME} - WebRTC connection state: {state}")
        
        if state == "connected":
            live_status.set()  # Mark as streaming
        elif state in ["disconnected", "failed", "closed"]:
            live_status.clear()  # Mark as not streaming
    
    # Initialize WebRTC peer
    try:
        webrtc_peer_instance = webrtc_peer.run_webrtc_peer(
            user_uid                    = user_uid,
            device_uid                  = device_uid,
            capture                     = capture,
            pc_mode                     = PC_MODE,
            frame_dimension             = FRAME_DIMENSION,
            on_connection_state_change  = on_connection_state_change
        )
        
        if SAVE_LOGS:
            logger.info(f"{TASK_NAME} - WebRTC peer initialized and listening for connections")
    except Exception as e:
        if SAVE_LOGS:
            logger.error(f"{TASK_NAME} - Failed to initialize WebRTC peer: {e}")
        status_checker.clear()
        clean_result = camera.clean_up_camera(capture, PC_MODE)
        exit()
    
    # Firebase reference for monitoring stream button
    stream_button_ref = db.reference(f"liveStream/{user_uid}/{device_uid}/liveStreamButton")
    
    try:
        while True:
            if not status_checker.is_set():
                if SAVE_LOGS:
                    logger.error(f"{TASK_NAME} - Process checker cleared, shutting down")
                break
            
            # Optional: Display window for debugging
            if SHOW_WINDOW and window_visible_state:
                if PC_MODE:
                    ret, raw_frame = capture.read()
                    if not ret:
                        if not IS_WEB_CAM:
                            capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            continue
                        if SAVE_LOGS:
                            logger.error(f"{TASK_NAME} - Error: Check the hardware camera.")
                        status_checker.clear()
                        break
                else:
                    raw_frame = capture.capture_array()
                
                raw_frame = cv2.resize(raw_frame, (FRAME_DIMENSION["width"], FRAME_DIMENSION["height"]))
                cv2.imshow(window_name, raw_frame)
                
                key = cv2.waitKey(1) & 0xFF
                
                # Press C → close/hide the window
                if key == ord('c'):
                    cv2.destroyWindow(window_name)
                    window_visible_state = False
                
                # Press W → show the window again
                elif key == ord('w'):
                    if not window_visible_state:
                        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                        window_visible_state = True
            else:
                # Small delay to prevent busy-waiting
                time.sleep(0.1)
            
            # Run async event loop to handle WebRTC events
            loop.run_until_complete(asyncio.sleep(0))
                        
    except KeyboardInterrupt:
        if SAVE_LOGS:
            logger.warning(f"{TASK_NAME} - Keyboard interrupt detected")
        status_checker.clear()
    
    except Exception as e:
        if SAVE_LOGS:
            logger.error(f"{TASK_NAME} - Unexpected error: {e}", exc_info=True)
        status_checker.clear()
    
    finally:
        # Cleanup WebRTC peer
        if webrtc_peer_instance:
            try:
                loop.run_until_complete(webrtc_peer_instance.stop())
                if SAVE_LOGS:
                    logger.info(f"{TASK_NAME} - WebRTC peer stopped")
            except Exception as e:
                if SAVE_LOGS:
                    logger.error(f"{TASK_NAME} - Error stopping WebRTC peer: {e}")
        
        # Cleanup camera
        clean_result = camera.clean_up_camera(capture, PC_MODE)
        if clean_result["status"] == "error":
            if SAVE_LOGS:
                logger.error(f"{TASK_NAME} - {clean_result['message']}")
        
        # Close event loop
        try:
            loop.close()
        except:
            pass
        
        if SAVE_LOGS:
            logger.info(f"{TASK_NAME} - Process stopped")