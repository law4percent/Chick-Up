// src/services/deviceService.ts
import { database } from '../config/firebase.config';
import { ref, get, set } from 'firebase/database';

class DeviceService {
  // Verify if device exists in realDevices
  async verifyDevice(deviceUid: string): Promise<boolean> {
    try {
      const deviceRef = ref(database, `realDevices/${deviceUid}`);
      const snapshot = await get(deviceRef);
      return snapshot.exists();
    } catch (error) {
      console.error('Error verifying device:', error);
      throw error;
    }
  }

  // Link device to user
  async linkDeviceToUser(userId: string, deviceUid: string): Promise<void> {
    try {
      const userDeviceRef = ref(database, `users/${userId}/linkedDevice`);
      await set(userDeviceRef, {
        deviceUid,
        linkedAt: new Date().toLocaleString('en-US')
      });
    } catch (error) {
      console.error('Error linking device:', error);
      throw error;
    }
  }

  // Get user's linked device
  async getLinkedDevice(userId: string): Promise<string | null> {
    try {
      const userDeviceRef = ref(database, `users/${userId}/linkedDevice/deviceUid`);
      const snapshot = await get(userDeviceRef);
      return snapshot.exists() ? snapshot.val() : null;
    } catch (error) {
      console.error('Error getting linked device:', error);
      return null;
    }
  }
}

export default new DeviceService();