// src/services/scheduleService.ts
import { ref, onValue, off, set, get, push, remove } from 'firebase/database';
import { database } from '../config/firebase.config';
import { FeedSchedule } from '../types/types';

class ScheduleService {
  /**
   * Subscribe to real-time schedule updates for a user
   */
  subscribeSchedules(
    userId: string,
    callback: (schedules: FeedSchedule[]) => void,
    onError?: (error: Error) => void
  ): () => void {
    const scheduleRef = ref(database, `schedules/${userId}`);

    const unsubscribe = onValue(
      scheduleRef,
      (snapshot) => {
        if (snapshot.exists()) {
          const data = snapshot.val();
          const schedules: FeedSchedule[] = Object.keys(data).map(key => ({
            id: key,
            ...data[key]
          }));
          callback(schedules);
        } else {
          callback([]);
        }
      },
      (error) => {
        console.error('❌ Schedule subscription error:', error);
        if (onError) {
          onError(error);
        }
      }
    );

    // Return cleanup function
    return () => off(scheduleRef);
  }

  /**
   * Get all schedules for a user
   */
  async getSchedules(userId: string): Promise<FeedSchedule[]> {
    try {
      const scheduleRef = ref(database, `schedules/${userId}`);
      const snapshot = await get(scheduleRef);

      if (snapshot.exists()) {
        const data = snapshot.val();
        return Object.keys(data).map(key => ({
          id: key,
          ...data[key]
        }));
      }
      return [];
    } catch (error) {
      console.error('❌ Error fetching schedules:', error);
      throw error;
    }
  }

  /**
   * Create a new feed schedule
   */
  async createSchedule(
    userId: string,
    time: string,
    days: number[],
    volumePercent: number
  ): Promise<string> {
    try {
      const timestamp = Date.now();
      
      const scheduleData: Omit<FeedSchedule, 'id'> = {
        userId,
        enabled: true,
        time,
        days,
        volumePercent,
        createdAt: timestamp,
        updatedAt: timestamp,
      };

      const scheduleRef = ref(database, `schedules/${userId}`);
      const newScheduleRef = push(scheduleRef);
      await set(newScheduleRef, scheduleData);

      console.log('✅ Feed schedule created successfully');
      return newScheduleRef.key || '';
    } catch (error) {
      console.error('❌ Error creating schedule:', error);
      throw error;
    }
  }

  /**
   * Update an existing schedule
   */
  async updateSchedule(
    userId: string,
    scheduleId: string,
    updates: Partial<Omit<FeedSchedule, 'id' | 'userId' | 'createdAt'>>
  ): Promise<void> {
    try {
      const scheduleRef = ref(database, `schedules/${userId}/${scheduleId}`);
      const existingSchedule = await this.getScheduleById(userId, scheduleId);

      if (!existingSchedule) {
        throw new Error('Schedule not found');
      }

      const updatedSchedule = {
        ...existingSchedule,
        ...updates,
        updatedAt: Date.now(),
      };

      await set(scheduleRef, updatedSchedule);
      console.log('✅ Schedule updated successfully');
    } catch (error) {
      console.error('❌ Error updating schedule:', error);
      throw error;
    }
  }

  /**
   * Get a specific schedule by ID
   */
  async getScheduleById(userId: string, scheduleId: string): Promise<FeedSchedule | null> {
    try {
      const scheduleRef = ref(database, `schedules/${userId}/${scheduleId}`);
      const snapshot = await get(scheduleRef);

      if (snapshot.exists()) {
        return {
          id: scheduleId,
          ...snapshot.val()
        };
      }
      return null;
    } catch (error) {
      console.error('❌ Error fetching schedule:', error);
      throw error;
    }
  }

  /**
   * Delete a schedule
   */
  async deleteSchedule(userId: string, scheduleId: string): Promise<void> {
    try {
      const scheduleRef = ref(database, `schedules/${userId}/${scheduleId}`);
      await remove(scheduleRef);
      console.log('✅ Schedule deleted successfully');
    } catch (error) {
      console.error('❌ Error deleting schedule:', error);
      throw error;
    }
  }

  /**
   * Toggle schedule enabled/disabled
   */
  async toggleSchedule(userId: string, scheduleId: string, enabled: boolean): Promise<void> {
    try {
      const scheduleRef = ref(database, `schedules/${userId}/${scheduleId}/enabled`);
      await set(scheduleRef, enabled);
      
      const updatedAtRef = ref(database, `schedules/${userId}/${scheduleId}/updatedAt`);
      await set(updatedAtRef, Date.now());
      
      console.log(`✅ Schedule ${enabled ? 'enabled' : 'disabled'}`);
    } catch (error) {
      console.error('❌ Error toggling schedule:', error);
      throw error;
    }
  }
}

export default new ScheduleService();