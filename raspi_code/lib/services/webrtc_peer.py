"""
Path: lib/services/webrtc_peer.py
Description:
    WebRTC peer implementation for Raspberry Pi.
    Streams video to mobile app via Firebase signaling + TURN relay.

Logging contract:
    - Public API methods (start, stop, run_webrtc_peer) → raise exceptions.
      The calling process (process_a) catches and logs them.
    - Internal async callbacks (ICE, signaling, polling) → use the module-level
      _log() bound to this file. These fire deep inside event loop tasks where
      exceptions cannot propagate meaningfully, so they log warn/error only.
"""

import time
import asyncio
from fractions  import Fraction
from typing     import Optional, Callable

import cv2
import numpy as np
from av         import VideoFrame
from aiortc     import (
    RTCPeerConnection, RTCSessionDescription,
    VideoStreamTrack, RTCConfiguration, RTCIceServer
)
from aiortc.sdp     import candidate_from_sdp
from firebase_admin import db

from lib.services.logger import get_logger

# Internal logger — used ONLY inside async callbacks that cannot raise.
# Restricted to warning/error to match the system-wide logging policy.
_log = get_logger("webrtc_peer.py")


# ─────────────────────────── EXCEPTIONS ──────────────────────────────────────

class WebRTCError(Exception):
    """Base exception for WebRTC errors."""
    pass

class WebRTCStartError(WebRTCError):
    """Raised when the peer fails to start."""
    pass

class WebRTCStopError(WebRTCError):
    """Raised when the peer fails to stop cleanly."""
    pass


# ─────────────────────────── VIDEO TRACK ─────────────────────────────────────

class CameraVideoTrack(VideoStreamTrack):
    """
    Custom video track that reads frames from a SharedFrameBuffer.

    Both webcam and Picamera2 expose capture_array() via the camera_controller
    shim, so no branching on camera type is needed here.
    If frame_buffer is provided it is preferred (decouples capture from WebRTC).
    """

    def __init__(
        self,
        capture,
        frame_dimension : dict,
        frame_buffer    = None
    ):
        super().__init__()
        self.capture      = capture
        self.width        = frame_dimension.get("width",  640)
        self.height       = frame_dimension.get("height", 480)
        self.frame_buffer = frame_buffer
        self._start       = time.time()
        self._timestamp   = 0
        self.fps          = 20

    async def recv(self) -> VideoFrame:
        if self._timestamp != 0:
            next_frame_time = self._start + (self._timestamp / 90000)
            wait = next_frame_time - time.time()
            if wait > 0:
                await asyncio.sleep(wait)

        self._timestamp += int(90000 / self.fps)
        pts       = self._timestamp
        time_base = Fraction(1, 90000)

        # Pull frame — buffer preferred, fall back to direct capture
        if self.frame_buffer is not None:
            frame = self.frame_buffer.get()
        else:
            frame = self.capture.capture_array()

        if frame is None:
            frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        else:
            frame = cv2.resize(frame, (self.width, self.height))

        frame                 = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        video_frame           = VideoFrame.from_ndarray(frame, format="rgb24")
        video_frame.pts       = pts
        video_frame.time_base = time_base
        return video_frame


# ─────────────────────────── WEBRTC PEER ─────────────────────────────────────

