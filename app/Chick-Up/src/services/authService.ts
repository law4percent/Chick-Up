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

class AuthService {
  /**
   * Sign up a new user
   */
  async signUp(formData: SignUpFormData): Promise<void> {
    let userCreated = false;
    let userCredential: any = null;

    try {
      // Step 1: Check if username already exists (public read required)
      const usernameRef = ref(database, `usernames/${formData.username.toLowerCase()}`);
      const usernameSnapshot = await get(usernameRef);
      
      if (usernameSnapshot.exists()) {
        throw new Error('Username already taken');
      }

      // Step 2: Create user in Firebase Authentication
      userCredential = await createUserWithEmailAndPassword(
        auth,
        formData.email,
        formData.password
      );
      userCreated = true;

      const user = userCredential.user;
      const timestamp = Date.now();

      // Step 3: Create user data object
      const userData: UserData = {
        uid: user.uid,
        username: formData.username,
        email: formData.email,
        phoneNumber: formData.phoneNumber,
        createdAt: timestamp,
        updatedAt: timestamp,
      };

      // Step 4: Store user data (authenticated write)
      await set(ref(database, `users/${user.uid}`), userData);

      // Step 5: Store username mapping with email (needed for login)
      await set(ref(database, `usernames/${formData.username.toLowerCase()}`), {
        uid: user.uid,
        email: formData.email, // ✅ Store email here for login
      });

      // Step 6: Sign out after registration
      await firebaseSignOut(auth);
      
      console.log('✅ User registered successfully');
      
    } catch (error: any) {
      // If database write failed but user was created, clean up
      if (userCreated && userCredential?.user) {
        try {
          await userCredential.user.delete();
          console.log('🧹 Cleaned up orphaned auth user');
        } catch (deleteError) {
          console.error('❌ Failed to clean up auth user:', deleteError);
        }
      }

      // Handle specific Firebase errors
      if (error.code === 'auth/email-already-in-use') {
        throw new Error('Email already in use');
      } else if (error.code === 'auth/weak-password') {
        throw new Error('Password should be at least 6 characters');
      } else if (error.code === 'auth/invalid-email') {
        throw new Error('Invalid email address');
      } else if (error.code === 'PERMISSION_DENIED') {
        throw new Error('Database permission denied. Please check Firebase rules.');
      }
      
      // Log the full error for debugging
      console.error('❌ Sign-up error:', {
        code: error.code,
        message: error.message,
        stack: error.stack
      });
      
      throw error;
    }
  }

  /**
   * Login user with username and password
   */
  async login(formData: LoginFormData): Promise<User> {
    try {
      // Get email directly from username mapping (public read)
      const usernameRef = ref(database, `usernames/${formData.username.toLowerCase()}`);
      const usernameSnapshot = await get(usernameRef);

      if (!usernameSnapshot.exists()) {
        throw new Error('Invalid username or password');
      }

      const { email } = usernameSnapshot.val();

      if (!email) {
        throw new Error('User data incomplete');
      }

      // Sign in with email and password
      const userCredential = await signInWithEmailAndPassword(
        auth,
        email,
        formData.password
      );

      console.log('✅ Login successful');
      return userCredential.user;
      
    } catch (error: any) {
      if (error.code === 'auth/invalid-credential' || error.code === 'auth/wrong-password') {
        throw new Error('Invalid username or password');
      } else if (error.code === 'auth/too-many-requests') {
        throw new Error('Too many failed attempts. Please try again later');
      } else if (error.code === 'PERMISSION_DENIED') {
        throw new Error('Database permission denied. Please check Firebase rules.');
      }
      
      console.error('❌ Login error:', {
        code: error.code,
        message: error.message
      });
      
      throw error;
    }
  }

  /**
   * Sign out current user
   */
  async signOut(): Promise<void> {
    await firebaseSignOut(auth);
    console.log('✅ User signed out');
  }

  /**
   * Get current user data
   */
  async getUserData(uid: string): Promise<UserData | null> {
    try {
      const userRef = ref(database, `users/${uid}`);
      const snapshot = await get(userRef);
      
      if (snapshot.exists()) {
        return snapshot.val() as UserData;
      }
      return null;
    } catch (error) {
      console.error('❌ Error fetching user data:', error);
      return null;
    }
  }

  /**
   * Check if username is available
   * Useful for real-time validation during sign-up
   */
  async isUsernameAvailable(username: string): Promise<boolean> {
    try {
      const usernameRef = ref(database, `usernames/${username.toLowerCase()}`);
      const snapshot = await get(usernameRef);
      return !snapshot.exists();
    } catch (error) {
      console.error('❌ Error checking username:', error);
      return false;
    }
  }
}

export default new AuthService();