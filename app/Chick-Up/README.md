# Chick-Up — Mobile App

React Native (Expo) companion app for the Chick-Up smart poultry automation system.

---

## Overview

The Chick-Up app lets you monitor and control your Raspberry Pi–based poultry
feeder remotely from your phone. It communicates with the device entirely
through Firebase Realtime Database — no direct network connection to the Pi
is required as long as both the phone and the Pi have internet access.

Live video uses WebRTC with a TURN relay server for networks behind NAT or CGNAT.

---

## Features

| Feature | Description |
|---------|-------------|
| **Device pairing** | Pair your account to a Raspberry Pi using a 6-character code shown on the device LCD |
| **Live sensor data** | Real-time feed and water level percentages, updated every ~100 ms by the Pi |
| **Manual controls** | Tap to trigger feed dispensing or water refill on demand |
| **Live camera stream** | WebRTC video stream from the Pi camera, relayed through TURN when needed |
| **Feed schedule** | Create weekly schedules for automatic feed dispensing (day + time + volume) |
| **Settings** | Configure alert thresholds, dispense volume, dispense duration, and auto-refill |
| **Analytics** | History of all feed and water actions, tagged by source (app / keypad / schedule) |
| **Profile** | Update username, phone number, or password |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | React Native + Expo |
| Language | TypeScript |
| Navigation | React Navigation (Drawer) |
| Backend / DB | Firebase Realtime Database |
| Auth | Firebase Authentication |
| Video | WebRTC (`react-native-webrtc`) |
| UI | StyleSheet + LinearGradient + Slider |

---

## Project Structure

```
src/
├── config/
│   ├── firebase.config.ts      — Firebase app initialization
│   └── theme.ts                — Shared colors, spacing, border radii
│
├── screens/
│   ├── DashboardScreen.tsx     — Main screen: levels, buttons, live stream, pairing
│   ├── SettingsScreen.tsx      — Feed + water configuration sliders
│   ├── ScheduleScreen.tsx      — Weekly feed schedule CRUD
│   ├── AnalyticsScreen.tsx     — Action history log
│   └── ProfileScreen.tsx       — Username / phone / password editor
│
├── services/
│   ├── authService.ts          — Sign up, sign in, sign out, getUserData
│   ├── deviceService.ts        — Pairing, linkedDevice subscribe/get/unlink
│   ├── sensorService.ts        — Feed + water level subscribe/get
│   ├── buttonService.ts        — Button timestamp write + subscribe
│   ├── settingsService.ts      — User settings read/write/subscribe
│   ├── scheduleService.ts      — Feed schedule CRUD + subscribe
│   ├── analyticsService.ts     — Action log write + read
│   └── webrtcService.ts        — WebRTC session lifecycle (TURN from .env)
│
└── types/
    └── types.ts                — All shared TypeScript interfaces
```

---

## Firebase Realtime Database Paths

```
users/{userId}/
    username
    email
    phoneNumber
    linkedDevice/
        deviceUid       ← written by app on pairing, deleted by Pi on logout
        linkedAt

settings/{userId}/
    feed/
        thresholdPercent
        dispenseVolumePercent
        dispenseCountdownMs
    water/
        thresholdPercent
        autoRefillEnabled
        autoRefillThreshold
    updatedAt

schedules/{userId}/{scheduleId}/
    time            "HH:MM"
    days            [0…6]   (0=Sun, JS convention)
    enabled         bool
    volumePercent   number
    createdAt       Unix ms
    updatedAt       Unix ms

buttons/{userId}/{deviceUid}/
    feedButton/lastUpdateAt     ← SERVER_TIMESTAMP written by app or Pi keypad
    waterButton/lastUpdateAt

sensors/{userId}/{deviceUid}/
    feedLevel       float %
    waterLevel      float %
    updatedAt       "MM/DD/YYYY HH:MM:SS"

analytics/logs/{userId}/{pushId}/
    action          "dispense" | "refill"
    type            "feed" | "water"
    volumePercent   float
    timestamp       Unix ms
    date            "MM/DD/YYYY"
    time            "HH:MM:SS"
    dayOfWeek       0–6  (JS convention)
    userId          string
    source          "app" | "keypad" | "schedule"

liveStream/{userId}/{deviceUid}/
    liveStreamButton            ← app toggles to request stream
    offer                       ← app writes WebRTC SDP offer
    answer                      ← Pi writes WebRTC SDP answer
    iceCandidates/raspi/        ← Pi ICE candidates
    iceCandidates/mobile/       ← app ICE candidates
    connectionState             ← Pi writes current WebRTC state

device_code/{code}/
    deviceUid   string
    createdAt   Unix ms
    status      "pending" | "paired" | "expired"
    userUid     string   (written by app on pairing)
    username    string   (written by app on pairing)
```

