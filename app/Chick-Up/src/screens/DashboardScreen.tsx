// src/screens/DashboardScreen.tsx
import React, { useState, useEffect, useRef } from 'react';
import { Modal, TextInput, View, Text, StyleSheet, TouchableOpacity, ScrollView, Alert, ActivityIndicator } from 'react-native';
import { DrawerNavigationProp } from '@react-navigation/drawer';
import { LinearGradient } from 'expo-linear-gradient';
import { RTCView } from 'react-native-webrtc';
import type { MediaStream } from 'react-native-webrtc';
import { MainDrawerParamList } from '../types/types';
import sensorService from '../services/sensorService';
import buttonService from '../services/buttonService';
import settingsService from '../services/settingsService';
import analyticsService from '../services/analyticsService';
import webrtcService from '../services/webrtcService';
import { auth } from '../config/firebase.config';
import deviceService from '../services/deviceService';

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
  const [feedVolume, setFeedVolume] = useState(10);

  // Dispense button states
  const [waterButtonDisabled, setWaterButtonDisabled] = useState(false);
  const [feedButtonDisabled, setFeedButtonDisabled] = useState(false);
  const [waterCountdown, setWaterCountdown] = useState(0);
  const [feedCountdown, setFeedCountdown] = useState(0);

  const isWaterLow = waterLevel < waterThreshold;
  const isFeedLow = feedLevel < feedThreshold;

  const [linkedDeviceUid, setLinkedDeviceUid] = useState<string | null>(null);
  const [showLinkModal, setShowLinkModal] = useState(false);

  const [deviceUidInput, setDeviceUidInput] = useState('');
  const [verifying, setVerifying] = useState(false);
  const [deviceExists, setDeviceExists] = useState<boolean | null>(null);

  // WebRTC states
  const [isStreaming, setIsStreaming] = useState(false);
  const [showStreamModal, setShowStreamModal] = useState(false);
  const [remoteStream, setRemoteStream] = useState<MediaStream | null>(null);
  const [connectionState, setConnectionState] = useState<string>('disconnected');
  const [streamError, setStreamError] = useState<string | null>(null);

  const handleToggleStream = async () => {
    if (!linkedDeviceUid) {
      Alert.alert('No Device', 'Please link a device first');
      return;
    }

    try {
      const userId = auth.currentUser?.uid;
      if (!userId) {
        Alert.alert('Error', 'User not authenticated');
        return;
      }

      if (isStreaming) {
        // Stop stream
        await webrtcService.stopConnection();
        setIsStreaming(false);
        setRemoteStream(null);
        setConnectionState('disconnected');
        setStreamError(null);
      } else {
        // Start stream
        setStreamError(null);
        setShowStreamModal(true);
        
        // Initialize WebRTC service
        await webrtcService.initialize(
          userId,
          linkedDeviceUid,
          (stream) => {
            console.log('Remote stream received in component');
            setRemoteStream(stream);
          },
          (state) => {
            console.log('Connection state changed:', state);
            setConnectionState(state);
            
            if (state === 'connected') {
              setIsStreaming(true);
              setStreamError(null);
            } else if (state === 'failed') {
              setStreamError('Connection failed. Please try again.');
              setIsStreaming(false);
            } else if (state === 'closed') {
              setIsStreaming(false);
              setRemoteStream(null);
            }
          },
          (error) => {
            console.error('WebRTC error:', error);
            setStreamError(error.message);
            setIsStreaming(false);
          }
        );

        // Start connection
        await webrtcService.startConnection();
        setConnectionState('connecting');
      }
      
    } catch (error: any) {
      console.error('Error toggling stream:', error);
      setStreamError(error.message || 'Failed to toggle stream');
      Alert.alert('Error', error.message || 'Failed to toggle stream');
      setIsStreaming(false);
    }
  };

  useEffect(() => {
    const loadLinkedDevice = async () => {
      setLoading(true);
      const userId = auth.currentUser?.uid;
      if (userId) {
        const deviceUid = await deviceService.getLinkedDevice(userId);
        setLinkedDeviceUid(deviceUid);
      }
    };
    loadLinkedDevice();
  }, []);

  const handleVerifyDevice = async () => {
    if (!deviceUidInput.trim()) return;
    
    setVerifying(true);
    try {
      const exists = await deviceService.verifyDevice(deviceUidInput.trim());
      setDeviceExists(exists);
      
      if (!exists) {
        Alert.alert('Not Found', 'This device UID does not exist in the system.');
      }
    } catch (error: any) {
      Alert.alert('Error', 'Failed to verify device. Please try again.');
      setDeviceExists(false);
    } finally {
      setVerifying(false);
    }
  };

  const handleLinkDevice = async () => {
    const userId = auth.currentUser?.uid;
    if (!userId || !deviceUidInput) return;

    try {
      await deviceService.linkDeviceToUser(userId, deviceUidInput.trim());
      setLinkedDeviceUid(deviceUidInput.trim());
      setShowLinkModal(false);
      setDeviceUidInput('');
      setDeviceExists(null);
      Alert.alert('Success', 'Device linked successfully!');
    } catch (error: any) {
      Alert.alert('Error', 'Failed to link device. Please try again.');
    }
  };

  // Load sensor data and settings on mount
  useEffect(() => {
    const userId = auth.currentUser?.uid;
    if (!userId) {
      Alert.alert('Error', 'User not authenticated');
      setLoading(false);
      return;
    }

    if (!linkedDeviceUid) {
      setLoading(false);
      return;
    }

    const initializeData = async () => {
      try {
        const existingSensorData = await sensorService.getSensorData(userId, linkedDeviceUid);
        if (!existingSensorData) {
          await sensorService.initializeSensorData(userId, linkedDeviceUid);
        }

        const existingButtonData = await buttonService.getButtonData(userId, linkedDeviceUid);
        if (!existingButtonData) {
          await buttonService.initializeButtonData(userId, linkedDeviceUid);
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

    const unsubscribeSensor = sensorService.subscribeSensorData(
      userId,
      linkedDeviceUid,
      (data) => {
        if (data) {
          setWaterLevel(data.waterLevel);
          setFeedLevel(data.feedLevel);
        }
        setLoading(false);
      },
      (error) => {
        console.error('Sensor subscription error:', error);
        Alert.alert('Error', 'Failed to load sensor data');
        setLoading(false);
      }
    );

    const unsubscribeButton = buttonService.subscribeButtonData(
      userId,
      linkedDeviceUid,
      (data) => {
        if (data) {
          if (data.waterButton?.lastUpdateAt) {
            const waterTimestamp = data.waterButton.lastUpdateAt;
            if (typeof waterTimestamp === 'number') {
              const date = new Date(waterTimestamp);
              const formatted = date.toLocaleString('en-US', {
                timeZone: 'Asia/Manila',
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
              });
              const [datePart, timePart] = formatted.split(', ');
              setLastWaterDate(datePart);
              setLastWaterTime(timePart);
            } else {
              const [datePart, timePart] = waterTimestamp.split(' ');
              setLastWaterDate(datePart);
              setLastWaterTime(timePart);
            }
          }
          
          if (data.feedButton?.lastUpdateAt) {
            const feedTimestamp = data.feedButton.lastUpdateAt;
            if (typeof feedTimestamp === 'number') {
              const date = new Date(feedTimestamp);
              const formatted = date.toLocaleString('en-US', {
                timeZone: 'Asia/Manila',
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
              });
              const [datePart, timePart] = formatted.split(', ');
              setLastFeedDate(datePart);
              setLastFeedTime(timePart);
            } else {
              const [datePart, timePart] = feedTimestamp.split(' ');
              setLastFeedDate(datePart);
              setLastFeedTime(timePart);
            }
          }
        }
      },
      (error) => {
        console.error('Button subscription error:', error);
      }
    );

    const unsubscribeSettings = settingsService.subscribeSettings(
      userId,
      (settings) => {
        if (settings) {
          setWaterThreshold(settings.water.thresholdPercent || 20);
          setFeedThreshold(settings.feed.thresholdPercent);
          setFeedVolume(settings.feed.dispenseVolumePercent);
        }
      },
      (error) => {
        console.error('Settings subscription error:', error);
      }
    );

    return () => {
      unsubscribeSensor();
      unsubscribeButton();
      unsubscribeSettings();
    };
  }, [linkedDeviceUid]);

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

  const handleWaterRefill = async () => {
    if (!linkedDeviceUid) {
      Alert.alert('No Device', 'Please link a device first');
      return;
    }

    try {
      const userId = auth.currentUser?.uid;
      if (!userId) {
        Alert.alert('Error', 'User not authenticated');
        return;
      }

      setWaterButtonDisabled(true);
      setWaterCountdown(3);

      await analyticsService.logAction(userId, 'water', 'refill', 0);
      await buttonService.updateButtonTimestamp(userId, linkedDeviceUid, 'water');

      Alert.alert('Success', 'Water refill command sent!');
    } catch (error: any) {
      console.error('Error refilling water:', error);
      Alert.alert('Error', error.message || 'Failed to refill water');
      setWaterButtonDisabled(false);
      setWaterCountdown(0);
    }
  };

  const handleFeedDispense = async () => {
    if (!linkedDeviceUid) {
      Alert.alert('No Device', 'Please link a device first');
      return;
    }

    try {
      const userId = auth.currentUser?.uid;
      if (!userId) {
        Alert.alert('Error', 'User not authenticated');
        return;
      }

      setFeedButtonDisabled(true);
      setFeedCountdown(3);

      await analyticsService.logAction(userId, 'feed', 'dispense', feedVolume);
      await buttonService.updateButtonTimestamp(userId, linkedDeviceUid, 'feed');

      Alert.alert('Success', `Feed dispense command sent! (${feedVolume}%)`);
    } catch (error: any) {
      console.error('Error dispensing feed:', error);
      Alert.alert('Error', error.message || 'Failed to dispense feed');
      setFeedButtonDisabled(false);
      setFeedCountdown(0);
    }
  };

  // Cleanup WebRTC on unmount
  useEffect(() => {
    return () => {
      if (isStreaming) {
        webrtcService.stopConnection();
      }
    };
  }, [isStreaming]);

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#4CAF50" />
        <Text style={styles.loadingText}>Loading dashboard...</Text>
      </View>
    );
  }

  if (!linkedDeviceUid) {
    return (
      <LinearGradient
        colors={['#FFFEF0', '#FFFEF0']}
        style={styles.container}
      >
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

        <View style={styles.noDeviceContainer}>
          <Text style={styles.noDeviceIcon}>📱</Text>
          <Text style={styles.noDeviceTitle}>No Device Linked</Text>
          <Text style={styles.noDeviceMessage}>
            Please link a device to start monitoring your poultry system
          </Text>
          <TouchableOpacity
            style={styles.linkDeviceButton}
            onPress={() => setShowLinkModal(true)}
          >
            <Text style={styles.linkDeviceButtonText}>Link Device</Text>
          </TouchableOpacity>
        </View>

        {/* Link Device Modal */}
        <Modal
          visible={showLinkModal}
          transparent
          animationType="fade"
          onRequestClose={() => setShowLinkModal(false)}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <Text style={styles.modalTitle}>Link Device</Text>
              <Text style={styles.modalSubtitle}>Enter your device UID to connect</Text>
              
              <TextInput
                style={styles.deviceInput}
                placeholder="Enter Device UID"
                value={deviceUidInput}
                onChangeText={(text) => {
                  setDeviceUidInput(text);
                  setDeviceExists(null);
                }}
                autoCapitalize="none"
              />

              {verifying && (
                <ActivityIndicator size="small" color="#4CAF50" style={styles.verifyIndicator} />
              )}

              {deviceExists === false && (
                <Text style={styles.errorText}>❌ Device UID not found</Text>
              )}

              {deviceExists === true && (
                <Text style={styles.successText}>✅ Device verified!</Text>
              )}

              <View style={styles.modalButtons}>
                <TouchableOpacity
                  style={[
                    styles.modalButton, 
                    styles.verifyButton,
                    (!deviceUidInput || verifying) && styles.modalButtonDisabled
                  ]}
                  onPress={handleVerifyDevice}
                  disabled={!deviceUidInput || verifying}
                >
                  <Text style={styles.modalButtonText}>
                    {verifying ? 'Verifying...' : 'Verify'}
                  </Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[
                    styles.modalButton,
                    styles.linkButton,
                    !deviceExists && styles.modalButtonDisabled
                  ]}
                  onPress={handleLinkDevice}
                  disabled={!deviceExists}
                >
                  <Text style={styles.modalButtonText}>Link Device</Text>
                </TouchableOpacity>
              </View>

              <TouchableOpacity
                style={styles.cancelButton}
                onPress={() => {
                  setShowLinkModal(false);
                  setDeviceUidInput('');
                  setDeviceExists(null);
                }}
              >
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Modal>
      </LinearGradient>
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

      {/* Device Badge */}
      <View style={styles.deviceBadge}>
        <Text style={styles.deviceLabel}>Connected Device:</Text>
        <TouchableOpacity onPress={() => setShowLinkModal(true)}>
          <Text style={styles.deviceUid}>{linkedDeviceUid}</Text>
        </TouchableOpacity>
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
            onPress={handleWaterRefill}
            disabled={waterButtonDisabled}
          >
            <Text style={styles.actionButtonIcon}>💧</Text>
            <Text style={styles.actionButtonText}>
              {waterButtonDisabled ? `Wait ${waterCountdown}s` : 'Refill Water'}
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
          <Text style={styles.statsTitle}>Last Activity</Text>
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

      {/* WebRTC Stream Modal */}
      <Modal
        visible={showStreamModal}
        transparent
        animationType="fade"
        onRequestClose={() => {
          setShowStreamModal(false);
          if (isStreaming) {
            handleToggleStream();
          }
        }}
      >
        <View style={styles.streamModalOverlay}>
          <View style={styles.streamModalContent}>
            <View style={styles.streamHeader}>
              <Text style={styles.streamTitle}>📹 Live Stream</Text>
              <TouchableOpacity
                onPress={() => {
                  setShowStreamModal(false);
                  if (isStreaming) {
                    handleToggleStream();
                  }
                }}
                style={styles.streamCloseButton}
              >
                <Text style={styles.streamCloseText}>✕</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.streamFrameContainer}>
              {remoteStream ? (
                <RTCView
                  streamURL={remoteStream.toURL()}
                  style={styles.rtcView}
                  objectFit="contain"
                />
              ) : (
                <View style={styles.streamPlaceholder}>
                  <Text style={styles.streamPlaceholderIcon}>📷</Text>
                  <Text style={styles.streamPlaceholderText}>
                    {connectionState === 'connecting' 
                      ? 'Connecting to Raspberry Pi...' 
                      : connectionState === 'connected'
                      ? 'Waiting for video stream...'
                      : 'No stream available'}
                  </Text>
                  {connectionState === 'connecting' && (
                    <ActivityIndicator size="large" color="#4CAF50" style={{ marginTop: 20 }} />
                  )}
                </View>
              )}
              
              {/* Connection State Indicator */}
              <View style={styles.connectionIndicator}>
                <View style={[
                  styles.connectionDot,
                  connectionState === 'connected' && styles.connectionDotConnected,
                  connectionState === 'connecting' && styles.connectionDotConnecting,
                  connectionState === 'failed' && styles.connectionDotFailed,
                ]} />
                <Text style={styles.connectionText}>
                  {connectionState === 'connected' ? 'LIVE' : 
                   connectionState === 'connecting' ? 'CONNECTING' :
                   connectionState === 'failed' ? 'FAILED' : 'DISCONNECTED'}
                </Text>
              </View>
            </View>

            {streamError && (
              <View style={styles.errorBanner}>
                <Text style={styles.errorBannerText}>⚠️ {streamError}</Text>
              </View>
            )}

            <View style={styles.streamControls}>
              <TouchableOpacity
                style={[
                  styles.streamControlButton,
                  isStreaming ? styles.stopButton : styles.startButton
                ]}
                onPress={handleToggleStream}
                disabled={connectionState === 'connecting'}
              >
                <Text style={styles.streamControlButtonText}>
                  {connectionState === 'connecting' 
                    ? '⏳ Connecting...' 
                    : isStreaming 
                    ? '⏹ Stop Stream' 
                    : '▶ Start Stream'}
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Floating Stream Button */}
      <TouchableOpacity
        style={[
          styles.streamButton,
          isStreaming && styles.streamButtonActive
        ]}
        onPress={() => setShowStreamModal(true)}
      >
        <Text style={styles.streamButtonIcon}>📹</Text>
        <Text style={styles.streamButtonText}>
          {isStreaming ? 'View Live Stream' : 'Start Live Stream'}
        </Text>
      </TouchableOpacity>
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
  deviceBadge: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 20,
    marginTop: 10,
    padding: 12,
    borderRadius: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  deviceLabel: {
    fontSize: 12,
    color: '#666',
    marginRight: 6,
  },
  deviceUid: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#4CAF50',
  },
  noDeviceText: {
    fontSize: 14,
    color: '#E53935',
    fontWeight: '500',
  },
  fab: {
    position: 'absolute',
    right: 20,
    bottom: 30,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#4CAF50',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalContent: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 24,
    width: '85%',
    maxWidth: 400,
  },
  modalTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 8,
    textAlign: 'center',
  },
  modalSubtitle: {
    fontSize: 14,
    color: '#666',
    marginBottom: 20,
    textAlign: 'center',
  },
  deviceInput: {
    borderWidth: 1,
    borderColor: '#E0E0E0',
    borderRadius: 12,
    padding: 12,
    fontSize: 16,
    marginBottom: 16,
  },
  verifyIndicator: {
    marginBottom: 12,
  },
  errorText: {
    color: '#E53935',
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 12,
  },
  successText: {
    color: '#4CAF50',
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 12,
  },
  modalButtons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  modalButton: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 12,
    marginHorizontal: 4,
  },
  verifyButton: {
    backgroundColor: '#2196F3',
  },
  linkButton: {
    backgroundColor: '#4CAF50',
  },
  modalButtonDisabled: {
    backgroundColor: '#BDBDBD',
    opacity: 0.5,
  },
  modalButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
    textAlign: 'center',
  },
  cancelButton: {
    paddingVertical: 12,
  },
  cancelButtonText: {
    color: '#666',
    fontSize: 16,
    textAlign: 'center',
  },
  noDeviceContainer: {
  flex: 1,
  justifyContent: 'center',
  alignItems: 'center',
  paddingHorizontal: 40,
  },
  noDeviceIcon: {
    fontSize: 80,
    marginBottom: 20,
  },
  noDeviceTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 12,
  },
  noDeviceMessage: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    marginBottom: 30,
    lineHeight: 24,
  },
  linkDeviceButton: {
    backgroundColor: '#4CAF50',
    paddingHorizontal: 32,
    paddingVertical: 16,
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 4,
  },
  linkDeviceButtonText: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: 'bold',
  },
  streamButton: {
    backgroundColor: '#9C27B0',
    paddingVertical: 18,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: 20,
    marginBottom: 20,
    flexDirection: 'row',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 4,
  },
  streamButtonActive: {
    backgroundColor: '#E53935',
  },
  streamButtonIcon: {
    fontSize: 24,
    marginRight: 8,
  },
  streamButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  streamModalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.9)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  streamModalContent: {
    backgroundColor: '#1E1E1E',
    borderRadius: 20,
    width: '90%',
    maxWidth: 500,
    padding: 20,
  },
  streamHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  streamTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#FFFFFF',
  },
  streamCloseButton: {
    padding: 8,
  },
  streamCloseText: {
    fontSize: 24,
    color: '#FFFFFF',
  },
  streamFrame: {
    backgroundColor: '#000000',
    borderRadius: 12,
    overflow: 'hidden',
    aspectRatio: 16 / 9,
    borderWidth: 3,
    borderColor: '#9C27B0',
  },
  streamImage: {
    width: '100%',
    height: '100%',
  },
  streamPlaceholder: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#2C2C2C',
  },
  streamPlaceholderIcon: {
    fontSize: 48,
    marginBottom: 12,
  },
  streamPlaceholderText: {
    color: '#999',
    fontSize: 16,
  },
  recordingIndicator: {
    position: 'absolute',
    top: 12,
    left: 12,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(229, 57, 53, 0.9)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
  },
  recordingDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#FFFFFF',
    marginRight: 6,
  },
  recordingText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: 'bold',
  },
  streamControls: {
    flexDirection: 'row',
    justifyContent: 'center',
  },
  streamControlButton: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
  },
  startButton: {
    backgroundColor: '#4CAF50',
  },
  stopButton: {
    backgroundColor: '#E53935',
  },
  streamControlButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  // WebRTC-specific styles
  streamFrameContainer: {
    width: '100%',
    height: 400,
    backgroundColor: '#000',
    borderRadius: 12,
    overflow: 'hidden',
    position: 'relative',
  },
  rtcView: {
    width: '100%',
    height: '100%',
  },
  connectionIndicator: {
    position: 'absolute',
    top: 16,
    left: 16,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
  },
  connectionDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#666',
    marginRight: 8,
  },
  connectionDotConnected: {
    backgroundColor: '#4CAF50',
  },
  connectionDotConnecting: {
    backgroundColor: '#FF9500',
  },
  connectionDotFailed: {
    backgroundColor: '#F44336',
  },
  connectionText: {
    color: '#FFF',
    fontSize: 12,
    fontWeight: '600',
  },
  errorBanner: {
    backgroundColor: '#FFEBEE',
    padding: 12,
    borderRadius: 8,
    marginTop: 12,
  },
  errorBannerText: {
    color: '#D32F2F',
    fontSize: 14,
    textAlign: 'center',
  },
});

export default DashboardScreen;