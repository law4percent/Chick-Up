// src/services/sensorService.ts
import { ref, set, get, onValue, update, off } from 'firebase/database';
import { database } from '../config/firebase.config';

export interface SensorData {
  waterLevel: number;
  feedLevel: number;
  updatedAt: string;
}

class SensorService {
  /**
   * Initialize sensor data for a new user with default device
   */
  async initializeSensorData(userId: string, deviceId: string = '-3GSRmf356dy6GFQSTGIF'): Promise<void> {
    try {
      const sensorRef = ref(database, `sensors/${userId}/${deviceId}`);
      const snapshot = await get(sensorRef);
      
      if (!snapshot.exists()) {
        const now = new Date();
        const formattedDate = this.formatDateTime(now);
        
        await set(sensorRef, {
          waterLevel: 0,
          feedLevel: 0,
          updatedAt: formattedDate
        });
        
        console.log('Sensor data initialized successfully');
      }
    } catch (error) {
      console.error('Error initializing sensor data:', error);
      throw error;
    }
  }

  /**
   * Get sensor data for a specific user and device
   */
  async getSensorData(userId: string, deviceId: string = '-3GSRmf356dy6GFQSTGIF'): Promise<SensorData | null> {
    try {
      const sensorRef = ref(database, `sensors/${userId}/${deviceId}`);
      const snapshot = await get(sensorRef);
      
      if (snapshot.exists()) {
        return snapshot.val() as SensorData;
      }
      return null;
    } catch (error) {
      console.error('Error getting sensor data:', error);
      throw error;
    }
  }

  /**
   * Subscribe to real-time sensor data updates
   */
  subscribeSensorData(
    userId: string,
    onUpdate: (data: SensorData | null) => void,
    onError: (error: Error) => void,
    deviceId: string = '-3GSRmf356dy6GFQSTGIF'
  ): () => void {
    const sensorRef = ref(database, `sensors/${userId}/${deviceId}`);
    
    const unsubscribe = onValue(
      sensorRef,
      (snapshot) => {
        if (snapshot.exists()) {
          onUpdate(snapshot.val() as SensorData);
        } else {
          onUpdate(null);
        }
      },
      (error) => {
        onError(error as Error);
      }
    );

    return () => off(sensorRef);
  }

  /**
   * Update sensor levels (for testing or manual updates)
   */
  async updateSensorLevels(
    userId: string,
    waterLevel?: number,
    feedLevel?: number,
    deviceId: string = '-3GSRmf356dy6GFQSTGIF'
  ): Promise<void> {
    try {
      const now = new Date();
      const formattedDate = this.formatDateTime(now);
      
      const sensorRef = ref(database, `sensors/${userId}/${deviceId}`);
      const updates: any = {
        updatedAt: formattedDate
      };
      
      if (waterLevel !== undefined) {
        updates.waterLevel = waterLevel;
      }
      if (feedLevel !== undefined) {
        updates.feedLevel = feedLevel;
      }
      
      await update(sensorRef, updates);
      console.log('Sensor levels updated successfully');
    } catch (error) {
      console.error('Error updating sensor levels:', error);
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

export default new SensorService();