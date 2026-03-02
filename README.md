# Chick-Up 🐣

> A smart IoT monitoring and automation system for small-scale poultry farming,
> built on Raspberry Pi with a companion mobile app.

---

## What Is Chick-Up?

Chick-Up is a Raspberry Pi–based IoT device that helps small poultry farmers
automate and remotely monitor their chick feeding and watering systems.
The device pairs with a mobile app via Firebase, allowing farmers to watch a
live camera feed, trigger feed dispensing or water refilling remotely, set
automatic schedules, and review usage analytics — all from their phone.

The device also operates independently: physical keypad buttons let the farmer
dispense feed or refill water directly, and the onboard LCD shows real-time
feed and water levels at a glance — no phone required.

---

## Repository Structure

```
chick-up/                          ← Raspberry Pi code (this repo)
│
├── main.py                        ← Entry point — auth loop + process management
├── credentials/
│   ├── .env                       ← Device configuration (not committed)
│   ├── serviceAccountKey.json     ← Firebase service account (not committed)
│   └── user_credentials.txt       ← Written after pairing (not committed)
│
└── lib/
    ├── processes/
    │   ├── process_a.py           ← Video streaming (WebRTC)
    │   └── process_b.py           ← Hardware control (sensors, motors, LCD, Firebase)
    │
    └── services/
        ├── auth.py                ← Device pairing + credential management
        ├── firebase_rtdb.py       ← Firebase RTDB wrapper (read, schedule, helpers)
        ├── logger.py              ← Custom rotating file logger
        ├── utils.py               ← Path + file utilities
        ├── webrtc_peer.py         ← WebRTC peer connection + ICE/TURN
        └── hardware/
            ├── camera_controller.py
            ├── motor_controller.py
            ├── keypad_controller.py
            ├── lcd_controller.py
            └── ultrasonic_controller.py

app/                               ← Mobile app (separate repo / folder)
    See README_APP.md for full app documentation.
```

---

## Key Features

**Remote monitoring**
Live video stream from the enclosure, accessible from anywhere via the mobile
app. Powered by WebRTC with TURN relay support for networks behind strict NAT
or CGNAT.

**Automated feeding and watering**
Feed dispensing runs on a configurable countdown timer (5 s – 5 min).
Water refilling runs automatically when the level drops below a configured
threshold and stops when the tank reaches capacity (95% hard cap).

**Schedule-based feeding**
The farmer sets weekly schedules from the app (day of week + time + volume).
The Pi checks the schedule every ~100 ms and triggers dispensing automatically
when a scheduled time is reached, firing exactly once per minute window even
if the Pi reboots mid-minute.

**Physical keypad control**
A 4×4 matrix keypad provides direct hardware control without needing the app.
`*` dispenses feed, `#` refills water, hold `D` for 3 seconds to log out.
Keypad presses write a `SERVER_TIMESTAMP` to Firebase so the app sees them
as regular button events in the analytics history.

**Live LCD status**
A 16×2 I2C LCD shows current feed and water fill percentages, active motor
state (`DISPENSING...` / `REFILLING...`), and low-level warnings — updated
every second.

**Analytics logging**
Every dispense and refill action is logged to Firebase with volume,
timestamp, day of week, and source (`app` / `keypad` / `schedule`).
Analytics are written by both the app (on button press) and the Pi (when the
motor cycle completes), so Pi-side volume measurements reflect real sensor data.

**Secure device pairing**
On first boot, the Pi generates a 6-character code displayed on the LCD.
The farmer enters it in the app to link their account to the device.
Credentials are stored locally and re-validated against Firebase on every boot.

**Clean logout and re-pairing**
Hold `D` for 3 seconds to log out from the keypad at any time. The Pi
terminates both processes, deletes local credentials, and removes
`users/{uid}/linkedDevice` from Firebase — the app reacts immediately
via its real-time subscription and shows "No Device" without a manual refresh.

---

## Hardware

