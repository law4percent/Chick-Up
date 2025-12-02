## Live Streaming with WebRTC and Firestore

Below is a clean, working starter example:

- **Raspberry Pi** → sends video using WebRTC
- **React Native** → receives and displays the stream
- **Firebase Realtime Database or Firestore** → used only for signaling
(exchanging offer/answer/ICE)

This is the standard architecture:

```
Raspberry Pi Camera → WebRTC → ICE → React Native (viewer)
                       ↑           ↑
                   Firebase Signaling (offer/answer)
```

### ✅ PART 1 — Raspberry Pi (Python WebRTC Sender)

Use aiortc, the most stable WebRTC library for Python.

**Install dependencies**

```bash
sudo apt update
sudo apt install python3-pip
pip3 install aiortc opencv-python av firebase_admin
```

**Raspberry Pi WebRTC sender (sender.py)**

[text](sender.py)


### ✅ PART 2 — Firebase Signaling Structure


Create a Firestore collection:

```bash
webrtc/
   offer      (React Native creates)
   answer     (Raspberry Pi writes)
   viewer_ice (React Native writes)
   raspi_ice  (Raspberry Pi writes)
```



### ✅ PART 3 — React Native Viewer (WebRTC Client)

Install WebRTC for React Native:

```bash
npm install react-native-webrtc
```


**React Native WebRTC viewer (Viewer.js)**

[text](View.js)




### Result

✔ Raspberry Pi streams live camera feed
✔ WebRTC sends real-time video (50–200ms delay)
✔ React Native receives and plays the stream
✔ Works anytime, anywhere with internet

This is already a working minimal system, but I can also give you:

✅ TURN server setup (to make it work behind firewalls)
✅ Better architecture
✅ Pi → Cloudflare Tunnel → RN (no port forwarding)
✅ Multi-viewer support






## WebRTC Signaling Using Firebase Realtime Database (RTDB)

Important:
RTDB works, but is slightly more fragile due to overwrite issues.
Still, this is the correct structure.


## 📁 RTDB Structure

Use a structure like this:
```
webrtc/
   offer/
      sdp: "...offer SDP..."
   answer/
      sdp: "...answer SDP..."
   ice/
      viewer/
         candidate1
         candidate2
         ...
      raspi/
         candidate1
         candidate2
         ...
```

This prevents overwriting and keeps ICE candidates separated.

## 🟦 PART 1 — Raspberry Pi (Python WebRTC sender, RTDB version)
**Install**
```bash
pip3 install aiortc opencv-python av firebase-admin
```

**sender_rtdb.py**

[text](sender_rtdb.py)



🟩 PART 2 — React Native WebRTC Viewer (RTDB version)
**Install dependencies**
```bash
npm install react-native-webrtc @react-native-firebase/app @react-native-firebase/database
```

**ViewerRTDB.js**

[text](ViewerRTDB.js)



### 🚀 Workflow Summary (RTDB version)
**Step 1 — React Native**

- Creates offer → writes to /webrtc/offer

- Sends viewer ICE → writes to /webrtc/ice/viewer

**Step 2 — Raspberry Pi**

- Reads /webrtc/offer

- Creates answer → writes to /webrtc/answer

- Sends raspi ICE → writes to /webrtc/ice/raspi

**Step 3 — Both sides**

- Listen for each other's ICE candidates

- WebRTC completes connection

- RTDB is no longer used

- P2P stream takes over (fast, low latency)