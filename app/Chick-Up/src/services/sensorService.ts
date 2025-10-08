// src/services/sensorService.ts
import { ref, onValue, off, set, get } from 'firebase/database';
import { database } from '../config/firebase.config';
import { SensorData, DispenseData } from '../types/types';

class SensorService {
  /**
   * Subscribe to real-time sensor data updates for a user
   */
  subscribeSensorData(
    userId: string,
    callback: (data: SensorData | null) => void,
    onError?: (error: Error) => void
  ): () => void {
    const sensorRef = ref(database, `sensors/${userId}`);

    const unsubscribe = onValue(
      sensorRef,
      (snapshot) => {
        if (snapshot.exists()) {
          const data = snapshot.val() as SensorData;
          callback(data);
        } else {
          callback(null);
        }
      },
      (error) => {
        console.error('❌ Sensor data subscription error:', error);
        if (onError) {
          onError(error);
        }
      }
    );

    // Return cleanup function
    return () => off(sensorRef);
  }

  /**
   * Get sensor data once (no real-time updates)
   */
  async getSensorData(userId: string): Promise<SensorData | null> {
    try {
      const sensorRef = ref(database, `sensors/${userId}`);
      const snapshot = await get(sensorRef);

      if (snapshot.exists()) {
        return snapshot.val() as SensorData;
      }
      return null;
    } catch (error) {
      console.error('❌ Error fetching sensor data:', error);
      throw error;
    }
  }

  /**
   * Update sensor data (for testing purposes - normally updated by ESP32)
   */
  async updateSensorData(userId: string, data: Partial<SensorData>): Promise<void> {
    try {
      const sensorRef = ref(database, `sensors/${userId}`);
      const existingData = await this.getSensorData(userId);

      const updatedData: SensorData = {
        ...existingData,
        ...data,
        updatedAt: Date.now(),
      } as SensorData;

      await set(sensorRef, updatedData);
      console.log('✅ Sensor data updated successfully');
    } catch (error) {
      console.error('❌ Error updating sensor data:', error);
      throw error;
    }
  }

  /**
   * Initialize default sensor data for a new user
   */
  async initializeSensorData(userId: string): Promise<void> {
    try {
      const timestamp = Date.now();
      const now = new Date(timestamp);
      const date = now.toLocaleDateString('en-US');
      const time = now.toLocaleTimeString('en-US', { hour12: false });

      const defaultData: SensorData = {
        waterLevel: 100,
        feedLevel: 100,
        lastWaterDispense: {
          date,
          time,
          timestamp,
        },
        lastFeedDispense: {
          date,
          time,
          timestamp,
        },
        updatedAt: timestamp,
      };

      await set(ref(database, `sensors/${userId}`), defaultData);
      console.log('✅ Default sensor data initialized');
    } catch (error) {
      console.error('❌ Error initializing sensor data:', error);
      throw error;
    }
  }

  /**
   * Update dispense timestamp after a dispense action
   */
  async updateDispenseTimestamp(
    userId: string,
    type: 'water' | 'feed'
  ): Promise<void> {
    try {
      const timestamp = Date.now();
      const now = new Date(timestamp);
      const date = now.toLocaleDateString('en-US');
      const time = now.toLocaleTimeString('en-US', { hour12: false });

      const dispenseData: DispenseData = {
        date,
        time,
        timestamp,
      };

      const path = type === 'water' ? 'lastWaterDispense' : 'lastFeedDispense';
      await set(ref(database, `sensors/${userId}/${path}`), dispenseData);

      console.log(`✅ ${type} dispense timestamp updated`);
    } catch (error) {
      console.error(`❌ Error updating ${type} dispense timestamp:`, error);
      throw error;
    }
  }
}

export default new SensorService();