| Component | Detail |
|-----------|--------|
| Raspberry Pi | Primary compute unit (any model with GPIO + camera) |
| USB Webcam or Picamera2 | Live video capture |
| Ultrasonic sensor × 2 | Feed level (trigger GPIO 23, echo GPIO 24), Water level (trigger GPIO 5, echo GPIO 6) |
| Relay module × 2 | Feed motor (GPIO 17), water motor (GPIO 27) |
| 4×4 Matrix Keypad | Physical input — rows GPIO 12/16/20/21, cols GPIO 26/19/13/6 |
| 16×2 I2C LCD | Local status display, I2C address `0x27` |

---

## System Architecture

`main.py` manages the full lifecycle in a single loop:

```
main.py  (outer loop — handles logout + re-pairing)
│
├── AuthService.authenticate()
│       LCD + keypad pairing menu
│       6-char code → Firebase → user pairs from app
│       Re-validates saved credentials on every boot
│
├── Process A  (video streaming)
│       Camera → SharedFrameBuffer
│       WebRTC peer connection (aiortc)
│       ICE/TURN via TURN relay server
│       Firebase signaling (offer / answer / ICE candidates)
│
└── Process B  (hardware control)
        Ultrasonic sensors → feed % + water %
        Keypad scan → physical button events
        Firebase RTDB → app buttons, schedules, settings
        Motor relays → feed dispense, water refill
        LCD → real-time status display
        Firebase → sensor writes, analytics, button timestamps
```

Process A and Process B share three `multiprocessing.Event` objects:

| Event | Purpose |
|-------|---------|
| `live_status` | Set when WebRTC is connected; Process B reads this to know the stream is active |
| `status_checker` | Global health flag; any process clears it on a fatal error to signal shutdown |
| `logout_requested` | Set by Process B when user holds D key; main.py terminates both processes and calls logout |

---

## Firebase Structure

```
/
├── liveStream/{userUid}/{deviceUid}/
│       offer                   ← app writes WebRTC SDP offer
│       answer                  ← Pi writes WebRTC SDP answer
│       iceCandidates/raspi/    ← Pi ICE candidates
│       iceCandidates/mobile/   ← app ICE candidates
│       connectionState         ← Pi writes current WebRTC state
│       liveStreamButton        ← app toggles to request stream
│
├── buttons/{userUid}/{deviceUid}/
│       feedButton/lastUpdateAt   ← SERVER_TIMESTAMP (app or Pi keypad)
│       waterButton/lastUpdateAt
│
├── schedules/{userUid}/{scheduleId}/
│       time            "HH:MM"
│       days            [1, 3, 5]    JS weekday indices (0=Sun)
│       enabled         bool
│       volumePercent   number
│
├── settings/{userUid}/
│       feed/
│           thresholdPercent
│           dispenseVolumePercent
│           dispenseCountdownMs
│       water/
│           thresholdPercent
│           autoRefillEnabled
│           autoRefillThreshold
│       updatedAt
│
├── sensors/{userUid}/{deviceUid}/
│       feedLevel   float %
│       waterLevel  float %
│       updatedAt   "MM/DD/YYYY HH:MM:SS"
│
├── analytics/logs/{userUid}/{pushId}/
│       action          "dispense" | "refill"
│       type            "feed" | "water"
│       volumePercent   float
│       timestamp       Unix ms
│       date            "MM/DD/YYYY"
│       time            "HH:MM:SS"
│       dayOfWeek       0–6 (JS convention — 0=Sun)
│       userId          string
│       source          "app" | "keypad" | "schedule"
│
├── device_code/{code}/
│       deviceUid   string
│       createdAt   Unix ms
│       status      "pending" | "paired" | "expired"
│       userUid     string   (written by app)
│       username    string   (written by app)
│
└── users/{userUid}/
        username
        email
        phoneNumber
        createdAt
        updatedAt
        linkedDevice/
            deviceUid   ← written by app on pairing, deleted by Pi on logout
            linkedAt
```

### Path scoping rationale

