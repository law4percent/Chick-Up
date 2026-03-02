# Chick-Up 🐣

> A smart IoT monitoring and automation system for small-scale poultry farming,
> built on Raspberry Pi with a companion mobile app.

---

## What Is Chick-Up?

Chick-Up is a Raspberry Pi-based IoT device designed to help small poultry farmers
automate and remotely monitor their chick feeding and watering systems.
The device pairs with a mobile app via Firebase, allowing farmers to watch a live
camera feed, trigger feed dispensing or water refilling remotely, set automatic
schedules, and review usage analytics — all from their phone.

The device also operates independently: physical keypad buttons let the farmer
dispense feed or refill water manually even without phone connectivity, and the
onboard LCD shows real-time feed and water levels at a glance.

---

## Key Features

**Remote monitoring**
Live video stream from the enclosure, accessible from anywhere via the mobile app.
Powered by WebRTC with TURN relay support for networks behind strict NAT or CGNAT.

**Automated feeding and watering**
Feed dispensing runs on a configurable countdown timer.
Water refilling runs automatically when the level drops below a set threshold,
and stops when the tank reaches capacity.

**Schedule-based feeding**
The farmer sets weekly schedules from the app. The device checks the current time
every 100ms and triggers dispensing automatically when a scheduled time is reached,
with a 60-second cooldown to prevent duplicate triggers.

**Physical keypad control**
A 4×4 matrix keypad provides direct hardware control without needing the app.
`*` dispenses feed, `#` refills water. Keypad presses are mirrored to Firebase
so the app sees them as regular button events.

**Live LCD status**
A 16×2 I2C LCD shows current feed and water fill percentages, active dispensing
or refilling state, and low-level warnings — updated every second.

**Analytics logging**
Every dispense and refill action is logged to Firebase with volume, timestamp,
day of week, and source (app or keypad), matching the mobile app's analytics
schema so both sources appear in the same history screen.

**Secure device pairing**
On first boot, the device generates a 6-character code displayed on the LCD.
The farmer enters it in the app to pair their account to the device.
Credentials are stored locally and re-validated against Firebase on every boot.

---

## Hardware

| Component            | Detail                                      |
|----------------------|---------------------------------------------|
| Raspberry Pi         | Primary compute unit                        |
| USB Webcam / Picamera2 | Live video capture                        |
| Ultrasonic sensors ×2 | Feed level (left), water level (right)    |
| Relay module ×2      | Feed motor (GPIO 17), water motor (GPIO 27) |
| 4×4 Matrix Keypad    | Physical input — feed (`*`) and water (`#`) |
| 16×2 I2C LCD         | Local status display (address `0x27`)       |

---

## System Architecture

The device runs two parallel processes managed by `main.py`:

```
main.py
├── Authentication (LCD + keypad pairing flow)
│
├── Process A — Video Streaming
│       Camera → SharedFrameBuffer → WebRTC → Mobile App
│       Firebase signaling (offer/answer/ICE)
│       TURN relay for NAT traversal
│
└── Process B — Hardware Control
        Ultrasonic sensors → feed/water level %
        Keypad scan → physical button events
        Firebase RTDB → app buttons, schedules, user settings
        Motor relays → feed dispense, water refill
        LCD → real-time status
        Firebase → sensor data, analytics, button timestamps
```

The two processes share two IPC Events:

- `live_status` — set when WebRTC is connected, cleared on disconnect
- `status_checker` — global health flag; any process clears it on fatal error,
  which signals the system to begin shutdown

---

## Firebase Structure

