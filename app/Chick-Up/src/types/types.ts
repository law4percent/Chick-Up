// src/types/types.ts

// User data structure in Realtime Database
export interface UserData {
  uid: string;
  username: string;
  email: string;
  phoneNumber: string;
  createdAt: number;
  updatedAt: number;
}

// Username to email mapping for login
export interface UsernameMapping {
  email: string;
}

// Navigation types
export type RootStackParamList = {
  Auth: undefined;
  Main: undefined;
};

export type MainDrawerParamList = {
  Dashboard: undefined;
  Profile: undefined;
  Settings: undefined;
  Schedule: undefined;
  DataLogging: undefined;
  Analytics: undefined;
};

// Form data types
export interface SignUpFormData {
  username: string;
  phoneNumber: string;
  email: string;
  password: string;
}

export interface LoginFormData {
  username: string;
  password: string;
}

// Sensor data structure
export interface DispenseData {
  date: string;
  time: string;
  timestamp: number;
}

export interface SensorData {
  waterLevel: number;
  feedLevel: number;
  lastWaterDispense: DispenseData;
  lastFeedDispense: DispenseData;
  updatedAt: number;
}

export interface DispenseSettings {
  thresholdPercent: number;
  dispenseVolumePercent: number;
  /**
   * How long the feed motor runs per dispense, in milliseconds.
   * Written to Firebase as-is — raspi reads it from
   * settings/{userUid}/feed/dispenseCountdownMs.
   * UI should display and accept seconds (divide/multiply by 1000).
   * Valid range: 5 000 – 300 000 ms (5 s – 5 min).
   * Default: 60 000 ms (60 s).
   */
  dispenseCountdownMs: number;
}

export interface WaterSettings {
  thresholdPercent: number;
  autoRefillEnabled: boolean;
  autoRefillThreshold: number;
}

export interface UserSettings {
  feed: DispenseSettings;
  water: WaterSettings;
  updatedAt: number;
}

// ─────────────────────────── PAIRING ─────────────────────────────────────────

/**
 * Shape written by the raspi to /device_code/{code}/ when it starts pairing.
 * The app reads this to get deviceUid, then writes back PairingAppWrite.
 */
export interface DeviceCodeEntry {
  deviceUid: string;   // e.g. "DEV_001"
  createdAt: number;   // Unix ms — used to detect expiry (60 s)
  status: 'pending' | 'paired' | 'expired';
}

/**
 * What the app writes back to /device_code/{code}/ to complete pairing.
 * The raspi polls for status === "paired" and reads userUid + username.
 */
export interface PairingAppWrite {
  userUid:  string;
  username: string;
  status:   'paired';
}

/**
 * Stored locally in AsyncStorage after a successful pairing.
 */
export interface LinkedDevice {
  deviceUid: string;
  linkedAt:  number;  // Unix ms
}

// ─────────────────────────── WEBRTC / TURN ───────────────────────────────────

/**
 * TURN server configuration stored in Firebase at
 * settings/{userUid}/turnServer/
 * Written by the user (or admin) — read by the app at stream start.
 *
 * serverUrl may be bare "host:port" or prefixed "turn:host:port" —
 * normalizeTurnHost() handles both, matching webrtc_peer.py logic.
 */
export interface TurnServerConfig {
  serverUrl: string;   // e.g. "143.198.45.67:3478" or "turn:143.198.45.67:3478"
  username:  string;   // e.g. "webrtc"
  password:  string;
}

// Schedule data structure for feeding
export interface FeedSchedule {
  id: string;
  userId: string;
  enabled: boolean;
  time: string;       // HH:MM format
  days: number[];     // 0=Sunday … 6=Saturday
  volumePercent: number;
  createdAt: number;
  updatedAt: number;
}

// Analytics data structure
export interface DispenseLog {
  id: string;
  userId: string;
  type: 'water' | 'feed';
  action: 'dispense' | 'refill';
  volumePercent: number;
  timestamp: number;
  date: string;
  time: string;
  dayOfWeek: number;
}

export interface DailyAnalytics {
  date: string;
  dayOfWeek: number;
  feedDispensed: number;
  waterRefilled: number;
  feedDispenseCount: number;
  waterRefillCount: number;
  avgFeedingTime: number;
  avgRefillTime: number;
}