// app/Chick-Up/src/screens/ProfileScreen.tsx
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Modal,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { auth, database } from '../config/firebase.config';
import { ref, get, set, update } from 'firebase/database';
import { updatePassword, reauthenticateWithCredential, EmailAuthProvider } from 'firebase/auth';
import { UserData } from '../types/types';
import { theme } from '../config/theme';
import authService from '../services/authService';
import { DrawerNavigationProp } from '@react-navigation/drawer';
import { MainDrawerParamList } from '../types/types';

type ProfileScreenNavigationProp = DrawerNavigationProp<MainDrawerParamList, 'Profile'>;
interface Props { navigation: ProfileScreenNavigationProp; }

// ─────────────────────────── MANUAL CONTENT ──────────────────────────────────

const MANUAL_SECTIONS = [
  {
    title: '1. System Overview',
    content:
      'Chick-Up automates feed dispensing and water refilling for a poultry enclosure. The Raspberry Pi monitors feed and water levels through ultrasonic sensors and drives two relay-controlled motors.\n\n' +
      'What the system does automatically:\n' +
      '• Measures feed and water levels continuously\n' +
      '• Warns you when levels drop below your configured thresholds\n' +
      '• Dispenses feed automatically on a schedule you configure\n' +
      '• Optionally refills water automatically when it gets too low\n' +
      '• Logs every feed and water action to analytics, tagged by source\n\n' +
      'What you do manually:\n' +
      '• Trigger feed dispensing or water refill on demand\n' +
      '• Watch a live camera stream\n' +
      '• Adjust thresholds and timing from the app',
  },
  {
    title: '2. Hardware Controls',
    content:
      'LCD Display\n' +
      'The device has a 16×2 LCD showing system status:\n\n' +
      '  Feed: 72.5%       → normal\n' +
      '  FEED LOW 15.0%    → below threshold\n' +
      '  DISPENSING...     → motor running\n' +
      '  REFILLING...      → pump running\n\n' +
      'Keypad — Pairing Menu\n' +
      '  2  →  Move cursor up\n' +
      '  8  →  Move cursor down\n' +
      '  A  →  Confirm selection\n\n' +
      'Keypad — While Running\n' +
      '  *          →  Dispense feed\n' +
      '  #          →  Refill water\n' +
      '  D (hold 3s) →  Logout\n\n' +
      'All other keys (0–9, B, C) are ignored during normal operation.',
  },
  {
    title: '3. First-Time Setup',
    content:
      'Powering On\n' +
      '1. Connect the Raspberry Pi to power.\n' +
      '2. LCD shows "Chick-Up / Initializing..." for ~2 seconds.\n' +
      '3. If no device has been paired, the pairing menu appears.\n\n' +
      'Pairing with the App\n' +
      '1. On the Pi keypad, press A to select Login.\n' +
      '2. The LCD shows a 6-character code valid for 60 seconds.\n' +
      '3. In the app, go to Dashboard → Pair Device.\n' +
      '4. Enter the code exactly as shown (uppercase, no spaces).\n' +
      '5. Tap Look Up, then tap Pair to complete.\n' +
      '6. The LCD confirms and the system starts automatically.\n\n' +
      'The code expires after 60 seconds. Press A again on the Pi to generate a new one.',
  },
  {
    title: '4. Daily Operation',
    content:
      'Manual Feed Dispense — Keypad\n' +
      'Press * once. The motor runs for the Dispense Duration set in Settings (default 60 s). It stops automatically. Pressing * while a dispense is in progress is ignored.\n\n' +
      'Manual Water Refill — Keypad\n' +
      'Press # once. The pump runs until the water level reaches 95% (hard safety cap) or your Auto Refill Target, whichever is lower. It stops automatically.\n\n' +
      'If water is already at or above 95%, pressing # does nothing.',
  },
  {
    title: '5. Mobile App',
    content:
      'Dashboard\n' +
      'Shows real-time feed and water levels, last action timestamps, warning indicators, and action buttons. If no device is paired, a Link Device prompt appears.\n\n' +
      'Manual Controls\n' +
      '• Refill Water — starts the pump. Runs until 95%. 3-second cooldown after each press.\n' +
      '• Dispense Feed — starts the motor for the configured Dispense Duration. Same cooldown.\n\n' +
      'Live Camera Stream\n' +
      'Tap Live Stream on the Dashboard. Connects via WebRTC. Takes 5–15 seconds to connect. If it shows FAILED, tap again to retry.\n\n' +
      'Settings\n' +
      'Feed: Alert Threshold (0–100%), Dispense Duration (5 s–5 min, entered as minutes + seconds).\n' +
      'Water: Alert Threshold (0–80%), Enable Auto Refill, Auto Refill Target Level (0–100%).\n' +
      'All changes take effect on the Pi live — no reboot needed.\n\n' +
      'Feed Schedule\n' +
      'Set a time (24-hour format) and select days. The Pi fires the motor once per minute window when the time matches. Schedules can be enabled/disabled without deleting them.\n\n' +
      'Analytics\n' +
      'Shows a full history of feed and water actions tagged by source: app, keypad, or schedule.',
  },
  {
    title: '6. Changing the Owner (Logout)',
    content:
      '1. On the Pi keypad, hold D for 3 seconds.\n' +
      '2. LCD shows "Hold D: Logout / Please wait..."\n' +
      '3. The Pi deletes its credentials and removes the device link from Firebase.\n' +
      '4. LCD returns to the pairing menu.\n\n' +
      'The previous account\'s Dashboard will show "No device paired" on the next refresh.',
  },
  {
    title: '7. Shutting Down',
    content:
      'From the pairing menu:\n' +
      '1. Press 8 to move cursor to Shutdown.\n' +
      '2. Press A to confirm.\n\n' +
      'While the system is running:\n' +
      '1. Hold D for 3 seconds to log out first.\n' +
      '2. Then navigate to Shutdown in the pairing menu and press A.\n\n' +
      '⚠️ Never unplug the Pi without shutting it down — this can corrupt the SD card.',
  },
  {
    title: '8. Understanding the Alerts',
    content:
      '• Feed / Water level warning — level dropped below Alert Threshold. Refill manually or wait for auto-refill.\n\n' +
      '• DISPENSING... / REFILLING... on LCD — motor is running normally. Wait for it to finish.\n\n' +
      '• App: "No Device" — no device is paired. Follow the pairing steps.\n\n' +
      '• App: "Connection failed" — live stream could not connect. Retry; check that the Pi is online.\n\n' +
      '• App: "Failed to send command" — button press could not reach Firebase. Check internet connection.\n\n' +
      '• LCD: "Auth invalid / Re-pairing..." — credentials failed. Pi will return to pairing menu automatically.\n\n' +
      '• LCD: "Code expired! / Press A to retry" — 60-second pairing window passed. Press A for a new code.',
  },
  {
    title: '9. Troubleshooting',
    content:
      'LCD is blank after powering on\n' +
      'Verify the I²C connection and address (0x27 default). Adjust the contrast potentiometer on the LCD backpack.\n\n' +
      'Live stream stays on "Connecting..."\n' +
      'Make sure the Pi is running (LCD shows sensor data). On mobile data, wait up to 30 seconds for the TURN relay. If consistently failing, verify coturn is running and port 3478 UDP/TCP is open.\n\n' +
      'Feed motor or pump does not run\n' +
      'Check the Pi is powered and the LCD is showing sensor data. Check relay wiring and GPIO connections. Check warning.log on the Pi.\n\n' +
      'Auto-refill triggers immediately at startup\n' +
      'Normal if sensors haven\'t stabilized — the system waits 2 seconds (20 boot ticks). If it persists, check ultrasonic sensor mounting.\n\n' +
      'Settings not taking effect\n' +
      'Ensure you tapped Save Settings. If the Dispense Duration shows a red border, fix the value first. The Pi picks up changes within ~100 ms.\n\n' +
      'A schedule did not fire\n' +
      'Check the schedule is enabled. Verify the time is in 24-hour format. The Pi must be online at the scheduled time — missed schedules are not retried. Ensure NTP is synced.\n\n' +
      'A schedule fired but no analytics entry appeared\n' +
      'The entry is written after the motor stops. Wait for the full Dispense Duration. Check Pi network connection.',
  },
];

