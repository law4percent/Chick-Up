// src/services/authService.ts
import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut as firebaseSignOut,
  User
} from 'firebase/auth';
import { ref, set, get } from 'firebase/database';
import { auth, database } from '../config/firebase.config';
import { UserData, SignUpFormData, LoginFormData } from '../types/types';
import settingsService from './settingsService';

class AuthService {

  /**
   * Sign up a new user.
   *
   * Flow:
   *   1. Check username availability
   *   2. Create Firebase Auth user
   *   3. Write users/{uid}
   *   4. Write usernames/{username}
   *   5. Initialize all default DB settings (settings, TURN config)  ← NEW
   *   6. Sign out (user must log in explicitly)
   */
  async signUp(formData: SignUpFormData): Promise<void> {
    let userCreated    = false;
    let userCredential: any = null;

    try {
      // ── Step 1: Username availability ─────────────────────────────────
      const usernameRef      = ref(database, `usernames/${formData.username.toLowerCase()}`);
      const usernameSnapshot = await get(usernameRef);
      if (usernameSnapshot.exists()) {
        throw new Error('Username already taken');
      }

      // ── Step 2: Create Firebase Auth user ────────────────────────────
      userCredential = await createUserWithEmailAndPassword(
        auth,
        formData.email,
        formData.password
      );
      userCreated = true;

      const user      = userCredential.user;
      const timestamp = Date.now();

      // ── Step 3: Write user profile ───────────────────────────────────
      const userData: UserData = {
        uid:         user.uid,
        username:    formData.username,
        email:       formData.email,
        phoneNumber: formData.phoneNumber,
        createdAt:   timestamp,
        updatedAt:   timestamp,
      };
      await set(ref(database, `users/${user.uid}`), userData);

      // ── Step 4: Write username → uid/email mapping ───────────────────
      await set(ref(database, `usernames/${formData.username.toLowerCase()}`), {
        uid:   user.uid,
        email: formData.email,
      });

      // ── Step 5: Initialize all default DB settings ───────────────────
      // This writes settings/{uid} including TURN server config from .env
      // The Raspi will not work until these defaults exist in Firebase.
      await settingsService.initializeUserDefaults(user.uid);

      // ── Step 6: Sign out — user must log in explicitly ───────────────
      await firebaseSignOut(auth);

      console.log('✅ User registered and defaults initialized');

    } catch (error: any) {
      // If DB write failed but Auth user was created — clean up orphan
      if (userCreated && userCredential?.user) {
        try {
          await userCredential.user.delete();
          console.log('🧹 Cleaned up orphaned auth user');
        } catch (deleteError) {
          console.error('❌ Failed to clean up auth user:', deleteError);
        }
      }

      if (error.code === 'auth/email-already-in-use') throw new Error('Email already in use');
      if (error.code === 'auth/weak-password')        throw new Error('Password should be at least 6 characters');
      if (error.code === 'auth/invalid-email')        throw new Error('Invalid email address');
      if (error.code === 'PERMISSION_DENIED')         throw new Error('Database permission denied. Please check Firebase rules.');

      console.error('❌ Sign-up error:', { code: error.code, message: error.message });
      throw error;
    }
  }

  /**
   * Login user with username and password.
   */
  async login(formData: LoginFormData): Promise<User> {
    try {
      const usernameRef      = ref(database, `usernames/${formData.username.toLowerCase()}`);
      const usernameSnapshot = await get(usernameRef);

      if (!usernameSnapshot.exists()) {
        throw new Error('Invalid username or password');
      }

      const { email } = usernameSnapshot.val();
      if (!email) throw new Error('User data incomplete');

      const userCredential = await signInWithEmailAndPassword(auth, email, formData.password);

      console.log('✅ Login successful');
      return userCredential.user;

    } catch (error: any) {
      if (error.code === 'auth/invalid-credential' || error.code === 'auth/wrong-password')
        throw new Error('Invalid username or password');
      if (error.code === 'auth/too-many-requests')
        throw new Error('Too many failed attempts. Please try again later');
      if (error.code === 'PERMISSION_DENIED')
        throw new Error('Database permission denied. Please check Firebase rules.');

      console.error('❌ Login error:', { code: error.code, message: error.message });
      throw error;
    }
  }

  /**
   * Sign out current user.
   */
  async signOut(): Promise<void> {
    await firebaseSignOut(auth);
    console.log('✅ User signed out');
  }

  /**
   * Get current user data from RTDB.
   */
  async getUserData(uid: string): Promise<UserData | null> {
    try {
      const snapshot = await get(ref(database, `users/${uid}`));
      return snapshot.exists() ? (snapshot.val() as UserData) : null;
    } catch (error) {
      console.error('❌ Error fetching user data:', error);
      return null;
    }
  }

  /**
   * Check if username is available (real-time validation during sign-up).
   */
  async isUsernameAvailable(username: string): Promise<boolean> {
    try {
      const snapshot = await get(ref(database, `usernames/${username.toLowerCase()}`));
      return !snapshot.exists();
    } catch (error) {
      console.error('❌ Error checking username:', error);
      return false;
    }
  }
}

export default new AuthService();