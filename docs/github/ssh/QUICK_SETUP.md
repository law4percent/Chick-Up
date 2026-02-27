# 🚀 Chick-Up - Quick Start Guide

## ⚡ Fast Setup (5 Minutes)

### 0️⃣ Set Up SSH (First Time Only - Highly Recommended)

**Why SSH?** No password prompts when pushing code!

**MacBook:**
```bash
ssh-keygen -t ed25519 -C "lawrence7roble@gmail.com"
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
cat ~/.ssh/id_ed25519.pub  # Copy this
```

**Windows:**
```bash
ssh-keygen -t ed25519 -C "lawrence7roble@gmail.com"
eval "$(ssh-agent -s)"  # Git Bash
ssh-add ~/.ssh/id_ed25519
cat ~/.ssh/id_ed25519.pub  # Copy this
```

**Add to GitHub:**
1. Go to: https://github.com/settings/keys
2. Click "New SSH key"
3. Title: "MacBook Office" or "Windows PC Home"
4. Paste key → Add

**Test:**
```bash
ssh -T git@github.com
# Should say: "Hi law4percent! ..."
```

See **SSH Setup Guide** for detailed instructions.

### 1️⃣ Create Project

```bash
# Using SSH (recommended):
git clone git@github.com:law4percent/Chick-Up.git
cd Chick-Up

# Or using HTTPS:
# git clone https://github.com/law4percent/Chick-Up.git
# cd Chick-Up
```

---

## 🔒 Security Checklist

- [ ] `.env` file created (DO NOT commit!)
- [ ] `.gitignore` includes `.env`
- [ ] Firebase Authentication enabled
- [ ] Database rules set properly
- [ ] `google-services.json` in root

---

## 💡 Pro Tips

### Development
```bash
# Use Expo Go app on your phone for quick testing
# Download from Play Store: "Expo Go"
# Scan QR code from terminal

# Or use Android emulator
npx expo start --android
```

### Environment Variables
```bash
# Access in code:
process.env.EXPO_PUBLIC_YOUR_VAR

# Must start with EXPO_PUBLIC_ to be accessible in app
# Private keys (without EXPO_PUBLIC_) only work in Node.js/server code
```

### Git Workflow
```bash
# Initialize git (if not done)
git init

# First commit
git add .
git commit -m "Initial Chick-Up setup with Firebase"

# Create repository on GitHub
# Then push
git remote add origin your-repo-url
git push -u origin main
```

---

## 🚀 Ready to Build!

Your Chick-Up project is fully configured and ready to go!