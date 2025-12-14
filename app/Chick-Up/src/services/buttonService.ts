// src/services/buttonService.ts
import { ref, set, get, onValue, update, off, serverTimestamp } from 'firebase/database';
import { database } from '../config/firebase.config';

export interface ButtonData {
  waterButton?: {
    lastUpdateAt: number | string; // Changed to accept both
  };
  feedButton?: {
    lastUpdateAt: number | string; // Changed to accept both
  };
}

class ButtonService {
  /**
   * Initialize button data for a user with their linked device
   */
  async initializeButtonData(userId: string, deviceId: string): Promise<void> {
    try {
      const buttonRef = ref(database, `buttons/${userId}/${deviceId}`);
      const snapshot = await get(buttonRef);
      
      if (!snapshot.exists()) {
        await set(buttonRef, {
          waterButton: {
            lastUpdateAt: serverTimestamp()
          },
          feedButton: {
            lastUpdateAt: serverTimestamp()
          }
        });
        
        console.log('Button data initialized successfully for device:', deviceId);
      }
    } catch (error) {
      console.error('Error initializing button data:', error);
      throw error;
    }
  }

  /**
   * Get button data for a specific user and device
   */
  async getButtonData(userId: string, deviceId: string): Promise<ButtonData | null> {
    try {
      const buttonRef = ref(database, `buttons/${userId}/${deviceId}`);
      const snapshot = await get(buttonRef);
      
      if (snapshot.exists()) {
        return snapshot.val() as ButtonData;
      }
      return null;
    } catch (error) {
      console.error('Error getting button data:', error);
      throw error;
    }
  }

  /**
   * Subscribe to real-time button data updates
   */
  subscribeButtonData(
    userId: string,
    deviceId: string,
    onUpdate: (data: ButtonData | null) => void,
    onError: (error: Error) => void
  ): () => void {
    const buttonRef = ref(database, `buttons/${userId}/${deviceId}`);
    
    const unsubscribe = onValue(
      buttonRef,
      (snapshot) => {
        if (snapshot.exists()) {
          onUpdate(snapshot.val() as ButtonData);
        } else {
          onUpdate(null);
        }
      },
      (error) => {
        onError(error as Error);
      }
    );

    return () => off(buttonRef);
  }

  /**
   * Update button timestamp when water is refilled or feed is dispensed
   * Uses Firebase Server Timestamp to avoid timezone issues
   */
  async updateButtonTimestamp(
    userId: string,
    deviceId: string,
    type: 'water' | 'feed'
  ): Promise<void> {
    try {
      const buttonPath = type === 'water' ? 'waterButton' : 'feedButton';
      const buttonRef = ref(database, `buttons/${userId}/${deviceId}/${buttonPath}`);
      
      // Use Firebase Server Timestamp - this is timezone-independent
      await update(buttonRef, {
        lastUpdateAt: serverTimestamp()
      });
      
      console.log(`${type} button timestamp updated using server timestamp`);
    } catch (error) {
      console.error(`Error updating ${type} button timestamp:`, error);
      throw error;
    }
  }

  /**
   * Helper to format timestamp for display (optional, for UI only)
   */
  formatTimestampForDisplay(timestamp: number, timezone: string = 'Asia/Manila'): string {
    try {
      const date = new Date(timestamp);
      return date.toLocaleString('en-US', {
        timeZone: timezone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      });
    } catch (error) {
      console.error('Error formatting timestamp:', error);
      return 'Invalid date';
    }
  }
}

export default new ButtonService();