// src/screens/DashboardScreen.tsx
import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { DrawerNavigationProp } from '@react-navigation/drawer';
import { MainDrawerParamList } from '../types/types';
import { theme } from '../config/theme';
import { auth } from '../config/firebase.config';

type DashboardScreenNavigationProp = DrawerNavigationProp<MainDrawerParamList, 'Dashboard'>;

interface Props {
  navigation: DashboardScreenNavigationProp;
}

const DashboardScreen: React.FC<Props> = ({ navigation }) => {
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity
          style={styles.menuButton}
          onPress={() => navigation.openDrawer()}
        >
          <Text style={styles.menuIcon}>☰</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Dashboard</Text>
      </View>

      <View style={styles.content}>
        <View style={styles.welcomeCard}>
          <Text style={styles.welcomeTitle}>Welcome to Chick-Up! 🐣</Text>
          <Text style={styles.welcomeText}>
            Your dashboard is ready. Swipe right from the left edge to open the navigation menu.
          </Text>
        </View>

        <View style={styles.infoCard}>
          <Text style={styles.infoTitle}>Quick Info</Text>
          <Text style={styles.infoText}>User: {auth.currentUser?.email}</Text>
          <Text style={styles.infoText}>Status: Active</Text>
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: theme.spacing.md,
    backgroundColor: theme.colors.primary,
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
  },
  menuButton: {
    padding: theme.spacing.sm,
  },
  menuIcon: {
    fontSize: 24,
    color: '#FFF',
  },
  headerTitle: {
    ...theme.typography.h2,
    color: '#FFF',
    marginLeft: theme.spacing.md,
  },
  content: {
    flex: 1,
    padding: theme.spacing.lg,
  },
  welcomeCard: {
    backgroundColor: theme.colors.secondary,
    borderRadius: theme.borderRadius.lg,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.md,
  },
  welcomeTitle: {
    ...theme.typography.h2,
    color: '#FFF',
    marginBottom: theme.spacing.sm,
  },
  welcomeText: {
    ...theme.typography.body,
    color: '#FFF',
    opacity: 0.9,
  },
  infoCard: {
    backgroundColor: theme.colors.surface,
    borderRadius: theme.borderRadius.lg,
    padding: theme.spacing.lg,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  infoTitle: {
    ...theme.typography.h3,
    color: theme.colors.text,
    marginBottom: theme.spacing.md,
  },
  infoText: {
    ...theme.typography.body,
    color: theme.colors.textSecondary,
    marginBottom: theme.spacing.sm,
  },
});

export default DashboardScreen;