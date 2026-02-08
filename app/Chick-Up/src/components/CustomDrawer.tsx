// src/components/CustomDrawer.tsx
import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
  Platform,
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

  const MenuItem = ({
    icon,
    label,
    route,
  }: {
    icon: string;
    label: string;
    route: string;
  }) => {
    const isActive = currentRoute === route;

    return (
      <TouchableOpacity
        style={styles.menuItem}
        activeOpacity={isActive ? 1 : 0.6}
        onPress={() => props.navigation.navigate(route)}
      >
        {isActive ? (
          <LinearGradient
            colors={['#8BC34A', '#66BB6A']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={styles.menuItemInner}
          >
            <Text style={styles.menuIconActive}>{icon}</Text>
            <Text style={[styles.menuText, styles.menuTextActive]}>{label}</Text>
          </LinearGradient>
        ) : (
          <View style={styles.menuItemInner}>
            <Text style={styles.menuIcon}>{icon}</Text>
            <Text style={styles.menuText}>{label}</Text>
          </View>
        )}
      </TouchableOpacity>
    );
  };

  return (
    <View style={styles.container}>
      <DrawerContentScrollView {...props} contentContainerStyle={styles.scrollView}>
        {/* Header */}
        <View style={styles.header}>
          <View style={styles.headerTopRow}>
            <TouchableOpacity
              style={styles.closeButton}
              onPress={() => props.navigation.closeDrawer()}
              activeOpacity={0.5}
            >
              <Text style={styles.closeIcon}>✕</Text>
            </TouchableOpacity>
          </View>
          <Text style={styles.appName}>Chick-Up</Text>
          <Text style={styles.tagline}>Smart Poultry Management</Text>
        </View>

        {/* Divider */}
        <View style={styles.divider} />

        {/* Menu */}
        <View style={styles.menuItems}>
          <MenuItem icon="📊" label="Dashboard" route="Dashboard" />
          <MenuItem icon="📅" label="Schedule" route="Schedule" />
          <MenuItem icon="📈" label="Analytics" route="Analytics" />
          <MenuItem icon="⚙️" label="Settings" route="Settings" />
          <MenuItem icon="👤" label="Profile" route="Profile" />
        </View>
      </DrawerContentScrollView>

      {/* Footer */}
      <View style={styles.footer}>
        <TouchableOpacity
          style={styles.logoutButton}
          onPress={handleLogout}
          activeOpacity={0.7}
        >
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
    backgroundColor: '#FAFAFA',
  },
  scrollView: {
    flexGrow: 1,
  },

  // ─── Header ──────────────────────────────────────────────
  header: {
    paddingHorizontal: 24,
    paddingTop: Platform.OS === 'ios' ? 60 : 48,
    paddingBottom: 20,
    backgroundColor: '#FFFFFF',
  },
  headerTopRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    alignItems: 'center',
    marginBottom: 16,
  },
  closeButton: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: '#F0F0F0',
    justifyContent: 'center',
    alignItems: 'center',
  },
  closeIcon: {
    fontSize: 16,
    color: '#888',
  },
  appName: {
    fontSize: 20,
    fontWeight: '700',
    color: '#1A1A1A',
    letterSpacing: 0.3,
  },
  tagline: {
    fontSize: 12,
    color: '#999',
    marginTop: 2,
    fontWeight: '500',
  },

  // ─── Divider ─────────────────────────────────────────────
  divider: {
    height: 1,
    backgroundColor: '#ECECEC',
    marginHorizontal: 20,
  },

  // ─── Menu ────────────────────────────────────────────────
  menuItems: {
    paddingTop: 12,
    paddingHorizontal: 12,
    gap: 4,
  },
  menuItem: {
    borderRadius: 12,
    overflow: 'hidden',
  },
  menuItemInner: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 13,
    paddingHorizontal: 16,
  },
  menuIcon: {
    fontSize: 18,
    marginRight: 14,
    width: 22,
    textAlign: 'center',
    opacity: 0.7,
  },
  menuIconActive: {
    fontSize: 18,
    marginRight: 14,
    width: 22,
    textAlign: 'center',
  },
  menuText: {
    fontSize: 15,
    color: '#555',
    fontWeight: '500',
  },
  menuTextActive: {
    color: '#FFFFFF',
    fontWeight: '600',
  },

  // ─── Footer ──────────────────────────────────────────────
  footer: {
    borderTopWidth: 1,
    borderTopColor: '#ECECEC',
    padding: 16,
    backgroundColor: '#FAFAFA',
  },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 13,
    borderRadius: 12,
    backgroundColor: '#FFF0F0',
    borderWidth: 1,
    borderColor: '#FFCDD2',
  },
  logoutIcon: {
    fontSize: 18,
    marginRight: 8,
  },
  logoutText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#E53935',
  },
});

export default CustomDrawer;