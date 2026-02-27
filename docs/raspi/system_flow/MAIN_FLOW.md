# MAIN_FLOW.md
> `main.py` — System Entry Point

---

## Overview

`main.py` is the single boot entry point for the Chick-Up Raspberry Pi system.
It owns hardware init, authentication, credential injection, and process lifecycle.
It never does hardware control or streaming itself — those are fully delegated to
Process A and Process B.

---

## Shared IPC Primitives

Declared in `__main__` and passed into both processes via their args dicts.

| Primitive       | Type                    | Purpose                                                  |
|-----------------|-------------------------|----------------------------------------------------------|
| `live_status`   | `multiprocessing.Event` | Set when WebRTC is connected. Cleared on disconnect.     |
| `status_checker`| `multiprocessing.Event` | Global health flag. Any process clears it on fatal error.|

---

## Boot Sequence

```
python main.py
│
├── 1. Load .env
│       credentials/.env → DEVICE_UID, CAMERA_INDEX, IS_WEB_CAM,
│                          FRAME_WIDTH, FRAME_HEIGHT, TURN_*, TEST_*
│
├── 2. Init Hardware (LCD + Keypad)
│       LCD_I2C(address=0x27, size=LCD_16x2)
│       Keypad4x4()
│       → on failure: log error, return (system halts)
│
├── 3. Authentication
│       AuthService.authenticate()
│       │
│       ├── credentials/credentials.txt EXISTS?
│       │       YES → re-validate against Firebase /users/{userUid}
│       │               valid   → load credentials, skip pairing
│       │               invalid → delete credentials.txt → show LCD menu
│       │
│       └── credentials.txt MISSING → show LCD menu
│               [A] Login  → pairing flow
│               [B] Shutdown → SystemExit (clean exit, nothing logged)
│
│   Exceptions caught and logged by main:
│       FirebaseInitError  → log error,   return
│       CredentialsError   → log error,   return
│       PairingError       → log error,   return
│       ValidationError    → log warning, return
│       SystemExit         → silent return
│       Exception          → log error,   return
│
├── 4. Credential Injection
│       user_credentials injected into:
│           process_A_args["USER_CREDENTIAL"]
│           process_B_args["USER_CREDENTIAL"]
│
├── 5. Spawn Processes
│       task_A = Process(target=process_A, kwargs=process_A_args)
│       task_B = Process(target=process_B, kwargs=process_B_args)
│       task_A.start()
│       task_B.start()
│
└── 6. Wait + Shutdown
        task_A.join()
        task_B.join()
        │
        ├── KeyboardInterrupt → log warning
        └── finally (always runs):
                terminate any alive tasks
                lcd.clear()
                keypad.cleanup()
```

---

## Process Args Passed

### process_A_args

| Key               | Type   | Value / Source                        |
|-------------------|--------|---------------------------------------|
| `TASK_NAME`       | str    | `"Process A"`                         |
| `live_status`     | Event  | shared IPC                            |
| `status_checker`  | Event  | shared IPC                            |
| `FRAME_DIMENSION` | dict   | `{"width": FRAME_WIDTH, "height": FRAME_HEIGHT}` |
| `IS_WEB_CAM`      | bool   | `.env`                                |
| `CAMERA_INDEX`    | int    | `.env`                                |
| `USER_CREDENTIAL` | dict   | injected after auth                   |
| `TURN_SERVER_URL` | str    | `.env`                                |
| `TURN_USERNAME`   | str    | `.env`                                |
| `TURN_PASSWORD`   | str    | `.env`                                |

### process_B_args

| Key                      | Type   | Value / Source          |
|--------------------------|--------|-------------------------|
| `TASK_NAME`              | str    | `"Process B"`           |
| `status_checker`         | Event  | shared IPC              |
| `live_status`            | Event  | shared IPC              |
| `USER_CREDENTIAL`        | dict   | injected after auth     |
| `DISPENSE_COUNTDOWN_TIME`| int    | `60000` ms (1 minute)   |
| `LCD_I2C_ADDR`           | int    | `0x27`                  |

---

## .env Variables

| Variable         | Used For                              |
|------------------|---------------------------------------|
| `PRODUCTION_MODE`| `true` = real pairing, `false` = test credentials |
| `DEVICE_UID`     | Unique device identifier              |
| `CAMERA_INDEX`   | Webcam device index                   |
| `IS_WEB_CAM`     | `true` = USB webcam, `false` = Picamera2 |
| `FRAME_WIDTH`    | Capture/stream width in pixels        |
| `FRAME_HEIGHT`   | Capture/stream height in pixels       |
| `TEST_USER_UID`  | Dev mode — skip real pairing          |
| `TEST_USERNAME`  | Dev mode — skip real pairing          |
| `TURN_SERVER_URL`| TURN relay server URL                 |
| `TURN_USERNAME`  | TURN credentials                      |
| `TURN_PASSWORD`  | TURN credentials                      |

---

## Error Handling Summary

| Scenario                        | Behaviour                        |
|---------------------------------|----------------------------------|
| LCD / Keypad init fails         | Log error, halt (return)         |
| Firebase unreachable at auth    | Log error, halt (return)         |
| Pairing fails                   | Log error, halt (return)         |
| Credentials file corrupted      | Log error, halt (return)         |
| Firebase re-validation fails    | Log warning, halt (return)       |
| User selects Shutdown from LCD  | Silent return (no log)           |
| KeyboardInterrupt during join   | Log warning, terminate processes |
| Process A or B crashes          | Other process continues running  |

---

## Logging Contract

`main.py` is a **process** — it uses `get_logger("main.py")` and logs freely.
Services it calls (`auth`, `firebase_rtdb`) are silent — they raise only.
All exception messages are logged here at the appropriate level.