> **Settings path note:** Settings are scoped to `{userId}`, not `{userId}/{deviceUid}`.
> This is intentional — settings represent the *user's* preferences (feeding regime,
> thresholds) which should carry over if the user swaps to a new Raspberry Pi.
> Sensor readings and button state are device-scoped because they reflect the
> *physical device's* current state.

---

## Environment Variables

Create a `.env` file in the project root (next to `package.json`):

```env
# Firebase
EXPO_PUBLIC_FIREBASE_API_KEY=
EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN=
EXPO_PUBLIC_FIREBASE_DATABASE_URL=
EXPO_PUBLIC_FIREBASE_PROJECT_ID=
EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET=
EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=
EXPO_PUBLIC_FIREBASE_APP_ID=

# TURN relay server — must match credentials/.env on the Pi
EXPO_PUBLIC_TURN_SERVER_URL=your-vps-ip:3478
EXPO_PUBLIC_TURN_USERNAME=webrtc
EXPO_PUBLIC_TURN_PASSWORD=your-password
```

TURN credentials are loaded at module load time in `webrtcService.ts` and are
**never written to Firebase**. They are bundled into the app at build time via
Expo's `EXPO_PUBLIC_` prefix convention.

---

## Setup

```bash
# Install dependencies
npm install

# Start Expo dev server
npx expo start

# Run on Android
npx expo run:android

# Run on iOS
npx expo run:ios
```

Requires Node.js 18+ and the Expo CLI. For `react-native-webrtc`, a native
build is required — Expo Go will not work for the live stream feature.
Use a development build:

```bash
npx expo prebuild
npx expo run:android    # or run:ios
```

---

## Key Design Decisions

### Why settings are user-scoped, not device-scoped

`/settings/{userId}/` stores preferences like feed threshold, dispense duration,
and auto-refill toggle. These are personal preferences that belong to the user,
not the hardware. If a user replaces their Pi, they want the same settings —
same flock, same feeding habits. Scoping to `{userId}/{deviceUid}` would force
users to reconfigure every time the Pi is swapped.

Paths that *are* device-scoped (`sensors`, `buttons`, `liveStream`) reflect
live hardware state — those must be device-specific.

### Why button timestamps instead of boolean flags

The app writes `SERVER_TIMESTAMP` to `buttons/{userId}/{deviceUid}/feedButton/lastUpdateAt`
instead of writing a boolean `true`. The Pi uses timestamp comparison to detect a
*new* press: it tracks the last timestamp it acted on and only triggers the motor
when the timestamp changes. This prevents the motor from re-triggering every loop
tick for the full minute that a freshly-written timestamp stays "fresh."

### Why analytics are written after the motor stops (Pi side)

App-side analytics are written immediately on button press. Pi-side analytics
(`source: "keypad"` and `source: "schedule"`) are written only after the motor
finishes its cycle. This means the `volumePercent` field on Pi entries reflects
the actual sensor-measured level change, not a configured estimate.

### Why linkedDevice uses a real-time subscription

`DashboardScreen` subscribes to `users/{userId}/linkedDevice` with `onValue`
rather than doing a one-time `get`. This means when the Pi calls `auth.logout()`
and deletes the `linkedDevice` node, the app immediately switches to the
"No Device" state without requiring a manual refresh.

---

## Pairing Flow

```
Pi LCD shows: "Code: AB3X7K / Expires in 60s"
                    ↓
App: user enters "AB3X7K" → taps Look Up
                    ↓
App reads  device_code/AB3X7K/  → validates not expired, not used
                    ↓
App writes device_code/AB3X7K/  → { userUid, username, status: "paired" }
App writes users/{uid}/linkedDevice → { deviceUid, linkedAt }
                    ↓
Pi polls device_code/AB3X7K/ → sees status: "paired"
Pi reads userUid + username, saves credentials.txt
Pi LCD shows: "Paired! / Hi, username!"
                    ↓
System starts (Process A + Process B)
```

---

## Logout Flow (Pi-initiated)

```
User holds D key on Pi keypad for 3 seconds
                    ↓
Pi terminates Process A + Process B
Pi deletes credentials/user_credentials.txt
Pi deletes users/{uid}/linkedDevice  from Firebase
Pi LCD returns to pairing menu
                    ↓
App's onValue subscription fires (linkedDevice → null)
App sets linkedDeviceUid = null → renders "No Device" screen
App stops any active WebRTC stream
```