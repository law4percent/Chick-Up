// src/services/triggerService.ts
import { ref, set, push } from 'firebase/database';
import { database } from '../config/firebase.config';
import { TriggerData } from '../types/types';

class TriggerService {
  /**
   * Create a dispense trigger
   */
  async createTrigger(
    userId: string,
    type: 'water' | 'feed',
    volumePercent: number
  ): Promise<string> {
    try {
      const timestamp = Date.now();
      
      const triggerData: TriggerData = {
        type,
        userId,
        timestamp,
        volumePercent,
        processed: false,
      };

      // Use timestamp as the key for uniqueness
      const triggerRef = ref(database, `triggers/${timestamp}`);
      await set(triggerRef, triggerData);

      console.log(`✅ ${type} trigger created with timestamp: ${timestamp}`);
      return timestamp.toString();
    } catch (error) {
      console.error(`❌ Error creating ${type} trigger:`, error);
      throw error;
    }
  }

  /**
   * Create a water dispense trigger
   */
  async createWaterTrigger(userId: string, volumePercent: number): Promise<string> {
    return this.createTrigger(userId, 'water', volumePercent);
  }

  /**
   * Create a feed dispense trigger
   */
  async createFeedTrigger(userId: string, volumePercent: number): Promise<string> {
    return this.createTrigger(userId, 'feed', volumePercent);
  }

  /**
   * Utility to wait for a specified duration (for cooldown)
   */
  async wait(milliseconds: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, milliseconds));
  }
}

export default new TriggerService();