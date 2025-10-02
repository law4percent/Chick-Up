// src/components/CustomDrawer.tsx
import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
} from 'react-native';
import {
  DrawerContentScrollView,
  DrawerContentComponentProps,
} from '@react-navigation/drawer';
import authService from '../services/authService';
import { theme } from '../config/theme';

const CustomDrawer: React.FC<DrawerContentComponentProps> = (props) => {
  const handleLogout = () => {
    Alert.alert(
      'Logout',
      'Are you sure you want to logout?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Logout',
          style: 'destructive',
          onPress: async () => {
            try {
              await authService.signOut();
            } catch (error) {
              Alert.alert('Error', 'Failed to logout');
            }
          },
        },
      ],
    );
  };

  return (
    <View style={styles.container}>
      <DrawerContentScrollView {...props} contentContainerStyle={styles.scrollView}>
        <View style={styles.header}>
          <Text style={styles.appName}>Chick-Up</Text>
          <Text style={styles.tagline}>Stay organized!</Text>
        </View>

        <View style={styles.menuItems}>
          <TouchableOpacity
            style={styles.menuItem}
            onPress={() => props.navigation.navigate('Dashboard')}
          >
            <Text style={styles.menuIcon}>🏠</Text>
            <Text style={styles.menuText}>Dashboard</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.menuItem}
            onPress={() => props.navigation.navigate('Profile')}
          >
            <Text style={styles.menuIcon}>👤</Text>
            <Text style={styles.menuText}>Profile</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.menuItem}
            onPress={() => props.navigation.navigate('Settings')}
          >
            <Text style={styles.menuIcon}>⚙️</Text>
            <Text style={styles.menuText}>Settings</Text>
          </TouchableOpacity>
        </View>
      </DrawerContentScrollView>

      <View style={styles.footer}>
        <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
          <Text style={styles.logoutIcon}>🚪</Text>
          <Text style={styles.logoutText}>Logout</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  scrollView: {
    flexGrow: 1,
  },
  header: {
    padding: theme.spacing.lg,
    backgroundColor: theme.colors.primary,
    borderBottomWidth: 2,
    borderBottomColor: theme.colors.secondary,
  },
  appName: {
    ...theme.typography.h1,
    color: '#FFF',
    marginBottom: theme.spacing.xs,
  },
  tagline: {
    ...theme.typography.caption,
    color: '#FFF',
    opacity: 0.9,
  },
  menuItems: {
    flex: 1,
    paddingTop: theme.spacing.md,
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: theme.spacing.md,
    marginHorizontal: theme.spacing.sm,
    marginVertical: theme.spacing.xs,
    borderRadius: theme.borderRadius.md,
  },
  menuIcon: {
    fontSize: 24,
    marginRight: theme.spacing.md,
  },
  menuText: {
    ...theme.typography.body,
    color: theme.colors.text,
    fontWeight: '600',
  },
  footer: {
    borderTopWidth: 1,
    borderTopColor: theme.colors.border,
    padding: theme.spacing.md,
  },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: theme.spacing.md,
    backgroundColor: theme.colors.error,
    borderRadius: theme.borderRadius.md,
  },
  logoutIcon: {
    fontSize: 20,
    marginRight: theme.spacing.sm,
  },
  logoutText: {
    ...theme.typography.button,
    color: '#FFF',
  },
});

export default CustomDrawer;