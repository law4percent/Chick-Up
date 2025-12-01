// src/screens/SettingsScreen.tsx
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Switch,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { DrawerNavigationProp } from '@react-navigation/drawer';
import { LinearGradient } from 'expo-linear-gradient';
import Slider from '@react-native-community/slider';
import { MainDrawerParamList, UserSettings } from '../types/types';
import settingsService from '../services/settingsService';
import { auth } from '../config/firebase.config';

type SettingsScreenNavigationProp = DrawerNavigationProp<MainDrawerParamList, 'Settings'>;

interface Props {
  navigation: SettingsScreenNavigationProp;
}

const SettingsScreen: React.FC<Props> = ({ navigation }) => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Feed settings
  const [feedThreshold, setFeedThreshold] = useState(20);
  const [feedVolume, setFeedVolume] = useState(10);

  // Water settings
  const [waterThreshold, setWaterThreshold] = useState(20);
  const [autoRefillEnabled, setAutoRefillEnabled] = useState(false);
  const [autoRefillThreshold, setAutoRefillThreshold] = useState(80);

  // Load settings on mount
  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const userId = auth.currentUser?.uid;
      if (!userId) {
        Alert.alert('Error', 'User not authenticated');
        return;
      }

      const settings = await settingsService.getSettings(userId);
      if (settings) {
        setFeedThreshold(settings.feed.thresholdPercent);
        setFeedVolume(settings.feed.dispenseVolumePercent);
        setWaterThreshold(settings.water.thresholdPercent);
        setAutoRefillEnabled(settings.water.autoRefillEnabled || false);
        setAutoRefillThreshold(settings.water.autoRefillThreshold || 80);
      } else {
        // Initialize default settings if none exist
        await settingsService.initializeSettings(userId);
        await loadSettings();
      }
    } catch (error) {
      console.error('Error loading settings:', error);
      Alert.alert('Error', 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSettings = async () => {
    try {
      setSaving(true);
      const userId = auth.currentUser?.uid;
      if (!userId) {
        Alert.alert('Error', 'User not authenticated');
        return;
      }

      const updatedSettings: UserSettings = {
        feed: {
          thresholdPercent: feedThreshold,
          dispenseVolumePercent: feedVolume,
        },
        water: {
          thresholdPercent: waterThreshold,
          autoRefillEnabled,
          autoRefillThreshold,
        },
        updatedAt: Date.now(),
      };

      await settingsService.updateSettings(userId, updatedSettings);
      Alert.alert('Success', 'Settings saved successfully!');
    } catch (error: any) {
      console.error('Error saving settings:', error);
      Alert.alert('Error', error.message || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#4CAF50" />
        <Text style={styles.loadingText}>Loading settings...</Text>
      </View>
    );
  }

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
          <Text style={styles.headerTitle}>Settings</Text>
          <Text style={styles.headerSubtitle}>Configure system preferences</Text>
        </View>
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {/* Feed Settings */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={[styles.iconCircle, { backgroundColor: '#FF9500' }]}>
              <Text style={styles.iconEmoji}>🌾</Text>
            </View>
            <View style={styles.cardHeaderText}>
              <Text style={styles.cardTitle}>Feed Settings</Text>
              <Text style={styles.cardSubtitle}>
                Configure feed threshold and volume
              </Text>
            </View>
          </View>

          {/* Feed Threshold */}
          <View style={styles.sliderContainer}>
            <View style={styles.sliderHeader}>
              <Text style={styles.sliderLabel}>Alert Threshold</Text>
              <Text style={styles.sliderValue}>{feedThreshold}%</Text>
            </View>
            <Slider
              style={styles.slider}
              minimumValue={0}
              maximumValue={100}
              step={1}
              value={feedThreshold}
              onValueChange={setFeedThreshold}
              minimumTrackTintColor="#FF9500"
              maximumTrackTintColor="#E0E0E0"
              thumbTintColor="#FF9500"
            />
            <Text style={styles.sliderDescription}>
              Alert when feed level drops below this percentage
            </Text>
          </View>

          {/* Feed Dispense Volume */}
          <View style={styles.sliderContainer}>
            <View style={styles.sliderHeader}>
              <Text style={styles.sliderLabel}>Dispense Volume</Text>
              <Text style={styles.sliderValue}>{feedVolume}%</Text>
            </View>
            <Slider
              style={styles.slider}
              minimumValue={0}
              maximumValue={100}
              step={1}
              value={feedVolume}
              onValueChange={setFeedVolume}
              minimumTrackTintColor="#FF9500"
              maximumTrackTintColor="#E0E0E0"
              thumbTintColor="#FF9500"
            />
            <Text style={styles.sliderDescription}>
              Amount of feed dispensed per trigger
            </Text>
          </View>
        </View>

        {/* Card 3: Water Settings */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={[styles.iconCircle, { backgroundColor: '#4A90E2' }]}>
              <Text style={styles.iconEmoji}>💧</Text>
            </View>
            <View style={styles.cardHeaderText}>
              <Text style={styles.cardTitle}>Water Settings</Text>
              <Text style={styles.cardSubtitle}>
                Configure water threshold and volume
              </Text>
            </View>
          </View>

          {/* Water Threshold */}
          <View style={styles.sliderContainer}>
            <View style={styles.sliderHeader}>
              <Text style={styles.sliderLabel}>Alert Threshold</Text>
              <Text style={styles.sliderValue}>{waterThreshold}%</Text>
            </View>
            <Slider
              style={styles.slider}
              minimumValue={0}
              maximumValue={100}
              step={1}
              value={waterThreshold}
              onValueChange={setWaterThreshold}
              minimumTrackTintColor="#2196F3"
              maximumTrackTintColor="#E0E0E0"
              thumbTintColor="#2196F3"
            />
            <Text style={styles.sliderDescription}>
              Alert when water level drops below this percentage
            </Text>
          </View>

          {/* Auto Refill Toggle */}
          <View style={styles.settingRow}>
            <Text style={styles.settingLabel}>Enable Auto Refill</Text>
            <Switch
              value={autoRefillEnabled}
              onValueChange={setAutoRefillEnabled}
              trackColor={{ false: '#D1D1D1', true: '#2196F3' }}
              thumbColor={autoRefillEnabled ? '#FFFFFF' : '#F4F3F4'}
            />
          </View>

          {/* Auto Refill Threshold */}
          {autoRefillEnabled && (
            <View style={styles.sliderContainer}>
              <View style={styles.sliderHeader}>
                <Text style={styles.sliderLabel}>Auto Refill Target Level</Text>
                <Text style={styles.sliderValue}>{autoRefillThreshold}%</Text>
              </View>
              <Slider
                style={styles.slider}
                minimumValue={0}
                maximumValue={100}
                step={1}
                value={autoRefillThreshold}
                onValueChange={setAutoRefillThreshold}
                minimumTrackTintColor="#2196F3"
                maximumTrackTintColor="#E0E0E0"
                thumbTintColor="#2196F3"
              />
              <Text style={styles.sliderDescription}>
                System will automatically refill water up to this level (e.g., if level is 20% and target is 80%, it refills 60%)
              </Text>
            </View>
          )}
        </View>

        {/* Save Button */}
        <TouchableOpacity
          style={[styles.saveButton, saving && styles.saveButtonDisabled]}
          onPress={handleSaveSettings}
          disabled={saving}
        >
          {saving ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <>
              <Text style={styles.saveButtonIcon}>💾</Text>
              <Text style={styles.saveButtonText}>Save Settings</Text>
            </>
          )}
        </TouchableOpacity>

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
  card: {
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
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
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
  cardSubtitle: {
    fontSize: 12,
    color: '#999',
  },
  settingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  settingLabel: {
    fontSize: 16,
    color: '#333',
    fontWeight: '500',
  },
  sliderContainer: {
    marginBottom: 24,
  },
  sliderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  sliderLabel: {
    fontSize: 16,
    color: '#333',
    fontWeight: '500',
  },
  sliderValue: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#4CAF50',
  },
  slider: {
    width: '100%',
    height: 40,
  },
  sliderDescription: {
    fontSize: 12,
    color: '#999',
    marginTop: 4,
  },
  saveButton: {
    backgroundColor: '#4CAF50',
    borderRadius: 16,
    paddingVertical: 16,
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#4CAF50',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
    marginTop: 10,
  },
  saveButtonDisabled: {
    backgroundColor: '#A5D6A7',
  },
  saveButtonIcon: {
    fontSize: 24,
    marginRight: 8,
  },
  saveButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
});

export default SettingsScreen;