// ─────────────────────────── COMPONENT ───────────────────────────────────────

const ProfileScreen: React.FC<Props> = ({ navigation }) => {
  const [userData, setUserData] = useState<UserData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [showManual, setShowManual] = useState(false);

  // Edit form state
  const [editedUsername, setEditedUsername] = useState('');
  const [editedPhoneNumber, setEditedPhoneNumber] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  useEffect(() => { loadUserData(); }, []);

  const loadUserData = async () => {
    try {
      setLoading(true);
      const user = auth.currentUser;
      if (!user) { Alert.alert('Error', 'No user logged in'); return; }
      const data = await authService.getUserData(user.uid);
      if (data) {
        setUserData(data);
        setEditedUsername(data.username);
        setEditedPhoneNumber(data.phoneNumber);
      }
    } catch (error) {
      console.error('Error loading user data:', error);
      Alert.alert('Error', 'Failed to load user data');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = () => {
    setIsEditing(true);
    setCurrentPassword('');
    setNewPassword('');
    setConfirmPassword('');
  };

  const handleCancel = () => {
    setIsEditing(false);
    if (userData) {
      setEditedUsername(userData.username);
      setEditedPhoneNumber(userData.phoneNumber);
    }
    setCurrentPassword('');
    setNewPassword('');
    setConfirmPassword('');
  };

  const validateChanges = (): boolean => {
    if (!editedUsername.trim()) { Alert.alert('Validation Error', 'Username cannot be empty'); return false; }
    if (editedUsername.length < 3) { Alert.alert('Validation Error', 'Username must be at least 3 characters'); return false; }
    if (!editedPhoneNumber.trim()) { Alert.alert('Validation Error', 'Phone number cannot be empty'); return false; }
    const phoneRegex = /^[0-9+\-\s()]+$/;
    if (!phoneRegex.test(editedPhoneNumber)) { Alert.alert('Validation Error', 'Invalid phone number format'); return false; }
    if (newPassword || confirmPassword) {
      if (!currentPassword) { Alert.alert('Validation Error', 'Current password is required to change password'); return false; }
      if (newPassword !== confirmPassword) { Alert.alert('Validation Error', 'New passwords do not match'); return false; }
      if (newPassword.length < 6) { Alert.alert('Validation Error', 'New password must be at least 6 characters'); return false; }
    }
    return true;
  };

  const handleSave = async () => {
    if (!validateChanges() || !userData) return;
    try {
      setSaving(true);
      const user = auth.currentUser;
      if (!user) { Alert.alert('Error', 'No user logged in'); return; }

      const hasUsernameChanged = editedUsername !== userData.username;
      const hasPhoneChanged    = editedPhoneNumber !== userData.phoneNumber;
      const hasPasswordChange  = newPassword.trim() !== '';

      if (hasUsernameChanged) {
        const isAvailable = await authService.isUsernameAvailable(editedUsername);
        if (!isAvailable) { Alert.alert('Error', 'Username already taken'); setSaving(false); return; }
      }

      if (hasPasswordChange) {
        try {
          const credential = EmailAuthProvider.credential(user.email!, currentPassword);
          await reauthenticateWithCredential(user, credential);
        } catch {
          Alert.alert('Error', 'Current password is incorrect');
          setSaving(false);
          return;
        }
        await updatePassword(user, newPassword);
      }

      if (hasUsernameChanged || hasPhoneChanged) {
        const updatedUserData = { ...userData, username: editedUsername, phoneNumber: editedPhoneNumber, updatedAt: Date.now() };
        await set(ref(database, `users/${user.uid}`), updatedUserData);
        if (hasUsernameChanged) {
          await set(ref(database, `usernames/${userData.username.toLowerCase()}`), null);
          await set(ref(database, `usernames/${editedUsername.toLowerCase()}`), { uid: user.uid, email: userData.email });
        }
        setUserData(updatedUserData);
      }

      Alert.alert('Success', 'Profile updated successfully');
      setIsEditing(false);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error: any) {
      console.error('Error updating profile:', error);
      Alert.alert('Error', error.message || 'Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#4CAF50" />
        <Text style={styles.loadingText}>Loading profile...</Text>
      </View>
    );
  }

  if (!userData) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>Failed to load user data</Text>
        <TouchableOpacity style={styles.retryButton} onPress={loadUserData}>
          <LinearGradient colors={['#FFD54F', '#4CAF50']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.retryButtonGradient}>
            <Text style={styles.retryButtonText}>Retry</Text>
          </LinearGradient>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <LinearGradient colors={['#FFFEF0', '#FFFEF0']} style={styles.container}>

      {/* ── Header ── */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.menuButton} onPress={() => navigation.openDrawer()}>
          <Text style={styles.menuIcon}>☰</Text>
        </TouchableOpacity>
        <View style={styles.headerTextContainer}>
          <Text style={styles.headerTitle}>Profile</Text>
          <Text style={styles.headerSubtitle}>IOT-CONTROLLED POULTRY MANAGEMENT</Text>
        </View>
        {!isEditing && (
          <TouchableOpacity style={styles.editButton} onPress={handleEdit}>
            <LinearGradient colors={['#FFD54F', '#4CAF50']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.editButtonGradient}>
              <Text style={styles.editButtonText}>Edit</Text>
            </LinearGradient>
          </TouchableOpacity>
        )}
      </View>

      <ScrollView style={styles.scrollView} contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">

        {/* ── Personal Information ── */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Personal Information</Text>

          <View style={styles.fieldContainer}>
            <Text style={styles.label}>Username</Text>
            <TextInput
              style={[styles.input, !isEditing && styles.inputDisabled]}
              value={editedUsername}
              onChangeText={setEditedUsername}
              editable={isEditing}
              autoCapitalize="none"
              placeholder="Enter username"
              placeholderTextColor="#999"
            />
          </View>

          <View style={styles.fieldContainer}>
            <Text style={styles.label}>Email</Text>
            <View style={[styles.input, styles.inputDisabled, styles.readOnlyContainer]}>
              <Text style={styles.readOnlyText}>{userData.email}</Text>
              <View style={styles.readOnlyBadge}>
                <Text style={styles.readOnlyBadgeText}>Read-only</Text>
              </View>
            </View>
          </View>

          <View style={styles.fieldContainer}>
            <Text style={styles.label}>Phone Number</Text>
            <TextInput
              style={[styles.input, !isEditing && styles.inputDisabled]}
              value={editedPhoneNumber}
              onChangeText={setEditedPhoneNumber}
              editable={isEditing}
              keyboardType="phone-pad"
              placeholder="Enter phone number"
              placeholderTextColor="#999"
            />
          </View>
        </View>

        {/* ── Change Password (edit mode only) ── */}
        {isEditing && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>🔒 Change Password (Optional)</Text>

            <View style={styles.fieldContainer}>
              <Text style={styles.label}>Current Password</Text>
              <TextInput style={styles.input} value={currentPassword} onChangeText={setCurrentPassword}
                secureTextEntry placeholder="Enter current password" placeholderTextColor="#999" autoCapitalize="none" />
            </View>
            <View style={styles.fieldContainer}>
              <Text style={styles.label}>New Password</Text>
              <TextInput style={styles.input} value={newPassword} onChangeText={setNewPassword}
                secureTextEntry placeholder="Enter new password" placeholderTextColor="#999" autoCapitalize="none" />
            </View>
            <View style={styles.fieldContainer}>
              <Text style={styles.label}>Confirm New Password</Text>
              <TextInput style={styles.input} value={confirmPassword} onChangeText={setConfirmPassword}
                secureTextEntry placeholder="Confirm new password" placeholderTextColor="#999" autoCapitalize="none" />
            </View>

            <View style={styles.passwordHintContainer}>
              <Text style={styles.passwordHint}>
                💡 Leave password fields empty if you don't want to change your password
              </Text>
            </View>
          </View>
        )}

        {/* ── Account Information ── */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📋 Account Information</Text>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Account Created:</Text>
            <Text style={styles.infoValue}>{new Date(userData.createdAt).toLocaleDateString()}</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Last Updated:</Text>
            <Text style={styles.infoValue}>{new Date(userData.updatedAt).toLocaleDateString()}</Text>
          </View>
        </View>

        {/* ── User Manual ── */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📖 User Manual</Text>
          <Text style={styles.manualDescription}>
            Complete guide for operating your Chick-Up device — hardware controls, pairing, settings, schedules, and troubleshooting.
          </Text>
          <TouchableOpacity style={styles.manualButton} onPress={() => setShowManual(true)}>
            <LinearGradient
              colors={['#2E7D32', '#4CAF50']}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
              style={styles.manualButtonGradient}
            >
              <Text style={styles.manualButtonText}>Open User Manual</Text>
            </LinearGradient>
          </TouchableOpacity>
        </View>

        {/* ── Save / Cancel (edit mode only) ── */}
        {isEditing && (
          <View style={styles.buttonContainer}>
            <TouchableOpacity style={[styles.button, styles.cancelButton]} onPress={handleCancel} disabled={saving}>
              <Text style={styles.cancelButtonText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.button, saving && styles.buttonDisabled]} onPress={handleSave} disabled={saving}>
              <LinearGradient colors={['#FFD54F', '#4CAF50']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.saveButtonGradient}>
                {saving
                  ? <ActivityIndicator size="small" color="#FFF" />
                  : <Text style={styles.saveButtonText}>💾 Save Changes</Text>
                }
              </LinearGradient>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>

      {/* ── User Manual Modal ── */}
      <Modal
        visible={showManual}
        animationType="slide"
        onRequestClose={() => setShowManual(false)}
      >
        <LinearGradient colors={['#FFFEF0', '#FFFEF0']} style={styles.container}>

          {/* Modal header */}
          <View style={styles.manualModalHeader}>
            <View>
              <Text style={styles.manualModalTitle}>📖 User Manual</Text>
              <Text style={styles.manualModalSubtitle}>Chick-Up Smart Poultry System</Text>
            </View>
            <TouchableOpacity style={styles.manualCloseButton} onPress={() => setShowManual(false)}>
              <Text style={styles.manualCloseText}>✕</Text>
            </TouchableOpacity>
          </View>

          <ScrollView
            style={styles.manualScroll}
            contentContainerStyle={styles.manualScrollContent}
            showsVerticalScrollIndicator={false}
          >
            {MANUAL_SECTIONS.map((section, index) => (
              <View key={index} style={styles.manualSection}>
                <View style={styles.manualSectionHeader}>
                  <Text style={styles.manualSectionTitle}>{section.title}</Text>
                </View>
                <Text style={styles.manualSectionBody}>{section.content}</Text>
              </View>
            ))}

            {/* Bottom close button for convenience */}
            <TouchableOpacity style={styles.manualBottomClose} onPress={() => setShowManual(false)}>
              <Text style={styles.manualBottomCloseText}>Close Manual</Text>
            </TouchableOpacity>

            <View style={{ height: 40 }} />
          </ScrollView>

        </LinearGradient>
      </Modal>

    </LinearGradient>
  );
};

// ─────────────────────────── STYLES ──────────────────────────────────────────

const styles = StyleSheet.create({
  container:        { flex: 1 },
  scrollView:       { flex: 1 },
  scrollContent:    { padding: 20 },
  centerContainer:  { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#FFFEF0', padding: 20 },
  loadingText:      { fontSize: 15, color: '#666', marginTop: theme.spacing.md },
  errorText:        { fontSize: 15, color: '#F44336', textAlign: 'center' },

  // Header
  header:              { flexDirection: 'row', alignItems: 'center', paddingTop: 50, paddingHorizontal: 20, paddingBottom: 20, justifyContent: 'space-between', backgroundColor: '#FFFEF0' },
  menuButton:          { padding: 8 },
  menuIcon:            { fontSize: 28, color: '#333' },
  headerTextContainer: { flex: 1, marginLeft: 12 },
  headerTitle:         { fontSize: 24, fontWeight: 'bold', color: '#2E7D32' },
  headerSubtitle:      { fontSize: 12, color: '#666', marginTop: 2 },
  editButton:          { borderRadius: theme.borderRadius.md, overflow: 'hidden', elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 4 },
  editButtonGradient:  { paddingHorizontal: 16, paddingVertical: 12, paddingLeft: 12 },
  editButtonText:      { fontSize: 15, fontWeight: '600', color: '#FFF' },

  // Sections
  section:      { backgroundColor: '#FFF', borderRadius: theme.borderRadius.lg, padding: theme.spacing.lg, marginBottom: theme.spacing.lg, elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 3 },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: '#333', marginBottom: theme.spacing.md },

  // Fields
  fieldContainer: { marginBottom: theme.spacing.md },
  label:          { fontSize: 14, color: '#666', marginBottom: theme.spacing.xs, fontWeight: '600' },
  input:          { backgroundColor: '#F9F9F9', borderWidth: 1, borderColor: '#E0E0E0', borderRadius: theme.borderRadius.md, padding: theme.spacing.md, fontSize: 16, color: '#333' },
  inputDisabled:  { backgroundColor: '#F5F5F5', color: '#999' },

  readOnlyContainer: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  readOnlyText:      { fontSize: 16, color: '#999', flex: 1 },
  readOnlyBadge:     { backgroundColor: '#FFD54F', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 4 },
  readOnlyBadgeText: { fontSize: 11, color: '#333', fontWeight: '600' },

  passwordHintContainer: { backgroundColor: '#FFF9E6', padding: theme.spacing.sm, borderRadius: theme.borderRadius.sm, marginTop: theme.spacing.sm, borderLeftWidth: 3, borderLeftColor: '#FFD54F' },
  passwordHint:          { fontSize: 13, color: '#666', fontStyle: 'italic' },

  infoRow:   { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: theme.spacing.sm, borderBottomWidth: 1, borderBottomColor: '#F0F0F0' },
  infoLabel: { fontSize: 15, color: '#666' },
  infoValue: { fontSize: 15, color: '#333', fontWeight: '600' },

  // Manual card
  manualDescription:    { fontSize: 13, color: '#666', lineHeight: 20, marginBottom: 16 },
  manualButton:         { borderRadius: theme.borderRadius.md, overflow: 'hidden', elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.15, shadowRadius: 4 },
  manualButtonGradient: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 14 },
  manualButtonIcon:     { fontSize: 20, marginRight: 8 },
  manualButtonText:     { fontSize: 16, fontWeight: '700', color: '#FFF' },

  // Manual modal
  manualModalHeader:   { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingTop: 50, paddingHorizontal: 20, paddingBottom: 16, backgroundColor: '#FFFEF0', borderBottomWidth: 1, borderBottomColor: '#E8F5E9' },
  manualModalTitle:    { fontSize: 22, fontWeight: 'bold', color: '#2E7D32' },
  manualModalSubtitle: { fontSize: 12, color: '#666', marginTop: 2 },
  manualCloseButton:   { width: 36, height: 36, borderRadius: 18, backgroundColor: '#F5F5F5', justifyContent: 'center', alignItems: 'center' },
  manualCloseText:     { fontSize: 16, color: '#666', fontWeight: '600' },

  manualScroll:        { flex: 1 },
  manualScrollContent: { paddingHorizontal: 20, paddingTop: 20 },

  manualSection:       { backgroundColor: '#FFF', borderRadius: 16, marginBottom: 16, overflow: 'hidden', elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.08, shadowRadius: 4 },
  manualSectionHeader: { backgroundColor: '#E8F5E9', paddingHorizontal: 16, paddingVertical: 12, borderLeftWidth: 4, borderLeftColor: '#2E7D32' },
  manualSectionTitle:  { fontSize: 15, fontWeight: '700', color: '#2E7D32' },
  manualSectionBody:   { fontSize: 14, color: '#444', lineHeight: 22, padding: 16 },

  manualBottomClose:     { backgroundColor: '#F5F5F5', borderRadius: 12, paddingVertical: 14, alignItems: 'center', marginTop: 8 },
  manualBottomCloseText: { fontSize: 15, fontWeight: '600', color: '#666' },

  // Action buttons
  buttonContainer:    { flexDirection: 'row', gap: theme.spacing.md, marginTop: theme.spacing.lg, marginBottom: theme.spacing.xl },
  button:             { flex: 1, borderRadius: theme.borderRadius.md, overflow: 'hidden', minHeight: 50, elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 4 },
  cancelButton:       { backgroundColor: '#FFF', borderWidth: 2, borderColor: '#E0E0E0', justifyContent: 'center', alignItems: 'center' },
  cancelButtonText:   { fontSize: 16, fontWeight: '600', color: '#666' },
  saveButtonGradient: { padding: theme.spacing.md, alignItems: 'center', justifyContent: 'center', minHeight: 50 },
  saveButtonText:     { fontSize: 16, fontWeight: '600', color: '#FFF' },
  buttonDisabled:     { opacity: 0.5 },

  retryButton:         { marginTop: theme.spacing.lg, borderRadius: theme.borderRadius.md, overflow: 'hidden', elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 4 },
  retryButtonGradient: { paddingHorizontal: theme.spacing.xl, paddingVertical: theme.spacing.md },
  retryButtonText:     { fontSize: 16, fontWeight: '600', color: '#FFF' },

  title: { fontSize: 28, fontWeight: '700', color: '#333' },
});

export default ProfileScreen;