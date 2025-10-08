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
import { LinearGradient } from 'expo-linear-gradient';
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

  const currentRoute = props.state.routes[props.state.index]?.name;

  const MenuItem = ({ icon, label, route }: { icon: string; label: string; route: string }) => {
    const isActive = currentRoute === route;
    
    if (isActive) {
      return (
        <TouchableOpacity
          style={styles.menuItem}
          onPress={() => props.navigation.navigate(route)}
        >
          <LinearGradient
            colors={['#FFD54F', '#4CAF50']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={styles.menuItemGradient}
          >
            <Text style={[styles.menuIcon, styles.menuIconActive]}>{icon}</Text>
            <Text style={[styles.menuText, styles.menuTextActive]}>{label}</Text>
          </LinearGradient>
        </TouchableOpacity>
      );
    }
    
    return (
      <TouchableOpacity
        style={styles.menuItem}
        onPress={() => props.navigation.navigate(route)}
      >
        <Text style={styles.menuIcon}>{icon}</Text>
        <Text style={styles.menuText}>{label}</Text>
      </TouchableOpacity>
    );
  };

  return (
    <View style={styles.container}>
      <DrawerContentScrollView {...props} contentContainerStyle={styles.scrollView}>
        <View style={styles.header}>
          <View style={styles.logoContainer}>
            <LinearGradient
                colors={['#FFD54F', '#4CAF50']}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 0 }}
                style={styles.logo}
              >
              <Text style={styles.logoEmoji}>🐣</Text>
            </LinearGradient>
            <TouchableOpacity style={styles.closeButton} onPress={() => props.navigation.closeDrawer()}>
              <Text style={styles.closeIcon}>✕</Text>
            </TouchableOpacity>
          </View>
          <Text style={styles.appName}>CHICK-UP</Text>
          <Text style={styles.tagline}>IoT Poultry System</Text>
        </View>
        
        <View style={styles.menuItems}>
          <MenuItem icon="📊" label="Dashboard" route="Dashboard" />
          <MenuItem icon="📝" label="Data Logging" route="DataLogging" />
          <MenuItem icon="👤" label="Profile" route="Profile" />
          <MenuItem icon="⚙️" label="Settings" route="Settings" />
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
    backgroundColor: '#FFFFFF',
  },
  scrollView: {
    flexGrow: 1,
  },
  header: {
    padding: theme.spacing.lg,
    paddingTop: theme.spacing.xl,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E5E5',
  },
  logoContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.md,
  },
  logo: {
    width: 50,
    height: 50,
    backgroundColor: '#8BC34A',
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  logoEmoji: {
    fontSize: 28,
  },
  closeButton: {
    width: 32,
    height: 32,
    justifyContent: 'center',
    alignItems: 'center',
  },
  closeIcon: {
    fontSize: 20,
    color: '#666',
  },
  appName: {
    fontSize: 18,
    fontWeight: '700',
    color: '#333',
    marginBottom: 2,
  },
  tagline: {
    fontSize: 12,
    color: '#999',
  },
  menuItems: {
    flex: 1,
    paddingTop: theme.spacing.lg,
    paddingHorizontal: theme.spacing.sm,
    gap: theme.spacing.sm
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 2,
    borderRadius: theme.borderRadius.lg,
    overflow: 'hidden',
    marginBottom: theme.spacing.sm
  },
  menuItemGradient: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: theme.spacing.md,
    paddingVertical: 14,
    width: '100%',
  },
  menuItemActive: {
    backgroundColor: '#8BC34A',
  },
  menuIcon: {
    fontSize: 20,
    marginRight: theme.spacing.md,
    width: 24,
    marginLeft: theme.spacing.md,
  },
  menuIconActive: {
    opacity: 1,
  },
  menuText: {
    fontSize: 15,
    color: '#666',
    fontWeight: '500',
  },
  menuTextActive: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
  footer: {
    borderTopWidth: 1,
    borderTopColor: '#E5E5E5',
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