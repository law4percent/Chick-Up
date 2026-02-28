// src/services/settingsService.ts
import { ref, onValue, off, set, get } from 'firebase/database';
import { database } from '../config/firebase.config';
import { UserSettings, DispenseSettings, WaterSettings } from '../types/types';

// ─────────────────────────── CONSTANTS ───────────────────────────────────────

const DEFAULT_DISPENSE_COUNTDOWN_MS = 60_000; // 60s — matches raspi default

// TURN credentials are intentionally NOT stored in Firebase.
// They are loaded directly from .env in webrtcService.ts at stream-start.
// Storing them in Firebase (even under settings/{userId}) would expose them
// to any authenticated user who can read the RTDB.
// The raspi reads TURN from its own credentials/.env — no Firebase needed.


// ─────────────────────────── SERVICE ─────────────────────────────────────────

class SettingsService {

  // ── Subscribe ───────────────────────────────────────────────────────────────

  /**
   * Subscribe to real-time settings updates for a user.
   */
  subscribeSettings(
    userId   : string,
    callback : (settings: UserSettings | null) => void,
    onError? : (error: Error) => void
  ): () => void {
    const settingsRef = ref(database, `settings/${userId}`);
    onValue(
      settingsRef,
      (snapshot) => { callback(snapshot.exists() ? (snapshot.val() as UserSettings) : null); },
      (error)    => { console.error('❌ Settings subscription error:', error); onError?.(error); }
    );
    return () => off(settingsRef);
  }

  // ── Read ────────────────────────────────────────────────────────────────────

  /**
   * Get user settings once (no real-time updates).
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

  // ── Write ───────────────────────────────────────────────────────────────────

  /**
   * Initialize ALL default settings for a new user.
   *
   * Called once from authService.signUp() immediately after account creation.
   * The Raspi depends on these values existing in Firebase before it can run.
   *
   * Writes only:
   *   settings/{userId}/feed
   *   settings/{userId}/water
   *   settings/{userId}/updatedAt
   *
   * Does NOT write turnServer — TURN credentials come from .env only.
   */
  async initializeUserDefaults(userId: string): Promise<void> {
    try {
      const defaults = {
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

      await set(ref(database, `settings/${userId}`), defaults);
      console.log('✅ User defaults initialized');

    } catch (error) {
      console.error('❌ Error initializing user defaults:', error);
      throw error;
    }
  }

  /**
   * Alias kept for backwards compatibility.
   */
  async initializeSettings(userId: string): Promise<void> {
    return this.initializeUserDefaults(userId);
  }

  /**
   * Update user settings.
   *
   * Writes feed, water, and updatedAt as individual granular writes —
   * never as a full set() on settings/{userId}. A full set() would delete
   * any sibling keys that exist at that path (future admin-written fields,
   * or other app versions writing additional keys).
   */
  async updateSettings(userId: string, settings: Partial<UserSettings>): Promise<void> {
    try {
      const writes: Promise<void>[] = [];

      if (settings.feed) {
        writes.push(set(ref(database, `settings/${userId}/feed`), settings.feed));
      }
      if (settings.water) {
        writes.push(set(ref(database, `settings/${userId}/water`), settings.water));
      }
      writes.push(set(ref(database, `settings/${userId}/updatedAt`), Date.now()));

      await Promise.all(writes);
      console.log('✅ Settings updated');
    } catch (error) {
      console.error('❌ Error updating settings:', error);
      throw error;
    }
  }

  /**
   * Update feed settings only.
   */
  async updateFeedSettings(userId: string, feedSettings: DispenseSettings): Promise<void> {
    try {
      if (feedSettings.thresholdPercent < 0 || feedSettings.thresholdPercent > 100)
        throw new Error('Threshold must be between 0 and 100');
      if (feedSettings.dispenseVolumePercent < 0 || feedSettings.dispenseVolumePercent > 100)
        throw new Error('Dispense volume must be between 0 and 100');
      if (
        feedSettings.dispenseCountdownMs !== undefined &&
        (feedSettings.dispenseCountdownMs < 5_000 || feedSettings.dispenseCountdownMs > 300_000)
      ) throw new Error('Dispense countdown must be between 5 000 ms and 300 000 ms');

      await set(ref(database, `settings/${userId}/feed`), feedSettings);
      await set(ref(database, `settings/${userId}/updatedAt`), Date.now());
      console.log('✅ Feed settings updated');
    } catch (error) {
      console.error('❌ Error updating feed settings:', error);
      throw error;
    }
  }

  /**
   * Update water settings only.
   */
  async updateWaterSettings(userId: string, waterSettings: WaterSettings): Promise<void> {
    try {
      if (waterSettings.thresholdPercent < 0 || waterSettings.thresholdPercent > 100)
        throw new Error('Threshold must be between 0 and 100');
      if (waterSettings.autoRefillThreshold < 0 || waterSettings.autoRefillThreshold > 100)
        throw new Error('Auto refill threshold must be between 0 and 100');

      await set(ref(database, `settings/${userId}/water`), waterSettings);
      await set(ref(database, `settings/${userId}/updatedAt`), Date.now());
      console.log('✅ Water settings updated');
    } catch (error) {
      console.error('❌ Error updating water settings:', error);
      throw error;
    }
  }

  // ── Getters ─────────────────────────────────────────────────────────────────

  async getThreshold(userId: string, type: 'water' | 'feed'): Promise<number> {
    try {
      const settings = await this.getSettings(userId);
      if (!settings) return 20;
      return type === 'water' ? settings.water.thresholdPercent : settings.feed.thresholdPercent;
    } catch { return 20; }
  }

  async getDispenseVolume(userId: string): Promise<number> {
    try {
      const settings = await this.getSettings(userId);
      return settings?.feed.dispenseVolumePercent ?? 10;
    } catch { return 10; }
  }

  async getDispenseCountdownMs(userId: string): Promise<number> {
    try {
      const settings = await this.getSettings(userId);
      return settings?.feed.dispenseCountdownMs ?? DEFAULT_DISPENSE_COUNTDOWN_MS;
    } catch { return DEFAULT_DISPENSE_COUNTDOWN_MS; }
  }
}

export default new SettingsService();