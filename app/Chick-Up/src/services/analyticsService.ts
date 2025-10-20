// src/services/analyticsService.ts
import { ref, onValue, off, set, get, push } from 'firebase/database';
import { database } from '../config/firebase.config';
import { DispenseLog, DailyAnalytics } from '../types/types';

class AnalyticsService {
  /**
   * Log a dispense/refill action
   */
  async logAction(
    userId: string,
    type: 'water' | 'feed',
    action: 'dispense' | 'refill',
    volumePercent: number
  ): Promise<void> {
    try {
      const timestamp = Date.now();
      const date = new Date(timestamp);
      const dateString = date.toLocaleDateString('en-US');
      const timeString = date.toLocaleTimeString('en-US', { hour12: false });
      const dayOfWeek = date.getDay();

      const logData: Omit<DispenseLog, 'id'> = {
        userId,
        type,
        action,
        volumePercent,
        timestamp,
        date: dateString,
        time: timeString,
        dayOfWeek,
      };

      const logRef = ref(database, `analytics/logs/${userId}`);
      const newLogRef = push(logRef);
      await set(newLogRef, logData);

      console.log(`✅ ${type} ${action} action logged`);
    } catch (error) {
      console.error('❌ Error logging action:', error);
      throw error;
    }
  }

  /**
   * Get all logs for a user
   */
  async getLogs(userId: string, limit?: number): Promise<DispenseLog[]> {
    try {
      const logRef = ref(database, `analytics/logs/${userId}`);
      const snapshot = await get(logRef);

      if (snapshot.exists()) {
        const data = snapshot.val();
        let logs: DispenseLog[] = Object.keys(data).map(key => ({
          id: key,
          ...data[key]
        }));

        // Sort by timestamp descending
        logs.sort((a, b) => b.timestamp - a.timestamp);

        if (limit) {
          logs = logs.slice(0, limit);
        }

        return logs;
      }
      return [];
    } catch (error) {
      console.error('❌ Error fetching logs:', error);
      throw error;
    }
  }

  /**
   * Get daily analytics for the past week
   */
  async getWeeklyAnalytics(userId: string): Promise<DailyAnalytics[]> {
    try {
      const logs = await this.getLogs(userId);
      const now = new Date();
      const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);

      // Filter logs from the past 7 days
      const recentLogs = logs.filter(log => log.timestamp >= sevenDaysAgo.getTime());

      // Group logs by date
      const logsByDate: { [date: string]: DispenseLog[] } = {};
      recentLogs.forEach(log => {
        if (!logsByDate[log.date]) {
          logsByDate[log.date] = [];
        }
        logsByDate[log.date].push(log);
      });

      // Calculate daily analytics
      const analytics: DailyAnalytics[] = [];
      
      for (let i = 6; i >= 0; i--) {
        const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
        const dateString = date.toLocaleDateString('en-US');
        const dayOfWeek = date.getDay();
        const dayLogs = logsByDate[dateString] || [];

        const feedLogs = dayLogs.filter(log => log.type === 'feed' && log.action === 'dispense');
        const waterLogs = dayLogs.filter(log => log.type === 'water' && log.action === 'refill');

        const feedDispensed = feedLogs.reduce((sum, log) => sum + log.volumePercent, 0);
        const waterRefilled = waterLogs.reduce((sum, log) => sum + log.volumePercent, 0);

        // Calculate average time (mock data - in real implementation, this would be tracked)
        const avgFeedingTime = feedLogs.length > 0 ? 3 : 0; // 3 minutes average
        const avgRefillTime = waterLogs.length > 0 ? 15 : 0; // 15 minutes average

        analytics.push({
          date: dateString,
          dayOfWeek,
          feedDispensed,
          waterRefilled,
          feedDispenseCount: feedLogs.length,
          waterRefillCount: waterLogs.length,
          avgFeedingTime,
          avgRefillTime,
        });
      }

      return analytics;
    } catch (error) {
      console.error('❌ Error fetching weekly analytics:', error);
      throw error;
    }
  }

  /**
   * Get summary statistics
   */
  async getSummaryStats(userId: string): Promise<{
    totalFeedDispensed: number;
    totalWaterRefilled: number;
    totalFeedActions: number;
    totalWaterActions: number;
    avgFeedPerDay: number;
    avgWaterPerDay: number;
  }> {
    try {
      const analytics = await this.getWeeklyAnalytics(userId);

      const totalFeedDispensed = analytics.reduce((sum, day) => sum + day.feedDispensed, 0);
      const totalWaterRefilled = analytics.reduce((sum, day) => sum + day.waterRefilled, 0);
      const totalFeedActions = analytics.reduce((sum, day) => sum + day.feedDispenseCount, 0);
      const totalWaterActions = analytics.reduce((sum, day) => sum + day.waterRefillCount, 0);

      return {
        totalFeedDispensed,
        totalWaterRefilled,
        totalFeedActions,
        totalWaterActions,
        avgFeedPerDay: totalFeedDispensed / 7,
        avgWaterPerDay: totalWaterRefilled / 7,
      };
    } catch (error) {
      console.error('❌ Error fetching summary stats:', error);
      throw error;
    }
  }

  /**
   * Subscribe to real-time analytics updates
   */
  subscribeAnalytics(
    userId: string,
    callback: (analytics: DailyAnalytics[]) => void,
    onError?: (error: Error) => void
  ): () => void {
    const logRef = ref(database, `analytics/logs/${userId}`);

    const unsubscribe = onValue(
      logRef,
      async () => {
        try {
          const analytics = await this.getWeeklyAnalytics(userId);
          callback(analytics);
        } catch (error: any) {
          if (onError) {
            onError(error);
          }
        }
      },
      (error) => {
        console.error('❌ Analytics subscription error:', error);
        if (onError) {
          onError(error);
        }
      }
    );

    // Return cleanup function
    return () => off(logRef);
  }
}

export default new AnalyticsService();