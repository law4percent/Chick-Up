# Firebase Realtime Database Schema

This document describes the complete Firebase Realtime Database structure for the Chick-Up IoT Poultry System.

## Database Structure

```
chickup-database/
├── users/
│   └── {userId}/
│       ├── uid: string
│       ├── username: string
│       ├── email: string
│       ├── phoneNumber: string
│       ├── createdAt: number
│       └── updatedAt: number
│
├── usernames/
│   └── {username}/
│       └── email: string
│
├── sensors/
│   └── {userId}/
│       ├── waterLevel: number (0-100)
│       ├── feedLevel: number (0-100)
│       ├── lastWaterDispense/
│       │   ├── date: string (MM/DD/YYYY)
│       │   ├── time: string (HH:MM:SS)
│       │   └── timestamp: number
│       ├── lastFeedDispense/
│       │   ├── date: string (MM/DD/YYYY)
│       │   ├── time: string (HH:MM:SS)
│       │   └── timestamp: number
│       └── updatedAt: number
│
├── settings/
│   └── {userId}/
│       ├── notifications/
│       │   └── smsEnabled: boolean
│       ├── feed/
│       │   ├── thresholdPercent: number (0-100)
│       │   └── dispenseVolumePercent: number (0-100)
│       ├── water/
│       │   ├── thresholdPercent: number (0-100)
│       │   ├── dispenseVolumePercent: number (0-100)
│       │   ├── autoRefillEnabled: boolean
│       │   └── autoRefillThreshold: number (0-100)
│       └── updatedAt: number
│
├── schedules/
│   └── {userId}/
│       └── {scheduleId}/
│           ├── userId: string
│           ├── enabled: boolean
│           ├── time: string (HH:MM format, e.g., "08:00")
│           ├── days: number[] (0=Sunday, 1=Monday, ..., 6=Saturday)
│           ├── volumePercent: number (0-100)
│           ├── createdAt: number
│           └── updatedAt: number
│
└── analytics/
    └── logs/
        └── {userId}/
            └── {logId}/
                ├── userId: string
                ├── type: "water" | "feed"
                ├── action: "dispense" | "refill"
                ├── volumePercent: number (0-100)
                ├── timestamp: number
                ├── date: string (MM/DD/YYYY)
                ├── time: string (HH:MM:SS)
                └── dayOfWeek: number (0-6)
```

## Data Types and Examples

### User Data
```json
{
  "users": {
    "abc123userId": {
      "uid": "abc123userId",
      "username": "farmowner",
      "email": "owner@farm.com",
      "phoneNumber": "+639123456789",
      "createdAt": 1700000000000,
      "updatedAt": 1700000000000
    }
  }
}
```

### Username Mapping
```json
{
  "usernames": {
    "farmowner": {
      "email": "owner@farm.com"
    }
  }
}
```

### Sensor Data
```json
{
  "sensors": {
    "abc123userId": {
      "waterLevel": 75,
      "feedLevel": 60,
      "lastWaterDispense": {
        "date": "10/20/2025",
        "time": "08:30:15",
        "timestamp": 1700000000000
      },
      "lastFeedDispense": {
        "date": "10/20/2025",
        "time": "09:15:30",
        "timestamp": 1700001000000
      },
      "updatedAt": 1700001000000
    }
  }
}
```

### Settings
```json
{
  "settings": {
    "abc123userId": {
      "notifications": {
        "smsEnabled": true
      },
      "feed": {
        "thresholdPercent": 20,
        "dispenseVolumePercent": 10
      },
      "water": {
        "thresholdPercent": 20,
        "autoRefillEnabled": true,
        "autoRefillThreshold": 80
      },
      "updatedAt": 1700000000000
    }
  }
}
```

