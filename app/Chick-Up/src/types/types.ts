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

export interface UserSettings {
  notifications: NotificationSettings;
  feed: DispenseSettings;
  water: DispenseSettings;
  updatedAt: number;
}

// Trigger data structure
export interface TriggerData {
  type: 'water' | 'feed';
  userId: string;
  timestamp: number;
  volumePercent: number;
  processed: boolean;
}