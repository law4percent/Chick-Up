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

echo "[4a/6] Creating and starting pigpio daemon service..."
sudo bash -c 'cat > /etc/systemd/system/pigpiod.service <<EOF
[Unit]
Description=Daemon required to control GPIO pins via pigpio
After=network.target

[Service]
ExecStart=/usr/local/bin/pigpiod
ExecStop=/bin/kill -s SIGTERM $MAINPID
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF'

sudo systemctl daemon-reload
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
echo "pigpiod service is active ✅"

echo "[5/6] Installing Python packages..."
if [ -f "requirements.txt" ]; then
    echo "Cleaning requirements.txt (removing opencv-python)..."
    grep -v '^opencv-python' requirements.txt > /tmp/req_clean.txt
    sudo pip3 install -r /tmp/req_clean.txt --break-system-packages
else
    echo "No requirements.txt found — skipping Python package installation."
fi

echo "[6/6] Setup complete! Reboot recommended."

read -p "Reboot now? (y/n): " answer
if [ "$answer" = "y" ]; then
    sudo reboot
fi
