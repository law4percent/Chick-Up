// src/services/analyticsService.ts
import { ref, push, set, get, query, orderByChild, limitToLast, onValue, off } from 'firebase/database';
import { database } from '../config/firebase.config';

export interface AnalyticsLog {
  action: 'refill' | 'dispense';
  type: 'water' | 'feed';
  volumePercent: number;
  timestamp: number;
  date: string;
  time: string;
  dayOfWeek: number;
  userId: string;
}

export interface DailyAnalytics {
  dayOfWeek: number;
  feedDispensed: number;
  waterRefilled: number;
  feedDispenseCount: number;
  waterRefillCount: number;
  avgFeedingTime: number;
  avgRefillTime: number;
}

export interface SummaryStats {
  totalFeedDispensed: number;
  totalWaterRefilled: number;
  totalFeedActions: number;
  totalWaterActions: number;
  avgFeedPerDay: number;
  avgWaterPerDay: number;
}

class AnalyticsService {
  /**
   * Log an action (water refill or feed dispense)
   */
  async logAction(
    userId: string,
    type: 'water' | 'feed',
    action: 'refill' | 'dispense',
    volumePercent: number
  ): Promise<void> {
    try {
      const now = new Date();
      const logsRef = ref(database, `analytics/logs/${userId}`);
      const newLogRef = push(logsRef);
      
      const logData: AnalyticsLog = {
        action,
        type,
        volumePercent,
        timestamp: now.getTime(),
        date: this.formatDate(now),
        time: this.formatTime(now),
        dayOfWeek: now.getDay(),
        userId
      };
      
      await set(newLogRef, logData);
      console.log(`${type} ${action} logged successfully`);
    } catch (error) {
      console.error('Error logging action:', error);
      throw error;
    }
  }

  /**
   * Get all logs for a user
   */
  async getAllLogs(userId: string): Promise<AnalyticsLog[]> {
    try {
      const logsRef = ref(database, `analytics/logs/${userId}`);
      const snapshot = await get(logsRef);
      
      if (snapshot.exists()) {
        const logs: AnalyticsLog[] = [];
        snapshot.forEach((childSnapshot) => {
          logs.push(childSnapshot.val() as AnalyticsLog);
        });
        return logs.sort((a, b) => b.timestamp - a.timestamp); // Most recent first
      }
      return [];
    } catch (error) {
      console.error('Error getting all logs:', error);
      throw error;
    }
  }

  /**
   * Get recent logs for a user
   */
  async getRecentLogs(userId: string, limit: number = 10): Promise<AnalyticsLog[]> {
    try {
      const logsRef = ref(database, `analytics/logs/${userId}`);
      const logsQuery = query(logsRef, orderByChild('timestamp'), limitToLast(limit));
      const snapshot = await get(logsQuery);
      
      if (snapshot.exists()) {
        const logs: AnalyticsLog[] = [];
        snapshot.forEach((childSnapshot) => {
          logs.push(childSnapshot.val() as AnalyticsLog);
        });
        return logs.reverse(); // Most recent first
      }
      return [];
    } catch (error) {
      console.error('Error getting recent logs:', error);
      throw error;
    }
  }

  /**
   * Get logs filtered by type (water or feed)
   */
  async getLogsByType(userId: string, type: 'water' | 'feed', limit: number = 10): Promise<AnalyticsLog[]> {
    try {
      const logs = await this.getAllLogs(userId);
      return logs.filter(log => log.type === type).slice(0, limit);
    } catch (error) {
      console.error('Error getting logs by type:', error);
      throw error;
    }
  }

  /**
   * Get the last action of a specific type
   */
  async getLastAction(userId: string, type: 'water' | 'feed'): Promise<AnalyticsLog | null> {
    try {
      const logs = await this.getLogsByType(userId, type, 1);
      return logs.length > 0 ? logs[0] : null;
    } catch (error) {
      console.error('Error getting last action:', error);
      throw error;
    }
  }

  /**
   * Subscribe to real-time analytics updates
   */
  subscribeAnalytics(
    userId: string,
    onUpdate: (analytics: DailyAnalytics[]) => void,
    onError: (error: Error) => void
  ): () => void {
    const logsRef = ref(database, `analytics/logs/${userId}`);
    
    const unsubscribe = onValue(
      logsRef,
      (snapshot) => {
        const logs: AnalyticsLog[] = [];
        if (snapshot.exists()) {
          snapshot.forEach((childSnapshot) => {
            logs.push(childSnapshot.val() as AnalyticsLog);
          });
        }
        
        const analytics = this.processLogsToWeekly(logs);
        onUpdate(analytics);
      },
      (error) => {
        onError(error as Error);
      }
    );

    return () => off(logsRef);
  }

