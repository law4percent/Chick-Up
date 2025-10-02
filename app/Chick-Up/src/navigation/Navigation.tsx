// src/navigation/Navigation.tsx
import React, { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createDrawerNavigator } from '@react-navigation/drawer';
import { onAuthStateChanged } from 'firebase/auth';
import { View, ActivityIndicator, StyleSheet } from 'react-native';

import { auth } from '../config/firebase.config';
import { RootStackParamList, AuthStackParamList, MainDrawerParamList } from '../types/types';
import { theme } from '../config/theme';

// Screens
import LoginScreen from '../screens/LoginScreen';
import SignUpScreen from '../screens/SignUpScreen';
import DashboardScreen from '../screens/DashboardScreen';
import CustomDrawer from '../components/CustomDrawer';

const RootStack = createNativeStackNavigator<RootStackParamList>();
const AuthStack = createNativeStackNavigator<AuthStackParamList>();
const MainDrawer = createDrawerNavigator<MainDrawerParamList>();

// Auth Navigator
const AuthNavigator = () => {
  return (
    <AuthStack.Navigator
      screenOptions={{
        headerShown: false,
      }}
    >
      <AuthStack.Screen name="Login" component={LoginScreen} />
      <AuthStack.Screen name="SignUp" component={SignUpScreen} />
    </AuthStack.Navigator>
  );
};

// Placeholder screen component for Profile and Settings
const PlaceholderScreen = () => (
  <View style={styles.placeholder}>
    <ActivityIndicator size="large" color={theme.colors.primary} />
  </View>
);

// Main Drawer Navigator with left-side drawer
const MainNavigator = () => {
  return (
    <MainDrawer.Navigator
      drawerContent={(props) => <CustomDrawer {...props} />}
      screenOptions={{
        headerShown: false,
        drawerPosition: 'left', // Left-side drawer
        drawerType: 'slide',
        drawerStyle: {
          width: 280,
          backgroundColor: theme.colors.background,
        },
        swipeEnabled: true, // Enable swipe gestures
        swipeEdgeWidth: 50, // Swipe from edge to open
      }}
    >
      <MainDrawer.Screen name="Dashboard" component={DashboardScreen} />
      {/* Add more screens here as you build them */}
      <MainDrawer.Screen 
        name="Profile" 
        component={PlaceholderScreen} 
        options={{ title: 'Profile' }}
      />
      <MainDrawer.Screen 
        name="Settings" 
        component={PlaceholderScreen} 
        options={{ title: 'Settings' }}
      />
    </MainDrawer.Navigator>
  );
};

// Main Navigation Component
const Navigation = () => {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
      setLoading(false);
    });

    return unsubscribe;
  }, []);

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={theme.colors.primary} />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <RootStack.Navigator screenOptions={{ headerShown: false }}>
        {user ? (
          <RootStack.Screen name="Main" component={MainNavigator} />
        ) : (
          <RootStack.Screen name="Auth" component={AuthNavigator} />
        )}
      </RootStack.Navigator>
    </NavigationContainer>
  );
};

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: theme.colors.background,
  },
  placeholder: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: theme.colors.background,
  },
});

export default Navigation;