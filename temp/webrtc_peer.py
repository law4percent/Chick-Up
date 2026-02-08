"""
Docstring for raspi_code.lib.services.webrtc_peer
Path: raspi_code/lib/services/webrtc_peer.py
Description: WebRTC peer implementation for Raspberry Pi to stream video to mobile app.
             NOW WITH TURN SERVER SUPPORT FOR BETTER NAT TRAVERSAL
"""

import asyncio
import cv2
import logging
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCConfiguration, RTCIceServer, RTCIceCandidate
from aiortc.sdp import candidate_from_sdp
from av import VideoFrame
import numpy as np
from firebase_admin import db
import time
from typing import Optional, Callable
from fractions import Fraction

logger = logging.getLogger(__name__)


class CameraVideoTrack(VideoStreamTrack):
    """Custom video track - same as before"""
    
    def __init__(self, capture, pc_mode: bool, frame_dimension: dict, frame_buffer=None):
        super().__init__()
        self.capture = capture
        self.pc_mode = pc_mode
        self.width = frame_dimension.get("width", 640)
        self.height = frame_dimension.get("height", 480)
        self.frame_buffer = frame_buffer
        self._start = time.time()
        self._timestamp = 0
        self.fps = 20
        
    async def recv(self):
        if self._timestamp != 0:
            next_frame_time = self._start + (self._timestamp / 90000)
            wait = next_frame_time - time.time()
            if wait > 0:
                await asyncio.sleep(wait)
        
        self._timestamp += int(90000 / self.fps)
        pts = self._timestamp
        time_base = Fraction(1, 90000)
        
        if self.frame_buffer is not None:
            frame = self.frame_buffer.get()
            if frame is None:
                frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        else:
            if self.pc_mode:
                ret, frame = self.capture.read()
                if not ret:
                    frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            else:
                frame = self.capture.capture_array()
            frame = cv2.resize(frame, (self.width, self.height))
        
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        video_frame = VideoFrame.from_ndarray(frame, format="rgb24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame


class WebRTCPeer:
    """WebRTC peer with TURN server support"""
    
    def __init__(self, user_uid: str, device_uid: str, capture, pc_mode: bool, 
                 frame_dimension: dict, on_connection_state_change: Optional[Callable] = None,
                 frame_buffer=None, 
                 turn_server_url: str = None, 
                 turn_username: str = None, 
                 turn_password: str = None):
        """
        Initialize WebRTC peer with TURN server support.
        
        NEW PARAMETERS:
            turn_server_url: TURN server URL (e.g., 'turn:your-vps-ip:3478')
            turn_username: TURN server username
            turn_password: TURN server password
        """
        self.user_uid = user_uid
        self.device_uid = device_uid
        self.capture = capture
        self.pc_mode = pc_mode
        self.frame_dimension = frame_dimension
        self.on_connection_state_change = on_connection_state_change
        self.frame_buffer = frame_buffer
        
        self.pc: Optional[RTCPeerConnection] = None
        self.video_track: Optional[CameraVideoTrack] = None
        
        # Firebase references
        self.stream_ref = db.reference(f"liveStream/{user_uid}/{device_uid}")
        self.offer_ref = self.stream_ref.child("offer")
        self.answer_ref = self.stream_ref.child("answer")
        self.ice_candidates_raspi_ref = self.stream_ref.child("iceCandidates/raspi")
        self.ice_candidates_mobile_ref = self.stream_ref.child("iceCandidates/mobile")
        self.connection_state_ref = self.stream_ref.child("connectionState")
        
        self.is_running = False
        self.candidates_sent = 0
        self.last_offer_timestamp = 0
        
        # NEW: ICE statistics for diagnostics
        self.ice_stats = {'host': 0, 'srflx': 0, 'relay': 0}
        
        # UPDATED: Configure ICE servers with TURN
        self.ice_servers = [
            RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
            RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
        ]
        
        # Add TURN server if credentials provided
        if turn_server_url and turn_username and turn_password:
            # Production-grade: Include both UDP and TCP for maximum compatibility
            self.ice_servers.append(
                RTCIceServer(
                    urls=[
                        turn_server_url + "?transport=udp",  # Try UDP first (faster)
                        turn_server_url + "?transport=tcp"   # TCP fallback for hostile networks
                    ],
                    username=turn_username,
                    credential=turn_password
                )
            )
            logger.info(f"✅ TURN server configured: {turn_server_url} (UDP+TCP)")
        else:
            logger.warning("⚠️ No TURN server - may fail on strict NATs")
        
        logger.info(f"WebRTC Peer initialized for user={user_uid}, device={device_uid}")
    
    def _create_peer_connection(self):
        """Create peer connection with TURN support"""
        config = RTCConfiguration(iceServers=self.ice_servers)
        pc = RTCPeerConnection(configuration=config)
        self.ice_stats = {'host': 0, 'srflx': 0, 'relay': 0}
        
        @pc.on("icecandidate")
        async def on_ice_candidate(candidate):
            if candidate and self.candidates_sent < 10:
                try:
                    # Track candidate type
                    cand_str = candidate.candidate
                    if 'typ host' in cand_str:
                        self.ice_stats['host'] += 1
                    elif 'typ srflx' in cand_str:
                        self.ice_stats['srflx'] += 1
                    elif 'typ relay' in cand_str:
                        self.ice_stats['relay'] += 1
                        logger.info("🔄 TURN relay candidate generated!")
                    
                    candidate_dict = {
                        "candidate": candidate.candidate,
                        "sdpMid": candidate.sdpMid,
                        "sdpMLineIndex": candidate.sdpMLineIndex,
                        "timestamp": int(time.time() * 1000)
                    }
                    self.ice_candidates_raspi_ref.push(candidate_dict)
                    self.candidates_sent += 1
                except Exception as e:
                    logger.error(f"Error sending ICE candidate: {e}")
        
        @pc.on("icegatheringstatechange")
        async def on_ice_gathering_state():
            if pc.iceGatheringState == "complete":
                logger.info(f"📊 ICE stats: {self.ice_stats}")
                if self.ice_stats['relay'] == 0:
                    logger.warning("⚠️ No TURN relay candidates - check TURN config")
        
        @pc.on("connectionstatechange")
        async def on_connection_state():
            state = pc.connectionState
            logger.info(f"Connection state: {state}")
            self.connection_state_ref.set(state)
            
            if self.on_connection_state_change:
                self.on_connection_state_change(state)
            
            if state == "connected":
                logger.info(f"✅ Connected! Used: {self.ice_stats}")
                self.candidates_sent = 0
            elif state in ["failed", "closed"]:
                logger.warning(f"Connection {state}. Stats: {self.ice_stats}")
                await self.cleanup()
        
        @pc.on("iceconnectionstatechange")
        async def on_ice_state():
            ice_state = pc.iceConnectionState
            logger.info(f"ICE state: {ice_state}")
            
            if ice_state == "failed":
                logger.error(f"❌ ICE failed! Stats: {self.ice_stats}")
                if self.ice_stats['relay'] == 0:
                    logger.error("  - No TURN relay - check server")
        
        return pc
    
    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        logger.info("Starting WebRTC peer...")
        self.connection_state_ref.set("disconnected")
        asyncio.create_task(self._poll_for_offers())
    
    async def _poll_for_offers(self):
        while self.is_running:
            try:
                offer_data = self.offer_ref.get()
                if offer_data and isinstance(offer_data, dict):
                    timestamp = offer_data.get("timestamp", 0)
                    if timestamp > self.last_offer_timestamp:
                        self.last_offer_timestamp = timestamp
                        logger.info(f"🆕 New offer (ts: {timestamp})")
                        await self._handle_offer(offer_data)
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Error polling offers: {e}")
                await asyncio.sleep(1)
    
    async def _handle_offer(self, offer_data):
        try:
            logger.info("📥 Received offer")
            
            try:
                self.offer_ref.delete()
            except:
                pass
            
            if self.pc:
                await self.pc.close()
                self.pc = None
            
            self.pc = self._create_peer_connection()
            
            self.video_track = CameraVideoTrack(
                self.capture, self.pc_mode, 
                self.frame_dimension, self.frame_buffer
            )
            self.pc.addTrack(self.video_track)
            
            offer = RTCSessionDescription(
                sdp=offer_data["sdp"],
                type=offer_data["type"]
            )
            await self.pc.setRemoteDescription(offer)
            
            answer = await self.pc.createAnswer()
            modified_sdp = self._apply_bitrate_limit(answer.sdp)
            if modified_sdp != answer.sdp:
                answer = RTCSessionDescription(sdp=modified_sdp, type=answer.type)
            
            await self.pc.setLocalDescription(answer)
            
            answer_dict = {
                "sdp": self.pc.localDescription.sdp,
                "type": self.pc.localDescription.type,
                "timestamp": int(time.time() * 1000)
            }
            self.answer_ref.set(answer_dict)
            logger.info("📤 Answer sent")
            
            asyncio.create_task(self._poll_for_mobile_ice_candidates())
            self.connection_state_ref.set("connecting")
            
        except Exception as e:
            logger.error(f"❌ Error handling offer: {e}")
            self.connection_state_ref.set("failed")
    
    async def _poll_for_mobile_ice_candidates(self):
        processed = set()
        while (self.pc and 
               self.pc.connectionState not in ["connected", "closed", "failed"] and 
               self.is_running):
            try:
                candidates_data = self.ice_candidates_mobile_ref.get()
                if candidates_data and isinstance(candidates_data, dict):
                    for key, cand_data in candidates_data.items():
                        if key not in processed and isinstance(cand_data, dict):
                            await self._add_ice_candidate(cand_data)
                            processed.add(key)
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.error(f"Error polling ICE: {e}")
                await asyncio.sleep(0.5)
    
    def _apply_bitrate_limit(self, sdp: str, max_kbps: int = 1500) -> str:
        lines = sdp.split('\r\n')
        modified = []
        video_section = False
        bitrate_added = False
        
        for line in lines:
            if line.startswith('m=video'):
                video_section = True
                bitrate_added = False
            elif line.startswith('m='):
                video_section = False
            
            modified.append(line)
            
            if video_section and line.startswith('a=rtpmap:') and not bitrate_added:
                modified.append(f'b=AS:{max_kbps}')
                modified.append(f'b=TIAS:{max_kbps * 1000}')
                bitrate_added = True
        
        return '\r\n'.join(modified)
    
    async def _add_ice_candidate(self, cand_data):
        try:
            if self.pc and "candidate" in cand_data:
                raw = cand_data["candidate"]
                if raw.startswith("candidate:"):
                    raw = raw.replace("candidate:", "", 1)
                
                if 'typ relay' in raw:
                    logger.info("✅ Received TURN relay from mobile")
                
                candidate = candidate_from_sdp(raw)
                candidate.sdpMid = cand_data.get("sdpMid")
                candidate.sdpMLineIndex = cand_data.get("sdpMLineIndex")
                await self.pc.addIceCandidate(candidate)
        except Exception as e:
            logger.error(f"Error adding ICE: {e}")
    
    async def cleanup(self):
        logger.info("🧹 Cleanup...")
        try:
            if self.pc:
                await self.pc.close()
                self.pc = None
            if self.video_track:
                self.video_track.stop()
                self.video_track = None
            
            try:
                self.offer_ref.delete()
                self.answer_ref.delete()
                self.ice_candidates_raspi_ref.delete()
                self.ice_candidates_mobile_ref.delete()
                self.connection_state_ref.set("disconnected")
            except:
                pass
            
            self.candidates_sent = 0
            logger.info("✅ Cleanup complete, listening for next offer")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    async def stop(self):
        logger.info("🛑 Stopping WebRTC peer")
        self.is_running = False
        await self.cleanup()


async def run_webrtc_peer(user_uid: str, device_uid: str, capture, pc_mode: bool, 
                          frame_dimension: dict, on_connection_state_change: Optional[Callable] = None,
                          frame_buffer=None,
                          turn_server_url: str = None,
                          turn_username: str = None,
                          turn_password: str = None):
    """
    Helper to run WebRTC peer with TURN support.
    
    NEW PARAMETERS:
        turn_server_url: e.g., 'turn:your-vps-ip:3478'
        turn_username: TURN username
        turn_password: TURN password
    """
    peer = WebRTCPeer(
        user_uid=user_uid,
        device_uid=device_uid,
        capture=capture,
        pc_mode=pc_mode,
        frame_dimension=frame_dimension,
        on_connection_state_change=on_connection_state_change,
        frame_buffer=frame_buffer,
        turn_server_url=turn_server_url,
        turn_username=turn_username,
        turn_password=turn_password
    )
    await peer.start()
    return peer