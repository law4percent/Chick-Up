#!/bin/bash
# setup.sh - FULL Production Setup for Raspberry Pi OS 13 (Trixie)

set -e

echo "========================================="
echo " Chick-Up AI - FULL Raspberry Pi Setup "
echo "========================================="

# -----------------------------
# 0. INTERNET CHECK
# -----------------------------
echo "=== 0. Checking Internet ==="
if ping -c 2 8.8.8.8 > /dev/null 2>&1; then
    echo "✓ Internet OK"
else
    echo "✗ No internet. Aborting."
    exit 1
fi

# -----------------------------
# 1. SYSTEM UPDATE
# -----------------------------
echo "=== 1. Updating System ==="
sudo apt update
sudo apt upgrade -y

# -----------------------------
# 2. ENABLE I2C (LCD SUPPORT)
# -----------------------------
echo "=== 2. Enabling I2C Interface ==="
sudo raspi-config nonint do_i2c 0 || true
sudo apt install -y i2c-tools

# -----------------------------
# 3. INSTALL SYSTEM DEPENDENCIES
# -----------------------------
echo "=== 3. Installing System Dependencies ==="

sudo apt install -y \
    build-essential cmake git pkg-config \
    python3-dev python3-venv python3-pip \
    libjpeg-dev zlib1g-dev libtiff-dev libpng-dev \
    libavcodec-dev libavformat-dev libswscale-dev libavdevice-dev \
    libblas-dev liblapack-dev gfortran libopenblas-dev \
    libxvidcore-dev libx264-dev libboost-dev libdrm-dev \
    libusb-1.0-0-dev libv4l-dev libopus-dev libvpx-dev libssl-dev \
    libcamera-dev python3-libcamera python3-picamera2 \
    ffmpeg rpicam-apps

# -----------------------------
# 4. CREATE VENV
# -----------------------------
echo "=== 4. Creating Virtual Environment ==="

if [ -d "chick-up-env" ]; then
    echo "✓ Virtual environment exists."
else
    python3 -m venv --system-site-packages chick-up-env
    echo "✓ Virtual environment created."
fi

source chick-up-env/bin/activate

# -----------------------------
# 5. STABLE PIP CONFIG
# -----------------------------
echo "=== 5. Configuring Pip ==="

export PIP_DEFAULT_TIMEOUT=120
export PIP_RETRIES=5

pip install --upgrade pip setuptools wheel \
    --index-url https://pypi.org/simple \
    --no-cache-dir

# -----------------------------
# 6. SAFE INSTALL FUNCTION
# -----------------------------
safe_pip_install() {
    PACKAGE=$1
    echo "Installing $PACKAGE ..."
    for i in 1 2 3; do
        if pip install "$PACKAGE" --index-url https://pypi.org/simple --no-cache-dir; then
            echo "✓ $PACKAGE installed"
            return 0
        else
            echo "Retry $i failed for $PACKAGE"
            sleep 3
        fi
    done
    echo "✗ Failed to install $PACKAGE"
    exit 1
}

# -----------------------------
# 7. INSTALL PYTHON PACKAGES
# -----------------------------
echo "=== 7. Installing Python Stack ==="

safe_pip_install numpy
safe_pip_install smbus2
safe_pip_install "av>=10.0.0"
safe_pip_install "aiortc>=1.5.0"
safe_pip_install opencv-python-headless
safe_pip_install firebase-admin
safe_pip_install RPi.GPIO

# -----------------------------
# 8. CAMERA SYMLINK FIX
# -----------------------------
echo "=== 8. Linking Camera Modules ==="

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
SITE_PACKAGES="$VIRTUAL_ENV/lib/python$PYTHON_VERSION/site-packages"

ln -sf /usr/lib/python3/dist-packages/libcamera* "$SITE_PACKAGES/" || true
ln -sf /usr/lib/python3/dist-packages/picamera2* "$SITE_PACKAGES/" || true

# -----------------------------
# 9. GPIO PERMISSIONS FIX
# -----------------------------
echo "=== 9. Configuring GPIO Permissions ==="
sudo usermod -aG gpio $USER || true

# -----------------------------
# 10. VERIFY INSTALLATION
# -----------------------------
echo "=== 10. Verifying Installation ==="

echo "--- I2C Devices ---"
sudo i2cdetect -y 1 || echo "⚠ I2C bus check failed"

echo "--- Camera ---"
rpicam-hello --list-cameras || echo "⚠ No camera detected"

echo "--- Python Modules ---"
python3 -c "import RPi.GPIO; print('✓ GPIO OK')" || echo "✗ GPIO failed"
python3 -c "import smbus2; print('✓ smbus2 OK')" || echo "✗ smbus2 failed"
python3 -c "import cv2; print(f'✓ OpenCV {cv2.__version__}')" || echo "✗ OpenCV failed"
python3 -c "import aiortc; print(f'✓ aiortc {aiortc.__version__}')" || echo "✗ WebRTC failed"
python3 -c "import firebase_admin; print('✓ Firebase OK')" || echo "✗ Firebase failed"

echo "-----------------------------------------"
echo "✓ FULL Setup Complete!"
echo ""
echo "IMPORTANT:"
echo "Reboot required for I2C & GPIO group changes."
echo "Run: sudo reboot"
echo ""
echo "After reboot:"
echo "source chick-up-env/bin/activate"
echo "python main.py"
echo "-----------------------------------------"