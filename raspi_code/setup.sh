#!/bin/bash
# setup.sh - Optimized for Debian Trixie (Raspberry Pi OS 13)

# Exit immediately if a command exits with a non-zero status
set -e

echo "=== 1. Updating System Packages ==="
sudo apt update && sudo apt upgrade -y

echo "=== 2. Installing System Dependencies ==="
# Note: libatlas-base-dev is replaced by libopenblas-dev in Trixie
sudo apt install -y build-essential cmake git pkg-config \
    python3-dev python3-venv python3-pip \
    libjpeg-dev zlib1g-dev libtiff-dev libpng-dev \
    libavcodec-dev libavformat-dev libswscale-dev libavdevice-dev \
    libblas-dev liblapack-dev gfortran libopenblas-dev \
    libxvidcore-dev libx264-dev libboost-dev libdrm-dev \
    libusb-1.0-0-dev libv4l-dev libopus-dev libvpx-dev libssl-dev \
    libcamera-dev python3-libcamera python3-picamera2 ffmpeg

echo "=== 3. Creating Virtual Environment ==="
# --system-site-packages allows the venv to see the global libcamera/picamera2
if [ -d "webrtc-env" ]; then
    echo "Virtual environment already exists."
else
    python3 -m venv --system-site-packages webrtc-env
    echo "Virtual environment created."
fi

# Activate environment
source webrtc-env/bin/activate

echo "=== 4. Upgrading Pip and Core Tools ==="
pip install --upgrade pip setuptools wheel

echo "=== 5. Installing Python Stack ==="
# We install these one by one to ensure clear error tracking
pip install numpy
pip install "av>=10.0.0" "aiortc>=1.5.0"
pip install opencv-python-headless firebase-admin RPi.GPIO

echo "=== 6. Fixing Symlinks (Trixie/PiOS Specific) ==="
# This manually ensures the venv can 'see' the camera bindings if system-site-packages fails
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
SITE_PACKAGES="$VIRTUAL_ENV/lib/python$PYTHON_VERSION/site-packages"

echo "Linking system camera modules to $SITE_PACKAGES..."
ln -sf /usr/lib/python3/dist-packages/libcamera* "$SITE_PACKAGES/"
ln -sf /usr/lib/python3/dist-packages/picamera2* "$SITE_PACKAGES/"

echo "=== 7. Verifying Hardware & Software ==="
echo "--- Camera Check ---"
if command -v rpicam-hello &> /dev/null; then
    rpicam-hello --list-cameras || echo "Warning: No camera found on CSI port."
else
    echo "rpicam-apps not found. Running: sudo apt install rpicam-apps"
    sudo apt install -y rpicam-apps
fi

echo "--- Module Check ---"
python3 -c "import libcamera; import picamera2; print('? libcamera/picamera2: OK')" || echo "? Camera import failed"
python3 -c "import cv2; print(f'? OpenCV: {cv2.__version__}')" || echo "? OpenCV failed"
python3 -c "import aiortc; print(f'? aiortc: {aiortc.__version__}')" || echo "? WebRTC failed"

echo "---"
echo "=== Setup Complete! ==="
echo "Run your code with:"
echo "source webrtc-env/bin/activate"
echo "python main.py"