### Schedules
```json
{
  "schedules": {
    "abc123userId": {
      "-NxYz123scheduleId": {
        "userId": "abc123userId",
        "enabled": true,
        "time": "08:00",
        "days": [1, 2, 3, 4, 5],
        "volumePercent": 10,
        "createdAt": 1700000000000,
        "updatedAt": 1700000000000
      },
      "-NxYz456scheduleId": {
        "userId": "abc123userId",
        "enabled": false,
        "time": "17:00",
        "days": [0, 6],
        "volumePercent": 15,
        "createdAt": 1700000000000,
        "updatedAt": 1700000000000
      }
    }
  }
}
```

### Analytics Logs
```json
{
  "analytics": {
    "logs": {
      "abc123userId": {
        "-NxYz789logId": {
          "userId": "abc123userId",
          "type": "feed",
          "action": "dispense",
          "volumePercent": 10,
          "timestamp": 1700000000000,
          "date": "10/20/2025",
          "time": "08:30:15",
          "dayOfWeek": 1
        },
        "-NxYz012logId": {
          "userId": "abc123userId",
          "type": "water",
          "action": "refill",
          "volumePercent": 15,
          "timestamp": 1700001000000,
          "date": "10/20/2025",
          "time": "09:15:30",
          "dayOfWeek": 1
        }
      }
    }
  }
}
```

## Firebase Security Rules

```json
{
  "rules": {
    "users": {
      "$uid": {
        ".read": "$uid === auth.uid",
        ".write": "$uid === auth.uid"
      }
    },
    "usernames": {
      ".read": true,
      "$username": {
        ".write": "auth != null"
      }
    },
    "sensors": {
      "$uid": {
        ".read": "$uid === auth.uid",
        ".write": "$uid === auth.uid || auth.token.admin === true"
      }
    },
    "settings": {
      "$uid": {
        ".read": "$uid === auth.uid",
        ".write": "$uid === auth.uid"
      }
    },
    "schedules": {
      "$uid": {
        ".read": "$uid === auth.uid",
        ".write": "$uid === auth.uid"
      }
    },
    "analytics": {
      "logs": {
        "$uid": {
          ".read": "$uid === auth.uid",
          ".write": "$uid === auth.uid"
        }
      }
    }
  }
}
```

## Integration Notes for Raspberry Pi / ESP32

### Updating Sensor Data
The IoT device should update `sensors/{userId}` with current water and feed levels.

### Schedule Processing
The IoT device should monitor `schedules/{userId}` and execute enabled schedules at the specified times.

## Data Flow

1. **User Action - Feed Dispensing (Mobile App)**
   - User presses "Dispense Feed"
   - App logs to `analytics/logs/{userId}` with fixed volume (e.g., 10%)
   - App updates `sensors/{userId}/lastFeedDispense`

2. **User Action - Water Refilling (Mobile App)**
   - User presses "Refill Water"
   - App logs to `analytics/logs/{userId}` with volume = 0 (calculated by IoT)
   - App updates `sensors/{userId}/lastWaterDispense`

3. **Raspberry Pi/ESP32 - Water Refill Logic**
   - Reads current water level from ultrasonic sensor (e.g., 20%)
   - Reads `autoRefillThreshold` from settings (e.g., 80%)
   - Calculates refill amount: 80% - 20% = 60%
   - Refills until level reaches 80%
   - Updates `sensors/{userId}/waterLevel` to 80%

4. **Raspberry Pi/ESP32 - Feed Dispensing**
   - Reads `feed/dispenseVolumePercent` from settings (e.g., 10%)
   - Dispenses exact 10% volume
   - Updates `sensors/{userId}/feedLevel`

5. **Scheduled Actions**
   - Raspberry Pi monitors `schedules/{userId}`
   - At scheduled time, executes feeding action
   - Updates sensor data and creates analytics log

4. **Analytics**
   - All actions logged to `analytics/logs/{userId}`
   - App reads and aggregates data for visualization
   - Calculates weekly statistics and trends

## Timestamp Format

All timestamps in the database use Unix timestamp (milliseconds since epoch):
- `Date.now()` in JavaScript
- Can be converted to readable format using `new Date(timestamp)`