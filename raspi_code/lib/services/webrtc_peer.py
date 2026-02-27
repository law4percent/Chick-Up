"""
Path: lib/services/webrtc_peer.py
Description:
    WebRTC peer implementation for Raspberry Pi.
    Streams video to mobile app via Firebase signaling + TURN relay.
"""

import time
import asyncio
from fractions      import Fraction
from typing         import Optional, Callable

import cv2
import numpy as np
from av              import VideoFrame
from aiortc          import (
    RTCPeerConnection, RTCSessionDescription,
    VideoStreamTrack, RTCConfiguration, RTCIceServer
)
from aiortc.sdp      import candidate_from_sdp
from firebase_admin  import db

from lib.services.logger import get_logger

log = get_logger("webrtc_peer")


# ─────────────────────────── VIDEO TRACK ─────────────────────────────────────

class CameraVideoTrack(VideoStreamTrack):
    """Custom video track that reads from a SharedFrameBuffer or direct capture."""

    def __init__(
        self,
        capture,
        pc_mode         : bool,
        frame_dimension : dict,
        frame_buffer    = None
    ):
        super().__init__()
        self.capture         = capture
        self.pc_mode         = pc_mode
        self.width           = frame_dimension.get("width",  640)
        self.height          = frame_dimension.get("height", 480)
        self.frame_buffer    = frame_buffer
        self._start          = time.time()
        self._timestamp      = 0
        self.fps             = 20

    async def recv(self) -> VideoFrame:
        if self._timestamp != 0:
            next_frame_time = self._start + (self._timestamp / 90000)
            wait = next_frame_time - time.time()
            if wait > 0:
                await asyncio.sleep(wait)

        self._timestamp += int(90000 / self.fps)
        pts       = self._timestamp
        time_base = Fraction(1, 90000)

        # Pull frame
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
        video_frame           = VideoFrame.from_ndarray(frame, format="rgb24")
        video_frame.pts       = pts
        video_frame.time_base = time_base
        return video_frame


# ─────────────────────────── WEBRTC PEER ─────────────────────────────────────