```
/
├── liveStream/{userUid}/{deviceUid}/
│       offer              ← mobile app writes WebRTC offer
│       answer             ← device writes WebRTC answer
│       iceCandidates/
│           raspi/         ← device ICE candidates
│           mobile/        ← app ICE candidates
│       connectionState    ← device writes current WebRTC state
│       liveStreamButton   ← app toggles to request stream
│
├── buttons/{userUid}/{deviceUid}/
│       feedButton/lastUpdateAt   ← app or keypad writes SERVER_TIMESTAMP
│       waterButton/lastUpdateAt  ← app or keypad writes SERVER_TIMESTAMP
│
├── schedules/{userUid}/
│       {scheduleId}/
│           time     "14:30"
│           days     [1, 3, 5]    (JS weekday indices)
│           enabled  true
│
├── settings/{userUid}/
│       feed/thresholdPercent
│       feed/dispenseVolumePercent
│       water/thresholdPercent
│       water/autoRefillEnabled
│
├── sensors/{userUid}/{deviceUid}/
│       feedLevel   float (%)
│       waterLevel  float (%)
│       updatedAt   "MM/DD/YYYY HH:MM:SS"
│
├── analytics/logs/{userUid}/
│       {pushId}/
│           action         "dispense" | "refill"
│           type           "feed" | "water"
│           volumePercent  float
│           timestamp      Unix ms
│           date           "MM/DD/YYYY"
│           time           "HH:MM:SS"
│           dayOfWeek      0–6 (JS convention)
│           userId         string
│           source         "keypad" | "app"
│
├── device_code/{code}/
│       deviceUid   string
│       createdAt   Unix ms
│       status      "pending" | "paired"
│       userUid     string     (written by app on pairing)
│       username    string     (written by app on pairing)
│
└── users/{userUid}/
        (existence checked during credential re-validation)
```

---

## Project Structure

```
chick-up/
├── main.py
├── credentials/
│       .env
│       serviceAccountKey.json
│       credentials.txt              ← written after pairing
│
└── lib/
    ├── processes/
    │       process_a.py             ← video streaming
    │       process_b.py             ← hardware control
    │
    └── services/
        ├── logger.py                ← custom rotating file logger
        ├── utils.py                 ← path / file utilities
        ├── auth.py                  ← pairing + credential management
        ├── firebase_rtdb.py         ← Firebase RTDB wrapper
        ├── webrtc_peer.py           ← WebRTC peer + signaling
        └── hardware/
                camera_controller.py
                motor_controller.py
                keypad_controller.py
                lcd_controller.py
                ultrasonic_contoller.py
```

---

## Logging System

Chick-Up uses a custom rotating logger (`lib/services/logger.py`).
Log files are written to `logs/` in the project root.

| File          | Contents                                 |
|---------------|------------------------------------------|
| `error.log`   | Errors only                              |
| `warning.log` | Warnings only                            |
| `info.log`    | Info messages                            |
| `debug.log`   | Debug messages                           |
| `bug.log`     | Critical / unexpected bugs               |
| `all.log`     | All of the above combined                |

Each file rotates at 10 MB and keeps the last 5 backups.

**Logging contract:**
- Processes (`main.py`, `process_a.py`, `process_b.py`) log freely at all levels.
- Services (`auth`, `firebase_rtdb`, `webrtc_peer`, `camera_controller`,
  `motor_controller`) raise exceptions only — no internal logging.
- Exception messages are logged by the calling process with full context.

---

## Environment Variables (`.env`)

| Variable           | Description                                        |
|--------------------|----------------------------------------------------|
| `PRODUCTION_MODE`  | `true` = real device pairing via LCD+app           |
| `DEVICE_UID`       | Unique identifier for this device                  |
| `IS_WEB_CAM`       | `true` = USB webcam, `false` = Picamera2           |
| `CAMERA_INDEX`     | Camera device index (webcam only)                  |
| `FRAME_WIDTH`      | Capture width in pixels                            |
| `FRAME_HEIGHT`     | Capture height in pixels                           |
| `TURN_SERVER_URL`  | TURN relay server URL                              |
| `TURN_USERNAME`    | TURN credentials username                          |
| `TURN_PASSWORD`    | TURN credentials password                          |
| `TEST_USER_UID`    | Dev mode — bypasses real pairing                   |
| `TEST_USERNAME`    | Dev mode — bypasses real pairing                   |

---

## First Boot Flow

```
1. Power on Raspberry Pi
2. main.py starts, LCD shows "Chick-Up / Initializing..."
3. No credentials.txt found → LCD shows menu:
       [A] Login
       [B] Shutdown
4. Press [A] → LCD shows 6-character pairing code
5. Open mobile app → enter code
6. App writes userUid + username to Firebase /device_code/{code}/
7. Device detects "paired" status, saves credentials.txt
8. Process A and Process B start
```

---

## Subsequent Boot Flow

```
1. Power on Raspberry Pi
2. main.py reads credentials.txt
3. Re-validates userUid against Firebase /users/{userUid}
4. Valid → inject credentials, start Process A and Process B
5. Invalid → delete credentials.txt, show LCD menu (re-pair)
```