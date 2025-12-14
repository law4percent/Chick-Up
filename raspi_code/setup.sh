#!/bin/bash

echo "==== Raspberry Pi Camera Project Setup ===="

echo "[1/6] Updating system packages..."
sudo apt update && sudo apt full-upgrade -y

echo "[2/6] Enabling camera interface (libcamera)..."
sudo raspi-config nonint do_camera 0

echo "[3/6] Installing required system packages..."
sudo apt install -y \
    python3-picamera2 \
    python3-libcamera \
    python3-opencv \
    python3-pip \
    git \
    build-essential

echo "[4/6] Installing pigpio from source..."
cd /tmp
if [ -d "pigpio" ]; then
    sudo rm -rf pigpio
fi
git clone https://github.com/joan2937/pigpio.git
cd pigpio
make
sudo make install

echo "[4a/6] Enabling and starting pigpio daemon..."
sudo systemctl enable pigpiod
sudo systemctl start pigpiod

echo "[5/6] Installing Python packages..."
if [ ! -f "requirements.txt" ]; then
    echo "ERROR: requirements.txt not found!"
    exit 1
fi

# Block pip from installing an x86 OpenCV wheel on ARM
echo "Cleaning requirements.txt (removing opencv-python)..."
grep -v '^opencv-python' requirements.txt > /tmp/req_clean.txt

sudo pip3 install -r /tmp/req_clean.txt --break-system-packages

echo "[6/6] Setup complete! Reboot required."

read -p "Reboot now? (y/n): " answer
if [ "$answer" = "y" ]; then
    sudo reboot
fi
