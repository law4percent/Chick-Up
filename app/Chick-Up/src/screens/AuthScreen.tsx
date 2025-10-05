// src/screens/AuthScreen.tsx
import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  ActivityIndicator,
  Image,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { RootStackParamList, LoginFormData, SignUpFormData } from '../types/types';
import authService from '../services/authService';

type AuthScreenNavigationProp = NativeStackNavigationProp<RootStackParamList, 'Auth'>;

interface Props {
  navigation: AuthScreenNavigationProp;
}

type TabType = 'login' | 'register';

const AuthScreen: React.FC<Props> = ({ navigation }) => {
  const [activeTab, setActiveTab] = useState<TabType>('login');
  const [loading, setLoading] = useState(false);

  // Login form state
  const [loginData, setLoginData] = useState<LoginFormData>({
    username: '',
    password: '',
  });

  // Sign up form state
  const [signUpData, setSignUpData] = useState<SignUpFormData>({
    username: '',
    phoneNumber: '',
    email: '',
    password: '',
  });

  // Login handlers
  const handleLoginChange = (field: keyof LoginFormData, value: string) => {
    setLoginData(prev => ({ ...prev, [field]: value }));
  };

  const validateLogin = (): boolean => {
    if (!loginData.username.trim()) {
      Alert.alert('Error', 'Please enter your username');
      return false;
    }
    if (!loginData.password) {
      Alert.alert('Error', 'Please enter your password');
      return false;
    }
    return true;
  };

  const handleLogin = async () => {
    if (!validateLogin()) return;

    setLoading(true);
    try {
      await authService.login(loginData);
      // Navigation handled by AuthContext
    } catch (error: any) {
      Alert.alert('Login Failed', error.message || 'Failed to login');
    } finally {
      setLoading(false);
    }
  };

  // Sign up handlers
  const handleSignUpChange = (field: keyof SignUpFormData, value: string) => {
    setSignUpData(prev => ({ ...prev, [field]: value }));
  };

  const validateSignUp = (): boolean => {
    if (!signUpData.username.trim()) {
      Alert.alert('Error', 'Please enter a username');
      return false;
    }
    if (signUpData.username.length < 3) {
      Alert.alert('Error', 'Username must be at least 3 characters');
      return false;
    }
    if (!signUpData.phoneNumber.trim()) {
      Alert.alert('Error', 'Please enter a phone number');
      return false;
    }
    if (!signUpData.email.trim()) {
      Alert.alert('Error', 'Please enter an email');
      return false;
    }
    if (!signUpData.password) {
      Alert.alert('Error', 'Please enter a password');
      return false;
    }
    if (signUpData.password.length < 6) {
      Alert.alert('Error', 'Password must be at least 6 characters');
      return false;
    }
    return true;
  };

  const handleSignUp = async () => {
    if (!validateSignUp()) return;

    setLoading(true);
    try {
      await authService.signUp(signUpData);
      Alert.alert(
        'Success',
        'Account created successfully! Please login.',
        [{ 
          text: 'OK', 
          onPress: () => {
            setActiveTab('login');
            setSignUpData({
              username: '',
              phoneNumber: '',
              email: '',
              password: '',
            });
          }
        }]
      );
    } catch (error: any) {
      Alert.alert('Sign Up Failed', error.message || 'Failed to create account');
    } finally {
      setLoading(false);
    }
  };

  return (
    <LinearGradient
      colors={['#4CAF50', '#8BC34A', '#CDDC39', '#FFEB3B']}
      style={styles.gradient}
      start={{ x: 0, y: 0 }}
      end={{ x: 0, y: 1 }}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.container}
      >
        <ScrollView 
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
        {/* Logo Section */}
        <View style={styles.logoContainer}>
          <View style={styles.logoCircle}>
            <Image
              source={require('../../assets/icon.png')} // Make this path easy to replace
              style={styles.logo}
              resizeMode="contain"
            />
          </View>
          <Text style={styles.appName}>CHICK-UP</Text>
          <Text style={styles.tagline}>SMART POULTRY AUTOMATION</Text>
        </View>

        {/* Card Container */}
        <View style={styles.card}>
          {/* Tab Buttons */}
          <View style={styles.tabContainer}>
            <TouchableOpacity
              style={[styles.tab, activeTab === 'login' && styles.activeTab]}
              onPress={() => setActiveTab('login')}
              disabled={loading}
            >
              <Text style={[styles.tabText, activeTab === 'login' && styles.activeTabText]}>
                LOGIN
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.tab, activeTab === 'register' && styles.activeTab]}
              onPress={() => setActiveTab('register')}
              disabled={loading}
            >
              <Text style={[styles.tabText, activeTab === 'register' && styles.activeTabText]}>
                REGISTER
              </Text>
            </TouchableOpacity>
          </View>

          {/* Login Form */}
          {activeTab === 'login' && (
            <View style={styles.formContainer}>
              <View style={styles.inputContainer}>
                <View style={styles.inputWrapper}>
                  <Text style={styles.inputIcon}>👤</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="Username or email"
                    placeholderTextColor="#999"
                    value={loginData.username}
                    onChangeText={(value) => handleLoginChange('username', value)}
                    autoCapitalize="none"
                    editable={!loading}
                  />
                </View>
              </View>

              <View style={styles.inputContainer}>
                <View style={styles.inputWrapper}>
                  <Text style={styles.inputIcon}>🔒</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="Password"
                    placeholderTextColor="#999"
                    value={loginData.password}
                    onChangeText={(value) => handleLoginChange('password', value)}
                    secureTextEntry
                    editable={!loading}
                  />
                </View>
              </View>

              <TouchableOpacity
                style={[styles.button, loading && styles.buttonDisabled]}
                onPress={handleLogin}
                disabled={loading}
              >
                {loading ? (
                  <ActivityIndicator color="#FFF" />
                ) : (
                  <Text style={styles.buttonText}>LOGIN</Text>
                )}
              </TouchableOpacity>

              <TouchableOpacity style={styles.forgotPassword}>
                <Text style={styles.forgotPasswordText}>Forgot password?</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* Register Form */}
          {activeTab === 'register' && (
            <View style={styles.formContainer}>
              <View style={styles.inputContainer}>
                <View style={styles.inputWrapper}>
                  <Text style={styles.inputIcon}>👤</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="Username"
                    placeholderTextColor="#999"
                    value={signUpData.username}
                    onChangeText={(value) => handleSignUpChange('username', value)}
                    autoCapitalize="none"
                    editable={!loading}
                  />
                </View>
              </View>

              <View style={styles.inputContainer}>
                <View style={styles.inputWrapper}>
                  <Text style={styles.inputIcon}>📱</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="Phone number"
                    placeholderTextColor="#999"
                    value={signUpData.phoneNumber}
                    onChangeText={(value) => handleSignUpChange('phoneNumber', value)}
                    keyboardType="phone-pad"
                    editable={!loading}
                  />
                </View>
              </View>

              <View style={styles.inputContainer}>
                <View style={styles.inputWrapper}>
                  <Text style={styles.inputIcon}>✉️</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="Email"
                    placeholderTextColor="#999"
                    value={signUpData.email}
                    onChangeText={(value) => handleSignUpChange('email', value)}
                    keyboardType="email-address"
                    autoCapitalize="none"
                    editable={!loading}
                  />
                </View>
              </View>

              <View style={styles.inputContainer}>
                <View style={styles.inputWrapper}>
                  <Text style={styles.inputIcon}>🔒</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="Password"
                    placeholderTextColor="#999"
                    value={signUpData.password}
                    onChangeText={(value) => handleSignUpChange('password', value)}
                    secureTextEntry
                    editable={!loading}
                  />
                </View>
              </View>

              <TouchableOpacity
                style={[styles.button, loading && styles.buttonDisabled]}
                onPress={handleSignUp}
                disabled={loading}
              >
                {loading ? (
                  <ActivityIndicator color="#FFF" />
                ) : (
                  <Text style={styles.buttonText}>REGISTER</Text>
                )}
              </TouchableOpacity>
            </View>
          )}
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
    </LinearGradient>
  );
};

