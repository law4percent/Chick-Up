// src/services/analyticsService.ts
import { ref, push, get, query, orderByChild, limitToLast, onValue, off } from 'firebase/database';
import { database } from '../config/firebase.config';

export type AnalyticsSource = 'app' | 'keypad' | 'schedule';

export interface AnalyticsEntry {
  action       : 'dispense' | 'refill';
  type         : 'feed' | 'water';
  volumePercent: number;
  timestamp    : number;
  date         : string;
  time         : string;
  dayOfWeek    : number;
  userId       : string;
  source       : AnalyticsSource;
}

// ── Types expected by AnalyticsScreen ────────────────────────────────────────

export interface DailyAnalytics {
  dayOfWeek         : number;   // 0 = Sun … 6 = Sat
  feedDispensed     : number;   // sum of volumePercent for feed actions
  waterRefilled     : number;   // sum of volumePercent for water actions
  feedDispenseCount : number;
  waterRefillCount  : number;
  avgFeedingTime    : number;   // placeholder — no duration data yet, always 0
  avgRefillTime     : number;   // placeholder — no duration data yet, always 0
}

export interface SummaryStats {
  totalFeedDispensed : number;
  totalWaterRefilled : number;
  totalFeedActions   : number;
  totalWaterActions  : number;
  avgFeedPerDay      : number;
  avgWaterPerDay     : number;
}

// ─────────────────────────────────────────────────────────────────────────────

/**
 * Aggregate a flat list of AnalyticsEntry records into 7 DailyAnalytics buckets
 * (one per day of the week, Sun–Sat). Entries from all time are included —
 * values accumulate across weeks. Days with no activity are returned as zeros.
 */
function aggregateToDailyAnalytics(entries: AnalyticsEntry[]): DailyAnalytics[] {
  const buckets: DailyAnalytics[] = Array.from({ length: 7 }, (_, i) => ({
    dayOfWeek        : i,
    feedDispensed    : 0,
    waterRefilled    : 0,
    feedDispenseCount: 0,
    waterRefillCount : 0,
    avgFeedingTime   : 0,
    avgRefillTime    : 0,
  }));

  for (const entry of entries) {
    const day = entry.dayOfWeek ?? 0;
    if (day < 0 || day > 6) continue;

    if (entry.type === 'feed') {
      buckets[day].feedDispensed     += entry.volumePercent ?? 0;
      buckets[day].feedDispenseCount += 1;
    } else if (entry.type === 'water') {
      buckets[day].waterRefilled    += entry.volumePercent ?? 0;
      buckets[day].waterRefillCount += 1;
    }
  }

  return buckets;
}

// ─────────────────────────────────────────────────────────────────────────────

class AnalyticsService {

  // ── Real-time subscription ──────────────────────────────────────────────────

  /**
   * Subscribe to real-time analytics updates for a user.
   * Calls back with aggregated DailyAnalytics[] whenever the log changes.
   * Returns an unsubscribe function.
   */
  subscribeAnalytics(
    userId   : string,
    callback : (data: DailyAnalytics[]) => void,
    onError? : (error: Error) => void,
  ): () => void {
    const logsRef = query(
      ref(database, `analytics/logs/${userId}`),
      orderByChild('timestamp'),
      limitToLast(200),
    );

    onValue(
      logsRef,
      (snapshot) => {
        const entries: AnalyticsEntry[] = [];
        if (snapshot.exists()) {
          snapshot.forEach(child => {
            entries.push(child.val() as AnalyticsEntry);
          });
        }
        callback(aggregateToDailyAnalytics(entries));
      },
      (error) => {
        console.error('❌ Analytics subscription error:', error);
        onError?.(error);
      },
    );

    return () => off(logsRef);
  }

  // ── Summary stats ───────────────────────────────────────────────────────────

  /**
   * Compute summary stats from the last 200 log entries.
   */
  async getSummaryStats(userId: string): Promise<SummaryStats> {
    try {
      const logsRef = query(
        ref(database, `analytics/logs/${userId}`),
        orderByChild('timestamp'),
        limitToLast(200),
      );
      const snapshot = await get(logsRef);

      const stats: SummaryStats = {
        totalFeedDispensed : 0,
        totalWaterRefilled : 0,
        totalFeedActions   : 0,
        totalWaterActions  : 0,
        avgFeedPerDay      : 0,
        avgWaterPerDay     : 0,
      };

      if (!snapshot.exists()) return stats;

      snapshot.forEach(child => {
        const entry = child.val() as AnalyticsEntry;
        if (entry.type === 'feed') {
          stats.totalFeedDispensed += entry.volumePercent ?? 0;
          stats.totalFeedActions   += 1;
        } else if (entry.type === 'water') {
          stats.totalWaterRefilled += entry.volumePercent ?? 0;
          stats.totalWaterActions  += 1;
        }
      });

      // Average over the 7 days of the week
      stats.avgFeedPerDay  = stats.totalFeedDispensed  / 7;
      stats.avgWaterPerDay = stats.totalWaterRefilled / 7;

      return stats;
    } catch (error) {
      console.error('❌ Failed to compute summary stats:', error);
      throw error;
    }
  }

  // ── Write ───────────────────────────────────────────────────────────────────

  async logAction(
    userId       : string,
    type         : 'feed' | 'water',
    action       : 'dispense' | 'refill',
    volumePercent: number,
  ): Promise<void> {
    const now       = new Date();
    const timestamp = now.getTime();
    const dayOfWeek = now.getDay();

    const pad  = (n: number) => String(n).padStart(2, '0');
    const date = `${pad(now.getMonth() + 1)}/${pad(now.getDate())}/${now.getFullYear()}`;
    const time = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;

    const entry: AnalyticsEntry = {
      action, type, volumePercent, timestamp, date, time, dayOfWeek, userId,
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

  // ── Read ────────────────────────────────────────────────────────────────────

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
        entries.push(child.val() as AnalyticsEntry);
      });

      return entries.reverse();
    } catch (error) {
      console.error('❌ Failed to fetch analytics:', error);
      throw error;
    }
  }
}

export default new AnalyticsService();