# Chick-Up 🐣

> A smart poultry care system that automates feeding and watering —
> controlled from your phone, powered by a Raspberry Pi.

---

## What Is Chick-Up?

Chick-Up is a small device that sits in your poultry enclosure and takes care
of the routine work for you. It measures how much feed and water is left,
automatically refills the water when it gets low, and dispenses feed on a
schedule you set from your phone.

You can watch a live camera view of your chickens, trigger feeding or watering
with a tap, and review a full history of everything the system has done — all
from the Chick-Up mobile app, from anywhere with an internet connection.

Even without your phone, the device works on its own: a small keypad on the
device lets you dispense feed or refill water manually, and a screen on the
device shows the current feed and water levels at all times.

---

## What Can It Do?

| Feature | What it means for you |
|---------|-----------------------|
| 📷 **Live camera** | Watch your chickens in real time from the app, wherever you are |
| 📊 **Level monitoring** | See feed and water percentages updated live on your phone and on the device screen |
| 🌾 **Dispense feed** | Tap a button in the app or press `*` on the device to feed your chickens on demand |
| 💧 **Refill water** | Tap a button in the app or press `#` on the device to start the water pump |
| 🔄 **Auto-refill** | Water refills automatically when it drops below a level you choose — no action needed |
| 📅 **Feed schedule** | Set a weekly feeding timetable (e.g. every weekday at 7 AM) and the device handles it |
| 🔔 **Low-level alerts** | The app warns you when feed or water is running low |
| 📋 **Action history** | See a log of every feeding and watering event, including whether it came from the app, the keypad, or a schedule |
| 🔐 **Secure pairing** | Link your phone account to the device using a one-time code shown on the device screen |
| 🔁 **Re-pairing** | Hand the device to a new owner — they can log in with their own account without any technical setup |

---

## How the System Works (Plain English)