const styles = StyleSheet.create({
  gradient: {
    flex: 1,
  },
  container: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingVertical: 40,
  },
  logoContainer: {
    alignItems: 'center',
    marginBottom: 40,
  },
  logoCircle: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: '#FFFFFF',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 8,
  },
  logo: {
    width: 80,
    height: 80,
  },
  appName: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#2E7D32',
    marginBottom: 4,
    letterSpacing: 2,
  },
  tagline: {
    fontSize: 12,
    color: '#1B5E20',
    letterSpacing: 1,
  },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    marginHorizontal: 30,
    paddingBottom: 30,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 8,
  },
  tabContainer: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: '#E0E0E0',
  },
  tab: {
    flex: 1,
    paddingVertical: 16,
    alignItems: 'center',
  },
  activeTab: {
    borderBottomWidth: 3,
    borderBottomColor: '#4CAF50',
  },
  tabText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#999',
    letterSpacing: 1,
  },
  activeTabText: {
    color: '#4CAF50',
  },
  formContainer: {
    paddingHorizontal: 20,
    paddingTop: 30,
  },
  inputContainer: {
    marginBottom: 16,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F5F5F5',
    borderRadius: 12,
    paddingHorizontal: 16,
    height: 50,
    borderWidth: 1,
    borderColor: '#E0E0E0',
  },
  inputIcon: {
    fontSize: 18,
    marginRight: 12,
  },
  input: {
    flex: 1,
    fontSize: 15,
    color: '#333',
  },
  button: {
    backgroundColor: '#4CAF50',
    borderRadius: 12,
    height: 50,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 10,
    shadowColor: '#4CAF50',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
  },
  buttonDisabled: {
    backgroundColor: '#A5D6A7',
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  forgotPassword: {
    alignItems: 'center',
    marginTop: 16,
  },
  forgotPasswordText: {
    color: '#4CAF50',
    fontSize: 14,
  },
});

export default AuthScreen;