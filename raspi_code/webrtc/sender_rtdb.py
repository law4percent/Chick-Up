import asyncio
import json
import cv2
from av import VideoFrame
from aiortc import RTCPeerConnection, VideoStreamTrack
from firebase_admin import credentials, db, initialize_app

cred = credentials.Certificate("serviceAccountKey.json")
initialize_app(cred, {
    "databaseURL": "https://YOUR-PROJECT-ID.firebaseio.com"
})

class CameraStream(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.cap = cv2.VideoCapture(0)

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        ret, frame = self.cap.read()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        video_frame = VideoFrame.from_ndarray(frame, format="rgb24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame

async def run():
    pc = RTCPeerConnection()
    pc.addTrack(CameraStream())

    offer_ref = db.reference("webrtc/offer")
    answer_ref = db.reference("webrtc/answer")
    ice_ref = db.reference("webrtc/ice/raspi")

    # Wait for offer
    print("Waiting for viewer offer...")
    while True:
        offer = offer_ref.get()
        if offer and "sdp" in offer:
            break
        await asyncio.sleep(1)

    print("Offer received.")
    await pc.setRemoteDescription(
        {"type": "offer", "sdp": offer["sdp"]}
    )

    # Create and upload answer
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    answer_ref.set({"sdp": pc.localDescription.sdp})

    # Handle ICE from viewer
    viewer_ice_ref = db.reference("webrtc/ice/viewer")

    def viewer_ice_listener(event):
        candidate = event.data
        if candidate:
            pc.addIceCandidate(candidate)

    viewer_ice_ref.listen(viewer_ice_listener)

    # Send Pi ICE candidates
    @pc.on("icecandidate")
    def on_ice(cand):
        if cand:
            ice_ref.push(cand.toJSON())

    print("Pi WebRTC running...")

asyncio.run(run())
