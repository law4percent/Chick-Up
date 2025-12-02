import cv2
import asyncio
import json
from aiortc import RTCPeerConnection, VideoStreamTrack
from firebase_admin import credentials, firestore, initialize_app
from av import VideoFrame

# Firebase init
cred = credentials.Certificate("serviceAccountKey.json")
initialize_app(cred)
db = firestore.client()

class CameraStream(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.cap = cv2.VideoCapture(0)

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        ret, frame = self.cap.read()

        if not ret:
            return None

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        video_frame = VideoFrame.from_ndarray(frame, format="rgb24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame

async def run():
    pc = RTCPeerConnection()
    pc.addTrack(CameraStream())

    offer_doc = db.collection("webrtc").document("offer")
    answer_doc = db.collection("webrtc").document("answer")

    print("Waiting for viewer offer...")
    while True:
        snap = offer_doc.get()
        if snap.exists:
            break
        await asyncio.sleep(1)

    offer = snap.to_dict()
    await pc.setRemoteDescription(offer["sdp"])

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    answer_doc.set({"sdp": json.loads(pc.localDescription.sdp), "type": "answer"})
    print("Sent answer.")

    @pc.on("icecandidate")
    def on_ice(cand):
        if cand:
            db.collection("webrtc").document("raspi_ice").set({
                "candidate": cand.toJSON()
            })

asyncio.run(run())
