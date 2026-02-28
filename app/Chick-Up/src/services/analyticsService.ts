// src/services/analyticsService.ts
import { ref, push, get, query, orderByChild, limitToLast } from 'firebase/database';
import { database } from '../config/firebase.config';

export type AnalyticsSource = 'app' | 'keypad' | 'schedule';

export interface AnalyticsEntry {
  action       : 'dispense' | 'refill';
  type         : 'feed' | 'water';
  volumePercent: number;
  timestamp    : number;        // Unix ms
  date         : string;        // "MM/DD/YYYY"
  time         : string;        // "HH:MM:SS"
  dayOfWeek    : number;        // 0 = Sun … 6 = Sat  (JS convention)
  userId       : string;
  source       : AnalyticsSource;
}

class AnalyticsService {
  /**
   * Log a feed or water action to analytics/logs/{userId}.
   *
   * Called by the APP after a button press succeeds.
   * The Raspberry Pi writes its own entries via _log_analytics() in process_b.py,
   * using source="keypad" or source="schedule".
   *
   * source is always "app" here — Pi-confirmed actions are written by the Pi.
   */
  async logAction(
    userId       : string,
    type         : 'feed' | 'water',
    action       : 'dispense' | 'refill',
    volumePercent: number,
  ): Promise<void> {
    const now       = new Date();
    const timestamp = now.getTime();

    // JS Date.getDay(): 0=Sun … 6=Sat — matches Pi's _PY_TO_JS_DAY mapping
    const dayOfWeek = now.getDay();

    const pad = (n: number) => String(n).padStart(2, '0');
    const date = `${pad(now.getMonth() + 1)}/${pad(now.getDate())}/${now.getFullYear()}`;
    const time = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;

    const entry: AnalyticsEntry = {
      action,
      type,
      volumePercent,
      timestamp,
      date,
      time,
      dayOfWeek,
      userId,
      source: 'app',
    };

    try {
      await push(ref(database, `analytics/logs/${userId}`), entry);
      console.log(`✅ Analytics logged: ${entry.source} ${type} ${action}`);
    } catch (error) {
      console.error('❌ Failed to log analytics:', error);
      throw error;
    }
  }

  /**
   * Fetch the last N analytics entries for a user, newest first.
   */
  async getRecentLogs(userId: string, limit: number = 50): Promise<AnalyticsEntry[]> {
    try {
      const logsRef = query(
        ref(database, `analytics/logs/${userId}`),
        orderByChild('timestamp'),
        limitToLast(limit),
      );
      const snapshot = await get(logsRef);
      if (!snapshot.exists()) return [];

      const entries: AnalyticsEntry[] = [];
      snapshot.forEach(child => {
        entries.push({ ...child.val() } as AnalyticsEntry);
      });

      // Newest first
      return entries.reverse();
    } catch (error) {
      console.error('❌ Failed to fetch analytics:', error);
      throw error;
    }
  }
}

export default new AnalyticsService();