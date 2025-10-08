// src/screens/DashboardScreen.tsx
import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from 'react-native';
import { DrawerNavigationProp } from '@react-navigation/drawer';
import { LinearGradient } from 'expo-linear-gradient';
import { MainDrawerParamList } from '../types/types';

type DashboardScreenNavigationProp = DrawerNavigationProp<MainDrawerParamList, 'Dashboard'>;

interface Props {
  navigation: DashboardScreenNavigationProp;
}

const DashboardScreen: React.FC<Props> = ({ navigation }) => {
  // Sample data - replace with real data from Firebase later
  const [waterLevel, setWaterLevel] = useState(17);
  const [feedLevel, setFeedLevel] = useState(48);
  const [lastWaterDate, setLastWaterDate] = useState('10/08/2025');
  const [lastWaterTime, setLastWaterTime] = useState('09:34:29');
  const [lastFeedDate, setLastFeedDate] = useState('10/08/2025');
  const [lastFeedTime, setLastFeedTime] = useState('09:34:21');

  const isWaterLow = waterLevel < 20;
  const isFeedLow = feedLevel < 20;

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

        {/* Critical Alert Banner */}
        {isWaterLow && (
          <View style={styles.criticalAlert}>
            <Text style={styles.criticalAlertIcon}>⚠️</Text>
            <Text style={styles.criticalAlertText}>
              Water level is critically low! Please refill the water container.
            </Text>
          </View>
        )}

        {/* Action Buttons */}
        <View style={styles.actionButtonsContainer}>
          <TouchableOpacity style={[styles.actionButton, styles.waterButton]}>
            <Text style={styles.actionButtonIcon}>💧</Text>
            <Text style={styles.actionButtonText}>Dispense Water</Text>
          </TouchableOpacity>

          <TouchableOpacity style={[styles.actionButton, styles.feedButton]}>
            <Text style={styles.actionButtonIcon}>🌾</Text>
            <Text style={styles.actionButtonText}>Dispense Feed</Text>
          </TouchableOpacity>
        </View>

        {/* Quick Stats Card */}
        <LinearGradient
          colors={['#FFD54F', '#4CAF50']}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          style={styles.statsCard}
        >
          <Text style={styles.statsTitle}>Quick Stats</Text>
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
        </LinearGradient>
      </ScrollView>
    </LinearGradient>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
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
  },
  statsTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#FFFFFF',
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
    color: '#FFFFFF',
    opacity: 0.9,
    marginBottom: 8,
  },
  statDate: {
    fontSize: 16,
    color: '#FFFFFF',
    fontWeight: '600',
    marginBottom: 4,
  },
  statValue: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#FFFFFF',
  },
});

export default DashboardScreen;