| Path | Scoped to | Why |
|------|-----------|-----|
| `sensors/{uid}/{deviceUid}` | User + Device | Live hardware state — specific to the physical Pi |
| `buttons/{uid}/{deviceUid}` | User + Device | Commands sent to a specific physical device |
| `liveStream/{uid}/{deviceUid}` | User + Device | WebRTC session with a specific Pi |
| `settings/{uid}` | User only | Personal preferences (thresholds, timing) — carries over when the Pi is replaced |
| `schedules/{uid}` | User only | Weekly feeding habits belong to the farmer, not the hardware |
| `analytics/{uid}` | User only | Full history survives a Pi swap or re-pairing |

---

## Environment Variables (`credentials/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `PRODUCTION_MODE` | Yes | `true` = real LCD/keypad pairing; `false` = use `TEST_*` credentials |
| `DEVICE_UID` | Yes | Unique identifier for this Pi (e.g. `DEV_001`) |
| `IS_WEB_CAM` | Yes | `true` = USB webcam; `false` = Picamera2 |
| `CAMERA_INDEX` | Yes | Camera device index (webcam: `0`; Picamera2: `0`) |
| `FRAME_WIDTH` | Yes | Capture width in pixels (e.g. `640`) |
| `FRAME_HEIGHT` | Yes | Capture height in pixels (e.g. `480`) |
| `FIREBASE_DATABASE_URL` | Yes | Full RTDB URL from Firebase console |
| `TURN_SERVER_URL` | Yes | TURN relay address `host:port` (e.g. `143.198.45.67:3478`) |
| `TURN_USERNAME` | Yes | TURN credentials username |
| `TURN_PASSWORD` | Yes | TURN credentials password |
| `TEST_USER_UID` | Dev only | Firebase UID used in `PRODUCTION_MODE=false` |
| `TEST_USERNAME` | Dev only | Username used in `PRODUCTION_MODE=false` |

TURN credentials must match the values in the app's `.env`
(`EXPO_PUBLIC_TURN_*`). They are never written to Firebase.

---

## Logging

Chick-Up uses a custom rotating logger (`lib/services/logger.py`).
All logs are written to `logs/` in the project root.

| File | Contents |
|------|----------|
| `error.log` | Errors only |
| `warning.log` | Warnings and above |
| `info.log` | Info and above |
| `debug.log` | Debug and above |
| `all.log` | Everything combined |

Each file rotates at 10 MB and keeps the last 5 backups.

**Contract:** Service modules (`auth`, `firebase_rtdb`, `webrtc_peer`, hardware
controllers) raise exceptions only — no internal logging. All logging is done
by the calling process with full context.

---

## Boot Flow

```
Power on
    ↓
main.py — init LCD + keypad (once, never re-initialized)
    ↓
credentials/user_credentials.txt exists?
    ├── Yes → "Validating..." → Firebase re-validate → if invalid, delete + re-pair
    └── No  → LCD menu: Login / Shutdown
                  ↓ Login
              Pi generates 6-char code → Firebase device_code/{code}/
              LCD: "Code: AB3X7K / Expires in 60s"
              Poll Firebase every 2s for status: "paired"
                  ↓ App pairs
              Save credentials.txt
    ↓
Start Process A (streaming) + Process B (hardware)
    ↓
Monitor processes:
    ├── logout_requested set (D held 3s) → stop both, auth.logout(), loop to menu
    └── processes exit normally → clean shutdown
```

---

## Auto-Run on Boot

See **[AUTORUN.md](AUTORUN.md)** for the complete guide to configuring
a systemd service so `main.py` starts automatically on every boot.

---

## App Documentation

See **[README_APP.md](README_APP.md)** for the companion mobile app —
React Native (Expo), Firebase, WebRTC — including setup, project structure,
Firebase path details, and key design decisions.

---

## Related Documents

| File | Contents |
|------|----------|
| `AUTORUN.md` | systemd service setup for auto-run on boot |
| `README_APP.md` | Mobile app documentation |
| `USER_MANUAL.md` | End-user manual (hardware + app) |
| `MAIN_FLOW.md` | Detailed main.py flow diagram |
| `PROCESS_A_FLOW.md` | Detailed Process A (streaming) flow |
| `PROCESS_B_FLOW.md` | Detailed Process B (hardware control) flow |
| `REFILL_LOGIC.md` | Water refill latch logic explanation |