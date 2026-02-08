// src/services/settingsService.ts
import { ref, onValue, off, set, get } from 'firebase/database';
import { database } from '../config/firebase.config';
import { UserSettings, DispenseSettings, /*NotificationSettings,*/ WaterSettings } from '../types/types';

class SettingsService {
  /**
   * Subscribe to real-time settings updates for a user
   */
  subscribeSettings(
    userId: string,
    callback: (settings: UserSettings | null) => void,
    onError?: (error: Error) => void
  ): () => void {
    const settingsRef = ref(database, `settings/${userId}`);

    const unsubscribe = onValue(
      settingsRef,
      (snapshot) => {
        if (snapshot.exists()) {
          const data = snapshot.val() as UserSettings;
          callback(data);
        } else {
          callback(null);
        }
      },
      (error) => {
        console.error('❌ Settings subscription error:', error);
        if (onError) {
          onError(error);
        }
      }
    );

    // Return cleanup function
    return () => off(settingsRef);
  }

  /**
   * Get user settings once (no real-time updates)
   */
  async getSettings(userId: string): Promise<UserSettings | null> {
    try {
      const settingsRef = ref(database, `settings/${userId}`);
      const snapshot = await get(settingsRef);

      if (snapshot.exists()) {
        return snapshot.val() as UserSettings;
      }
      return null;
    } catch (error) {
      console.error('❌ Error fetching settings:', error);
      throw error;
    }
  }

  /**
   * Update user settings
   */
  async updateSettings(userId: string, settings: Partial<UserSettings>): Promise<void> {
    try {
      const settingsRef = ref(database, `settings/${userId}`);
      const existingSettings = await this.getSettings(userId);

      // Deep merge to ensure nested water settings are properly preserved
      const updatedSettings: UserSettings = {
        // notifications: {
        //   ...existingSettings?.notifications,
        //   ...settings.notifications,
        // },
        feed: {
          ...existingSettings?.feed,
          ...settings.feed,
        },
        water: {
          ...existingSettings?.water,
          ...settings.water,
        },
        updatedAt: Date.now(),
      } as UserSettings;

      await set(settingsRef, updatedSettings);
      console.log('✅ Settings updated successfully');
    } catch (error) {
      console.error('❌ Error updating settings:', error);
      throw error;
    }
  }

  /**
   * Update notification settings
   */
  async updateNotificationSettings(
    userId: string,
    // notifications: NotificationSettings
  ): Promise<void> {
    try {
      // await set(ref(database, `settings/${userId}/notifications`), notifications);
      await set(ref(database, `settings/${userId}/updatedAt`), Date.now());
      console.log('✅ Notification settings updated');
    } catch (error) {
      console.error('❌ Error updating notification settings:', error);
      throw error;
    }
  }

  /**
   * Update feed settings
   */
  async updateFeedSettings(userId: string, feedSettings: DispenseSettings): Promise<void> {
    try {
      // Validate inputs
      if (feedSettings.thresholdPercent < 0 || feedSettings.thresholdPercent > 100) {
        throw new Error('Threshold must be between 0 and 100');
      }
      if (feedSettings.dispenseVolumePercent < 0 || feedSettings.dispenseVolumePercent > 100) {
        throw new Error('Dispense volume must be between 0 and 100');
      }

      await set(ref(database, `settings/${userId}/feed`), feedSettings);
      await set(ref(database, `settings/${userId}/updatedAt`), Date.now());
      console.log('✅ Feed settings updated');
    } catch (error) {
      console.error('❌ Error updating feed settings:', error);
      throw error;
    }
  }

  /**
   * Update water settings
   */
  async updateWaterSettings(userId: string, waterSettings: WaterSettings): Promise<void> {
    try {
      // Validate inputs
      if (waterSettings.thresholdPercent < 0 || waterSettings.thresholdPercent > 100) {
        throw new Error('Threshold must be between 0 and 100');
      }
      if (waterSettings.autoRefillThreshold < 0 || waterSettings.autoRefillThreshold > 100) {
        throw new Error('Auto refill threshold must be between 0 and 100');
      }

      await set(ref(database, `settings/${userId}/water`), waterSettings);
      await set(ref(database, `settings/${userId}/updatedAt`), Date.now());
      console.log('✅ Water settings updated');
    } catch (error) {
      console.error('❌ Error updating water settings:', error);
      throw error;
    }
  }

  /**
   * Initialize default settings for a new user
   */
  async initializeSettings(userId: string): Promise<void> {
    try {
      const defaultSettings: UserSettings = {
        // notifications: {
        //   smsEnabled: true,
        // },
        feed: {
          thresholdPercent: 20,
          dispenseVolumePercent: 10,
        },
        water: {
          thresholdPercent: 20,
          autoRefillEnabled: false,
          autoRefillThreshold: 80,
        },
        updatedAt: Date.now(),
      };

      await set(ref(database, `settings/${userId}`), defaultSettings);
      console.log('✅ Default settings initialized');
    } catch (error) {
      console.error('❌ Error initializing settings:', error);
      throw error;
    }
  }

  /**
   * Get threshold for a specific type
   */
  async getThreshold(userId: string, type: 'water' | 'feed'): Promise<number> {
    try {
      const settings = await this.getSettings(userId);
      if (!settings) {
        return 20; // Default threshold
      }
      return type === 'water' 
        ? settings.water.thresholdPercent 
        : settings.feed.thresholdPercent;
    } catch (error) {
      console.error(`❌ Error getting ${type} threshold:`, error);
      return 20; // Fallback to default
    }
  }

  /**
   * Get dispense volume for a specific type
   */
  async getDispenseVolume(userId: string, type: 'feed'): Promise<number> {
    try {
      const settings = await this.getSettings(userId);
      if (!settings) {
        return 10; // Default feed volume
      }
      return settings.feed.dispenseVolumePercent;
    } catch (error) {
      console.error(`❌ Error getting ${type} dispense volume:`, error);
      return 10; // Fallback to default
    }
  }
}

export default new SettingsService();