class WebRTCPeer:
    """
    WebRTC peer with TURN server support.

    Handles:
    - Firebase signaling (offer / answer / ICE candidates)
    - TURN relay for strict NAT / CGNAT mobile networks
    - Auto-reconnect on new offers
    - Bitrate limiting

    Public methods raise exceptions.
    Internal async callbacks log via _log() — they cannot raise meaningfully.
    """

    def __init__(
        self,
        user_uid                  : str,
        device_uid                : str,
        capture,
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
        self.frame_dimension            = frame_dimension
        self.on_connection_state_change = on_connection_state_change
        self.frame_buffer               = frame_buffer

        self.pc           : Optional[RTCPeerConnection] = None
        self.video_track  : Optional[CameraVideoTrack]  = None
        self.is_running   : bool = False
        self.candidates_sent      : int  = 0
        self.last_offer_timestamp : int  = 0
        self.ice_stats            : dict = {"host": 0, "srflx": 0, "relay": 0}

        # Firebase refs
        self.stream_ref                = db.reference(f"liveStream/{user_uid}/{device_uid}")
        self.offer_ref                 = self.stream_ref.child("offer")
        self.answer_ref                = self.stream_ref.child("answer")
        self.ice_candidates_raspi_ref  = self.stream_ref.child("iceCandidates/raspi")
        self.ice_candidates_mobile_ref = self.stream_ref.child("iceCandidates/mobile")
        self.connection_state_ref      = self.stream_ref.child("connectionState")

        # ICE / TURN servers
        self.ice_servers = [
            RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
            RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
        ]

        if turn_server_url and turn_username and turn_password:
            # Normalize: strip any existing scheme prefix so we can rebuild correctly.
            # Handles both "turn:host:port" and bare "host:port" from .env.
            _host = turn_server_url
            for _prefix in ("turns:", "turn:", "stun:"):
                if _host.startswith(_prefix):
                    _host = _host[len(_prefix):]
                    break

            self.ice_servers.append(
                RTCIceServer(
                    urls=[
                        f"turn:{_host}?transport=udp",
                        f"turn:{_host}?transport=tcp",
                    ],
                    username   = turn_username,
                    credential = turn_password
                )
            )
        else:
            _log(
                details="No TURN server configured — may fail on strict NATs",
                log_type="warning"
            )

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
                    elif "typ relay" in cand_str: self.ice_stats["relay"] += 1

                    self.ice_candidates_raspi_ref.push({
                        "candidate"     : candidate.candidate,
                        "sdpMid"        : candidate.sdpMid,
                        "sdpMLineIndex" : candidate.sdpMLineIndex,
                        "timestamp"     : int(time.time() * 1000)
                    })
                    self.candidates_sent += 1
                except Exception as e:
                    _log(details=f"ICE candidate send failed: {e}", log_type="error")

        @pc.on("icegatheringstatechange")
        async def on_ice_gathering_state():
            if pc.iceGatheringState == "complete" and self.ice_stats["relay"] == 0:
                _log(
                    details=f"ICE gathering complete — no relay candidates. Stats: {self.ice_stats}",
                    log_type="warning"
                )

        @pc.on("connectionstatechange")
        async def on_connection_state():
            state = pc.connectionState
            try:
                self.connection_state_ref.set(state)
            except Exception as e:
                _log(details=f"Failed to write connection state to Firebase: {e}", log_type="warning")

            if self.on_connection_state_change:
                self.on_connection_state_change(state)

            if state == "connected":
                self.candidates_sent = 0
            elif state in ["failed", "closed"]:
                _log(
                    details=f"Connection {state} | ICE stats: {self.ice_stats}",
                    log_type="warning"
                )
                await self._cleanup()

        @pc.on("iceconnectionstatechange")
        async def on_ice_state():
            if pc.iceConnectionState == "failed":
                _log(
                    details=(
                        f"ICE connection failed | stats: {self.ice_stats} | "
                        f"relay used: {self.ice_stats['relay'] > 0}"
                    ),
                    log_type="error"
                )

        return pc

    # ─────────────────────────── START / POLL ────────────────────────────────

    async def start(self) -> None:
        """
        Start the peer and begin polling Firebase for offers.

        Raises:
            WebRTCStartError: If the initial Firebase connection state write fails.
        """
        if self.is_running:
            return
        self.is_running = True
        try:
            self.connection_state_ref.set("disconnected")
        except Exception as e:
            raise WebRTCStartError(
                f"Failed to write initial connection state to Firebase: {e}. "
                f"Source: {__name__}"
            ) from e

        asyncio.create_task(self._poll_for_offers())

    async def _poll_for_offers(self) -> None:
        """Internal loop — logs internally, does not raise."""
        while self.is_running:
            try:
                offer_data = self.offer_ref.get()
                if offer_data and isinstance(offer_data, dict):
                    timestamp = offer_data.get("timestamp", 0)
                    if timestamp > self.last_offer_timestamp:
                        self.last_offer_timestamp = timestamp
                        await self._handle_offer(offer_data)
                await asyncio.sleep(0.5)
            except Exception as e:
                _log(details=f"Offer poll error: {e}", log_type="error")
                await asyncio.sleep(1)

    # ─────────────────────────── OFFER / ANSWER ──────────────────────────────

    async def _handle_offer(self, offer_data: dict) -> None:
        """Internal handler — logs internally, does not raise."""
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
                capture         = self.capture,
                frame_dimension = self.frame_dimension,
                frame_buffer    = self.frame_buffer
            )
            self.pc.addTrack(self.video_track)

            offer = RTCSessionDescription(
                sdp  = offer_data["sdp"],
                type = offer_data["type"]
            )
            await self.pc.setRemoteDescription(offer)

            answer       = await self.pc.createAnswer()
            modified_sdp = self._apply_bitrate_limit(answer.sdp)
            if modified_sdp != answer.sdp:
                answer = RTCSessionDescription(sdp=modified_sdp, type=answer.type)

            # setLocalDescription triggers ICE gathering. Wait for it to
            # complete before sending the answer — otherwise socket.send()
            # fires on a half-initialised ICE agent and raises an exception,
            # and host/srflx/relay candidates all stay at 0.
            await self.pc.setLocalDescription(answer)
            await self._wait_for_ice_gather(timeout=10.0)

            self.answer_ref.set({
                "sdp"       : self.pc.localDescription.sdp,
                "type"      : self.pc.localDescription.type,
                "timestamp" : int(time.time() * 1000)
            })

            asyncio.create_task(self._poll_for_mobile_ice_candidates())

            try:
                self.connection_state_ref.set("connecting")
            except Exception:
                pass

        except Exception as e:
            _log(details=f"Offer handling failed: {e}", log_type="error")
            try:
                self.connection_state_ref.set("failed")
            except Exception:
                pass

    async def _wait_for_ice_gather(self, timeout: float = 10.0) -> None:
        """
        Block until iceGatheringState == 'complete' or timeout expires.

        Without this wait, the raspi sends the answer SDP before local ICE
        candidates are ready. The subsequent STUN/TURN socket writes land on
        sockets that aiortc has already started tearing down, which produces:
            socket.send() raised exception
        and leaves host/srflx/relay candidate counts all at 0.

        10 seconds is generous — normal ICE gather on a Pi with WiFi takes
        under 2 seconds for host candidates.
        """
        deadline = time.time() + timeout
        while self.pc and self.pc.iceGatheringState != "complete":
            if time.time() > deadline:
                _log(
                    details=(
                        f"ICE gather timed out after {timeout:.0f}s — "
                        f"state={getattr(self.pc, 'iceGatheringState', 'gone')} "
                        f"stats={self.ice_stats}"
                    ),
                    log_type="warning"
                )
                return
            await asyncio.sleep(0.1)

    # ─────────────────────────── ICE CANDIDATES ──────────────────────────────

    async def _poll_for_mobile_ice_candidates(self) -> None:
        """Internal loop — logs internally, does not raise."""
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
                _log(details=f"Mobile ICE candidate poll error: {e}", log_type="error")
                await asyncio.sleep(0.5)

    async def _add_ice_candidate(self, cand_data: dict) -> None:
        """Internal — logs internally, does not raise."""
        try:
            if self.pc and "candidate" in cand_data:
                raw = cand_data["candidate"]
                if raw.startswith("candidate:"):
                    raw = raw.replace("candidate:", "", 1)

                candidate               = candidate_from_sdp(raw)
                candidate.sdpMid        = cand_data.get("sdpMid")
                candidate.sdpMLineIndex = cand_data.get("sdpMLineIndex")
                await self.pc.addIceCandidate(candidate)
        except Exception as e:
            _log(details=f"Add ICE candidate failed: {e}", log_type="error")

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

    async def _cleanup(self) -> None:
        """
        Internal cleanup — called from connection state callbacks.
        Logs internally, does not raise.
        """
        try:
            if self.pc:
                await self.pc.close()
                self.pc = None
            if self.video_track:
                self.video_track.stop()
                self.video_track = None

            for ref in [
                self.offer_ref,
                self.answer_ref,
                self.ice_candidates_raspi_ref,
                self.ice_candidates_mobile_ref,
            ]:
                try:
                    ref.delete()
                except Exception:
                    pass

            try:
                self.connection_state_ref.set("disconnected")
            except Exception:
                pass

            self.candidates_sent = 0
        except Exception as e:
            _log(details=f"Cleanup error: {e}", log_type="error")

    async def stop(self) -> None:
        """
        Gracefully stop the peer.

        Raises:
            WebRTCStopError: If an unexpected error occurs during stop.
        """
        self.is_running = False
        try:
            await self._cleanup()
        except Exception as e:
            raise WebRTCStopError(
                f"Error stopping WebRTC peer: {e}. Source: {__name__}"
            ) from e

    def __repr__(self) -> str:
        return f"WebRTCPeer(user={self.user_uid}, device={self.device_uid})"


# ─────────────────────────── PUBLIC HELPER ───────────────────────────────────

async def run_webrtc_peer(
    user_uid                  : str,
    device_uid                : str,
    capture,
    frame_dimension           : dict,
    on_connection_state_change: Optional[Callable] = None,
    frame_buffer              = None,
    turn_server_url           : str = None,
    turn_username             : str = None,
    turn_password             : str = None
) -> WebRTCPeer:
    """
    Create and start a WebRTCPeer.

    Raises:
        WebRTCStartError: Propagated from WebRTCPeer.start().

    Returns:
        Running WebRTCPeer instance.
    """
    peer = WebRTCPeer(
        user_uid                   = user_uid,
        device_uid                 = device_uid,
        capture                    = capture,
        frame_dimension            = frame_dimension,
        on_connection_state_change = on_connection_state_change,
        frame_buffer               = frame_buffer,
        turn_server_url            = turn_server_url,
        turn_username              = turn_username,
        turn_password              = turn_password
    )
    await peer.start()
    return peer