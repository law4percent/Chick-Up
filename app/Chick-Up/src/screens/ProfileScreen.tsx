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

interface Props {
  navigation: ProfileScreenNavigationProp;
}
const ProfileScreen: React.FC<Props> = ({ navigation }) => {
// export default function ProfileScreen() {
  const [userData, setUserData] = useState<UserData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  // Edit form state
  const [editedUsername, setEditedUsername] = useState('');
  const [editedPhoneNumber, setEditedPhoneNumber] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  useEffect(() => {
    loadUserData();
  }, []);

  const loadUserData = async () => {
    try {
      setLoading(true);
      const user = auth.currentUser;
      if (!user) {
        Alert.alert('Error', 'No user logged in');
        return;
      }

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
    // Reset password fields when entering edit mode
    setCurrentPassword('');
    setNewPassword('');
    setConfirmPassword('');
  };

  const handleCancel = () => {
    setIsEditing(false);
    // Reset form to original values
    if (userData) {
      setEditedUsername(userData.username);
      setEditedPhoneNumber(userData.phoneNumber);
    }
    setCurrentPassword('');
    setNewPassword('');
    setConfirmPassword('');
  };

  const validateChanges = (): boolean => {
    // Validate username
    if (!editedUsername.trim()) {
      Alert.alert('Validation Error', 'Username cannot be empty');
      return false;
    }
    if (editedUsername.length < 3) {
      Alert.alert('Validation Error', 'Username must be at least 3 characters');
      return false;
    }

    // Validate phone number
    if (!editedPhoneNumber.trim()) {
      Alert.alert('Validation Error', 'Phone number cannot be empty');
      return false;
    }
    const phoneRegex = /^[0-9+\-\s()]+$/;
    if (!phoneRegex.test(editedPhoneNumber)) {
      Alert.alert('Validation Error', 'Invalid phone number format');
      return false;
    }

    // Validate password change if user wants to change password
    if (newPassword || confirmPassword) {
      if (!currentPassword) {
        Alert.alert('Validation Error', 'Current password is required to change password');
        return false;
      }
      if (newPassword !== confirmPassword) {
        Alert.alert('Validation Error', 'New passwords do not match');
        return false;
      }
      if (newPassword.length < 6) {
        Alert.alert('Validation Error', 'New password must be at least 6 characters');
        return false;
      }
    }

    return true;
  };

  const handleSave = async () => {
    if (!validateChanges() || !userData) return;

    try {
      setSaving(true);
      const user = auth.currentUser;
      if (!user) {
        Alert.alert('Error', 'No user logged in');
        return;
      }

      const hasUsernameChanged = editedUsername !== userData.username;
      const hasPhoneChanged = editedPhoneNumber !== userData.phoneNumber;
      const hasPasswordChange = newPassword.trim() !== '';

      // Check if username is already taken (if changed)
      if (hasUsernameChanged) {
        const isAvailable = await authService.isUsernameAvailable(editedUsername);
        if (!isAvailable) {
          Alert.alert('Error', 'Username already taken');
          setSaving(false);
          return;
        }
      }

      // Re-authenticate user if password change is requested
      if (hasPasswordChange) {
        try {
          const credential = EmailAuthProvider.credential(
            user.email!,
            currentPassword
          );
          await reauthenticateWithCredential(user, credential);
        } catch (error: any) {
          Alert.alert('Error', 'Current password is incorrect');
          setSaving(false);
          return;
        }
      }

      // Update password first if requested
      if (hasPasswordChange) {
        await updatePassword(user, newPassword);
      }

      // Update user data in database
      const updates: any = {};
      
      if (hasUsernameChanged || hasPhoneChanged) {
        const updatedUserData = {
          ...userData,
          username: editedUsername,
          phoneNumber: editedPhoneNumber,
          updatedAt: Date.now(),
        };

        // Update users node
        await set(ref(database, `users/${user.uid}`), updatedUserData);

        // If username changed, update username mapping
        if (hasUsernameChanged) {
          // Remove old username mapping
          await set(ref(database, `usernames/${userData.username.toLowerCase()}`), null);
          
          // Add new username mapping
          await set(ref(database, `usernames/${editedUsername.toLowerCase()}`), {
            uid: user.uid,
            email: userData.email,
          });
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
          <LinearGradient
            colors={['#FFD54F', '#4CAF50']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={styles.retryButtonGradient}
          >
            <Text style={styles.retryButtonText}>Retry</Text>
          </LinearGradient>
        </TouchableOpacity>
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
                <Text style={styles.headerTitle}>Profile</Text>
                <Text style={styles.headerSubtitle}>Smart Poultry Automation</Text>
            </View>
            {!isEditing && (
                <TouchableOpacity style={styles.editButton} onPress={handleEdit}>
                <LinearGradient
                    colors={['#FFD54F', '#4CAF50']}
                    start={{ x: 0, y: 0 }}
                    end={{ x: 1, y: 0 }}
                    style={styles.editButtonGradient}
                >
                    <Text style={styles.editButtonText}>✏️ Edit</Text>
                </LinearGradient>
                </TouchableOpacity>
            )}
        </View>
        
        <ScrollView
            style={styles.scrollView}
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
        >
            {/* <View style={styles.header}>
            <Text style={styles.title}>Profile</Text>

            </View> */}


            <View style={styles.section}>
            <Text style={styles.sectionTitle}>Personal Information</Text>

            {/* Username Field */}
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

            {/* Email Field (Read-only) */}
            <View style={styles.fieldContainer}>
                <Text style={styles.label}>Email</Text>
                <View style={[styles.input, styles.inputDisabled, styles.readOnlyContainer]}>
                <Text style={styles.readOnlyText}>{userData.email}</Text>
                <View style={styles.readOnlyBadge}>
                    <Text style={styles.readOnlyBadgeText}>Read-only</Text>
                </View>
                </View>
            </View>

            {/* Phone Number Field */}
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

            {/* Password Change Section (only visible when editing) */}
            {isEditing && (
            <View style={styles.section}>
                <Text style={styles.sectionTitle}>🔒 Change Password (Optional)</Text>
                
                <View style={styles.fieldContainer}>
                <Text style={styles.label}>Current Password</Text>
                <TextInput
                    style={styles.input}
                    value={currentPassword}
                    onChangeText={setCurrentPassword}
                    secureTextEntry
                    placeholder="Enter current password"
                    placeholderTextColor="#999"
                    autoCapitalize="none"
                />
                </View>

                <View style={styles.fieldContainer}>
                <Text style={styles.label}>New Password</Text>
                <TextInput
                    style={styles.input}
                    value={newPassword}
                    onChangeText={setNewPassword}
                    secureTextEntry
                    placeholder="Enter new password"
                    placeholderTextColor="#999"
                    autoCapitalize="none"
                />
                </View>

                <View style={styles.fieldContainer}>
                <Text style={styles.label}>Confirm New Password</Text>
                <TextInput
                    style={styles.input}
                    value={confirmPassword}
                    onChangeText={setConfirmPassword}
                    secureTextEntry
                    placeholder="Confirm new password"
                    placeholderTextColor="#999"
                    autoCapitalize="none"
                />
                </View>

                <View style={styles.passwordHintContainer}>
                <Text style={styles.passwordHint}>
                    💡 Leave password fields empty if you don't want to change your password
                </Text>
                </View>
            </View>
            )}

            {/* Account Info */}
            <View style={styles.section}>
            <Text style={styles.sectionTitle}>📋 Account Information</Text>
            <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>Account Created:</Text>
                <Text style={styles.infoValue}>
                {new Date(userData.createdAt).toLocaleDateString()}
                </Text>
            </View>
            <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>Last Updated:</Text>
                <Text style={styles.infoValue}>
                {new Date(userData.updatedAt).toLocaleDateString()}
                </Text>
            </View>
            </View>

            {/* Action Buttons */}
            {isEditing && (
            <View style={styles.buttonContainer}>
                <TouchableOpacity
                style={[styles.button, styles.cancelButton]}
                onPress={handleCancel}
                disabled={saving}
                >
                <Text style={styles.cancelButtonText}>Cancel</Text>
                </TouchableOpacity>

                <TouchableOpacity
                style={[styles.button, saving && styles.buttonDisabled]}
                onPress={handleSave}
                disabled={saving}
                >
                <LinearGradient
                    colors={['#FFD54F', '#4CAF50']}
                    start={{ x: 0, y: 0 }}
                    end={{ x: 1, y: 0 }}
                    style={styles.saveButtonGradient}
                >
                    {saving ? (
                    <ActivityIndicator size="small" color="#FFF" />
                    ) : (
                    <Text style={styles.saveButtonText}>💾 Save Changes</Text>
                    )}
                </LinearGradient>
                </TouchableOpacity>
            </View>
            )}
        </ScrollView>
    </LinearGradient>

  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1
  },
  scrollView: {
    flex: 1,
  },
  headerTextContainer: {
    flex: 1,
    marginLeft: 12,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#2E7D32',
  },
  scrollContent: {
    padding: 20,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#FFFEF0',
    padding: 20,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingTop: 50,
    paddingHorizontal: 20,
    justifyContent: 'space-between',
    paddingBottom: 20,
    backgroundColor: '#FFFEF0',
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: '#333',
  },
  editButton: {
    borderRadius: theme.borderRadius.md,
    overflow: 'hidden',
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  editButtonGradient: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    paddingLeft: 12
  },
  editButtonText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
  },
  section: {
    backgroundColor: '#FFF',
    borderRadius: theme.borderRadius.lg,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.lg,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 3,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginBottom: theme.spacing.md,
  },
  fieldContainer: {
    marginBottom: theme.spacing.md,
  },
  label: {
    fontSize: 14,
    color: '#666',
    marginBottom: theme.spacing.xs,
    fontWeight: '600',
  },
  input: {
    backgroundColor: '#F9F9F9',
    borderWidth: 1,
    borderColor: '#E0E0E0',
    borderRadius: theme.borderRadius.md,
    padding: theme.spacing.md,
    fontSize: 16,
    color: '#333',
  },
  inputDisabled: {
    backgroundColor: '#F5F5F5',
    color: '#999',
  },
  readOnlyContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  readOnlyText: {
    fontSize: 16,
    color: '#999',
    flex: 1,
  },
  readOnlyBadge: {
    backgroundColor: '#FFD54F',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  readOnlyBadgeText: {
    fontSize: 11,
    color: '#333',
    fontWeight: '600',
  },
  passwordHintContainer: {
    backgroundColor: '#FFF9E6',
    padding: theme.spacing.sm,
    borderRadius: theme.borderRadius.sm,
    marginTop: theme.spacing.sm,
    borderLeftWidth: 3,
    borderLeftColor: '#FFD54F',
  },
  passwordHint: {
    fontSize: 13,
    color: '#666',
    fontStyle: 'italic',
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: theme.spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: '#F0F0F0',
  },
  infoLabel: {
    fontSize: 15,
    color: '#666',
  },
  infoValue: {
    fontSize: 15,
    color: '#333',
    fontWeight: '600',
  },
  buttonContainer: {
    flexDirection: 'row',
    gap: theme.spacing.md,
    marginTop: theme.spacing.lg,
    marginBottom: theme.spacing.xl,
  },
  button: {
    flex: 1,
    borderRadius: theme.borderRadius.md,
    overflow: 'hidden',
    minHeight: 50,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  cancelButton: {
    backgroundColor: '#FFF',
    borderWidth: 2,
    borderColor: '#E0E0E0',
    justifyContent: 'center',
    alignItems: 'center',
  },
  cancelButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#666',
  },
  saveButtonGradient: {
    padding: theme.spacing.md,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 50,
  },
  saveButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  loadingText: {
    fontSize: 15,
    color: '#666',
    marginTop: theme.spacing.md,
  },
  errorText: {
    fontSize: 15,
    color: '#F44336',
    textAlign: 'center',
  },
  retryButton: {
    marginTop: theme.spacing.lg,
    borderRadius: theme.borderRadius.md,
    overflow: 'hidden',
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  retryButtonGradient: {
    paddingHorizontal: theme.spacing.xl,
    paddingVertical: theme.spacing.md,
  },
  retryButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  menuButton: {
    padding: 8,
  },
  menuIcon: {
    fontSize: 28,
    color: '#333',
  },
  headerSubtitle: {
    fontSize: 12,
    color: '#666',
    marginTop: 2,
  },
});

export default ProfileScreen;