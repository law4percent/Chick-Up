# 🐣 Chick-Up

A modern React Native mobile application built with Expo, TypeScript, and Firebase.

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![React Native](https://img.shields.io/badge/React%20Native-Expo-blue.svg)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-blue.svg)
![Firebase](https://img.shields.io/badge/Firebase-Realtime%20DB-orange.svg)

## 📱 Features

- ✅ **User Authentication** - Secure sign up and login with Firebase
- ✅ **Username-based Login** - Users login with username instead of email
- ✅ **Left-Side Drawer Navigation** - Smooth swipe gestures
- ✅ **Real-time Database** - Firebase Realtime Database integration
- ✅ **TypeScript** - Full type safety and better developer experience
- ✅ **Modern UI** - Yellow & Green themed design
- ✅ **Agile Ready** - Structured for iterative development

## 🛠️ Tech Stack

- **Framework**: React Native (Expo)
- **Language**: TypeScript
- **Navigation**: React Navigation (Drawer + Stack)
- **Backend**: Firebase (Authentication + Realtime Database)
- **State Management**: React Hooks
- **Storage**: AsyncStorage (for auth persistence)

## 📋 Prerequisites

- Node.js (v18 or higher)
- npm or yarn
- Expo Go app (for testing on physical device)
- Android Studio (for emulator) or Xcode (for iOS)
- Firebase account

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/chick-up.git
cd chick-up
```

### 2. Install Dependencies

```bash
npm install
```

### 3. Configure Environment

Create a `.env` file in the root directory:

```bash
cp .env.example .env
```

The `.env` file should contain (already pre-configured):

```env
EXPO_PUBLIC_FIREBASE_API_KEY=your_api_key
EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN=your_auth_domain
EXPO_PUBLIC_FIREBASE_DATABASE_URL=your_database_url
EXPO_PUBLIC_FIREBASE_PROJECT_ID=your_project_id
EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET=your_storage_bucket
EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
EXPO_PUBLIC_FIREBASE_APP_ID=your_app_id
```

### 4. Set Up Firebase

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Open project: **chick-up-1c2df**
3. Enable **Authentication** → Email/Password
4. Create **Realtime Database** → Set rules (see below)

**Database Rules:**

```json
{
  "rules": {
    "users": {
      "$uid": {
        ".read": "$uid === auth.uid",
        ".write": "$uid === auth.uid"
      }
    },
    "usernames": {
      ".read": "auth != null",
      "$username": {
        ".write": "!data.exists() && auth != null"
      }
    }
  }
}
```

### 5. Run the App

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

## 📁 Project Structure

```
Chick-Up/
├── .env                    # Environment variables (not committed)
├── .env.example            # Environment template
├── google-services.json    # Android Firebase config
├── env.d.ts               # TypeScript env definitions
├── App.tsx                # Main entry point
├── app.json               # Expo configuration
│
└── src/
    ├── config/
    │   ├── firebase.config.ts    # Firebase initialization
    │   └── theme.ts              # App theme
    ├── types/
    │   └── types.ts              # TypeScript types
    ├── services/
    │   └── authService.ts        # Auth logic
    ├── components/
    │   └── CustomDrawer.tsx      # Navigation drawer
    ├── screens/
    │   ├── SignUpScreen.tsx      # Registration
    │   ├── LoginScreen.tsx       # Login
    │   └── DashboardScreen.tsx   # Main screen
    └── navigation/
        └── Navigation.tsx        # App navigation
```

## 🎨 Theme

The app uses a yellow and green color scheme:

- **Primary**: `#FFD700` (Yellow)
- **Secondary**: `#4CAF50` (Green)

Customize colors in `src/config/theme.ts`.

## 🔐 Authentication Flow

1. **Sign Up**: User creates account with username, email, phone, and password
2. **Redirect**: After successful registration, redirects to Login
3. **Login**: User logs in with username and password
4. **Dashboard**: After login, redirects to main Dashboard

## 📱 Navigation

- **Left Drawer**: Swipe right from left edge to open
- **Menu Items**: Dashboard, Profile, Settings
- **Logout**: Available in drawer footer

## 🧪 Testing

### Test Account

```
Username: testuser
Phone: +639123456789
Email: test@example.com
Password: test123456
```

### Test Scenarios

1. **Sign Up Flow**
   - Navigate to Sign Up
   - Fill in all fields
   - Submit and verify redirect to Login

2. **Login Flow**
   - Enter credentials
   - Verify redirect to Dashboard

3. **Navigation**
   - Swipe right to open drawer
   - Test menu navigation
   - Test logout

## 🏗️ Building for Production

### Android

```bash
# Install EAS CLI
npm install -g eas-cli

# Login to Expo
eas login

# Configure EAS
eas build:configure

# Build APK (for testing)
eas build --platform android --profile preview

# Build AAB (for Play Store)
eas build --platform android --profile production
```

### iOS (Mac only)

```bash
eas build --platform ios --profile production
```

## 🔧 Development

### Available Scripts

```bash
# Start development server
npm start

# Run on Android
npm run android

# Run on iOS
npm run ios

# Run on web
npm run web

# Type checking
npm run tsc

# Clear cache
npx expo start --clear
```

### Code Style

- Use TypeScript for all new files
- Follow functional component pattern
- Use hooks for state management
- Keep components small and focused

## 🐛 Troubleshooting

### Firebase Connection Issues
```bash
# Verify .env file exists and has correct values
# Restart Expo with cleared cache
npx expo start --clear
```

### Gesture Handler Not Working
```bash
# Ensure proper import order in App.tsx
import 'react-native-gesture-handler';
```

### Environment Variables Not Loading
```bash
# Restart Expo after changing .env
npx expo start --clear
```

## 📚 Documentation

- [Expo Documentation](https://docs.expo.dev/)
- [React Navigation](https://reactnavigation.org/)
- [Firebase Documentation](https://firebase.google.com/docs)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License.

## 👨‍💻 Author

**Mr. iTnology**
- Package: `com.mr_itnology.chick_up`
- Firebase Project: `chick-up-1c2df`

## 🙏 Acknowledgments

- Expo team for the amazing framework
- Firebase for backend services
- React Navigation for routing
- The React Native community

---

**Built with ❤️ using React Native & Expo**