// src/navigation/Navigation.tsx
import React, { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createDrawerNavigator } from '@react-navigation/drawer';
import { onAuthStateChanged } from 'firebase/auth';
import { View, ActivityIndicator, StyleSheet } from 'react-native';

import { auth } from '../config/firebase.config';
import { RootStackParamList, MainDrawerParamList } from '../types/types';
import { theme } from '../config/theme';

// Screens
import AuthScreen from '../screens/AuthScreen';
import DashboardScreen from '../screens/DashboardScreen';
import CustomDrawer from '../components/CustomDrawer';

const RootStack = createNativeStackNavigator<RootStackParamList>();
const MainDrawer = createDrawerNavigator<MainDrawerParamList>();

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
        drawerPosition: 'left',
        drawerType: 'slide',
        drawerStyle: {
          width: 280,
          backgroundColor: theme.colors.background,
        },
        swipeEnabled: true,
        swipeEdgeWidth: 50,
      }}
    >
      <MainDrawer.Screen name="Dashboard" component={DashboardScreen} />
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
          <RootStack.Screen name="Auth" component={AuthScreen} />
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