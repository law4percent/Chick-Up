// src/screens/AnalyticsScreen.tsx
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Alert,
  ActivityIndicator,
  Dimensions,
} from 'react-native';
import { DrawerNavigationProp } from '@react-navigation/drawer';
import { LinearGradient } from 'expo-linear-gradient';
import { MainDrawerParamList } from '../types/types';
import analyticsService, { DailyAnalytics, SummaryStats } from '../services/analyticsService';
import { auth } from '../config/firebase.config';

type AnalyticsScreenNavigationProp = DrawerNavigationProp<MainDrawerParamList, 'Analytics'>;

interface Props {
  navigation: AnalyticsScreenNavigationProp;
}

const SCREEN_WIDTH = Dimensions.get('window').width;
const CHART_WIDTH = SCREEN_WIDTH - 40;
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const AnalyticsScreen: React.FC<Props> = ({ navigation }) => {
  const [loading, setLoading] = useState(true);
  const [analytics, setAnalytics] = useState<DailyAnalytics[]>([]);
  const [summaryStats, setSummaryStats] = useState<SummaryStats>({
    totalFeedDispensed: 0,
    totalWaterRefilled: 0,
    totalFeedActions: 0,
    totalWaterActions: 0,
    avgFeedPerDay: 0,
    avgWaterPerDay: 0,
  });

  useEffect(() => {
    loadAnalytics();
  }, []);

  const loadAnalytics = async () => {
    try {
      const userId = auth.currentUser?.uid;
      if (!userId) {
        Alert.alert('Error', 'User not authenticated');
        setLoading(false);
        return;
      }

      // Subscribe to real-time analytics
      const unsubscribe = analyticsService.subscribeAnalytics(
        userId,
        async (analyticsData) => {
          setAnalytics(analyticsData);
          const stats = await analyticsService.getSummaryStats(userId);
          setSummaryStats(stats);
          setLoading(false);
        },
        (error) => {
          console.error('Analytics subscription error:', error);
          Alert.alert('Error', 'Failed to load analytics');
          setLoading(false);
        }
      );

      return unsubscribe;
    } catch (error) {
      console.error('Error loading analytics:', error);
      Alert.alert('Error', 'Failed to load analytics');
      setLoading(false);
    }
  };

  const renderBarChart = (
    data: DailyAnalytics[],
    getValue1: (item: DailyAnalytics) => number,
    getValue2: (item: DailyAnalytics) => number,
    color1: string,
    color2: string,
    label1: string,
    label2: string,
    unit: string
  ) => {
    const maxValue = Math.max(
      ...data.map(d => Math.max(getValue1(d), getValue2(d))),
      1
    );

    return (
      <View style={styles.chartContainer}>
        <View style={styles.chartBars}>
          {data.map((item, index) => {
            const value1 = getValue1(item);
            const value2 = getValue2(item);
            const height1 = (value1 / maxValue) * 120;
            const height2 = (value2 / maxValue) * 120;

            return (
              <View key={index} style={styles.barGroup}>
                <View style={styles.barPair}>
                  <View style={styles.barContainer}>
                    <View style={[styles.bar, { height: height1, backgroundColor: color1 }]} />
                  </View>
                  <View style={styles.barContainer}>
                    <View style={[styles.bar, { height: height2, backgroundColor: color2 }]} />
                  </View>
                </View>
                <Text style={styles.barLabel}>{DAYS[item.dayOfWeek]}</Text>
              </View>
            );
          })}
        </View>

        <View style={styles.chartLegend}>
          <View style={styles.legendItem}>
            <View style={[styles.legendColor, { backgroundColor: color1 }]} />
            <Text style={styles.legendText}>{label1}</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={[styles.legendColor, { backgroundColor: color2 }]} />
            <Text style={styles.legendText}>{label2}</Text>
          </View>
        </View>
      </View>
    );
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#4CAF50" />
        <Text style={styles.loadingText}>Loading analytics...</Text>
      </View>
    );
  }

  // Show empty state if no data
  const hasData = analytics.some(item => 
    item.feedDispensed > 0 || item.waterRefilled > 0
  );

  return (
    <LinearGradient colors={['#FFFEF0', '#FFFEF0']} style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          style={styles.menuButton}
          onPress={() => navigation.openDrawer()}
        >
          <Text style={styles.menuIcon}>☰</Text>
        </TouchableOpacity>
        <View style={styles.headerTextContainer}>
          <Text style={styles.headerTitle}>Analytics</Text>
          <Text style={styles.headerSubtitle}>Weekly insights</Text>
        </View>
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {/* Summary Cards */}
        <View style={styles.summaryContainer}>
          <View style={styles.summaryCard}>
            <Text style={styles.summaryIcon}>🌾</Text>
            <Text style={styles.summaryValue}>{summaryStats.totalFeedDispensed.toFixed(0)}%</Text>
            <Text style={styles.summaryLabel}>Total Feed</Text>
            <Text style={styles.summarySubtext}>{summaryStats.totalFeedActions} actions</Text>
          </View>

          <View style={styles.summaryCard}>
            <Text style={styles.summaryIcon}>💧</Text>
            <Text style={styles.summaryValue}>{summaryStats.totalWaterRefilled.toFixed(0)}%</Text>
            <Text style={styles.summaryLabel}>Total Water</Text>
            <Text style={styles.summarySubtext}>{summaryStats.totalWaterActions} refills</Text>
          </View>
        </View>

        {!hasData ? (
          // Empty State
          <View style={styles.emptyState}>
            <Text style={styles.emptyStateIcon}>📊</Text>
            <Text style={styles.emptyStateTitle}>No Analytics Data Yet</Text>
            <Text style={styles.emptyStateText}>
              Start using the water refill and feed dispense buttons on the dashboard to see your analytics here.
            </Text>
            <TouchableOpacity
              style={styles.emptyStateButton}
              onPress={() => navigation.navigate('Dashboard')}
            >
              <Text style={styles.emptyStateButtonText}>Go to Dashboard</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <>
            {/* Volume Chart */}
            <View style={styles.chartCard}>
              <View style={styles.chartHeader}>
                <Text style={styles.chartTitle}>📊 Weekly Volume</Text>
                <Text style={styles.chartSubtitle}>Feed dispensed vs Water refilled</Text>
              </View>
              {renderBarChart(
                analytics,
                (item) => item.feedDispensed,
                (item) => item.waterRefilled,
                '#FF9500',
                '#2196F3',
                'Feed Dispensed',
                'Water Refilled',
                '%'
              )}
              <View style={styles.chartFooter}>
                <Text style={styles.chartFooterText}>
                  Daily Avg: {summaryStats.avgFeedPerDay.toFixed(1)}% feed, {summaryStats.avgWaterPerDay.toFixed(1)}% water
                </Text>
              </View>
            </View>

            {/* Time Comparison Chart */}
            <View style={styles.chartCard}>
              <View style={styles.chartHeader}>
                <Text style={styles.chartTitle}>⏱️ Time Efficiency</Text>
                <Text style={styles.chartSubtitle}>Average time consumed per day</Text>
              </View>
              {renderBarChart(
                analytics,
                (item) => item.avgFeedingTime,
                (item) => item.avgRefillTime,
                '#4CAF50',
                '#FF5722',
                'Feeding Time',
                'Refilling Time',
                'min'
              )}
              <View style={styles.infoBox}>
                <Text style={styles.infoIcon}>💡</Text>
                <View style={styles.infoTextContainer}>
                  <Text style={styles.infoTitle}>Time Savings Insight</Text>
                  <Text style={styles.infoText}>
                    Automated system reduces manual feeding time by ~90%. Traditional method: ~30 mins/day. Automated: ~3 mins/day.
                  </Text>
                </View>
              </View>
            </View>

            {/* Weekly Activity Table */}
            <View style={styles.tableCard}>
              <Text style={styles.tableTitle}>📋 Weekly Activity</Text>
              <View style={styles.table}>
                <View style={styles.tableHeader}>
                  <Text style={[styles.tableHeaderCell, { flex: 1.5 }]}>Day</Text>
                  <Text style={styles.tableHeaderCell}>Feed</Text>
                  <Text style={styles.tableHeaderCell}>Water</Text>
                  <Text style={styles.tableHeaderCell}>Actions</Text>
                </View>
                {analytics.map((item, index) => (
                  <View key={index} style={styles.tableRow}>
                    <Text style={[styles.tableCell, { flex: 1.5 }]}>{DAYS[item.dayOfWeek]}</Text>
                    <Text style={styles.tableCell}>{item.feedDispensed.toFixed(0)}%</Text>
                    <Text style={styles.tableCell}>{item.waterRefilled.toFixed(0)}%</Text>
                    <Text style={styles.tableCell}>{item.feedDispenseCount + item.waterRefillCount}</Text>
                  </View>
                ))}
              </View>
            </View>
          </>
        )}

        <View style={{ height: 30 }} />
      </ScrollView>
    </LinearGradient>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#FFFEF0',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
    color: '#666',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingTop: 50,
    paddingHorizontal: 20,
    paddingBottom: 20,
    backgroundColor: '#FFFEF0',
  },
  menuButton: {
    padding: 8,
  },
  menuIcon: {
    fontSize: 28,
    color: '#333',
  },
  headerTextContainer: {
    marginLeft: 12,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#2E7D32',
  },
  headerSubtitle: {
    fontSize: 12,
    color: '#666',
    marginTop: 2,
  },
  content: {
    flex: 1,
    paddingHorizontal: 20,
  },
  summaryContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  summaryCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 20,
    width: '48%',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 3,
  },
  summaryIcon: {
    fontSize: 32,
    marginBottom: 8,
  },
  summaryValue: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 4,
  },
  summaryLabel: {
    fontSize: 14,
    color: '#666',
    marginBottom: 4,
  },
  summarySubtext: {
    fontSize: 12,
    color: '#999',
  },
  emptyState: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 40,
    alignItems: 'center',
    marginTop: 40,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 3,
  },
  emptyStateIcon: {
    fontSize: 64,
    marginBottom: 16,
  },
  emptyStateTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 12,
  },
  emptyStateText: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 24,
  },
  emptyStateButton: {
    backgroundColor: '#4CAF50',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 12,
  },
  emptyStateButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: 'bold',
  },
  chartCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 20,
    marginBottom: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 3,
  },
  chartHeader: {
    marginBottom: 20,
  },
  chartTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 4,
  },
  chartSubtitle: {
    fontSize: 12,
    color: '#666',
  },
  chartContainer: {
    paddingVertical: 10,
  },
  chartBars: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'flex-end',
    height: 150,
    marginBottom: 10,
  },
  barGroup: {
    alignItems: 'center',
    flex: 1,
  },
  barPair: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 2,
    marginBottom: 8,
  },
  barContainer: {
    width: 16,
    height: 120,
    justifyContent: 'flex-end',
  },
  bar: {
    width: '100%',
    borderTopLeftRadius: 4,
    borderTopRightRadius: 4,
    minHeight: 2,
  },
  barLabel: {
    fontSize: 10,
    color: '#666',
    fontWeight: '600',
  },
  chartLegend: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 20,
    marginTop: 10,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  legendColor: {
    width: 12,
    height: 12,
    borderRadius: 2,
  },
  legendText: {
    fontSize: 12,
    color: '#666',
  },
  chartFooter: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#E0E0E0',
  },
  chartFooterText: {
    fontSize: 12,
    color: '#666',
    textAlign: 'center',
  },
  infoBox: {
    flexDirection: 'row',
    backgroundColor: '#E8F5E9',
    padding: 16,
    borderRadius: 12,
    marginTop: 16,
  },
  infoIcon: {
    fontSize: 24,
    marginRight: 12,
  },
  infoTextContainer: {
    flex: 1,
  },
  infoTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#2E7D32',
    marginBottom: 4,
  },
  infoText: {
    fontSize: 12,
    color: '#1B5E20',
    lineHeight: 18,
  },
  tableCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 20,
    marginBottom: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 3,
  },
  tableTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 16,
  },
  table: {
    borderRadius: 8,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: '#E0E0E0',
  },
  tableHeader: {
    flexDirection: 'row',
    backgroundColor: '#F5F5F5',
    paddingVertical: 12,
    paddingHorizontal: 12,
  },
  tableHeaderCell: {
    flex: 1,
    fontSize: 12,
    fontWeight: 'bold',
    color: '#333',
    textAlign: 'center',
  },
  tableRow: {
    flexDirection: 'row',
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderTopWidth: 1,
    borderTopColor: '#E0E0E0',
  },
  tableCell: {
    flex: 1,
    fontSize: 12,
    color: '#666',
    textAlign: 'center',
  },
});

export default AnalyticsScreen;