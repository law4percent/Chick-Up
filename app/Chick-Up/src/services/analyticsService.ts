// src/services/analyticsService.ts
import { ref, push, get, query, orderByChild, limitToLast, onValue, off } from 'firebase/database';
import { database } from '../config/firebase.config';

export type AnalyticsSource = 'app' | 'keypad' | 'schedule';

export interface AnalyticsEntry {
  action          : 'dispense' | 'refill';
  type            : 'feed' | 'water';
  volumePercent   : number;
  durationSeconds : number;   // water refill duration; 0 for feed entries
  timestamp       : number;
  date            : string;
  time            : string;
  dayOfWeek       : number;
  userId          : string;
  source          : AnalyticsSource;
}

// ── Types expected by AnalyticsScreen ────────────────────────────────────────

export interface DailyAnalytics {
  dayOfWeek            : number;  // 0 = Sun … 6 = Sat
  feedDispensed        : number;  // kg dispensed per day: feedDispenseCount × kgPerDispense
  feedDispenseCount    : number;
  waterRefillCount     : number;
  totalRefillDuration  : number;  // sum of durationSeconds for water actions
  avgDurationSeconds   : number;  // totalRefillDuration / waterRefillCount
  avgFeedingTime       : number;  // always 0 — no feed duration data
}

export interface SummaryStats {
  totalFeedDispensed        : number;  // total kg dispensed this week
  totalFeedActions          : number;
  totalWaterActions         : number;
  totalRefillDurationSeconds: number;  // sum of all water durationSeconds
  avgRefillDurationPerDay   : number;  // totalRefillDurationSeconds / 7
  avgFeedPerDay             : number;  // average kg dispensed per day
}

// ─────────────────────────────────────────────────────────────────────────────

function aggregateToDailyAnalytics(entries: AnalyticsEntry[]): DailyAnalytics[] {
  const buckets: DailyAnalytics[] = Array.from({ length: 7 }, (_, i) => ({
    dayOfWeek          : i,
    feedDispensed      : 0,
    feedDispenseCount  : 0,
    waterRefillCount   : 0,
    totalRefillDuration: 0,
    avgDurationSeconds : 0,
    avgFeedingTime     : 0,
  }));

  for (const entry of entries) {
    const day = entry.dayOfWeek ?? 0;
    if (day < 0 || day > 6) continue;

    if (entry.type === 'feed') {
      buckets[day].feedDispensed     += entry.volumePercent ?? 0;  // Pi writes kgPerDispense here
      buckets[day].feedDispenseCount += 1;
    } else if (entry.type === 'water') {
      buckets[day].waterRefillCount   += 1;
      buckets[day].totalRefillDuration += entry.durationSeconds ?? 0;
    }
  }

  // Compute avg duration per day
  for (const bucket of buckets) {
    bucket.avgDurationSeconds = bucket.waterRefillCount > 0
      ? Math.round(bucket.totalRefillDuration / bucket.waterRefillCount)
      : 0;
  }

  return buckets;
}

// ─────────────────────────────────────────────────────────────────────────────

class AnalyticsService {

  // ── Real-time subscription ──────────────────────────────────────────────────

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
          snapshot.forEach(child => { entries.push(child.val() as AnalyticsEntry); });
        }
        callback(aggregateToDailyAnalytics(entries));
      },
      (error) => { console.error('❌ Analytics subscription error:', error); onError?.(error); },
    );

    return () => off(logsRef);
  }

  // ── Summary stats ───────────────────────────────────────────────────────────

  async getSummaryStats(userId: string): Promise<SummaryStats> {
    try {
      const logsRef = query(
        ref(database, `analytics/logs/${userId}`),
        orderByChild('timestamp'),
        limitToLast(200),
      );
      const snapshot = await get(logsRef);

      const stats: SummaryStats = {
        totalFeedDispensed        : 0,
        totalFeedActions          : 0,
        totalWaterActions         : 0,
        totalRefillDurationSeconds: 0,
        avgRefillDurationPerDay   : 0,
        avgFeedPerDay             : 0,
      };

      if (!snapshot.exists()) return stats;

      snapshot.forEach(child => {
        const entry = child.val() as AnalyticsEntry;
        if (entry.type === 'feed') {
          stats.totalFeedDispensed += entry.volumePercent ?? 0;  // Pi writes kgPerDispense here
          stats.totalFeedActions   += 1;
        } else if (entry.type === 'water') {
          stats.totalWaterActions          += 1;
          stats.totalRefillDurationSeconds += entry.durationSeconds ?? 0;
        }
      });

      stats.avgFeedPerDay           = stats.totalFeedDispensed        / 7;
      stats.avgRefillDurationPerDay = stats.totalRefillDurationSeconds / 7;

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
      action,
      type,
      volumePercent,
      durationSeconds: 0,   // app-side water commands don't know duration — Pi writes this
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
      snapshot.forEach(child => { entries.push(child.val() as AnalyticsEntry); });
      return entries.reverse();
    } catch (error) {
      console.error('❌ Failed to fetch analytics:', error);
      throw error;
    }
  }
}

export default new AnalyticsService();