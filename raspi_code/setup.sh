#!/bin/bash
# setup.sh - Production Optimized for Raspberry Pi OS 13 (Trixie)

set -e

echo "========================================="
echo " Chick-Up AI - Raspberry Pi Setup Script "
echo "========================================="

# -----------------------------
# 0. NETWORK CHECK
# -----------------------------
echo "=== 0. Checking Internet Connection ==="
if ping -c 2 8.8.8.8 > /dev/null 2>&1; then
    echo "✓ Internet connection OK"
else
    echo "✗ No internet connection detected. Aborting."
    exit 1
fi

# -----------------------------
# 1. UPDATE SYSTEM
# -----------------------------
echo "=== 1. Updating System Packages ==="
sudo apt update
sudo apt upgrade -y

# -----------------------------
# 2. INSTALL SYSTEM DEPENDENCIES
# -----------------------------
echo "=== 2. Installing System Dependencies ==="

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
# 3. CREATE VIRTUAL ENVIRONMENT
# -----------------------------
echo "=== 3. Creating Virtual Environment ==="

if [ -d "chick-up-env" ]; then
    echo "✓ Virtual environment already exists."
else
    python3 -m venv --system-site-packages chick-up-env
    echo "✓ Virtual environment created."
fi

source chick-up-env/bin/activate

# -----------------------------
# 4. PIP CONFIGURATION (FIXES TIMEOUT ISSUE)
# -----------------------------
echo "=== 4. Configuring Pip (Stable Mode) ==="

export PIP_DEFAULT_TIMEOUT=120
export PIP_RETRIES=5

pip install --upgrade pip setuptools wheel \
    --index-url https://pypi.org/simple \
    --no-cache-dir

# -----------------------------
# 5. SAFE INSTALL FUNCTION (WITH RETRY)
# -----------------------------
safe_pip_install() {
    PACKAGE=$1
    echo "Installing $PACKAGE ..."
    for i in 1 2 3; do
        if pip install "$PACKAGE" --index-url https://pypi.org/simple --no-cache-dir; then
            echo "✓ $PACKAGE installed successfully"
            return 0
        else
            echo "Retry $i failed for $PACKAGE. Retrying..."
            sleep 3
        fi
    done
    echo "✗ Failed to install $PACKAGE after retries."
    exit 1
}

# -----------------------------
# 6. INSTALL PYTHON STACK
# -----------------------------
echo "=== 6. Installing Python Stack ==="

safe_pip_install numpy
safe_pip_install "av>=10.0.0"
safe_pip_install "aiortc>=1.5.0"
safe_pip_install opencv-python-headless
safe_pip_install firebase-admin
safe_pip_install RPi.GPIO

# -----------------------------
# 7. FIX CAMERA SYMLINK (TRIXIE SPECIFIC)
# -----------------------------
echo "=== 7. Linking Camera Modules ==="

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
SITE_PACKAGES="$VIRTUAL_ENV/lib/python$PYTHON_VERSION/site-packages"

ln -sf /usr/lib/python3/dist-packages/libcamera* "$SITE_PACKAGES/" || true
ln -sf /usr/lib/python3/dist-packages/picamera2* "$SITE_PACKAGES/" || true

echo "✓ Camera modules linked"

# -----------------------------
# 8. VERIFY INSTALLATION
# -----------------------------
echo "=== 8. Verifying Hardware & Software ==="

echo "--- Camera Check ---"
rpicam-hello --list-cameras || echo "⚠ No camera detected."

echo "--- Python Module Check ---"
python3 -c "import libcamera; import picamera2; print('✓ libcamera/picamera2 OK')" || echo "✗ Camera import failed"
python3 -c "import cv2; print(f'✓ OpenCV {cv2.__version__}')" || echo "✗ OpenCV failed"
python3 -c "import aiortc; print(f'✓ aiortc {aiortc.__version__}')" || echo "✗ WebRTC failed"
python3 -c "import firebase_admin; print('✓ Firebase Admin OK')" || echo "✗ Firebase failed"

echo "-----------------------------------------"
echo "✓ Setup Complete!"
echo ""
echo "To activate environment:"
echo "source chick-up-env/bin/activate"
echo ""
echo "Then run:"
echo "python main.py"
echo "-----------------------------------------"