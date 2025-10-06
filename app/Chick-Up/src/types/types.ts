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