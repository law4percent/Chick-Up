// src/screens/SettingsScreen.tsx
import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView,
  Alert, ActivityIndicator, TextInput, KeyboardAvoidingView, Platform,
} from 'react-native';
import { DrawerNavigationProp } from '@react-navigation/drawer';
import { LinearGradient } from 'expo-linear-gradient';
import Slider from '@react-native-community/slider';
import { MainDrawerParamList, UserSettings } from '../types/types';
import settingsService from '../services/settingsService';
import { auth } from '../config/firebase.config';

type SettingsScreenNavigationProp = DrawerNavigationProp<MainDrawerParamList, 'Settings'>;
interface Props { navigation: SettingsScreenNavigationProp; }

function splitToMinSec(totalSec: number): { minutes: number; seconds: number } {
  return { minutes: Math.floor(totalSec / 60), seconds: totalSec % 60 };
}

function validateDuration(minutes: string, seconds: string): string | null {
  const m = parseInt(minutes || '0', 10);
  const s = parseInt(seconds  || '0', 10);
  if (isNaN(m) || isNaN(s))  return 'Please enter valid numbers.';
  if (s < 0 || s > 59)       return 'Seconds must be between 0 and 59.';
  if (m < 0)                 return 'Minutes cannot be negative.';
  const totalSec = m * 60 + s;
  if (totalSec < 5)          return 'Duration must be at least 5 seconds.';
  if (totalSec > 300)        return 'Duration cannot exceed 5 minutes (300 s).';
  return null;
}