  /**
   * Process logs into weekly analytics (last 7 days)
   */
  private processLogsToWeekly(logs: AnalyticsLog[]): DailyAnalytics[] {
    // Get the last 7 days
    const today = new Date();
    const weeklyData: DailyAnalytics[] = [];
    
    for (let i = 6; i >= 0; i--) {
      const date = new Date(today);
      date.setDate(date.getDate() - i);
      const dayOfWeek = date.getDay();
      
      // Filter logs for this day
      const dayLogs = logs.filter(log => {
        const logDate = new Date(log.timestamp);
        return logDate.toDateString() === date.toDateString();
      });
      
      // Calculate metrics for this day
      const feedLogs = dayLogs.filter(log => log.type === 'feed');
      const waterLogs = dayLogs.filter(log => log.type === 'water');
      
      const feedDispensed = feedLogs.reduce((sum, log) => sum + log.volumePercent, 0);
      const waterRefilled = waterLogs.reduce((sum, log) => sum + log.volumePercent, 0);
      
      // Estimate time (rough calculation: 0.5 min per action)
      const avgFeedingTime = feedLogs.length * 0.5;
      const avgRefillTime = waterLogs.length * 0.5;
      
      weeklyData.push({
        dayOfWeek,
        feedDispensed,
        waterRefilled,
        feedDispenseCount: feedLogs.length,
        waterRefillCount: waterLogs.length,
        avgFeedingTime,
        avgRefillTime,
      });
    }
    
    return weeklyData;
  }

  /**
   * Get summary statistics
   */
  async getSummaryStats(userId: string): Promise<SummaryStats> {
    try {
      const logs = await this.getAllLogs(userId);
      
      const feedLogs = logs.filter(log => log.type === 'feed');
      const waterLogs = logs.filter(log => log.type === 'water');
      
      const totalFeedDispensed = feedLogs.reduce((sum, log) => sum + log.volumePercent, 0);
      const totalWaterRefilled = waterLogs.reduce((sum, log) => sum + log.volumePercent, 0);
      
      // Calculate daily averages (last 7 days)
      const sevenDaysAgo = new Date();
      sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
      
      const recentFeedLogs = feedLogs.filter(log => log.timestamp >= sevenDaysAgo.getTime());
      const recentWaterLogs = waterLogs.filter(log => log.timestamp >= sevenDaysAgo.getTime());
      
      const recentFeedVolume = recentFeedLogs.reduce((sum, log) => sum + log.volumePercent, 0);
      const recentWaterVolume = recentWaterLogs.reduce((sum, log) => sum + log.volumePercent, 0);
      
      return {
        totalFeedDispensed,
        totalWaterRefilled,
        totalFeedActions: feedLogs.length,
        totalWaterActions: waterLogs.length,
        avgFeedPerDay: recentFeedVolume / 7,
        avgWaterPerDay: recentWaterVolume / 7,
      };
    } catch (error) {
      console.error('Error getting summary stats:', error);
      return {
        totalFeedDispensed: 0,
        totalWaterRefilled: 0,
        totalFeedActions: 0,
        totalWaterActions: 0,
        avgFeedPerDay: 0,
        avgWaterPerDay: 0,
      };
    }
  }

  /**
   * Calculate total volume dispensed/refilled for a specific type
   */
  async getTotalVolume(userId: string, type: 'water' | 'feed'): Promise<number> {
    try {
      const logs = await this.getLogsByType(userId, type, 1000);
      return logs.reduce((total, log) => total + log.volumePercent, 0);
    } catch (error) {
      console.error('Error calculating total volume:', error);
      throw error;
    }
  }

  /**
   * Format date as "MM/DD/YYYY"
   */
  private formatDate(date: Date): string {
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const year = date.getFullYear();
    return `${month}/${day}/${year}`;
  }

  /**
   * Format time as "HH:MM:SS"
   */
  private formatTime(date: Date): string {
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    return `${hours}:${minutes}:${seconds}`;
  }
}

export default new AnalyticsService();