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
  Auth: undefined;  // Direct auth screen (no nested stack)
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

// Settings structures
export interface NotificationSettings {
  smsEnabled: boolean;
}

export interface DispenseSettings {
  thresholdPercent: number;
  dispenseVolumePercent: number;
}

export interface WaterSettings {
  thresholdPercent: number;
  autoRefillEnabled: boolean;
  autoRefillThreshold: number;
}

export interface UserSettings {
  notifications: NotificationSettings;
  feed: DispenseSettings;
  water: WaterSettings;
  updatedAt: number;
}

// Schedule data structure for feeding
export interface FeedSchedule {
  id: string;
  userId: string;
  enabled: boolean;
  time: string; // HH:MM format
  days: number[]; // 0=Sunday, 1=Monday, etc.
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