const SettingsScreen: React.FC<Props> = ({ navigation }) => {
  const [loading, setLoading] = useState(true);
  const [saving,  setSaving]  = useState(false);

  // Feed settings
  const [feedThreshold,       setFeedThreshold]       = useState(20);
  const [dispenseMinutes,     setDispenseMinutes]     = useState('1');
  const [dispenseSeconds,     setDispenseSeconds]     = useState('0');
  const [durationError,       setDurationError]       = useState<string | null>(null);

  // Water settings — alert threshold only; auto-refill removed
  const [waterThreshold, setWaterThreshold] = useState(20);

  useEffect(() => { loadSettings(); }, []);

  const loadSettings = async () => {
    try {
      const userId = auth.currentUser?.uid;
      if (!userId) { Alert.alert('Error', 'User not authenticated'); return; }

      const settings = await settingsService.getSettings(userId);
      if (settings) {
        setFeedThreshold(settings.feed.thresholdPercent);
        const totalSec = Math.round((settings.feed.dispenseCountdownMs ?? 60_000) / 1_000);
        const { minutes, seconds } = splitToMinSec(totalSec);
        setDispenseMinutes(String(minutes));
        setDispenseSeconds(String(seconds));
        setWaterThreshold(settings.water.thresholdPercent);
      } else {
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
    const error = validateDuration(dispenseMinutes, dispenseSeconds);
    if (error) { setDurationError(error); return; }
    setDurationError(null);

    try {
      setSaving(true);
      const userId = auth.currentUser?.uid;
      if (!userId) { Alert.alert('Error', 'User not authenticated'); return; }

      const totalSec = parseInt(dispenseMinutes || '0', 10) * 60
                     + parseInt(dispenseSeconds  || '0', 10);

      const updatedSettings: UserSettings = {
        feed: {
          thresholdPercent:    feedThreshold,
          dispenseCountdownMs: totalSec * 1_000,
        },
        water: {
          thresholdPercent: waterThreshold,
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

  const handleMinutesChange = (val: string) => {
    setDispenseMinutes(val);
    setDurationError(validateDuration(val, dispenseSeconds));
  };

  const handleSecondsChange = (val: string) => {
    setDispenseSeconds(val);
    setDurationError(validateDuration(dispenseMinutes, val));
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
      <View style={styles.header}>
        <TouchableOpacity style={styles.menuButton} onPress={() => navigation.openDrawer()}>
          <Text style={styles.menuIcon}>☰</Text>
        </TouchableOpacity>
        <View style={styles.headerTextContainer}>
          <Text style={styles.headerTitle}>Settings</Text>
          <Text style={styles.headerSubtitle}>Configure system preferences</Text>
        </View>
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>

          {/* ── Feed Settings ── */}
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <View style={[styles.iconCircle, { backgroundColor: '#FF9500' }]}>
                <Text style={styles.iconEmoji}>🌾</Text>
              </View>
              <View style={styles.cardHeaderText}>
                <Text style={styles.cardTitle}>Feed Settings</Text>
                <Text style={styles.cardSubtitle}>Configure feed threshold and dispense duration</Text>
              </View>
            </View>

            <View style={styles.sliderContainer}>
              <View style={styles.sliderHeader}>
                <Text style={styles.sliderLabel}>Alert Threshold</Text>
                <Text style={styles.sliderValue}>{feedThreshold}%</Text>
              </View>
              <Slider
                style={styles.slider}
                minimumValue={0} maximumValue={100} step={1}
                value={feedThreshold} onValueChange={setFeedThreshold}
                minimumTrackTintColor="#FF9500" maximumTrackTintColor="#E0E0E0" thumbTintColor="#FF9500"
              />
              <Text style={styles.sliderDescription}>Alert when feed level drops below this percentage</Text>
            </View>

            <View style={styles.inputContainer}>
              <Text style={styles.sliderLabel}>Dispense Duration</Text>
              <Text style={styles.sliderDescription}>
                How long the feed motor runs per dispense (5 s – 5 min). Raspi picks up changes live — no reboot needed.
              </Text>
              <View style={styles.durationRow}>
                <View style={styles.durationField}>
                  <TextInput
                    style={[styles.durationInput, durationError ? styles.durationInputError : null]}
                    value={dispenseMinutes} onChangeText={handleMinutesChange}
                    keyboardType="number-pad" maxLength={1} selectTextOnFocus
                  />
                  <Text style={styles.durationUnit}>min</Text>
                </View>
                <Text style={styles.durationSeparator}>:</Text>
                <View style={styles.durationField}>
                  <TextInput
                    style={[styles.durationInput, durationError ? styles.durationInputError : null]}
                    value={dispenseSeconds} onChangeText={handleSecondsChange}
                    keyboardType="number-pad" maxLength={2} selectTextOnFocus
                  />
                  <Text style={styles.durationUnit}>sec</Text>
                </View>
              </View>
              {durationError && <Text style={styles.errorText}>{durationError}</Text>}
            </View>
          </View>

          {/* ── Water Settings ── */}
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <View style={[styles.iconCircle, { backgroundColor: '#4A90E2' }]}>
                <Text style={styles.iconEmoji}>💧</Text>
              </View>
              <View style={styles.cardHeaderText}>
                <Text style={styles.cardTitle}>Water Settings</Text>
                <Text style={styles.cardSubtitle}>Configure water alert threshold</Text>
              </View>
            </View>

            <View style={styles.sliderContainer}>
              <View style={styles.sliderHeader}>
                <Text style={styles.sliderLabel}>Alert Threshold</Text>
                <Text style={styles.sliderValue}>{waterThreshold}%</Text>
              </View>
              <Slider
                style={styles.slider}
                minimumValue={0} maximumValue={100} step={1}
                value={waterThreshold} onValueChange={setWaterThreshold}
                minimumTrackTintColor="#2196F3" maximumTrackTintColor="#E0E0E0" thumbTintColor="#2196F3"
              />
              <Text style={styles.sliderDescription}>
                Alert when water level drops below this percentage. Refill is manual — press Refill Water on the Dashboard or # on the keypad.
              </Text>
            </View>
          </View>

          {/* Save Button */}
          <TouchableOpacity
            style={[styles.saveButton, saving && styles.saveButtonDisabled]}
            onPress={handleSaveSettings} disabled={saving}>
            {saving
              ? <ActivityIndicator color="#FFFFFF" />
              : (<>
                  <Text style={styles.saveButtonIcon}>💾</Text>
                  <Text style={styles.saveButtonText}>Save Settings</Text>
                </>)
            }
          </TouchableOpacity>

          <View style={{ height: 30 }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </LinearGradient>
  );
};

const styles = StyleSheet.create({
  container:        { flex: 1 },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#FFFEF0' },
  loadingText:      { marginTop: 12, fontSize: 16, color: '#666' },
  header: { flexDirection: 'row', alignItems: 'center', paddingTop: 50, paddingHorizontal: 20, paddingBottom: 20, backgroundColor: '#FFFEF0' },
  menuButton:          { padding: 8 },
  menuIcon:            { fontSize: 28, color: '#333' },
  headerTextContainer: { marginLeft: 12 },
  headerTitle:         { fontSize: 24, fontWeight: 'bold', color: '#2E7D32' },
  headerSubtitle:      { fontSize: 12, color: '#666', marginTop: 2 },
  content:             { flex: 1, paddingHorizontal: 20 },
  card: { backgroundColor: '#FFFFFF', borderRadius: 20, padding: 20, marginBottom: 20, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 8, elevation: 3 },
  cardHeader:     { flexDirection: 'row', alignItems: 'center', marginBottom: 20 },
  iconCircle:     { width: 60, height: 60, borderRadius: 30, justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  iconEmoji:      { fontSize: 28 },
  cardHeaderText: { flex: 1 },
  cardTitle:      { fontSize: 18, fontWeight: 'bold', color: '#333', marginBottom: 4 },
  cardSubtitle:   { fontSize: 12, color: '#999' },
  sliderContainer: { marginBottom: 24 },
  sliderHeader:    { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  sliderLabel:       { fontSize: 16, color: '#333', fontWeight: '500' },
  sliderValue:       { fontSize: 18, fontWeight: 'bold', color: '#4CAF50' },
  slider:            { width: '100%', height: 40 },
  sliderDescription: { fontSize: 12, color: '#999', marginTop: 4 },
  inputContainer:    { marginBottom: 8 },
  durationRow:       { flexDirection: 'row', alignItems: 'center', marginTop: 12, gap: 8 },
  durationField:     { flexDirection: 'row', alignItems: 'center', gap: 6 },
  durationInput:     { width: 64, height: 48, borderWidth: 1.5, borderColor: '#E0E0E0', borderRadius: 10, backgroundColor: '#FAFAFA', textAlign: 'center', fontSize: 20, fontWeight: '600', color: '#333' },
  durationInputError:{ borderColor: '#F44336', backgroundColor: '#FFF5F5' },
  durationUnit:      { fontSize: 14, color: '#999', fontWeight: '500' },
  durationSeparator: { fontSize: 22, fontWeight: 'bold', color: '#CCC', marginHorizontal: 2 },
  errorText:         { marginTop: 8, fontSize: 12, color: '#F44336' },
  saveButton:        { backgroundColor: '#4CAF50', borderRadius: 16, paddingVertical: 16, flexDirection: 'row', justifyContent: 'center', alignItems: 'center', shadowColor: '#4CAF50', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.3, shadowRadius: 8, elevation: 4, marginTop: 10 },
  saveButtonDisabled:{ backgroundColor: '#A5D6A7' },
  saveButtonIcon:    { fontSize: 24, marginRight: 8 },
  saveButtonText:    { color: '#FFFFFF', fontSize: 16, fontWeight: 'bold' },
});

export default SettingsScreen;