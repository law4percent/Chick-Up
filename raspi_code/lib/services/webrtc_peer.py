"""
Docstring for raspi_code.lib.services.webrtc_peer
Path: raspi_code/lib/services/webrtc_peer.py
Description: WebRTC peer implementation for Raspberry Pi to stream video to mobile app.
             Handles peer connection, video track creation, and Firebase-based signaling.
"""

import asyncio
import cv2
import logging
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCConfiguration, RTCIceServer, RTCIceCandidate
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
    Optimized for Raspberry Pi with frame rate throttling to prevent CPU overload.
    """
    
    def __init__(self, capture, pc_mode: bool, frame_dimension: dict):
        super().__init__()
        self.capture = capture
        self.pc_mode = pc_mode
        self.width = frame_dimension.get("width", 640)
        self.height = frame_dimension.get("height", 480)
        
        # Required by aiortc's timing logic
        self._start = time.time()
        self._timestamp = 0
        
        # 20 FPS is optimal for Pi thermal management and bandwidth
        # Lower FPS = less CPU usage = cooler Pi = more stable streaming
        self.fps = 20
        self.frame_duration = 1 / self.fps
        
    async def recv(self):
        """
        Receive next video frame in WebRTC format.
        Called by aiortc to get frames for streaming.
        Includes frame rate throttling to prevent CPU overload.
        """
        # 1. THROTTLE: Ensure we don't exceed target FPS
        # This prevents the Pi from overheating by trying to send too many frames
        if self._timestamp != 0:
            next_frame_time = self._start + (self._timestamp / 90000)
            wait = next_frame_time - time.time()
            if wait > 0:
                await asyncio.sleep(wait)
        
        # 2. Timing logic (using 90kHz clock for WebRTC standard)
        self._timestamp += int(90000 / self.fps)
        pts = self._timestamp
        time_base = Fraction(1, 90000)
        
        # 3. Capture frame from camera
        if self.pc_mode:
            ret, frame = self.capture.read()
            if not ret:
                logger.error("Failed to read frame from camera")
                # Return black frame on error
                frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        else:
            # Picamera2 mode
            frame = self.capture.capture_array()
        
        # 4. Resize to target dimensions
        frame = cv2.resize(frame, (self.width, self.height))
        
        # 5. Convert BGR to RGB (OpenCV uses BGR, WebRTC expects RGB)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 6. Create VideoFrame from numpy array
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
        # 
        # TROUBLESHOOTING NETWORK ISSUES:
        # --------------------------------
        # 1. "Connecting..." forever → Check if Pi and Phone are on SAME Wi-Fi
        # 2. "Failed" immediately → Firewall blocking UDP ports
        # 3. Works on Wi-Fi but not on 4G/LTE → Need TURN server (relay)
        #
        # For local testing: Ensure both devices on same network
        # For production: Add TURN server to ice_servers list
        #
        # Example TURN server (you'd need to set up your own):
        # RTCIceServer(
        #     urls=["turn:your-turn-server.com:3478"],
        #     username="your-username",
        #     credential="your-password"
        # )
        self.ice_servers = [
            RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
            RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
            RTCIceServer(urls=["stun:stun2.l.google.com:19302"]),
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
                
                # Reset candidate counter once connected
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
            ice_state = pc.iceConnectionState
            logger.info(f"ICE connection state: {ice_state}")
            
            # Log additional diagnostic info
            if ice_state == "checking":
                logger.debug("Checking ICE candidates...")
            elif ice_state == "connected":
                logger.info("ICE connection established - peer-to-peer connection active")
            elif ice_state == "failed":
                logger.error("ICE connection failed - check network/firewall settings")
        
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
        
        # Use polling instead of Firebase .listen() for better async compatibility
        asyncio.create_task(self._poll_for_offers())
        logger.info("Started polling for WebRTC offers from mobile app")
    
    async def _poll_for_offers(self):
        """
        Poll Firebase for new offers instead of using .listen()
        This works better with asyncio event loop.
        """
        last_offer_timestamp = 0
        
        while self.is_running:
            try:
                offer_data = self.offer_ref.get()
                
                if offer_data and isinstance(offer_data, dict):
                    timestamp = offer_data.get("timestamp", 0)
                    
                    # Only process if it's a new offer
                    if timestamp > last_offer_timestamp:
                        last_offer_timestamp = timestamp
                        logger.info(f"New offer detected (timestamp: {timestamp})")
                        await self._handle_offer(offer_data)
                
                await asyncio.sleep(0.5)  # Poll every 500ms
                
            except Exception as e:
                logger.error(f"Error polling for offers: {e}")
                await asyncio.sleep(1)  # Wait longer on error
    
    async def _handle_offer(self, offer_data):
        """
        Handle incoming offer from mobile app.
        Creates answer and sets up video track.
        """
        try:
            logger.info("Received offer from mobile app")
            
            # Delete offer immediately to prevent processing it twice
            # This prevents "InvalidStateError: Cannot handle answer in signaling state stable"
            try:
                self.offer_ref.delete()
                logger.debug("Offer deleted from Firebase to prevent duplicate processing")
            except Exception as e:
                logger.warning(f"Could not delete offer (may already be deleted): {e}")
            
            # Clean up existing connection if any
            if self.pc:
                await self.pc.close()
                self.pc = None
            
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
            
            # Optional: Modify SDP for bitrate control (helps with weak Wi-Fi)
            # This sets a maximum bitrate to prevent quality degradation on poor connections
            modified_sdp = self._apply_bitrate_limit(answer.sdp)
            if modified_sdp != answer.sdp:
                logger.info("Applied bitrate limit to SDP for better stability")
                answer = RTCSessionDescription(sdp=modified_sdp, type=answer.type)
            
            # Set local description ONLY ONCE (calling twice causes InvalidStateError)
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
            
            # Start polling for ICE candidates from mobile app
            asyncio.create_task(self._poll_for_mobile_ice_candidates())
            logger.info("Started polling for ICE candidates from mobile app")
            
            # Update connection state
            self.connection_state_ref.set("connecting")
            
        except Exception as e:
            logger.error(f"Error handling offer: {e}", exc_info=True)
            self.connection_state_ref.set("failed")
    
    async def _poll_for_mobile_ice_candidates(self):
        """
        Poll for ICE candidates from mobile app.
        Runs until connection is established or closed.
        """
        processed_candidates = set()
        
        while (self.pc and 
               self.pc.connectionState not in ["connected", "closed", "failed"] and 
               self.is_running):
            try:
                candidates_data = self.ice_candidates_mobile_ref.get()
                
                if candidates_data and isinstance(candidates_data, dict):
                    for key, candidate_data in candidates_data.items():
                        # Skip if already processed
                        if key in processed_candidates:
                            continue
                        
                        if isinstance(candidate_data, dict) and "candidate" in candidate_data:
                            await self._add_ice_candidate(candidate_data)
                            processed_candidates.add(key)
                
                await asyncio.sleep(0.2)  # Poll every 200ms
                
            except Exception as e:
                logger.error(f"Error polling for ICE candidates: {e}")
                await asyncio.sleep(0.5)
        
        logger.info("Stopped polling for ICE candidates")
    
    def _apply_bitrate_limit(self, sdp: str, max_bitrate_kbps: int = 1500) -> str:
        """
        Apply bitrate limit to SDP for better quality on weak Wi-Fi.
        
        Args:
            sdp: Original SDP string
            max_bitrate_kbps: Maximum bitrate in kbps (default 1500 = 1.5 Mbps)
                             Good values: 500-2000 kbps depending on network
        
        Returns:
            Modified SDP with bitrate limit
        """
        lines = sdp.split('\r\n')
        modified_lines = []
        video_section = False
        bitrate_added = False
        
        for line in lines:
            # Detect video section
            if line.startswith('m=video'):
                video_section = True
                bitrate_added = False
            elif line.startswith('m='):
                video_section = False
            
            modified_lines.append(line)
            
            # Add bitrate limit after video codec line
            if video_section and line.startswith('a=rtpmap:') and not bitrate_added:
                # Extract payload type
                parts = line.split()
                if len(parts) >= 2:
                    payload_type = parts[0].split(':')[1]
                    # Add bandwidth limit (b=AS: for application-specific maximum)
                    modified_lines.append(f'b=AS:{max_bitrate_kbps}')
                    # Add TIAS (Transport Independent Application Specific Maximum)
                    modified_lines.append(f'b=TIAS:{max_bitrate_kbps * 1000}')
                    bitrate_added = True
                    logger.debug(f"Added bitrate limit: {max_bitrate_kbps} kbps")
        
        return '\r\n'.join(modified_lines)
    
    async def _add_ice_candidate(self, candidate_data):
        """Add ICE candidate from mobile app."""
        try:
            if self.pc and "candidate" in candidate_data:
                # Pass candidate string as first positional argument (aiortc requirement)
                candidate = RTCIceCandidate(
                    candidate_data["candidate"],  # Positional argument, not keyword
                    candidate_data.get("sdpMid"),
                    candidate_data.get("sdpMLineIndex")
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
            
            # Clear Firebase data - Use delete() instead of set(None)
            # Firebase Admin SDK doesn't accept None values
            try:
                self.offer_ref.delete()
            except Exception:
                pass  # Ignore if already deleted
            
            try:
                self.answer_ref.delete()
            except Exception:
                pass
            
            try:
                self.ice_candidates_raspi_ref.delete()
            except Exception:
                pass
            
            try:
                self.ice_candidates_mobile_ref.delete()
            except Exception:
                pass
            
            # Set connection state to disconnected (use string, not None)
            try:
                self.connection_state_ref.set("disconnected")
            except Exception:
                pass
            
            logger.info("WebRTC peer cleanup complete")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def stop(self):
        """Stop the WebRTC peer gracefully."""
        await self.cleanup()


# Helper function to run WebRTC peer in async context
async def run_webrtc_peer(user_uid: str, device_uid: str, capture, pc_mode: bool, 
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
    await peer.start()
    
    return peer