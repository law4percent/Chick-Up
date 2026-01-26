"""
Docstring for raspi_code.lib.services.webrtc_peer
Path: raspi_code/lib/services/webrtc_peer.py
Description: WebRTC peer implementation for Raspberry Pi to stream video to mobile app.
             Handles peer connection, video track creation, and Firebase-based signaling.
"""

import asyncio
import cv2
import logging
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCConfiguration, RTCIceServer
from aiortc.contrib.media import MediaPlayer
from av import VideoFrame
import numpy as np
from firebase_admin import db
import json
import time
from typing import Optional, Callable
from fractions import Fraction

logger = logging.getLogger(__name__)


class CameraVideoTrack(VideoStreamTrack):
    """
    Custom video track that reads frames from OpenCV capture and converts to WebRTC format.
    """
    
    def __init__(self, capture, pc_mode: bool, frame_dimension: dict):
        super().__init__()
        self.capture = capture
        self.pc_mode = pc_mode
        self.width = frame_dimension["width"]
        self.height = frame_dimension["height"]
        self._timestamp = 0
        self._start_time = time.time()
        
    async def recv(self):
        """
        Receive next video frame in WebRTC format.
        Called by aiortc to get frames for streaming.
        """
        pts, time_base = await self.next_timestamp()
        
        # Capture frame from camera
        if self.pc_mode:
            ret, frame = self.capture.read()
            if not ret:
                logger.error("Failed to read frame from camera")
                # Return black frame on error
                frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        else:
            # Picamera2 mode
            frame = self.capture.capture_array()
        
        # Resize to target dimensions
        frame = cv2.resize(frame, (self.width, self.height))
        
        # Convert BGR to RGB (OpenCV uses BGR, WebRTC expects RGB)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Create VideoFrame from numpy array
        video_frame = VideoFrame.from_ndarray(frame, format="rgb24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        
        return video_frame


class WebRTCPeer:
    """
    WebRTC peer for Raspberry Pi that handles:
    - Video streaming via WebRTC
    - Firebase-based signaling (SDP exchange, ICE candidates)
    - Connection lifecycle management
    """
    
    def __init__(self, user_uid: str, device_uid: str, capture, pc_mode: bool, 
                 frame_dimension: dict, on_connection_state_change: Optional[Callable] = None):
        """
        Initialize WebRTC peer.
        
        Args:
            user_uid: Firebase user UID
            device_uid: Device UID
            capture: OpenCV capture object or Picamera2 object
            pc_mode: True for PC/USB camera, False for Pi Camera
            frame_dimension: Dict with 'width' and 'height' keys
            on_connection_state_change: Optional callback for connection state changes
        """
        self.user_uid = user_uid
        self.device_uid = device_uid
        self.capture = capture
        self.pc_mode = pc_mode
        self.frame_dimension = frame_dimension
        self.on_connection_state_change = on_connection_state_change
        
        # WebRTC components
        self.pc: Optional[RTCPeerConnection] = None
        self.video_track: Optional[CameraVideoTrack] = None
        
        # Firebase references
        self.stream_ref = db.reference(f"liveStream/{user_uid}/{device_uid}")
        self.offer_ref = self.stream_ref.child("offer")
        self.answer_ref = self.stream_ref.child("answer")
        self.ice_candidates_raspi_ref = self.stream_ref.child("iceCandidates/raspi")
        self.ice_candidates_mobile_ref = self.stream_ref.child("iceCandidates/mobile")
        self.connection_state_ref = self.stream_ref.child("connectionState")
        
        # State tracking
        self.is_running = False
        self.candidates_sent = 0
        
        # STUN server configuration (Google's free STUN servers)
        self.ice_servers = [
            RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
            RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
        ]
        
        logger.info(f"WebRTC Peer initialized for user={user_uid}, device={device_uid}")
    
    def _create_peer_connection(self):
        """Create and configure RTCPeerConnection."""
        config = RTCConfiguration(iceServers=self.ice_servers)
        pc = RTCPeerConnection(configuration=config)
        
        # Handle ICE candidate events
        @pc.on("icecandidate")
        async def on_ice_candidate(candidate):
            if candidate and self.candidates_sent < 10:  # Limit ICE candidates
                try:
                    candidate_dict = {
                        "candidate": candidate.candidate,
                        "sdpMid": candidate.sdpMid,
                        "sdpMLineIndex": candidate.sdpMLineIndex,
                        "timestamp": int(time.time() * 1000)
                    }
                    self.ice_candidates_raspi_ref.push(candidate_dict)
                    self.candidates_sent += 1
                    logger.debug(f"Sent ICE candidate {self.candidates_sent}")
                except Exception as e:
                    logger.error(f"Error sending ICE candidate: {e}")
        
        # Handle connection state changes
        @pc.on("connectionstatechange")
        async def on_connection_state_change():
            state = pc.connectionState
            logger.info(f"Connection state changed to: {state}")
            
            try:
                self.connection_state_ref.set(state)
                
                if self.on_connection_state_change:
                    self.on_connection_state_change(state)
                
                # Stop listening for mobile ICE candidates once connected
                if state == "connected":
                    logger.info("WebRTC connection established successfully!")
                    self.candidates_sent = 0  # Reset for next connection
                elif state in ["failed", "closed"]:
                    logger.warning(f"Connection {state}, cleaning up...")
                    await self.cleanup()
            except Exception as e:
                logger.error(f"Error handling connection state change: {e}")
        
        # Handle ICE connection state
        @pc.on("iceconnectionstatechange")
        async def on_ice_connection_state_change():
            logger.info(f"ICE connection state: {pc.iceConnectionState}")
        
        return pc
    
    async def start(self):
        """
        Start WebRTC peer and listen for offers from mobile app.
        This runs in the background and handles the signaling process.
        """
        if self.is_running:
            logger.warning("WebRTC peer already running")
            return
        
        self.is_running = True
        logger.info("Starting WebRTC peer, listening for offers...")
        
        # Set initial connection state
        self.connection_state_ref.set("disconnected")
        
        # Listen for offers from mobile app
        def offer_listener(event):
            if event.data and self.is_running:
                asyncio.create_task(self._handle_offer(event.data))
        
        self.offer_ref.listen(offer_listener)
        logger.info("Listening for WebRTC offers from mobile app")
    
    async def _handle_offer(self, offer_data):
        """
        Handle incoming offer from mobile app.
        Creates answer and sets up video track.
        """
        try:
            logger.info("Received offer from mobile app")
            
            # Clean up existing connection if any
            if self.pc:
                await self.pc.close()
            
            # Create new peer connection
            self.pc = self._create_peer_connection()
            
            # Create and add video track
            self.video_track = CameraVideoTrack(
                self.capture, 
                self.pc_mode, 
                self.frame_dimension
            )
            self.pc.addTrack(self.video_track)
            logger.info("Video track added to peer connection")
            
            # Set remote description (offer)
            offer = RTCSessionDescription(
                sdp=offer_data["sdp"],
                type=offer_data["type"]
            )
            await self.pc.setRemoteDescription(offer)
            logger.info("Remote description (offer) set")
            
            # Create answer
            answer = await self.pc.createAnswer()
            await self.pc.setLocalDescription(answer)
            logger.info("Answer created and local description set")
            
            # Send answer to mobile app via Firebase
            answer_dict = {
                "sdp": self.pc.localDescription.sdp,
                "type": self.pc.localDescription.type,
                "timestamp": int(time.time() * 1000)
            }
            self.answer_ref.set(answer_dict)
            logger.info("Answer sent to mobile app via Firebase")
            
            # Listen for ICE candidates from mobile app
            def mobile_ice_listener(event):
                if event.data and self.pc and self.pc.connectionState not in ["connected", "closed"]:
                    for candidate_data in event.data.values():
                        if isinstance(candidate_data, dict):
                            asyncio.create_task(self._add_ice_candidate(candidate_data))
            
            self.ice_candidates_mobile_ref.listen(mobile_ice_listener)
            logger.info("Listening for ICE candidates from mobile app")
            
            # Update connection state
            self.connection_state_ref.set("connecting")
            
        except Exception as e:
            logger.error(f"Error handling offer: {e}", exc_info=True)
            self.connection_state_ref.set("failed")
    
    async def _add_ice_candidate(self, candidate_data):
        """Add ICE candidate from mobile app."""
        try:
            if self.pc and "candidate" in candidate_data:
                from aiortc import RTCIceCandidate
                
                candidate = RTCIceCandidate(
                    candidate=candidate_data["candidate"],
                    sdpMid=candidate_data.get("sdpMid"),
                    sdpMLineIndex=candidate_data.get("sdpMLineIndex")
                )
                await self.pc.addIceCandidate(candidate)
                logger.debug("Added ICE candidate from mobile app")
        except Exception as e:
            logger.error(f"Error adding ICE candidate: {e}")
    
    async def cleanup(self):
        """Clean up WebRTC resources and Firebase listeners."""
        logger.info("Cleaning up WebRTC peer...")
        self.is_running = False
        
        try:
            # Close peer connection
            if self.pc:
                await self.pc.close()
                self.pc = None
            
            # Stop video track
            if self.video_track:
                self.video_track.stop()
                self.video_track = None
            
            # Clear Firebase data
            self.offer_ref.set(None)
            self.answer_ref.set(None)
            self.ice_candidates_raspi_ref.set(None)
            self.ice_candidates_mobile_ref.set(None)
            self.connection_state_ref.set("disconnected")
            
            logger.info("WebRTC peer cleanup complete")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def stop(self):
        """Stop the WebRTC peer gracefully."""
        await self.cleanup()


# Helper function to run WebRTC peer in async context
def run_webrtc_peer(user_uid: str, device_uid: str, capture, pc_mode: bool, 
                    frame_dimension: dict, on_connection_state_change: Optional[Callable] = None):
    """
    Helper function to initialize and run WebRTC peer.
    
    Args:
        user_uid: Firebase user UID
        device_uid: Device UID
        capture: Camera capture object
        pc_mode: PC mode flag
        frame_dimension: Frame dimensions dict
        on_connection_state_change: Optional callback for connection state changes
    
    Returns:
        WebRTCPeer instance
    """
    peer = WebRTCPeer(
        user_uid=user_uid,
        device_uid=device_uid,
        capture=capture,
        pc_mode=pc_mode,
        frame_dimension=frame_dimension,
        on_connection_state_change=on_connection_state_change
    )
    
    # Start the peer (this will listen for offers)
    asyncio.create_task(peer.start())
    
    return peer