class WebRTCPeer:
    """
    WebRTC peer with TURN server support.

    Handles:
    - Firebase signaling (offer/answer/ICE candidates)
    - TURN relay for strict NAT / CGNAT mobile networks
    - Auto-reconnect on new offers
    - Bitrate limiting
    """

    def __init__(
        self,
        user_uid                  : str,
        device_uid                : str,
        capture,
        pc_mode                   : bool,
        frame_dimension           : dict,
        on_connection_state_change: Optional[Callable] = None,
        frame_buffer              = None,
        turn_server_url           : str = None,
        turn_username             : str = None,
        turn_password             : str = None
    ):
        self.user_uid                   = user_uid
        self.device_uid                 = device_uid
        self.capture                    = capture
        self.pc_mode                    = pc_mode
        self.frame_dimension            = frame_dimension
        self.on_connection_state_change = on_connection_state_change
        self.frame_buffer               = frame_buffer

        self.pc           : Optional[RTCPeerConnection]  = None
        self.video_track  : Optional[CameraVideoTrack]   = None
        self.is_running   : bool  = False
        self.candidates_sent      : int   = 0
        self.last_offer_timestamp : int   = 0
        self.ice_stats            : dict  = {"host": 0, "srflx": 0, "relay": 0}

        # Firebase refs
        self.stream_ref                = db.reference(f"liveStream/{user_uid}/{device_uid}")
        self.offer_ref                 = self.stream_ref.child("offer")
        self.answer_ref                = self.stream_ref.child("answer")
        self.ice_candidates_raspi_ref  = self.stream_ref.child("iceCandidates/raspi")
        self.ice_candidates_mobile_ref = self.stream_ref.child("iceCandidates/mobile")
        self.connection_state_ref      = self.stream_ref.child("connectionState")

        # ICE servers
        self.ice_servers = [
            RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
            RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
        ]

        if turn_server_url and turn_username and turn_password:
            self.ice_servers.append(
                RTCIceServer(
                    urls=[
                        turn_server_url + "?transport=udp",
                        turn_server_url + "?transport=tcp"
                    ],
                    username   = turn_username,
                    credential = turn_password
                )
            )
            log(f"TURN configured: {turn_server_url} (UDP+TCP)", log_type="info")
        else:
            log("No TURN server — may fail on strict NATs", log_type="warn")

    # ─────────────────────────── PEER CONNECTION ─────────────────────────────

    def _create_peer_connection(self) -> RTCPeerConnection:
        """Create a new RTCPeerConnection with ICE/TURN config and event handlers."""
        config = RTCConfiguration(iceServers=self.ice_servers)
        pc     = RTCPeerConnection(configuration=config)
        self.ice_stats = {"host": 0, "srflx": 0, "relay": 0}

        @pc.on("icecandidate")
        async def on_ice_candidate(candidate):
            if candidate and self.candidates_sent < 10:
                try:
                    cand_str = candidate.candidate
                    if   "typ host"  in cand_str: self.ice_stats["host"]  += 1
                    elif "typ srflx" in cand_str: self.ice_stats["srflx"] += 1
                    elif "typ relay" in cand_str:
                        self.ice_stats["relay"] += 1
                        log("TURN relay candidate generated", log_type="info")

                    self.ice_candidates_raspi_ref.push({
                        "candidate"     : candidate.candidate,
                        "sdpMid"        : candidate.sdpMid,
                        "sdpMLineIndex" : candidate.sdpMLineIndex,
                        "timestamp"     : int(time.time() * 1000)
                    })
                    self.candidates_sent += 1
                except Exception as e:
                    log(f"Error sending ICE candidate: {e}", log_type="error")

        @pc.on("icegatheringstatechange")
        async def on_ice_gathering_state():
            if pc.iceGatheringState == "complete":
                log(f"ICE gathering complete: {self.ice_stats}", log_type="info")
                if self.ice_stats["relay"] == 0:
                    log("No TURN relay candidates — check TURN config", log_type="warn")

        @pc.on("connectionstatechange")
        async def on_connection_state():
            state = pc.connectionState
            log(f"Connection state: {state}", log_type="info")
            self.connection_state_ref.set(state)

            if self.on_connection_state_change:
                self.on_connection_state_change(state)

            if state == "connected":
                self.candidates_sent = 0
            elif state in ["failed", "closed"]:
                log(f"Connection {state} | ICE stats: {self.ice_stats}", log_type="warn")
                await self.cleanup()

        @pc.on("iceconnectionstatechange")
        async def on_ice_state():
            if pc.iceConnectionState == "failed":
                log(f"ICE failed | stats: {self.ice_stats}", log_type="error")
                if self.ice_stats["relay"] == 0:
                    log("No TURN relay used — check server config", log_type="error")

        return pc

    # ─────────────────────────── START / POLL ────────────────────────────────

    async def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        log("WebRTC peer started, polling for offers...", log_type="info")
        self.connection_state_ref.set("disconnected")
        asyncio.create_task(self._poll_for_offers())

    async def _poll_for_offers(self) -> None:
        while self.is_running:
            try:
                offer_data = self.offer_ref.get()
                if offer_data and isinstance(offer_data, dict):
                    timestamp = offer_data.get("timestamp", 0)
                    if timestamp > self.last_offer_timestamp:
                        self.last_offer_timestamp = timestamp
                        log(f"New offer received (ts: {timestamp})", log_type="info")
                        await self._handle_offer(offer_data)
                await asyncio.sleep(0.5)
            except Exception as e:
                log(f"Error polling offers: {e}", log_type="error")
                await asyncio.sleep(1)

    # ─────────────────────────── OFFER / ANSWER ──────────────────────────────

    async def _handle_offer(self, offer_data: dict) -> None:
        try:
            try:
                self.offer_ref.delete()
            except Exception:
                pass

            if self.pc:
                await self.pc.close()
                self.pc = None

            self.pc = self._create_peer_connection()

            self.video_track = CameraVideoTrack(
                self.capture,
                self.pc_mode,
                self.frame_dimension,
                self.frame_buffer
            )
            self.pc.addTrack(self.video_track)

            offer = RTCSessionDescription(
                sdp  = offer_data["sdp"],
                type = offer_data["type"]
            )
            await self.pc.setRemoteDescription(offer)

            answer = await self.pc.createAnswer()

            # Apply bitrate limit
            modified_sdp = self._apply_bitrate_limit(answer.sdp)
            if modified_sdp != answer.sdp:
                answer = RTCSessionDescription(sdp=modified_sdp, type=answer.type)

            await self.pc.setLocalDescription(answer)

            self.answer_ref.set({
                "sdp"       : self.pc.localDescription.sdp,
                "type"      : self.pc.localDescription.type,
                "timestamp" : int(time.time() * 1000)
            })
            log("Answer sent to mobile", log_type="info")

            asyncio.create_task(self._poll_for_mobile_ice_candidates())
            self.connection_state_ref.set("connecting")

        except Exception as e:
            log(f"Error handling offer: {e}", log_type="error")
            self.connection_state_ref.set("failed")

    # ─────────────────────────── ICE CANDIDATES ──────────────────────────────

    async def _poll_for_mobile_ice_candidates(self) -> None:
        processed = set()
        while (
            self.pc and
            self.pc.connectionState not in ["connected", "closed", "failed"] and
            self.is_running
        ):
            try:
                candidates_data = self.ice_candidates_mobile_ref.get()
                if candidates_data and isinstance(candidates_data, dict):
                    for key, cand_data in candidates_data.items():
                        if key not in processed and isinstance(cand_data, dict):
                            await self._add_ice_candidate(cand_data)
                            processed.add(key)
                await asyncio.sleep(0.2)
            except Exception as e:
                log(f"Error polling mobile ICE candidates: {e}", log_type="error")
                await asyncio.sleep(0.5)

    async def _add_ice_candidate(self, cand_data: dict) -> None:
        try:
            if self.pc and "candidate" in cand_data:
                raw = cand_data["candidate"]
                if raw.startswith("candidate:"):
                    raw = raw.replace("candidate:", "", 1)

                if "typ relay" in raw:
                    log("Received TURN relay candidate from mobile", log_type="info")

                candidate               = candidate_from_sdp(raw)
                candidate.sdpMid        = cand_data.get("sdpMid")
                candidate.sdpMLineIndex = cand_data.get("sdpMLineIndex")
                await self.pc.addIceCandidate(candidate)
        except Exception as e:
            log(f"Error adding ICE candidate: {e}", log_type="error")

    # ─────────────────────────── BITRATE ─────────────────────────────────────

    def _apply_bitrate_limit(self, sdp: str, max_kbps: int = 1500) -> str:
        lines         = sdp.split("\r\n")
        modified      = []
        video_section = False
        bitrate_added = False

        for line in lines:
            if line.startswith("m=video"):
                video_section = True
                bitrate_added = False
            elif line.startswith("m="):
                video_section = False

            modified.append(line)

            if video_section and line.startswith("a=rtpmap:") and not bitrate_added:
                modified.append(f"b=AS:{max_kbps}")
                modified.append(f"b=TIAS:{max_kbps * 1000}")
                bitrate_added = True

        return "\r\n".join(modified)

    # ─────────────────────────── CLEANUP / STOP ──────────────────────────────

    async def cleanup(self) -> None:
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
            except Exception:
                pass

            self.candidates_sent = 0
            log("Cleanup complete, listening for next offer", log_type="info")
        except Exception as e:
            log(f"Cleanup error: {e}", log_type="error")

    async def stop(self) -> None:
        log("Stopping WebRTC peer", log_type="info")
        self.is_running = False
        await self.cleanup()

    def __repr__(self) -> str:
        return f"WebRTCPeer(user={self.user_uid}, device={self.device_uid})"


# ─────────────────────────── HELPER ──────────────────────────────────────────

async def run_webrtc_peer(
    user_uid                  : str,
    device_uid                : str,
    capture,
    pc_mode                   : bool,
    frame_dimension           : dict,
    on_connection_state_change: Optional[Callable] = None,
    frame_buffer              = None,
    turn_server_url           : str = None,
    turn_username             : str = None,
    turn_password             : str = None
) -> WebRTCPeer:
    """
    Convenience function to create and start a WebRTCPeer.

    Returns:
        Running WebRTCPeer instance
    """
    peer = WebRTCPeer(
        user_uid                   = user_uid,
        device_uid                 = device_uid,
        capture                    = capture,
        pc_mode                    = pc_mode,
        frame_dimension            = frame_dimension,
        on_connection_state_change = on_connection_state_change,
        frame_buffer               = frame_buffer,
        turn_server_url            = turn_server_url,
        turn_username              = turn_username,
        turn_password              = turn_password
    )
    await peer.start()
    return peer