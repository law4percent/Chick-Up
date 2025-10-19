// src/screens/DashboardScreen.tsx
import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Alert, ActivityIndicator } from 'react-native';
import { DrawerNavigationProp } from '@react-navigation/drawer';
import { LinearGradient } from 'expo-linear-gradient';
import { MainDrawerParamList, SensorData, UserSettings } from '../types/types';
import sensorService from '../services/sensorService';
import settingsService from '../services/settingsService';
import triggerService from '../services/triggerService';
import { auth } from '../config/firebase.config';

type DashboardScreenNavigationProp = DrawerNavigationProp<MainDrawerParamList, 'Dashboard'>;

interface Props {
  navigation: DashboardScreenNavigationProp;
}

const DashboardScreen: React.FC<Props> = ({ navigation }) => {
  const [loading, setLoading] = useState(true);
  const [waterLevel, setWaterLevel] = useState(0);
  const [feedLevel, setFeedLevel] = useState(0);
  const [lastWaterDate, setLastWaterDate] = useState('--/--/----');
  const [lastWaterTime, setLastWaterTime] = useState('--:--:--');
  const [lastFeedDate, setLastFeedDate] = useState('--/--/----');
  const [lastFeedTime, setLastFeedTime] = useState('--:--:--');

  // Settings for dynamic thresholds
  const [waterThreshold, setWaterThreshold] = useState(20);
  const [feedThreshold, setFeedThreshold] = useState(20);
  const [waterVolume, setWaterVolume] = useState(15);
  const [feedVolume, setFeedVolume] = useState(10);

  // Dispense button states
  const [waterButtonDisabled, setWaterButtonDisabled] = useState(false);
  const [feedButtonDisabled, setFeedButtonDisabled] = useState(false);
  const [waterCountdown, setWaterCountdown] = useState(0);
  const [feedCountdown, setFeedCountdown] = useState(0);

  const isWaterLow = waterLevel < waterThreshold;
  const isFeedLow = feedLevel < feedThreshold;

  // Load sensor data and settings on mount
  useEffect(() => {
    const userId = auth.currentUser?.uid;
    if (!userId) {
      Alert.alert('Error', 'User not authenticated');
      setLoading(false);
      return;
    }

    // Initialize sensor data and settings if they don't exist
    const initializeData = async () => {
      try {
        const existingSensorData = await sensorService.getSensorData(userId);
        if (!existingSensorData) {
          await sensorService.initializeSensorData(userId);
        }

        const existingSettings = await settingsService.getSettings(userId);
        if (!existingSettings) {
          await settingsService.initializeSettings(userId);
        }
      } catch (error) {
        console.error('Error initializing data:', error);
      }
    };

    initializeData();

    // Subscribe to real-time sensor data
    const unsubscribeSensor = sensorService.subscribeSensorData(
      userId,
      (data) => {
        if (data) {
          setWaterLevel(data.waterLevel);
          setFeedLevel(data.feedLevel);
          setLastWaterDate(data.lastWaterDispense.date);
          setLastWaterTime(data.lastWaterDispense.time);
          setLastFeedDate(data.lastFeedDispense.date);
          setLastFeedTime(data.lastFeedDispense.time);
        }
        setLoading(false);
      },
      (error) => {
        console.error('Sensor subscription error:', error);
        Alert.alert('Error', 'Failed to load sensor data');
        setLoading(false);
      }
    );

    // Subscribe to real-time settings for dynamic thresholds
    const unsubscribeSettings = settingsService.subscribeSettings(
      userId,
      (settings) => {
        if (settings) {
          setWaterThreshold(settings.water.thresholdPercent);
          setFeedThreshold(settings.feed.thresholdPercent);
          setWaterVolume(settings.water.dispenseVolumePercent);
          setFeedVolume(settings.feed.dispenseVolumePercent);
        }
      },
      (error) => {
        console.error('Settings subscription error:', error);
      }
    );

    // Cleanup subscriptions on unmount
    return () => {
      unsubscribeSensor();
      unsubscribeSettings();
    };
  }, []);

  // Water button countdown effect
  useEffect(() => {
    if (waterCountdown > 0) {
      const timer = setTimeout(() => setWaterCountdown(waterCountdown - 1), 1000);
      return () => clearTimeout(timer);
    } else if (waterCountdown === 0 && waterButtonDisabled) {
      setWaterButtonDisabled(false);
    }
  }, [waterCountdown, waterButtonDisabled]);

  // Feed button countdown effect
  useEffect(() => {
    if (feedCountdown > 0) {
      const timer = setTimeout(() => setFeedCountdown(feedCountdown - 1), 1000);
      return () => clearTimeout(timer);
    } else if (feedCountdown === 0 && feedButtonDisabled) {
      setFeedButtonDisabled(false);
    }
  }, [feedCountdown, feedButtonDisabled]);

  const handleWaterDispense = async () => {
    try {
      const userId = auth.currentUser?.uid;
      if (!userId) {
        Alert.alert('Error', 'User not authenticated');
        return;
      }

      setWaterButtonDisabled(true);
      setWaterCountdown(3);

      await triggerService.createWaterTrigger(userId, waterVolume);
      await sensorService.updateDispenseTimestamp(userId, 'water');

    } catch (error: any) {
      console.error('Error dispensing water:', error);
      Alert.alert('Error', error.message || 'Failed to dispense water');
      setWaterButtonDisabled(false);
      setWaterCountdown(0);
    }
  };

  const handleFeedDispense = async () => {
    try {
      const userId = auth.currentUser?.uid;
      if (!userId) {
        Alert.alert('Error', 'User not authenticated');
        return;
      }

      setFeedButtonDisabled(true);
      setFeedCountdown(3);

      await triggerService.createFeedTrigger(userId, feedVolume);
      await sensorService.updateDispenseTimestamp(userId, 'feed');

    } catch (error: any) {
      console.error('Error dispensing feed:', error);
      Alert.alert('Error', error.message || 'Failed to dispense feed');
      setFeedButtonDisabled(false);
      setFeedCountdown(0);
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#4CAF50" />
        <Text style={styles.loadingText}>Loading dashboard...</Text>
      </View>
    );
  }

  return (
    <LinearGradient
      colors={['#FFFEF0', '#FFFEF0']}
      style={styles.container}
    >
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          style={styles.menuButton}
          onPress={() => navigation.openDrawer()}
        >
          <Text style={styles.menuIcon}>☰</Text>
        </TouchableOpacity>
        <View style={styles.headerTextContainer}>
          <Text style={styles.headerTitle}>Chick-Up</Text>
          <Text style={styles.headerSubtitle}>Smart Poultry Automation</Text>
        </View>
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {/* Level Cards Container */}
        <View style={styles.levelCardsContainer}>
          {/* Water Level Card */}
          <View style={styles.levelCard}>
            <View style={styles.cardHeader}>
              <View style={[styles.iconCircle, { backgroundColor: "#4A90E2" }]}>
                <Text style={styles.iconEmoji}>💧</Text>
              </View>
              <View style={styles.cardHeaderText}>
                <Text style={styles.cardTitle}>Water</Text>
                <View style={styles.currentLevelRow}>
                  <Text style={styles.currentLevelText}>Current Level</Text>
                  {isWaterLow && <Text style={styles.warningIcon}>⚠️</Text>}
                </View>
              </View>
            </View>

            <View style={styles.levelInfoContainer}>
              <Text style={styles.levelLabel}>Level</Text>
              <Text style={[styles.levelPercentage, isWaterLow && styles.levelLow]}>
                {waterLevel}%
              </Text>
            </View>

            {/* Progress Bar */}
            <View style={styles.progressBarContainer}>
              <View style={styles.progressBarBg}>
                <View 
                  style={[
                    styles.progressBarFill,
                    { width: `${waterLevel}%` },
                    isWaterLow && styles.progressBarLow
                  ]} 
                />
              </View>
            </View>

            {isWaterLow && (
              <View style={styles.alertContainer}>
                <Text style={styles.alertIcon}>⚠️</Text>
                <Text style={styles.alertText}>Low water level - please refill soon!</Text>
              </View>
            )}
          </View>

          {/* Feed Level Card */}
          <View style={styles.levelCard}>
            <View style={styles.cardHeader}>
              <View style={[styles.iconCircle, { backgroundColor: "#FF9500" }]}>
                <Text style={styles.iconEmoji}>🌾</Text>
              </View>
              <View style={styles.cardHeaderText}>
                <Text style={styles.cardTitle}>Feed</Text>
                <View style={styles.currentLevelRow}>
                  <Text style={styles.currentLevelText}>Current Level</Text>
                  {isFeedLow && <Text style={styles.warningIcon}>⚠️</Text>}
                </View>
              </View>
            </View>

            <View style={styles.levelInfoContainer}>
              <Text style={styles.levelLabel}>Level</Text>
              <Text style={[styles.levelPercentage, isFeedLow && styles.levelLow]}>
                {feedLevel}%
              </Text>
            </View>

            {/* Progress Bar */}
            <View style={styles.progressBarContainer}>
              <View style={styles.progressBarBg}>
                <View 
                  style={[
                    styles.progressBarFill,
                    { width: `${feedLevel}%` },
                    isFeedLow && styles.progressBarLow,
                    !isFeedLow && { backgroundColor: '#4CAF50' }
                  ]} 
                />
              </View>
            </View>

            {isFeedLow && (
              <View style={styles.alertContainer}>
                <Text style={styles.alertIcon}>⚠️</Text>
                <Text style={styles.alertText}>Low feed level - please refill soon!</Text>
              </View>
            )}
          </View>
        </View>

        {/* Critical Alert Banner - Shows when either water or feed is low */}
        {(isWaterLow || isFeedLow) && (
          <View style={styles.criticalAlert}>
            <Text style={styles.criticalAlertIcon}>⚠️</Text>
            <Text style={styles.criticalAlertText}>
              {isWaterLow && isFeedLow
                ? 'Water and feed levels are critically low! Please refill both containers.'
                : isWaterLow
                ? 'Water level is critically low! Please refill the water container.'
                : 'Feed level is critically low! Please refill the feed container.'}
            </Text>
          </View>
        )}

        {/* Action Buttons */}
        <View style={styles.actionButtonsContainer}>
          <TouchableOpacity
            style={[
              styles.actionButton,
              styles.waterButton,
              waterButtonDisabled && styles.actionButtonDisabled
            ]}
            onPress={handleWaterDispense}
            disabled={waterButtonDisabled}
          >
            <Text style={styles.actionButtonIcon}>💧</Text>
            <Text style={styles.actionButtonText}>
              {waterButtonDisabled ? `Wait ${waterCountdown}s` : 'Dispense Water'}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.actionButton,
              styles.feedButton,
              feedButtonDisabled && styles.actionButtonDisabled
            ]}
            onPress={handleFeedDispense}
            disabled={feedButtonDisabled}
          >
            <Text style={styles.actionButtonIcon}>🌾</Text>
            <Text style={styles.actionButtonText}>
              {feedButtonDisabled ? `Wait ${feedCountdown}s` : 'Dispense Feed'}
            </Text>
          </TouchableOpacity>
        </View>

        {/* Quick Stats Card */}
        <View style={styles.statsCard}>
          <Text style={styles.statsTitle}>Quick Stats (Found)</Text>
          <View style={styles.statsRow}>
            <View style={styles.statColumn}>
              <Text style={styles.statLabel}>Last Water</Text>
              <Text style={styles.statDate}>{lastWaterDate}</Text>
              <Text style={styles.statValue}>{lastWaterTime}</Text>
            </View>
            <View style={styles.statColumn}>
              <Text style={styles.statLabel}>Last Feed</Text>
              <Text style={styles.statDate}>{lastFeedDate}</Text>
              <Text style={styles.statValue}>{lastFeedTime}</Text>
            </View>
          </View>
        </View>
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
  levelCardsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 20,
    marginBottom: 20,
  },
  levelCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 20,
    width: '48%',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 3,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  iconCircle: {
    width: 60,
    height: 60,
    borderRadius: 30,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  iconEmoji: {
    fontSize: 28,
  },
  cardHeaderText: {
    flex: 1,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 4,
  },
  currentLevelRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  currentLevelText: {
    fontSize: 12,
    color: '#999',
  },
  warningIcon: {
    fontSize: 12,
    marginLeft: 4,
  },
  levelInfoContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  levelLabel: {
    fontSize: 16,
    color: '#666',
  },
  levelPercentage: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#4CAF50',
  },
  levelLow: {
    color: '#E53935',
  },
  progressBarContainer: {
    marginBottom: 12,
  },
  progressBarBg: {
    height: 8,
    backgroundColor: '#E0E0E0',
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: '#333',
    borderRadius: 4,
  },
  progressBarLow: {
    backgroundColor: '#E53935',
  },
  alertContainer: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#FFEBEE',
    padding: 10,
    borderRadius: 8,
    marginTop: 8,
  },
  alertIcon: {
    fontSize: 14,
    marginRight: 6,
  },
  alertText: {
    flex: 1,
    fontSize: 11,
    color: '#C62828',
    lineHeight: 16,
  },
  criticalAlert: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFF9C4',
    padding: 16,
    borderRadius: 12,
    marginBottom: 20,
    borderLeftWidth: 4,
    borderLeftColor: '#F9A825',
  },
  criticalAlertIcon: {
    fontSize: 24,
    marginRight: 12,
  },
  criticalAlertText: {
    flex: 1,
    fontSize: 14,
    color: '#333',
    fontWeight: '500',
  },
  actionButtonsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  actionButton: {
    width: '48%',
    paddingVertical: 20,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 4,
  },
  waterButton: {
    backgroundColor: '#2196F3',
  },
  feedButton: {
    backgroundColor: '#FF9500',
  },
  actionButtonDisabled: {
    backgroundColor: '#BDBDBD',
    opacity: 0.6,
  },
  actionButtonIcon: {
    fontSize: 32,
    marginBottom: 8,
  },
  actionButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: 'bold',
  },
  statsCard: {
    borderRadius: 20,
    padding: 24,
    marginBottom: 30,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 3,
    backgroundColor: '#FFF9C4',
  },
  statsTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#000000ff',
    marginBottom: 20,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  statColumn: {
    alignItems: 'center',
  },
  statLabel: {
    fontSize: 14,
    color: '#000000ff',
    opacity: 0.9,
    marginBottom: 8,
  },
  statDate: {
    fontSize: 16,
    color: '#000000ff',
    fontWeight: '600',
    marginBottom: 4,
  },
  statValue: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#000000ff',
  },
});

export default DashboardScreen;