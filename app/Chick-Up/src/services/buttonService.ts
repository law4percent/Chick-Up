// src/services/buttonService.ts
import { ref, set, get, onValue, update, off } from 'firebase/database';
import { database } from '../config/firebase.config';

export interface ButtonData {
  waterButton?: {
    lastUpdateAt: string;
  };
  feedButton?: {
    lastUpdateAt: string;
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
        const now = new Date();
        const formattedDate = this.formatDateTime(now);
        
        await set(buttonRef, {
          waterButton: {
            lastUpdateAt: formattedDate
          },
          feedButton: {
            lastUpdateAt: formattedDate
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
   */
  async updateButtonTimestamp(
    userId: string,
    deviceId: string,
    type: 'water' | 'feed'
  ): Promise<void> {
    try {
      const now = new Date();
      const formattedDate = this.formatDateTime(now);
      
      const buttonPath = type === 'water' ? 'waterButton' : 'feedButton';
      const buttonRef = ref(database, `buttons/${userId}/${deviceId}/${buttonPath}`);
      
      await update(buttonRef, {
        lastUpdateAt: formattedDate
      });
      
      console.log(`${type} button timestamp updated for device:`, deviceId);
    } catch (error) {
      console.error(`Error updating ${type} button timestamp:`, error);
      throw error;
    }
  }

  /**
   * Format date and time as "MM/DD/YYYY HH:MM:SS"
   */
  private formatDateTime(date: Date): string {
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const year = date.getFullYear();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    
    return `${month}/${day}/${year} ${hours}:${minutes}:${seconds}`;
  }
}

export default new ButtonService();