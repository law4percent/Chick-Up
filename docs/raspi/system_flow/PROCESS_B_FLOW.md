# PROCESS_B_FLOW.md
> `lib/processes/process_b.py` — Hardware Control Process

---

## Overview

Process B owns all physical hardware — sensors, motors, keypad, and LCD.
It runs a 100ms polling loop that reads sensor data and Firebase state, drives
feed and water motors in response, updates the LCD display, and writes analytics
back to Firebase. It also mirrors the `live_status` Event from Firebase so
Process A knows whether streaming should be active.

---

## Responsibilities

- GPIO initialization and cleanup
- Camera-independent hardware: keypad, motors, ultrasonic sensors, LCD
- Reading Firebase RTDB state every 100ms (app buttons, schedules, user settings)
- Motor control: feed dispensing (countdown timer) + water refilling (level-based)
- Physical keypad support: `*` triggers feed, `#` triggers water
- Writing `SERVER_TIMESTAMP` to Firebase on physical keypad press
- Writing analytics to Firebase on action completion
- Pushing sensor readings to Firebase every loop tick
- `live_status` Event sync from Firebase liveStreamButton state

---

## Dependencies

| Module                  | Role                                               |
|-------------------------|----------------------------------------------------|
| `firebase_rtdb`         | Firebase init, RTDB read/write, analytics push     |
| `keypad_controller`     | 4×4 matrix keypad scanning                        |
| `motor_controller`      | Feed (GPIO 17) and water (GPIO 27) relay control  |
| `ultrasonic_contoller`  | Left (feed) and right (water) distance sensors    |
| `lcd_controller`        | 16×2 I2C LCD status display                       |
| `logger`                | `get_logger("process_b.py")`                      |

---

## Startup Sequence

```
process_B(process_B_args)
│
├── 1. Unpack args
│       TASK_NAME, status_checker, live_status,
│       USER_CREDENTIAL, DISPENSE_COUNTDOWN_TIME, LCD_I2C_ADDR
│
├── 2. GPIO setup
│       GPIO.setmode(GPIO.BCM)
│       GPIO.setwarnings(False)
│
├── 3. Init Firebase
│       firebase_rtdb.initialize_firebase()
│       → singleton — safe if Process A already initialized it
│       → on FirebaseInitError: log error, clear status_checker,
│                               GPIO.cleanup(), return
│
├── 4. Build Firebase refs
│       firebase_rtdb.setup_RTDB(user_uid, device_uid)
│       → buttons/*, schedules/*, liveStream/*, settings/*, sensors/*
│
├── 5. Init Hardware
│       keypad.setup_keypad()
│       motor.setup_motors()         ← on MotorSetupError: log error,
│                                       clear status_checker, GPIO.cleanup(), return
│       distance.setup_ultrasonics()
│
├── 6. Init LCD (non-fatal)
│       lcd.setup_lcd(addr=LCD_I2C_ADDR, cols=16, rows=2)
│       → on failure: log warning, continue without LCD (lcd_obj = None)
│       → on success: show "Chick-Up / Initializing..." for 2s
│
└── 7. Start main loop — see below
```

---

## Main Loop (100ms tick)

```
while True:
│
├── Check status_checker
│       not set → log warning, break (triggers finally)
│
├── Read pins (_read_pins_data)
│       keypad.scan_key()
│           "*" → current_feed_physical_button_state = True
│           "#" → current_water_physical_button_state = True
│       distance.read_left_distance()  → feed level %
│       distance.read_right_distance() → water level %
│       → on exception: log error, clear status_checker, break (FATAL)
│
├── Read Firebase (firebase_rtdb.read_RTDB)
│       → current_feed_app_button_state
│       → current_water_app_button_state
│       → current_feed_schedule_state
│       → current_live_button_state
│       → current_user_settings (thresholds, dispense %, auto-refill)
│       → on FirebaseReadError or Exception: log warning (throttled 10s), continue
│           (last known state is preserved — process keeps running)
│
├── Sync live_status
│       current_live_button_state → live_status.set() / live_status.clear()
│
├── Compute level warnings
│       feed_warning  = feed_level  <= feed_threshold_warning
│       water_warning = water_level <= water_threshold_warning
│
├── Physical keypad → Firebase timestamp
│       feed  keypad pressed → _update_button_timestamp(database_ref, "feed")
│       water keypad pressed → _update_button_timestamp(database_ref, "water")
│       → mirrors app's buttonService.updateButtonTimestamp()
│       → on FirebaseWriteError: log warning (non-fatal)
│
├── Button aggregation
│       feed_button_pressed  = (physical OR app_button OR schedule) AND NOT dispensing
│       water_button_pressed = (physical OR app_button)
│
├── Snapshot levels (before action)
│       feed_button_pressed  AND NOT dispense_active → snapshot feed_level
│       water_button_pressed AND NOT refill_active   → snapshot water_level
│
├── Motor logic
│       _dispense_it(...)  → countdown timer-based feed dispensing
│       _refill_it(...)    → level + manual water refill
│
├── Analytics on completion (transition detection)
│       prev_dispense_active=True  AND dispense_active=False
│           → _log_analytics(user_uid, "feed",  feed_before  - feed_now)
│       prev_refill_active=True    AND refill_active=False
│           → _log_analytics(user_uid, "water", water_now    - water_before)
│       → on FirebaseWriteError: log warning (non-fatal)
│
├── Update LCD (every 1 second)
│       _update_lcd_display(...)
│       → silent on failure (LCD errors must not break the loop)
│
└── Push sensor data to Firebase
        sensors/{userUid}/{deviceUid}/feedLevel, waterLevel, updatedAt
        → on exception: log warning (throttled 10s), continue
```

