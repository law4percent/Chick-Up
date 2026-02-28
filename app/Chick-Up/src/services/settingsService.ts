// src/services/settingsService.ts
import { ref, onValue, off, set, get } from 'firebase/database';
import { database } from '../config/firebase.config';
import { UserSettings, DispenseSettings, WaterSettings } from '../types/types';

const DEFAULT_DISPENSE_COUNTDOWN_MS = 60_000; // 60 s — matches raspi DEFAULT_DISPENSE_COUNTDOWN_MS

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

    onValue(
      settingsRef,
      (snapshot) => {
        if (snapshot.exists()) {
          callback(snapshot.val() as UserSettings);
        } else {
          callback(null);
        }
      },
      (error) => {
        console.error('❌ Settings subscription error:', error);
        onError?.(error);
      }
    );

    return () => off(settingsRef);
  }

  /**
   * Get user settings once (no real-time updates)
   */
  async getSettings(userId: string): Promise<UserSettings | null> {
    try {
      const snapshot = await get(ref(database, `settings/${userId}`));
      return snapshot.exists() ? (snapshot.val() as UserSettings) : null;
    } catch (error) {
      console.error('❌ Error fetching settings:', error);
      throw error;
    }
  }

  /**
   * Update user settings (deep merge to preserve nested fields)
   */
  async updateSettings(userId: string, settings: Partial<UserSettings>): Promise<void> {
    try {
      const existing = await this.getSettings(userId);
      const updated: UserSettings = {
        feed: {
          ...existing?.feed,
          ...settings.feed,
        },
        water: {
          ...existing?.water,
          ...settings.water,
        },
        updatedAt: Date.now(),
      } as UserSettings;

      await set(ref(database, `settings/${userId}`), updated);
      console.log('✅ Settings updated successfully');
    } catch (error) {
      console.error('❌ Error updating settings:', error);
      throw error;
    }
  }

  /**
   * Update feed settings.
   * Includes dispenseCountdownMs — raspi picks this up on next boot
   * and also live mid-session via its 100 ms read loop.
   */
  async updateFeedSettings(userId: string, feedSettings: DispenseSettings): Promise<void> {
    try {
      if (feedSettings.thresholdPercent < 0 || feedSettings.thresholdPercent > 100) {
        throw new Error('Threshold must be between 0 and 100');
      }
      if (feedSettings.dispenseVolumePercent < 0 || feedSettings.dispenseVolumePercent > 100) {
        throw new Error('Dispense volume must be between 0 and 100');
      }
      if (
        feedSettings.dispenseCountdownMs !== undefined &&
        (feedSettings.dispenseCountdownMs < 5_000 || feedSettings.dispenseCountdownMs > 300_000)
      ) {
        throw new Error('Dispense countdown must be between 5 000 ms (5 s) and 300 000 ms (5 min)');
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
   * Initialize default settings for a new user.
   * dispenseCountdownMs defaults to 60 000 ms — matches raspi hardcoded default.
   */
  async initializeSettings(userId: string): Promise<void> {
    try {
      const defaultSettings: UserSettings = {
        feed: {
          thresholdPercent:      20,
          dispenseVolumePercent: 10,
          dispenseCountdownMs:   DEFAULT_DISPENSE_COUNTDOWN_MS,
        },
        water: {
          thresholdPercent:    20,
          autoRefillEnabled:   false,
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
      if (!settings) return 20;
      return type === 'water'
        ? settings.water.thresholdPercent
        : settings.feed.thresholdPercent;
    } catch {
      return 20;
    }
  }

  /**
   * Get dispense volume
   */
  async getDispenseVolume(userId: string, type: 'feed'): Promise<number> {
    try {
      const settings = await this.getSettings(userId);
      return settings?.feed.dispenseVolumePercent ?? 10;
    } catch {
      return 10;
    }
  }

  /**
   * Get dispense countdown in milliseconds
   */
  async getDispenseCountdownMs(userId: string): Promise<number> {
    try {
      const settings = await this.getSettings(userId);
      return settings?.feed.dispenseCountdownMs ?? DEFAULT_DISPENSE_COUNTDOWN_MS;
    } catch {
      return DEFAULT_DISPENSE_COUNTDOWN_MS;
    }
  }
}

export default new SettingsService();