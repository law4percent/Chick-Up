# PROCESS_A_FLOW.md
> `lib/processes/process_a.py` — Video Streaming Process

---

## Overview

Process A owns everything related to live video streaming.
It captures frames from a camera (USB webcam or Picamera2), passes them through
a thread-safe `SharedFrameBuffer`, and streams them to the mobile app via WebRTC
with TURN relay support. It has no display output and does no hardware control.

---

## Responsibilities

- Camera initialization and cleanup
- Firebase initialization (singleton — safe to call alongside Process B)
- WebRTC peer lifecycle (offer/answer signaling, ICE, TURN)
- Frame capture loop at ~100 FPS target
- `live_status` Event management (set on WebRTC connected, cleared on disconnect)

---

## Dependencies

| Module                  | Role                                              |
|-------------------------|---------------------------------------------------|
| `camera_controller`     | Camera init/cleanup, `capture_array()` shim       |
| `webrtc_peer`           | WebRTC peer, Firebase signaling, TURN relay       |
| `firebase_rtdb`         | Firebase app initialization (singleton)           |
| `logger`                | `get_logger("process_a.py")`                      |

---

## Startup Sequence

```
process_A(process_A_args)
│
├── 1. Unpack args
│       TASK_NAME, live_status, status_checker,
│       FRAME_DIMENSION, IS_WEB_CAM, CAMERA_INDEX,
│       USER_CREDENTIAL, TURN_SERVER_URL/USERNAME/PASSWORD
│
├── 2. Init Camera
│       camera.config_camera(IS_WEB_CAM, CAMERA_INDEX, FRAME_DIMENSION)
│       → returns capture object with unified capture_array() API
│       → on CameraError: log error, clear status_checker, return
│
├── 3. Init Firebase
│       firebase_rtdb.initialize_firebase()
│       → singleton — safe if Process B already initialized it
│       → on FirebaseInitError: log error, clear status_checker,
│                               cleanup camera, return
│
├── 4. Setup SharedFrameBuffer
│       Thread-safe lock + Event between capture loop and WebRTC track
│
├── 5. Create asyncio event loop
│       asyncio.new_event_loop() on this process's thread
│
├── 6. Register connection state callback
│       on_connection_state_change(state):
│           "connected"                     → live_status.set()
│           "disconnected"/"failed"/"closed"→ log warning, live_status.clear()
│
├── 7. Init WebRTC Peer
│       run_webrtc_peer(user_uid, device_uid, capture, frame_dimension,
│                       on_connection_state_change, frame_buffer,
│                       turn_server_url, turn_username, turn_password)
│       → starts Firebase offer polling internally
│       → on WebRTCStartError: log error, clear status_checker,
│                              cleanup camera, return
│
└── 8. Start streaming loop
        _streaming_loop() — see below
```

---

## Streaming Loop

Runs inside `loop.run_until_complete(_streaming_loop())` — async, 10ms sleep per tick.

```
while status_checker.is_set():
│
├── capture.capture_array()
│       → None frame: log warning, clear status_checker, break
│
├── cv2.resize(frame, (width, height))
│
├── frame_buffer.update(frame)
│       → WebRTC CameraVideoTrack.recv() reads from here
│
├── frame_count++
│
└── every 60 seconds:
        log FPS and total frame count (info)
```

---

## Shutdown Sequence

Triggered by `status_checker` being cleared (by any process) or an exception.

```
finally (always runs):
│
├── webrtc_peer_instance.stop()
│       → closes RTCPeerConnection, deletes Firebase signaling refs
│       → on WebRTCStopError: log warning (non-fatal)
│
├── _safe_cleanup(capture, IS_WEB_CAM)
│       camera.clean_up_camera()
│       → on failure: log warning
│
├── loop.close()
│       → silently ignored on failure
│
└── log "Process stopped" (info)
```

---

## SharedFrameBuffer

Decouples the synchronous camera capture loop from the async WebRTC track.

| Method           | Description                                      |
|------------------|--------------------------------------------------|
| `update(frame)`  | Write new frame under lock, set `_new_frame` event |
| `get()`          | Read latest frame copy under lock                |
| `wait_for_frame(timeout)` | Block until new frame is available      |
| `clear_event()`  | Reset the `_new_frame` event                     |

The WebRTC `CameraVideoTrack.recv()` calls `frame_buffer.get()` on every video
frame request rather than calling `capture_array()` directly — this prevents
the async WebRTC loop from blocking on camera I/O.

---

## WebRTC Internals (via `webrtc_peer.py`)

| Stage              | Detail                                                          |
|--------------------|-----------------------------------------------------------------|
| Signaling          | Firebase RTDB `/liveStream/{userUid}/{deviceUid}/`              |
| Offer polling      | 500ms interval, picks up new offers by timestamp comparison     |
| ICE servers        | 2× Google STUN + TURN (UDP + TCP transports) if configured     |
| Bitrate limit      | SDP injection: `b=AS:1500` / `b=TIAS:1500000`                  |
| ICE candidate cap  | Max 10 candidates sent to Firebase per connection               |
| Reconnect          | Automatic — new offer triggers new `RTCPeerConnection`          |
| Internal logging   | `_log` (warning/error only) inside async callbacks              |

---

## Camera Modes

| Mode       | Condition          | Capture object         |
|------------|--------------------|------------------------|
| USB Webcam | `IS_WEB_CAM=True`  | OpenCV `VideoCapture`  |
| Picamera2  | `IS_WEB_CAM=False` | `Picamera2` instance   |

Both expose identical `capture_array()` via the `camera_controller` shim.
No branching in Process A or `CameraVideoTrack`.

---

## Error Handling Summary

| Scenario                     | Behaviour                                          |
|------------------------------|----------------------------------------------------|
| Camera init fails            | Log error, clear status_checker, return            |
| Firebase init fails          | Log error, clear status_checker, cleanup cam, return |
| WebRTC peer start fails      | Log error, clear status_checker, cleanup cam, return |
| Empty frame from camera      | Log warning, clear status_checker, break loop      |
| WebRTC state: disconnected   | Log warning, clear live_status                     |
| WebRTC stop fails            | Log warning (non-fatal, cleanup continues)         |
| Camera cleanup fails         | Log warning (non-fatal)                            |
| Unexpected loop exception    | Log error, clear status_checker                    |
| KeyboardInterrupt            | Log warning, clear status_checker                  |

---

## Logging Contract

Process A uses `get_logger("process_a.py")` and logs at `info`, `warning`, `error`.
Services it calls (`camera_controller`, `firebase_rtdb`, `webrtc_peer` public API)
are silent — they raise only. Internal async callbacks inside `webrtc_peer` use
their own `_log` at `warning`/`error` only, since exceptions cannot propagate
from event loop callbacks.