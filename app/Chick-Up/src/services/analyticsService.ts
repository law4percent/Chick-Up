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

export interface WeekRange {
  startMs : number;
  endMs   : number;
  label   : string;  // e.g. "Mar 22 – Mar 28"
}

// ─────────────────────────────────────────────────────────────────────────────

/**
 * Returns the Sun–Sat week range for a given weekOffset.
 * weekOffset =  0 → current week
 * weekOffset = -1 → last week
 * weekOffset = -2 → two weeks ago
 */
function getWeekRange(weekOffset: number = 0): WeekRange {
  const now         = new Date();
  const dayOfWeek   = now.getDay(); // 0 = Sun
  const startOfWeek = new Date(now);
  startOfWeek.setDate(now.getDate() - dayOfWeek + weekOffset * 7);
  startOfWeek.setHours(0, 0, 0, 0);

  const endOfWeek = new Date(startOfWeek);
  endOfWeek.setDate(startOfWeek.getDate() + 6);
  endOfWeek.setHours(23, 59, 59, 999);

  const pad    = (n: number) => String(n).padStart(2, '0');
  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const startLabel = `${MONTHS[startOfWeek.getMonth()]} ${pad(startOfWeek.getDate())}`;
  const endLabel   = `${MONTHS[endOfWeek.getMonth()]} ${pad(endOfWeek.getDate())}`;

  return {
    startMs : startOfWeek.getTime(),
    endMs   : endOfWeek.getTime(),
    label   : `${startLabel} – ${endLabel}`,
  };
}

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
      buckets[day].waterRefillCount    += 1;
      buckets[day].totalRefillDuration += entry.durationSeconds ?? 0;
    }
  }

  for (const bucket of buckets) {
    bucket.avgDurationSeconds = bucket.waterRefillCount > 0
      ? Math.round(bucket.totalRefillDuration / bucket.waterRefillCount)
      : 0;
  }

  return buckets;
}

function computeSummary(entries: AnalyticsEntry[]): SummaryStats {
  const stats: SummaryStats = {
    totalFeedDispensed        : 0,
    totalFeedActions          : 0,
    totalWaterActions         : 0,
    totalRefillDurationSeconds: 0,
    avgRefillDurationPerDay   : 0,
    avgFeedPerDay             : 0,
  };

  for (const entry of entries) {
    if (entry.type === 'feed') {
      stats.totalFeedDispensed += entry.volumePercent ?? 0;
      stats.totalFeedActions   += 1;
    } else if (entry.type === 'water') {
      stats.totalWaterActions          += 1;
      stats.totalRefillDurationSeconds += entry.durationSeconds ?? 0;
    }
  }

  stats.avgFeedPerDay           = stats.totalFeedDispensed        / 7;
  stats.avgRefillDurationPerDay = stats.totalRefillDurationSeconds / 7;

  return stats;
}

// ─────────────────────────────────────────────────────────────────────────────

class AnalyticsService {

  // ── Real-time subscription (current week only) ──────────────────────────────
  //
  // Only the current week (weekOffset = 0) needs a live listener since past
  // weeks are immutable. For past weeks use getWeekAnalytics() instead.

  subscribeAnalytics(
    userId   : string,
    callback : (data: DailyAnalytics[], stats: SummaryStats) => void,
    onError? : (error: Error) => void,
  ): () => void {
    const logsRef = query(
      ref(database, `analytics/logs/${userId}`),
      orderByChild('timestamp'),
      limitToLast(500),
    );

    onValue(
      logsRef,
      (snapshot) => {
        const allEntries: AnalyticsEntry[] = [];
        if (snapshot.exists()) {
          snapshot.forEach(child => { allEntries.push(child.val() as AnalyticsEntry); });
        }
        const { startMs, endMs } = getWeekRange(0);
        const thisWeek = allEntries.filter(e => e.timestamp >= startMs && e.timestamp <= endMs);
        callback(aggregateToDailyAnalytics(thisWeek), computeSummary(thisWeek));
      },
      (error) => { console.error('❌ Analytics subscription error:', error); onError?.(error); },
    );

    return () => off(logsRef);
  }

  // ── One-time fetch for any week offset ─────────────────────────────────────

  async getWeekAnalytics(
    userId     : string,
    weekOffset : number,
  ): Promise<{ analytics: DailyAnalytics[]; stats: SummaryStats; weekRange: WeekRange }> {
    try {
      const weekRange = getWeekRange(weekOffset);

      const logsRef = query(
        ref(database, `analytics/logs/${userId}`),
        orderByChild('timestamp'),
        limitToLast(500),
      );
      const snapshot = await get(logsRef);

      const allEntries: AnalyticsEntry[] = [];
      if (snapshot.exists()) {
        snapshot.forEach(child => { allEntries.push(child.val() as AnalyticsEntry); });
      }

      const weekEntries = allEntries.filter(
        e => e.timestamp >= weekRange.startMs && e.timestamp <= weekRange.endMs
      );

      return {
        analytics : aggregateToDailyAnalytics(weekEntries),
        stats     : computeSummary(weekEntries),
        weekRange,
      };
    } catch (error) {
      console.error('❌ Failed to fetch week analytics:', error);
      throw error;
    }
  }

  // ── Get week range label only ───────────────────────────────────────────────

  getWeekRange(weekOffset: number): WeekRange {
    return getWeekRange(weekOffset);
  }

  // ── Summary stats (kept for backwards compatibility) ───────────────────────

  async getSummaryStats(userId: string, weekOffset: number = 0): Promise<SummaryStats> {
    try {
      const { startMs, endMs } = getWeekRange(weekOffset);
      const logsRef = query(
        ref(database, `analytics/logs/${userId}`),
        orderByChild('timestamp'),
        limitToLast(500),
      );
      const snapshot = await get(logsRef);
      if (!snapshot.exists()) return computeSummary([]);

      const entries: AnalyticsEntry[] = [];
      snapshot.forEach(child => {
        const entry = child.val() as AnalyticsEntry;
        if (entry.timestamp >= startMs && entry.timestamp <= endMs) {
          entries.push(entry);
        }
      });

      return computeSummary(entries);
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
      durationSeconds: 0,
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