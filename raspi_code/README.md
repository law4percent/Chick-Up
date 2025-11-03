# Raspberry Pi AI Integration — Project Outline

## Repo layout
```
raspi_code/
├─ README.md
├─ main.py                      # Entry point: orchestrates services
├─ venv/                        # Python virtual environment
└─ lib/
   └─ services/
      ├─ firebase_credentials.py  # Firebase Realtime DB helpers (auth, read/write)
      ├─ detection.py            # Model loading + inference + annotation helpers
      ├─ live_stream.py          # Streaming server / RTSP or WebRTC wrapper + trigger logic
      └─ alert.py                # Intruder detection + alert sending logic
```

## Phases & Tasks

### Phase 3 — AI on Raspberry Pi
**Goal:** Run the model reliably on the Pi and draw detections on frames.
- **Task 3.1 — Inference performance testing**
  - Run sample inference loop on Pi (CPU / GPU / NPU if available).
  - Measure: FPS, latency per frame, memory usage, and CPU load.
  - Log results to file for each model/config.
  - Acceptance criteria: Stable inference (no OOM), baseline FPS recorded.
- **Task 3.2 — Annotation integration**
  - Integrate bounding-box / label drawing into the frame pipeline.
  - Ensure annotations are lightweight (draw on a copy of frame).
  - Acceptance criteria: Annotated frames are produced and viewable locally or via stream.

### Phase 4 — Counting feature
**Goal:** Count chickens in each frame/period and store counts.
- **Task 4.1 — Chicken counting algorithm**
  - Implement counting logic (e.g., track object IDs across frames or simple per-frame count with smoothing).
  - Consider debounce/window to avoid double-counting.
  - Acceptance criteria: Count per time window (e.g., per minute) produced.
- **Task 4.2 — Database update**
  - Send counts to Firebase Realtime DB (RTDB) with timestamp and metadata.
  - Acceptance criteria: RTDB receives records with `{timestamp, count, camera_id}`.

### Phase 5 — Alert feature
**Goal:** Raise an alert when any non-normal entity is detected (treat all classes as intruder).
- **Task 5.1 — Intruder annotation**
  - When detection confidence > threshold, mark detected object as `intruder`.
  - Do not distinguish intruder types — all classes are `intruder`.
  - Acceptance criteria: Annotated frames (or event) flagged with `intruder=true`.
- **Task 5.2 — Database update**
  - Send intruder events to RTDB with image reference (or snapshot URL), timestamp, and confidence.
  - Acceptance criteria: RTDB receives events with `{timestamp, intruder: true, snapshot_url/confidence}`.

### Phase 6 — Live streaming
**Goal:** Stream video on-demand from the Pi based on remote trigger.
- **Task 6.1 — Triggered stream**
  - Implement trigger reading from RTDB (or via pub/sub): if `stream_button == ON`, start streaming.
  - Streaming options: simple MJPEG stream, RTSP, or WebRTC (depends on requirements).
  - Acceptance criteria: When app toggles button, Pi starts/stops stream and the client can view it.

### Phase 7 — User credentials (phone number)
**Goal:** Make Raspberry Pi able to read user's phone number credentials from RTDB for verification or labeling.
- **Task 7.1 — Read phone-number credentials**
  - Securely fetch user phone numbers from RTDB using `firebase_credentials.py`.
  - Do not store sensitive data in plaintext on device; use minimal caching and appropriate access rules.
  - Acceptance criteria: Pi can read `user_credentials/{user_id}/phone_number` and use it as needed.

## Implementation notes & responsibilities (file-level)
- `main.py`
  - Initialize services, start threads (detection, streaming, DB listener).
  - Graceful shutdown & health checks.
- `lib/services/firebase_credentials.py`
  - Wrap Firebase initialization, authentication, read/write helpers, and a simple listener for RTDB changes (stream trigger, phone credentials).
- `lib/services/detection.py`
  - Load model (TFLite / ONNX / PyTorch Mobile).
  - Provide `run_inference(frame) -> detections` and `annotate_frame(frame, detections) -> annotated_frame`.
  - Provide helper to convert detections to event payloads (counts/intruder).
- `lib/services/live_stream.py`
  - Provide `start_stream()` / `stop_stream()` and optionally `get_stream_url()`.
  - Implement efficient frame source (use the same frames from detection or a dedicated capture to avoid contention).
- `lib/services/alert.py`
  - Build and push alert payloads to RTDB and optionally to other channels (SMS/email) later.
  - Provide snapshot capture helper.

## Testing & debugging
- Provide `tests/` or `tools/` scripts to:
  - Run model inference on sample video and dump annotated output.
  - Run counting on recorded footage and produce `.csv` logs.
  - Simulate RTDB updates for live-stream trigger and intruder events.
- Logging: structured JSON logs are recommended for later parsing.

## Security & data privacy
- Use Firebase security rules limiting read/write operations.
- Avoid storing user phone numbers on disk unencrypted.
- Rotate service credentials when possible.

## Example RTDB schema (suggested)
**To Be Discussed Soon**


## Quick checklist (copy into issue tracker)
- [ ] Add model benchmark script + logging (Phase 3.1)
- [ ] Hook annotate_frame into main pipeline (Phase 3.2)
- [ ] Implement counting algorithm + smoothing (Phase 4.1)
- [ ] Push counts to RTDB (Phase 4.2)
- [ ] Mark detections as `intruder` and snapshot (Phase 5.1)
- [ ] Push alerts to RTDB (Phase 5.2)
- [ ] Add RTDB listener for streaming toggle and implement start/stop stream (Phase 6.1)
- [ ] Implement secure RTDB read for phone credentials (Phase 7.1)
