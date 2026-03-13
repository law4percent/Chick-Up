# Chick-Up — User Manual

**Smart Poultry Automation System**
Raspberry Pi + Mobile App

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Hardware Controls](#2-hardware-controls)
   - 2.1 [LCD Display](#21-lcd-display)
   - 2.2 [Keypad Reference](#22-keypad-reference)
3. [First-Time Setup](#3-first-time-setup)
   - 3.1 [Powering On](#31-powering-on)
   - 3.2 [Pairing with the App](#32-pairing-with-the-app)
4. [Daily Operation](#4-daily-operation)
   - 4.1 [What the LCD Shows](#41-what-the-lcd-shows)
   - 4.2 [Manual Feed Dispense — Keypad](#42-manual-feed-dispense--keypad)
   - 4.3 [Manual Water Refill — Keypad](#43-manual-water-refill--keypad)
5. [Mobile App](#5-mobile-app)
   - 5.1 [Dashboard](#51-dashboard)
   - 5.2 [Manual Controls from the App](#52-manual-controls-from-the-app)
   - 5.3 [Live Camera Stream](#53-live-camera-stream)
   - 5.4 [Settings](#54-settings)
   - 5.5 [Feed Schedule](#55-feed-schedule)
   - 5.6 [Analytics](#56-analytics)
6. [Changing the Owner (Logout)](#6-changing-the-owner-logout)
7. [Shutting Down](#7-shutting-down)
8. [Understanding the Alerts](#8-understanding-the-alerts)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. System Overview

Chick-Up automates feed dispensing and water refilling for a poultry enclosure. The Raspberry Pi monitors feed and water levels through ultrasonic sensors and drives two relay-controlled motors. You control and monitor the system from a mobile app over the internet.

**What the system does automatically:**
- Measures feed and water levels continuously
- Warns you on the app when levels drop below your configured thresholds
- Dispenses feed automatically on a schedule you configure (day of week + time)
- Optionally refills water automatically when it gets too low (auto-refill)
- Logs every feed and water action to the analytics history, tagged by source (app, keypad, or schedule)

**What you do manually:**
- Trigger feed dispensing or water refill on demand (app or physical keypad)
- Watch a live camera stream
- Adjust thresholds and timing from the app

---

## 2. Hardware Controls

### 2.1 LCD Display

The device has a **16-character × 2-line LCD**. It shows different things depending on what state the system is in.

**Before pairing (menu):**
```
> Login
  Shutdown
```

**While running (normal operation):**
```
Feed: 72.5%
Water: 48.0%
```

**When a level is low:**
```
FEED LOW 15.0%
Water: 48.0%
```

**When the motor is active:**
```
DISPENSING...
Water: 48.0%
```
or
```
Feed: 72.5%
REFILLING...
```

---

### 2.2 Keypad Reference

The device uses a 4×4 matrix keypad. Here is what each key does depending on the current state.

#### In the pairing menu (before the system is running)

| Key | Action |
|-----|--------|
| `2` | Move cursor **up** |
| `8` | Move cursor **down** |
| `A` | **Confirm** selected option |

#### While the system is running

| Key | Action |
|-----|--------|
| `*` | **Dispense feed** — triggers the feed motor for one cycle |
| `#` | **Refill water** — triggers the water pump until the tank is full (or up to 95%) |
| `D` *(hold 3 s)* | **Logout** — stops the system and returns to the pairing menu |

> **Tip:** All other keys (`0–9`, `B`, `C`) are ignored during normal operation. You cannot accidentally trigger anything by pressing them.

---

## 3. First-Time Setup

### 3.1 Powering On

1. Connect the Raspberry Pi to power.
2. The LCD shows **"Chick-Up / Initializing..."** for about 2 seconds while the system boots.
3. If no device has been paired before, the pairing menu appears:

```
> Login
  Shutdown
```

If a device was previously paired, it goes straight to **"Validating... / Please wait"** and then jumps to normal operation — skip to [Section 4](#4-daily-operation).

---

### 3.2 Pairing with the App

Pairing links your mobile account to this specific Raspberry Pi. You only need to do this once per account.

**On the Raspberry Pi:**

1. In the pairing menu, press `A` to confirm **Login**.
2. The LCD shows a 6-character code and a countdown:

```
Enter code in app:
>>> AB3X7K <<<
```

The code is valid for **60 seconds**. If it expires, the menu returns automatically — just press `A` again to get a new code.

> Press `*` at any time during the countdown to cancel and go back to the menu.

**On the app:**

1. Open the Chick-Up app and log in (or create an account if you haven't yet).
2. On the Dashboard, tap **"Link Device"** (shown when no device is paired).
3. Type the 6-character code exactly as shown on the LCD (uppercase, no spaces).
4. Tap **"Look Up"** — the app verifies the code is valid and not expired.
5. If found, the device ID is shown. Tap **"Pair"** to complete.

**Back on the Raspberry Pi:**

The LCD confirms pairing:
```
Paired!
Hi, yourusername!
```

The system then starts automatically. Normal operation begins within a few seconds.

---

## 4. Daily Operation

### 4.1 What the LCD Shows

During normal operation the LCD updates every second with current levels.

| Display | Meaning |
|---------|---------|
| `Feed: 72.5%` | Feed container is 72.5% full — normal |
| `Water: 48.0%` | Water container is 48.0% full — normal |
| `FEED LOW 15.0%` | Feed is below your alert threshold — needs refilling |
| `WATER LOW 12.0%` | Water is below your alert threshold |
| `DISPENSING...` | Feed motor is actively running |
| `REFILLING...` | Water pump is actively running |

Both lines update independently, so you might see `DISPENSING...` on line 1 and `Water: 48.0%` on line 2 at the same time.

---

### 4.2 Manual Feed Dispense — Keypad

Press `*` once. The LCD changes to `DISPENSING...` immediately.

The motor runs for the **Dispense Duration** you configured in the app Settings (default: 60 seconds). It stops automatically when the timer ends. You cannot stop it early from the keypad once it has started.

If you press `*` while a dispense is already in progress, nothing happens — the system ignores it until the current cycle finishes.

---

### 4.3 Manual Water Refill — Keypad

Press `#` once. The LCD changes to `REFILLING...`.

The pump runs until the water level reaches **95%** (a hard safety cap built into the system) or your configured Auto Refill Target level, whichever is lower. It stops automatically. You do not need to press anything to stop it.

If the water is already at or above 95%, pressing `#` does nothing.

---

## 5. Mobile App

### 5.1 Dashboard

The Dashboard is the main screen. It shows:

- **Feed level** and **Water level** as percentages, updated in real time
- **Last feed** and **last water** action timestamps (date and time, Philippine Time)
- A warning indicator if either level is below your configured threshold
- Action buttons: **Refill Water** and **Dispense Feed**
- A **Live Stream** button to watch the camera

If no device is paired yet, the Dashboard shows a **"Link Device"** prompt instead. Follow the pairing steps in [Section 3.2](#32-pairing-with-the-app).

---

### 5.2 Manual Controls from the App

**Refill Water** — sends a command to the Raspberry Pi to start the water pump. The pump runs until the tank reaches 95%. A 3-second cooldown is applied to the button after each press to prevent accidental double-sends.

**Dispense Feed** — sends a command to start the feed motor. The motor runs for the configured Dispense Duration. Same 3-second button cooldown applies.

> **Important:** These buttons send a command over the internet to the Raspberry Pi. If the Pi is offline or not reachable, you will see an error message and no action is logged. Check that the Pi is powered on and connected to the network.

---

### 5.3 Live Camera Stream

Tap the **Live Stream** button on the Dashboard. The app connects to the Raspberry Pi camera via WebRTC (a direct peer-to-peer video connection).

**Connection states shown on screen:**

| State | Meaning |
|-------|---------|
| Connecting... | Negotiating the connection — usually takes 5–15 seconds |
| LIVE | Video is streaming successfully |
| FAILED | Connection could not be established |

**Tips for reliable streaming:**
- Works best on Wi-Fi. On mobile data, the connection goes through a TURN relay server — slightly higher latency is normal.
- If it shows FAILED, tap the button again to retry. The first attempt sometimes fails if the Pi just woke up.
- Tap the button again to stop the stream and close the video window.

---

### 5.4 Settings

Open Settings from the navigation menu (☰). All changes take effect on the Raspberry Pi **immediately without a reboot** — the Pi reads updated values from the cloud within one loop cycle (about 100 ms).

#### Feed Settings

| Setting | Description | Range | Default |
|---------|-------------|-------|---------|
| Alert Threshold | App shows a warning when feed drops below this | 0–100% | 20% |
| Dispense Duration | How long the feed motor runs per dispense cycle. Enter minutes and seconds in the two input fields (e.g. `1` min `30` sec). The Pi picks up changes live — no reboot needed. | 5 s – 5 min | 1 min 0 sec |

#### Water Settings

| Setting | Description | Range | Default |
|---------|-------------|-------|---------|
| Alert Threshold | App shows a warning when water drops below this (max 80% recommended) | 0–80% | 20% |
| Enable Auto Refill | Pi automatically starts the pump when water drops to threshold | On / Off | Off |
| Auto Refill Target Level | How full to fill the tank during auto-refill (pump always stops at 95%) | 0–100% | 80% |

After adjusting the settings, tap **Save Settings**. The app confirms with a success message. If the Dispense Duration value is out of range, an error appears below the input fields — correct it before saving.

---

### 5.5 Feed Schedule

Open **Schedule** from the navigation menu (☰). Schedules tell the Raspberry Pi to automatically dispense feed at a specific time on specific days of the week. The Pi checks the schedule every loop tick (~100 ms) and triggers the feed motor exactly once when the scheduled time arrives.

#### Creating a Schedule

Tap the **+** button (bottom right). A form slides up with two settings:

| Field | Description |
|-------|-------------|
| **Time (HH:MM)** | The time to dispense, in 24-hour format. Example: `06:30` for 6:30 AM, `18:00` for 6:00 PM. |
| **Select Days** | Tap any combination of Sun–Sat. Selected days are highlighted in green. At least one day is required. |

Tap **Save** to create the schedule. It becomes active immediately — no reboot required.

#### Managing Schedules

Each schedule card shows the time and the day pattern. Three controls are available:

- **Toggle switch** — enables or disables the schedule without deleting it. A disabled schedule is ignored by the Pi.
- **✏️ Edit** — opens the same form pre-filled with the current values. Tap Save to apply changes.
- **🗑️ Delete** — prompts for confirmation before permanently removing the schedule.

The schedule list is sorted by time (earliest first).

#### How It Works on the Pi

When the current time matches a schedule's `HH:MM` and the day matches, the Pi treats it exactly like a manual feed button press — the motor runs for the configured **Dispense Duration** (from Settings). The schedule fires **once per minute window** even if the Pi reboots mid-minute. A schedule that is already dispensing cannot re-trigger until the current dispense finishes.

The analytics entry written for a schedule trigger is tagged `source: "schedule"` so you can tell it apart from manual presses.

> **Day numbering:** Days in the app use JavaScript convention (0 = Sunday, 1 = Monday … 6 = Saturday). This matches the Pi's internal day conversion, so a schedule set for "Mon" on the app will fire on Monday on the Pi.

---

### 5.6 Analytics

Open Analytics from the navigation menu. This shows a history of all feed and water actions, including:

- **Source** — where the action came from: `app` (tapped in the app), `keypad` (physical `*` or `#` key on the Pi), or `schedule` (automated schedule fired)
- The date, time, and day of the week
- The volume change recorded at the time of the action

Analytics are written by both the app and the Raspberry Pi. App-side entries (`source: app`) are logged when the command is sent successfully. Pi-side entries (`source: keypad` and `source: schedule`) are logged when the action completes — i.e. after the motor stops — so the volume measurement reflects the actual level change.

---

## 6. Changing the Owner (Logout)

If you want to pair the Raspberry Pi with a different account, you need to log out from the device. This deletes the stored credentials on the Pi and unlinks the device from your account.

**To log out while the system is running:**

1. Go to the Raspberry Pi keypad.
2. **Hold the `D` key for 3 seconds.**
3. The LCD shows:
   ```
   Hold D: Logout
   Please wait...
   ```
4. Both processes stop cleanly. The Pi deletes its credentials and removes the device link from Firebase.
5. The LCD returns to the pairing menu:
   ```
   > Login
     Shutdown
   ```

You can now pair with a new account by following [Section 3.2](#32-pairing-with-the-app) again.

> **On the app:** After logout, the previous account's Dashboard will show "No device paired" on the next refresh, because the device link is removed from Firebase automatically.

---

## 7. Shutting Down

**From the pairing menu** (before the system has started):
1. Press `8` to move the cursor to **Shutdown**.
2. Press `A` to confirm.
3. The LCD shows `Shutting down... / Goodbye!` and the Pi shuts down cleanly.

**While the system is running:**
There is no direct shutdown key while processes are running. To shut down:
1. First log out by holding `D` for 3 seconds.
2. Once the pairing menu reappears, navigate to **Shutdown** and press `A`.

> Never unplug the Raspberry Pi without shutting it down first — this can corrupt the SD card.

---

## 8. Understanding the Alerts

| Alert | Cause | What to do |
|-------|-------|------------|
| Feed level warning (LCD + app) | Feed dropped below Alert Threshold | Refill the physical feed container. Tap Dispense Feed or press `*` if needed. |
| Water level warning (LCD + app) | Water dropped below Alert Threshold | Tap Refill Water or press `#`. If auto-refill is on, the Pi handles it automatically. |
| `DISPENSING...` on LCD | Feed motor is running | Normal. Wait for it to finish. |
| `REFILLING...` on LCD | Water pump is running | Normal. Stops automatically at 95% or target level. |
| App: "No Device" | No device is paired to your account | Follow [Section 3.2](#32-pairing-with-the-app). |
| App: "Connection failed" | Live stream could not connect | Retry. Check that the Pi is powered and online. |
| App: "Failed to send command" | Button press could not reach Firebase | Check phone internet connection. |
| LCD: "Auth invalid / Re-pairing..." | Saved credentials failed validation | The Pi will automatically return to the pairing menu. Pair again. |
| LCD: "Firebase error / Check network" | Pi cannot reach Firebase at boot | Check the Pi's network connection. Restart after fixing. |
| LCD: "Pairing failed / Try again" | Firebase write error during pairing | Press `A` to retry from the pairing menu. |
| LCD: "Code expired! / Press A to retry" | 60-second pairing window passed | Press `A` on the keypad to generate a new code, then repeat in the app. |

---

## 9. Troubleshooting

**The LCD is blank after powering on.**
The LCD I²C address may not be responding. Verify the I²C connection and address (`0x27` by default). Check that the contrast potentiometer on the LCD backpack is adjusted.

**The pairing code expired before I could enter it.**
Codes expire after 60 seconds. Press `A` on the keypad to go back to the pairing menu, then select Login again to generate a fresh code.

**I entered the code in the app but it says "Code expired".**
Either more than 60 seconds passed, or the code was already used. Press `A` on the keypad to generate a new one.

**The live stream stays on "Connecting..." and never connects.**
- Make sure the Raspberry Pi is running (LCD should show sensor data).
- If you are on mobile data, the connection routes through the TURN server. Try waiting up to 30 seconds.
- If it consistently fails, verify the TURN server is running on the VPS (`sudo systemctl status coturn`) and that port 3478 UDP/TCP is open in both the OS firewall and the cloud provider firewall.

**The feed motor or water pump does not run when I press the button.**
- Check that the Pi is powered and the LCD is showing sensor data (system is running).
- If you are using the app, check that the command sent successfully (no error alert).
- Check relay wiring and GPIO connections.
- Check `warning.log` on the Pi for any motor error messages.

**Auto-refill triggers immediately after the system starts.**
This is caused by the sensors reading 0% before they stabilize. The system waits 2 seconds (20 boot ticks) before enabling auto-refill after startup. If it still happens, check that the ultrasonic sensors are properly mounted and not obstructed.

**The water pump runs but never stops.**
The pump stops when the water level reaches 95% as read by the right ultrasonic sensor. If the sensor is mispositioned or gives incorrect readings, the pump may run too long. Check the sensor mounting. The pump will also stop if you restart the Pi.

**Settings I changed in the app are not taking effect.**
- Ensure you tapped **Save Settings** after making changes.
- If the Dispense Duration fields show a red border, correct the value first — settings are not saved while there is a validation error.
- The Pi picks up new settings within one loop tick (about 100 ms). If it has been more than 1 second and nothing changed, check the Pi's network connection.

**The app shows old sensor data after restarting the Pi.**
The Dashboard subscribes to real-time Firebase updates. Pull down to refresh or navigate away and back. The Pi writes new sensor data to Firebase every loop tick, so values should update within seconds of the Pi starting.

**I held D for 3 seconds but nothing happened.**
The `D` key hold detection requires the system to be fully running (past the boot stabilization period, about 2 seconds after startup). Make sure you are holding `D` continuously — releasing and re-pressing resets the 3-second timer.

**A schedule did not fire at the expected time.**
- Check that the schedule is **enabled** (toggle switch is on in the Schedule screen).
- Verify the time is in 24-hour format (`18:00` not `6:00 PM`).
- The Pi must be running and connected to Firebase at the scheduled time. If it was offline, the missed schedule will not be retried.
- Schedules fire based on the **Pi's system clock**. If the Pi's time is wrong (e.g. first boot without NTP sync), schedules may fire at the wrong time. Ensure the Pi has internet access so NTP can synchronize the clock automatically.

**A schedule fired but no analytics entry appeared.**
The analytics entry is written after the motor stops (not when it starts). Wait for the full Dispense Duration to pass. If it still does not appear, check the Pi's network connection — analytics writes require Firebase access.

**A schedule seems to fire twice.**
This should not happen after the latest update. Each schedule fires exactly once per minute window. If you see a duplicate, check that you are running the latest `process_b.py`.