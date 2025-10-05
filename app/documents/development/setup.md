# Chick-Up - Complete Setup Guide

## 📋 Prerequisites

- Node.js (v18 or higher recommended)
- npm or yarn
- Android Studio (for Android emulator) or physical Android device
- Firebase account

**Note**: No need to install `expo-cli` globally! We'll use `npx` commands instead.

---

## 🚀 Step-by-Step Setup

### 1. Create Expo Project

```bash
npx create-expo-app@latest Chick-Up --template blank-typescript
cd Chick-Up
```

### 2. Install Dependencies

```bash
# Firebase
npm install firebase

# Navigation
npm install @react-navigation/native @react-navigation/drawer @react-navigation/native-stack

# Expo dependencies for navigation
npx expo install react-native-gesture-handler react-native-reanimated react-native-screens react-native-safe-area-context

# AsyncStorage for auth persistence
npm install @react-native-async-storage/async-storage
```

### 3. Configure Firebase

#### 3.1 Create Firebase Project
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Add Project"
3. Enter project name: "Chick-Up"
4. Follow the setup wizard

#### 3.2 Enable Authentication
1. In Firebase Console, go to **Authentication**
2. Click "Get Started"
3. Enable **Email/Password** sign-in method

#### 3.3 Create Realtime Database
1. In Firebase Console, go to **Realtime Database**
2. Click "Create Database"
3. Choose location (preferably closest to your users)
4. Start in **Test Mode** (we'll set rules later)

#### 3.4 Get Firebase Config
1. Go to **Project Settings** (gear icon)
2. Scroll to "Your apps" section
3. Click the web icon (`</>`)
4. Register app with nickname "Chick-Up"
5. Copy the `firebaseConfig` object

#### 3.5 Update firebase.config.ts
Replace the placeholder config in `src/config/firebase.config.ts` with your actual Firebase configuration.

#### 3.6 Set Database Rules
1. Go to **Realtime Database → Rules**
2. Paste the rules from the "Firebase Realtime Database Structure" artifact
3. Click **Publish**

### 4. Create Project Structure

Create the following directory structure:

```bash
mkdir -p src/config src/types src/services src/components src/screens src/navigation
```

### 5. Add All Source Files

Copy all the code from the artifacts into their respective files:

- `src/config/firebase.config.ts`
- `src/config/theme.ts`
- `src/types/types.ts`
- `src/services/authService.ts`
- `src/components/CustomDrawer.tsx`
- `src/screens/SignUpScreen.tsx`
- `src/screens/LoginScreen.tsx`
- `src/screens/DashboardScreen.tsx`
- `src/navigation/Navigation.tsx`
- `App.tsx` (replace existing)

### 6. Configure babel.config.js

Update `babel.config.js` to include Reanimated plugin:

```javascript
module.exports = function(api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    plugins: ['react-native-reanimated/plugin'],
  };
};
```

### 7. Update app.json

Add the following configuration:

```json
{
  "expo": {
    "name": "Chick-Up",
    "slug": "chick-up",
    "version": "1.0.0",
    "orientation": "portrait",
    "icon": "./assets/icon.png",
    "userInterfaceStyle": "light",
    "splash": {
      "image": "./assets/splash.png",
      "resizeMode": "contain",
      "backgroundColor": "#FFD700"
    },
    "assetBundlePatterns": [
      "**/*"
    ],
    "ios": {
      "supportsTablet": true
    },
    "android": {
      "adaptiveIcon": {
        "foregroundImage": "./assets/adaptive-icon.png",
        "backgroundColor": "#FFD700"
      },
      "package": "com.yourcompany.chickup"
    },
    "web": {
      "favicon": "./assets/favicon.png"
    }
  }
}
```

### 8. Run the App

**Important**: Use `npx expo` commands (not global `expo-cli`)

```bash
# Start Expo development server
npx expo start

# Run on Android
npx expo start --android

# Run on iOS (Mac only)
npx expo start --ios

# Clear cache if needed
npx expo start --clear
```

**Why `npx`?**
- Always uses the latest Expo version
- No global dependencies to manage
- Cleaner, more reliable development experience
- Official Expo recommendation (global `expo-cli` is deprecated)

---

## ✅ Testing the App

### Test Sign Up Flow
1. Open the app
2. Click "Sign Up"
3. Fill in the form:
   - Username: testuser
   - Phone: +1234567890
   - Email: test@example.com
   - Password: test123456
4. Click "Sign Up"
5. You should see success message and be redirected to Login

### Test Login Flow
1. Enter username: testuser
2. Enter password: test123456
3. Click "Login"
4. You should be redirected to Dashboard

### Test Navigation
1. On Dashboard, swipe right from the left edge
2. Drawer should open
3. Tap menu items to navigate
4. Swipe left or tap outside to close drawer
5. Test logout functionality

---

## 🔧 Troubleshooting

### Firebase Connection Issues
- Double-check your Firebase config credentials
- Ensure Authentication and Realtime Database are enabled
- Check Firebase Console for any errors

### Navigation Gestures Not Working
- Make sure `react-native-gesture-handler` is imported in `App.tsx`
- Wrap app with `<GestureHandlerRootView>`
- Clear cache: `npx expo start --clear`

### TypeScript Errors
- Run `npm install` to ensure all dependencies are installed
- Check that all import paths are correct
- Restart TypeScript server in your IDE

### Build Errors
```bash
# Clear cache and reinstall
rm -rf node_modules
npm install
npx expo start --clear
```

---

## 📱 Building for Production

### Android APK/AAB

**Using EAS Build (Recommended)**

```bash
# Install EAS CLI globally (this one is OK to install globally)
npm install -g eas-cli

# Login to Expo account (create one if needed at expo.dev)
eas login

# Configure EAS for your project
eas build:configure

# Build development/preview APK (for testing)
eas build --platform android --profile preview

# Build production AAB (for Google Play Store)
eas build --platform android --profile production
```

**Alternative: Local Build (Classic)**

```bash
# For local builds, you need Android Studio configured
npx expo prebuild
npx expo run:android --variant release
```

**Note**: EAS Build is cloud-based and handles all the complex Android/iOS build configuration for you.

---

## 🎨 Customization Tips

### Change Theme Colors
Edit `src/config/theme.ts`:
```typescript
primary: '#YOUR_YELLOW_HEX',
secondary: '#YOUR_GREEN_HEX',
```

### Add New Screens
1. Create screen file in `src/screens/`
2. Add to navigation in `src/navigation/Navigation.tsx`
3. Add menu item in `src/components/CustomDrawer.tsx`

### Modify Database Structure
1. Update types in `src/types/types.ts`
2. Update service methods in `src/services/authService.ts`
3. Update Firebase rules if needed

---

## 📚 Next Steps

1. **Add Profile Screen** - Display and edit user information
2. **Add Settings Screen** - App preferences and configuration
3. **Implement Features** - Add your core app functionality
4. **Add Loading States** - Improve UX with skeleton loaders
5. **Error Handling** - More robust error handling and validation
6. **Push Notifications** - Using Firebase Cloud Messaging
7. **Offline Support** - Handle offline scenarios gracefully

---

## 💡 Modern Expo Workflow (2024+)

### Why No Global `expo-cli`?

**🚫 Old Way (Deprecated)**
```bash
npm install -g expo-cli  # DON'T DO THIS
expo start
```

**✅ New Way (Official)**
```bash
npx expo start  # Always up-to-date
```

### Key Benefits

1. **Always Latest Version** - `npx` fetches the newest Expo tools automatically
2. **No Version Conflicts** - Each project uses its own Expo version
3. **Cleaner System** - No global dependencies cluttering your machine
4. **Official Standard** - Recommended by Expo team since 2022

### Common Commands

```bash
# Create new project
npx create-expo-app@latest my-app

# Start development server
npx expo start

# Install packages
npx expo install package-name

# Update dependencies
npx expo install --fix

# Run on specific platform
npx expo start --android
npx expo start --ios

# Clear cache
npx expo start --clear

# Check for updates
npx expo-doctor
```

### Developer Tools

```bash
# Expo Go app for testing (on your phone)
# Download from Play Store or App Store

# Press in terminal while expo is running:
# a - run on Android
# i - run on iOS
# w - run on web
# r - reload app
# m - toggle menu
```

---

## 🐛 Known Issues & Solutions

**Issue**: Drawer doesn't open on swipe
- **Solution**: Ensure `swipeEnabled: true` in drawer options

**Issue**: Firebase auth persistence not working
- **Solution**: Check AsyncStorage is properly installed and linked

**Issue**: Username already taken but no user exists
- **Solution**: Manually check/clean the `usernames` node in Firebase Console

---

Good luck with your Chick-Up project! 🐣✨