---

## Motor Logic Detail

### Feed Dispensing (`_dispense_it`)

```
feed_button_pressed AND NOT dispense_active
    → dispense_active = True, record start time

dispense_active AND elapsed >= DISPENSE_COUNTDOWN_TIME (default 60s)
    → dispense_active = False

_handle_feed_dispense(dispense_active)
    → True  → GPIO 17 relay ON
    → False → GPIO 17 relay OFF
```

### Water Refilling (`_refill_it`)

```
auto_refill_enabled AND water_level <= threshold AND NOT refill_active
    → refill_active = True

water_button_pressed AND NOT refill_active
    → refill_active = True (manual override)

water_level >= MAX_REFILL_LEVEL (95%) AND refill_active
    → refill_active = False (stop when full)

_handle_water_refill(refill_active)
    → True  → GPIO 27 relay ON
    → False → GPIO 27 relay OFF
```

---

## LCD Display Logic

Updated every 1 second. Priority: active action > warning > normal.

| Row   | Dispensing      | Feed Warning          | Normal              |
|-------|-----------------|-----------------------|---------------------|
| Line 1| `DISPENSING...` | `FEED LOW {level}%`   | `Feed: {level}%`    |

| Row   | Refilling       | Water Warning         | Normal              |
|-------|-----------------|-----------------------|---------------------|
| Line 2| `REFILLING...`  | `WATER LOW {level}%`  | `Water: {level}%`   |

LCD failures are fully silent — they must not interrupt the hardware control loop.

---

## Firebase Data Written

| Path                                      | Written by            | When                          |
|-------------------------------------------|-----------------------|-------------------------------|
| `buttons/{uid}/{dev}/feedButton/lastUpdateAt`  | physical keypad press | `*` key pressed          |
| `buttons/{uid}/{dev}/waterButton/lastUpdateAt` | physical keypad press | `#` key pressed          |
| `analytics/logs/{uid}` (push)             | action completion     | dispense or refill ends       |
| `sensors/{uid}/{dev}/feedLevel`           | every loop tick       | always                        |
| `sensors/{uid}/{dev}/waterLevel`          | every loop tick       | always                        |
| `sensors/{uid}/{dev}/updatedAt`           | every loop tick       | always                        |

---

## Analytics Entry Shape

Written on action completion. Matches `analyticsService.ts logAction()` exactly.

```json
{
  "action"        : "dispense" | "refill",
  "type"          : "feed" | "water",
  "volumePercent" : 12.5,
  "timestamp"     : 1718000000000,
  "date"          : "06/10/2025",
  "time"          : "14:32:01",
  "dayOfWeek"     : 2,
  "userId"        : "agjtuFg6YIcJWNfbDsc8QAlMEtj1",
  "source"        : "keypad"
}
```

`dayOfWeek` uses JS convention: Sunday=0, Monday=1 … Saturday=6.

---

## Shutdown Sequence

```
finally (always runs, even on unexpected exception):
│
├── motor.stop_all_motors()
│       → on MotorError: log error (GPIO failure at shutdown — still continues)
│
├── lcd_obj.display_message("Chick-Up", "Shutting down...")
│       sleep 1s → lcd.cleanup_lcd()
│       → silently ignored on failure
│
├── GPIO.cleanup()
│
└── log "Process stopped" (info)
```

---

## Error Handling Summary

| Scenario                          | Behaviour                                           |
|-----------------------------------|-----------------------------------------------------|
| Firebase init fails               | Log error, clear status_checker, GPIO cleanup, return |
| Motor setup fails                 | Log error, clear status_checker, GPIO cleanup, return |
| LCD init fails                    | Log warning, continue without LCD                   |
| Sensor read fails                 | Log error, clear status_checker, break (FATAL)      |
| Firebase read fails               | Log warning (throttled 10s), use last known state   |
| Button timestamp write fails      | Log warning, continue                               |
| Analytics write fails             | Log warning, continue                               |
| Sensor DB push fails              | Log warning (throttled 10s), continue               |
| Motor stop during cleanup fails   | Log error, cleanup continues                        |
| KeyboardInterrupt                 | Log warning, clear status_checker, finally runs     |
| Unexpected exception              | Log error, clear status_checker, re-raise, finally runs |

---

## Logging Contract

Process B uses `get_logger("process_b.py")` and logs at `info`, `warning`, `error`.
Services (`firebase_rtdb`, `motor_controller`) are silent — they raise only.
DB errors in the main loop are throttled to 1 log per 10 seconds to avoid
flooding the log file during sustained connectivity loss.