The device (Raspberry Pi) and the mobile app never talk to each other directly.
Instead, they both communicate through **Firebase** — a secure cloud database
made by Google. The app writes a command to Firebase (for example, "dispense
feed"), and the device reads it and activates the motor. The device writes
sensor readings to Firebase, and the app reads them to show you the current
levels.

The live video stream is the exception — that goes directly from the device to
your phone (using a technology called WebRTC) for low latency. If your home
network blocks direct connections, the video is routed through a relay server
automatically.

---

## The Device Hardware

| Part | What it does |
|------|-------------|
| Raspberry Pi | The brain — runs all the software |
| Camera (webcam or Pi camera) | Captures the live video stream |
| 2 × Ultrasonic sensors | Measure the feed level and water level by bouncing sound off the surface |
| 2 × Relay modules | Act as electronic switches to turn the feed motor and water pump on/off |
| 4×4 Keypad | Physical buttons on the device: `*` = feed, `#` = water, hold `D` 3 sec = logout |
| 16×2 LCD screen | Small text display showing current levels and status messages |

---

## The Mobile App

The app works on both Android and iOS.

**Screens:**

- **Dashboard** — live feed/water levels, manual feed and water buttons, live stream, device pairing
- **Schedule** — set up automatic feeding times by day of week
- **Settings** — adjust alert thresholds, how long the motor runs, and auto-refill behaviour
- **Analytics** — full history of every feeding and watering action
- **Profile** — update your username, phone number, or password

See **[README_APP.md](https://github.com/law4percent/Chick-Up/blob/main/app/Chick-Up/README.md)** for the full app documentation.

---

## Files in This Repository

```
chick-up/
│
├── main.py                    ← Start here — runs the whole system
│
├── credentials/               ← Private config files (not shared publicly)
│   ├── .env                   ← Your device settings (camera, Firebase URL, etc.)
│   ├── serviceAccountKey.json ← Firebase access key
│   └── user_credentials.txt   ← Created automatically after pairing
│
└── lib/
    ├── processes/
    │   ├── process_a.py       ← Handles the live video stream
    │   └── process_b.py       ← Handles sensors, motors, keypad, and LCD
    │
    └── services/
        ├── auth.py            ← Manages device pairing and login
        ├── firebase_rtdb.py   ← Reads and writes data to Firebase
        ├── logger.py          ← Saves log files for troubleshooting
        ├── utils.py           ← Shared helper functions
        ├── webrtc_peer.py     ← Manages the live video connection
        └── hardware/          ← Controls each physical component
```

---

## Cloud Database Layout (Firebase)

All data is organised in Firebase like a folder tree.
Here is what each section stores and why:

| Path | What is stored here | Tied to |
|------|---------------------|---------|
| `users/{account}/` | Your username, email, phone, and linked device | You |
| `settings/{account}/` | Your preferences — thresholds, motor duration, auto-refill | You |
| `schedules/{account}/` | Your weekly feeding schedules | You |
| `sensors/{account}/{device}/` | Live feed and water level readings | You + Device |
| `buttons/{account}/{device}/` | When feed or water button was last pressed | You + Device |
| `liveStream/{account}/{device}/` | Data used to set up the live video connection | You + Device |
| `analytics/logs/{account}/` | Full history of every feed and water action | You |
| `device_code/{code}/` | Temporary pairing codes shown on the device LCD | Device only |

> **Why are settings and schedules not tied to the device?**
> Your preferences and feeding schedules belong to *you*, not to a piece
> of hardware. If your Raspberry Pi breaks and you replace it, you just
> pair the new one and all your settings and schedules are already there —
> nothing to re-enter. Only live data that physically comes from a specific
> device (sensor readings, video, button presses) is tied to the device ID.

---

## Device Configuration

Before the device can run, you fill in a configuration file called `.env`
inside the `credentials/` folder. You only need to do this once during setup.

| Setting | What to put here |
|---------|-----------------|
| `PRODUCTION_MODE` | `true` when using the real device; `false` for testing on a PC |
| `DEVICE_UID` | A unique name for this device, e.g. `DEV_001` |
| `IS_WEB_CAM` | `true` for a USB webcam; `false` for a Pi camera module |
| `CAMERA_INDEX` | Usually `0` — the first camera connected |
| `FRAME_WIDTH` / `FRAME_HEIGHT` | Video resolution, e.g. `640` × `480` |
| `FIREBASE_DATABASE_URL` | The URL of your Firebase database (from the Firebase console) |
| `TURN_SERVER_URL` | Address of the video relay server, e.g. `123.456.7.8:3478` |
| `TURN_USERNAME` | Username for the relay server |
| `TURN_PASSWORD` | Password for the relay server |

> **What is the relay server?**
> The TURN relay is only used for the live video stream. It is needed when
> your home network or mobile data connection blocks direct video.
> The same username and password must be set in both the device `.env` and
> the app's `.env`. They are **never** stored in Firebase.

---

## What Happens When You Turn It On

```
1. Power on the Raspberry Pi
         ↓
2. Screen shows "Chick-Up / Initializing..."
         ↓
3. Has it been paired before?
   ├── Yes → "Validating..." → checks Firebase → starts normally
   └── No  → Screen shows the pairing menu:
                 > Login
                   Shutdown
         ↓  Press A to select Login
4. Screen shows a 6-character code, e.g.:
         Code: AB3X7K
         Expires in 60s
         ↓
5. Open the Chick-Up app → tap "Link Device" → type the code → tap Pair
         ↓
6. Screen confirms: "Paired! / Hi, [your name]!"
         ↓
7. System starts — levels appear on screen, motors are ready
```

If the 60-second window expires before you enter the code, press `A` on the
keypad to generate a new one.

---

## Switching Accounts / Logging Out

Hold the **`D` key** on the device keypad for **3 seconds**.

The device stops, deletes its saved login, and returns to the pairing menu.
The app automatically shows "No Device" — no manual refresh needed.
The next person can then pair their own account by following the steps above.

---

## Auto-Start on Boot

By default, you need to manually run the software after powering on the Pi.
To make it start automatically every time the Pi is powered on — with no
keyboard, monitor, or SSH needed — follow the guide in:

**[AUTORUN.md](https://github.com/law4percent/Chick-Up/blob/main/docs/raspi/AUTORUN.md)**

---

## Log Files

The device saves log files in a `logs/` folder inside the project for
troubleshooting. If something is not working, these are the first place to look.

| File | What it records |
|------|----------------|
| `error.log` | Serious errors that stopped something from working |
| `warning.log` | Non-critical issues worth knowing about |
| `info.log` | Normal operation events (started, paired, dispensed, etc.) |
| `all.log` | Everything combined |

Each file is capped at 10 MB and rolls over automatically.

---

## Related Documents

| Document | What it covers |
|----------|---------------|
| [AUTORUN.md](https://github.com/law4percent/Chick-Up/blob/main/docs/raspi/AUTORUN.md) | How to make the device start automatically on power-on |
| [README_APP.md](https://github.com/law4percent/Chick-Up/blob/main/app/Chick-Up/README.md) | Full mobile app documentation |
| [USER_MANUAL.md](https://github.com/law4percent/Chick-Up/blob/main/docs/USER_MANUAL.md) | Step-by-step guide for everyday use (no technical background needed) |
| [MAIN_FLOW.md](https://github.com/law4percent/Chick-Up/blob/main/docs/raspi/system_flow/MAIN_FLOW.md) | Detailed diagram of how main.py works |
| [PROCESS_A_FLOW.md](https://github.com/law4percent/Chick-Up/blob/main/docs/raspi/system_flow/PROCESS_A_FLOW.md) | How the video streaming process works |
| [PROCESS_B_FLOW.md](https://github.com/law4percent/Chick-Up/blob/main/docs/raspi/system_flow/PROCESS_B_FLOW.md) | How the hardware control process works |
| [REFILL_LOGIC.md](https://github.com/law4percent/Chick-Up/blob/main/docs/raspi/system_flow/REFILL_FLOW.md) | How the auto water-refill logic works |

---

## License

This project is licensed under the [MIT License](https://github.com/law4percent/Chick-Up?tab=MIT-1-ov-file).