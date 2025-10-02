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
    try {
      // Check if username already exists
      const usernameRef = ref(database, `usernames/${formData.username.toLowerCase()}`);
      const usernameSnapshot = await get(usernameRef);
      
      if (usernameSnapshot.exists()) {
        throw new Error('Username already taken');
      }

      // Create user in Firebase Authentication
      const userCredential = await createUserWithEmailAndPassword(
        auth,
        formData.email,
        formData.password
      );

      const user = userCredential.user;
      const timestamp = Date.now();

      // Create user data object
      const userData: UserData = {
        uid: user.uid,
        username: formData.username,
        email: formData.email,
        phoneNumber: formData.phoneNumber,
        createdAt: timestamp,
        updatedAt: timestamp,
      };

      // Store user data in Realtime Database
      await set(ref(database, `users/${user.uid}`), userData);

      // Store username to email mapping for login
      await set(ref(database, `usernames/${formData.username.toLowerCase()}`), {
        email: formData.email,
      });

      // Sign out after registration (user will be redirected to login)
      await firebaseSignOut(auth);
    } catch (error: any) {
      if (error.code === 'auth/email-already-in-use') {
        throw new Error('Email already in use');
      } else if (error.code === 'auth/weak-password') {
        throw new Error('Password should be at least 6 characters');
      } else if (error.code === 'auth/invalid-email') {
        throw new Error('Invalid email address');
      }
      throw error;
    }
  }

  /**
   * Login user with username and password
   */
  async login(formData: LoginFormData): Promise<User> {
    try {
      // Get email from username
      const usernameRef = ref(database, `usernames/${formData.username.toLowerCase()}`);
      const usernameSnapshot = await get(usernameRef);

      if (!usernameSnapshot.exists()) {
        throw new Error('Invalid username or password');
      }

      const email = usernameSnapshot.val().email;

      // Sign in with email and password
      const userCredential = await signInWithEmailAndPassword(
        auth,
        email,
        formData.password
      );

      return userCredential.user;
    } catch (error: any) {
      if (error.code === 'auth/invalid-credential' || error.code === 'auth/wrong-password') {
        throw new Error('Invalid username or password');
      } else if (error.code === 'auth/too-many-requests') {
        throw new Error('Too many failed attempts. Please try again later');
      }
      throw error;
    }
  }

  /**
   * Sign out current user
   */
  async signOut(): Promise<void> {
    await firebaseSignOut(auth);
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
      console.error('Error fetching user data:', error);
      return null;
    }
  }
}

export default new AuthService();