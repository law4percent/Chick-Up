// src/screens/ScheduleScreen.tsx
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Alert,
  ActivityIndicator,
  Modal,
  Switch,
  TextInput,
} from 'react-native';
import { DrawerNavigationProp } from '@react-navigation/drawer';
import { LinearGradient } from 'expo-linear-gradient';
import Slider from '@react-native-community/slider';
import { MainDrawerParamList, FeedSchedule } from '../types/types';
import scheduleService from '../services/scheduleService';
import { auth } from '../config/firebase.config';

type ScheduleScreenNavigationProp = DrawerNavigationProp<MainDrawerParamList, 'Schedule'>;

interface Props {
  navigation: ScheduleScreenNavigationProp;
}

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const ScheduleScreen: React.FC<Props> = ({ navigation }) => {
  const [loading, setLoading] = useState(true);
  const [schedules, setSchedules] = useState<FeedSchedule[]>([]);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<FeedSchedule | null>(null);

  // Form states
  const [time, setTime] = useState('08:00');
  const [selectedDays, setSelectedDays] = useState<number[]>([1, 2, 3, 4, 5]); // Mon-Fri
  const [volumePercent, setVolumePercent] = useState(10);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadSchedules();
  }, []);

  const loadSchedules = async () => {
    try {
      const userId = auth.currentUser?.uid;
      if (!userId) {
        Alert.alert('Error', 'User not authenticated');
        return;
      }

      const unsubscribe = scheduleService.subscribeSchedules(
        userId,
        (schedulesData) => {
          setSchedules(schedulesData.sort((a, b) => a.time.localeCompare(b.time)));
          setLoading(false);
        },
        (error) => {
          console.error('Schedule subscription error:', error);
          Alert.alert('Error', 'Failed to load schedules');
          setLoading(false);
        }
      );

      return unsubscribe;
    } catch (error) {
      console.error('Error loading schedules:', error);
      Alert.alert('Error', 'Failed to load schedules');
      setLoading(false);
    }
  };

  const handleOpenModal = (schedule?: FeedSchedule) => {
    if (schedule) {
      setEditingSchedule(schedule);
      setTime(schedule.time);
      setSelectedDays(schedule.days);
      setVolumePercent(schedule.volumePercent);
    } else {
      setEditingSchedule(null);
      setTime('08:00');
      setSelectedDays([1, 2, 3, 4, 5]);
      setVolumePercent(10);
    }
    setModalVisible(true);
  };

  const handleCloseModal = () => {
    setModalVisible(false);
    setEditingSchedule(null);
  };

  const toggleDay = (day: number) => {
    if (selectedDays.includes(day)) {
      setSelectedDays(selectedDays.filter(d => d !== day));
    } else {
      setSelectedDays([...selectedDays, day].sort());
    }
  };

  const handleSaveSchedule = async () => {
    try {
      if (selectedDays.length === 0) {
        Alert.alert('Error', 'Please select at least one day');
        return;
      }

      const userId = auth.currentUser?.uid;
      if (!userId) {
        Alert.alert('Error', 'User not authenticated');
        return;
      }

      setSaving(true);

      if (editingSchedule) {
        await scheduleService.updateSchedule(userId, editingSchedule.id, {
          time,
          days: selectedDays,
          volumePercent,
        });
        Alert.alert('Success', 'Schedule updated successfully!');
      } else {
        await scheduleService.createSchedule(userId, time, selectedDays, volumePercent);
        Alert.alert('Success', 'Schedule created successfully!');
      }

      handleCloseModal();
    } catch (error: any) {
      console.error('Error saving schedule:', error);
      Alert.alert('Error', error.message || 'Failed to save schedule');
    } finally {
      setSaving(false);
    }
  };

  const handleToggleSchedule = async (schedule: FeedSchedule) => {
    try {
      const userId = auth.currentUser?.uid;
      if (!userId) return;

      await scheduleService.toggleSchedule(userId, schedule.id, !schedule.enabled);
    } catch (error: any) {
      console.error('Error toggling schedule:', error);
      Alert.alert('Error', error.message || 'Failed to toggle schedule');
    }
  };

  const handleDeleteSchedule = async (schedule: FeedSchedule) => {
    Alert.alert(
      'Delete Schedule',
      'Are you sure you want to delete this schedule?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              const userId = auth.currentUser?.uid;
              if (!userId) return;

              await scheduleService.deleteSchedule(userId, schedule.id);
              Alert.alert('Success', 'Schedule deleted successfully');
            } catch (error: any) {
              console.error('Error deleting schedule:', error);
              Alert.alert('Error', error.message || 'Failed to delete schedule');
            }
          },
        },
      ]
    );
  };

  const formatDays = (days: number[]) => {
    if (days.length === 7) return 'Every day';
    if (days.length === 5 && !days.includes(0) && !days.includes(6)) return 'Weekdays';
    if (days.length === 2 && days.includes(0) && days.includes(6)) return 'Weekends';
    return days.map(d => DAYS[d]).join(', ');
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#4CAF50" />
        <Text style={styles.loadingText}>Loading schedules...</Text>
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
          <Text style={styles.headerTitle}>Feed Schedule</Text>
          <Text style={styles.headerSubtitle}>Manage feeding times</Text>
        </View>
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {schedules.length === 0 ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyIcon}>📅</Text>
            <Text style={styles.emptyTitle}>No Schedules Yet</Text>
            <Text style={styles.emptyText}>
              Create your first feeding schedule to automate your poultry care
            </Text>
          </View>
        ) : (
          schedules.map((schedule) => (
            <View key={schedule.id} style={styles.scheduleCard}>
              <View style={styles.scheduleHeader}>
                <View style={styles.scheduleTimeContainer}>
                  <Text style={styles.scheduleTime}>{schedule.time}</Text>
                  <Text style={styles.scheduleDays}>{formatDays(schedule.days)}</Text>
                </View>
                <Switch
                  value={schedule.enabled}
                  onValueChange={() => handleToggleSchedule(schedule)}
                  trackColor={{ false: '#D1D1D1', true: '#4CAF50' }}
                  thumbColor={schedule.enabled ? '#FFFFFF' : '#F4F3F4'}
                />
              </View>
              
              <View style={styles.scheduleInfo}>
                <Text style={styles.scheduleLabel}>Feed Volume</Text>
                <Text style={styles.scheduleValue}>{schedule.volumePercent}%</Text>
              </View>

              <View style={styles.scheduleActions}>
                <TouchableOpacity
                  style={[styles.actionBtn, styles.editBtn]}
                  onPress={() => handleOpenModal(schedule)}
                >
                  <Text style={styles.actionBtnText}>✏️ Edit</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.actionBtn, styles.deleteBtn]}
                  onPress={() => handleDeleteSchedule(schedule)}
                >
                  <Text style={styles.actionBtnText}>🗑️ Delete</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))
        )}

        <View style={{ height: 100 }} />
      </ScrollView>

      {/* Add Schedule Button */}
      <TouchableOpacity
        style={styles.fab}
        onPress={() => handleOpenModal()}
      >
        <Text style={styles.fabIcon}>+</Text>
      </TouchableOpacity>

      {/* Schedule Modal */}
      <Modal
        visible={modalVisible}
        animationType="slide"
        transparent={true}
        onRequestClose={handleCloseModal}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>
              {editingSchedule ? 'Edit Schedule' : 'New Schedule'}
            </Text>

            {/* Time Input */}
            <View style={styles.formGroup}>
              <Text style={styles.formLabel}>Time (HH:MM)</Text>
              <TextInput
                style={styles.textInput}
                value={time}
                onChangeText={setTime}
                placeholder="08:00"
                keyboardType="numbers-and-punctuation"
              />
            </View>

            {/* Days Selection */}
            <View style={styles.formGroup}>
              <Text style={styles.formLabel}>Select Days</Text>
              <View style={styles.daysContainer}>
                {DAYS.map((day, index) => (
                  <TouchableOpacity
                    key={index}
                    style={[
                      styles.dayButton,
                      selectedDays.includes(index) && styles.dayButtonSelected,
                    ]}
                    onPress={() => toggleDay(index)}
                  >
                    <Text
                      style={[
                        styles.dayButtonText,
                        selectedDays.includes(index) && styles.dayButtonTextSelected,
                      ]}
                    >
                      {day}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* Volume Slider */}
            <View style={styles.formGroup}>
              <View style={styles.sliderHeader}>
                <Text style={styles.formLabel}>Feed Volume</Text>
                <Text style={styles.sliderValue}>{volumePercent}%</Text>
              </View>
              <Slider
                style={styles.slider}
                minimumValue={0}
                maximumValue={100}
                step={1}
                value={volumePercent}
                onValueChange={setVolumePercent}
                minimumTrackTintColor="#FF9500"
                maximumTrackTintColor="#E0E0E0"
                thumbTintColor="#FF9500"
              />
            </View>

            {/* Action Buttons */}
            <View style={styles.modalActions}>
              <TouchableOpacity
                style={[styles.modalBtn, styles.cancelBtn]}
                onPress={handleCloseModal}
                disabled={saving}
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalBtn, styles.saveBtn, saving && styles.saveBtnDisabled]}
                onPress={handleSaveSchedule}
                disabled={saving}
              >
                {saving ? (
                  <ActivityIndicator color="#FFFFFF" />
                ) : (
                  <Text style={styles.saveBtnText}>Save</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
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
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 80,
  },
  emptyIcon: {
    fontSize: 64,
    marginBottom: 16,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 8,
  },
  emptyText: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
    paddingHorizontal: 40,
  },
  scheduleCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 3,
  },
  scheduleHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  scheduleTimeContainer: {
    flex: 1,
  },
  scheduleTime: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
  },
  scheduleDays: {
    fontSize: 14,
    color: '#666',
    marginTop: 4,
  },
  scheduleInfo: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: '#E0E0E0',
    marginBottom: 12,
  },
  scheduleLabel: {
    fontSize: 14,
    color: '#666',
  },
  scheduleValue: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#FF9500',
  },
  scheduleActions: {
    flexDirection: 'row',
    gap: 12,
  },
  actionBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center',
  },
  editBtn: {
    backgroundColor: '#2196F3',
  },
  deleteBtn: {
    backgroundColor: '#E53935',
  },
  actionBtnText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
  fab: {
    position: 'absolute',
    bottom: 30,
    right: 30,
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: '#4CAF50',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  fabIcon: {
    fontSize: 32,
    color: '#FFFFFF',
    fontWeight: 'bold',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    maxHeight: '80%',
  },
  modalTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 24,
  },
  formGroup: {
    marginBottom: 24,
  },
  formLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
  },
  textInput: {
    borderWidth: 1,
    borderColor: '#E0E0E0',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    color: '#333',
  },
  daysContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 8,
  },
  dayButton: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#E0E0E0',
    alignItems: 'center',
  },
  dayButtonSelected: {
    backgroundColor: '#4CAF50',
    borderColor: '#4CAF50',
  },
  dayButtonText: {
    fontSize: 12,
    color: '#666',
    fontWeight: '600',
  },
  dayButtonTextSelected: {
    color: '#FFFFFF',
  },
  sliderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  sliderValue: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#FF9500',
  },
  slider: {
    width: '100%',
    height: 40,
  },
  modalActions: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 8,
  },
  modalBtn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
  },
  cancelBtn: {
    backgroundColor: '#F5F5F5',
  },
  cancelBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#666',
  },
  saveBtn: {
    backgroundColor: '#4CAF50',
  },
  saveBtnDisabled: {
    backgroundColor: '#A5D6A7',
  },
  saveBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
  },
});

export default ScheduleScreen;