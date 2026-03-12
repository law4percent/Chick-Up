# Chick-Up — Auto-Run on Boot

This guide explains how to configure the Raspberry Pi so `main.py` starts
automatically every time the Pi powers on, with no manual SSH or terminal
intervention required.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Method: systemd Service (Recommended)](#2-method-systemd-service-recommended)
   - 2.1 [Why systemd](#21-why-systemd)
   - 2.2 [Create the Service File](#22-create-the-service-file)
   - 2.3 [Enable and Start](#23-enable-and-start)
   - 2.4 [Verify It Is Running](#24-verify-it-is-running)
3. [Checking Logs](#3-checking-logs)
4. [Updating the Code](#4-updating-the-code)
5. [Temporarily Stopping the Service](#5-temporarily-stopping-the-service)
6. [Permanently Disabling Auto-Run](#6-permanently-disabling-auto-run)
7. [Troubleshooting](#7-troubleshooting)
8. [Appendix: Full Service File Reference](#8-appendix-full-service-file-reference)

---

## 1. Prerequisites

Before setting up auto-run, confirm all of the following are true:

```bash
# 1. Python 3 is available
python3 --version          # should print Python 3.9 or higher

# 2. The project runs manually without errors
cd /home/pi/chick-up
python3 main.py            # should show LCD init, not crash

# 3. All dependencies are installed
pip3 list | grep -E "firebase|RPi|aiortc|python-dotenv"

# 4. credentials/.env exists and is filled in
cat credentials/.env       # should show DEVICE_UID, FIREBASE_DATABASE_URL etc.

# 5. credentials/serviceAccountKey.json exists
ls credentials/serviceAccountKey.json
```

Do not proceed until `python3 main.py` works correctly from the terminal.
Auto-run cannot fix configuration or dependency problems — it will just
fail silently on every boot instead.

---

## 2. Method: systemd Service (Recommended)

### 2.1 Why systemd

systemd is the standard init system on Raspberry Pi OS (Bullseye and Bookworm).
It gives you:

- **Automatic restart** if `main.py` crashes
- **Boot ordering control** — waits for networking before starting
- **Logging** — all stdout/stderr captured in `journalctl`
- **Clean stop** — sends SIGTERM so GPIO cleanup runs properly
- **Easy management** — start, stop, restart, status with one command

### 2.2 Create the Service File

Open a new service file with nano:

```bash
sudo nano /etc/systemd/system/chickup.service
```

Paste the following content exactly. **Read the comments** and adjust the
two paths marked with `← CHANGE THIS` if your project is not in
`/home/pi/chick-up`:

```ini
[Unit]
Description=Chick-Up Poultry Automation System
# Wait for the network stack to be up before starting.
# This is required because Firebase and TURN connections need internet.
After=network-online.target pigpiod.service
Wants=network-online.target

[Service]
# ── Identity ──────────────────────────────────────────────────────────────────
# Run as the pi user so GPIO, I2C, and the camera are accessible.
# If your username is not "pi", change both lines below.
User=chick-up2025
Group=chick-up2025

# ── Paths ─────────────────────────────────────────────────────────────────────
# WorkingDirectory must be the project root — main.py uses relative paths
# like credentials/.env and credentials/serviceAccountKey.json.
WorkingDirectory=/home/chick-up2025/Desktop/Chick-Up/raspi_code

# Full path to python3 and main.py.
ExecStart=/home/chick-up2025/Desktop/Chick-Up/raspi_code/chick-up-env/bin/python /home/chick-up2025/Desktop/Chick-Up/raspi_code/main.py

# ── Restart policy ────────────────────────────────────────────────────────────
# Restart on any non-zero exit code (crash) but NOT on clean exit (code 0).
# main.py exits with code 0 on clean shutdown (Shutdown menu or KeyboardInterrupt).
Restart=on-failure
RestartSec=5

# ── Output ────────────────────────────────────────────────────────────────────
# Send all stdout/stderr to the systemd journal (viewable with journalctl).
StandardOutput=journal
StandardError=journal

# ── GPIO cleanup ──────────────────────────────────────────────────────────────
# Give main.py up to 10 seconds to call GPIO.cleanup() and lcd.clear()
# before systemd sends SIGKILL.
TimeoutStopSec=10

# ── Environment ───────────────────────────────────────────────────────────────
# Uncomment the line below if python3 is in a virtualenv instead of system python.
# Environment=PATH=/home/pi/chick-up/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
# ExecStart=/home/pi/chick-up/venv/bin/python3 /home/pi/chick-up/main.py

[Install]
# Start this service when the Pi boots into multi-user mode (normal operation).
WantedBy=multi-user.target
```

Save and exit: `Ctrl+O` → `Enter` → `Ctrl+X`.

---

### 2.3 Enable and Start

Run these four commands in order:

```bash
# Tell systemd to read the new file
sudo systemctl daemon-reload

# Enable — marks the service to start on every boot
sudo systemctl enable chickup.service

# Start immediately without rebooting (for testing)
sudo systemctl start chickup.service

# Confirm it is active
sudo systemctl status chickup.service
```

The status output should show `Active: active (running)`. Example:

```
● chickup.service - Chick-Up Poultry Automation System
     Loaded: loaded (/etc/systemd/system/chickup.service; enabled; ...)
     Active: active (running) since Mon 2026-03-02 08:00:01 PST; 3s ago
   Main PID: 1234 (python3)
```

If you see `Active: failed` or `Active: activating`, jump to
[Section 7 (Troubleshooting)](#7-troubleshooting).

---

### 2.4 Verify It Is Running

```bash
# Check that main.py is actually running as a process
ps aux | grep main.py

# Watch live log output for the first 30 seconds
sudo journalctl -u chickup.service -f --lines=50

# Reboot and confirm it starts automatically
sudo reboot
# After reboot, SSH back in and run:
sudo systemctl status chickup.service
```

---

## 3. Checking Logs

Chick-Up writes its own rotating log files to `logs/` inside the project
directory. systemd also captures all stdout/stderr in the journal.

### Application logs (detailed, from `logger.py`)

```bash
# Most recent errors
tail -50 /home/pi/chick-up/logs/error.log

# Most recent warnings
tail -50 /home/pi/chick-up/logs/warning.log

# Everything combined
tail -100 /home/pi/chick-up/logs/all.log

# Follow all logs in real time
tail -f /home/pi/chick-up/logs/all.log
```

### systemd journal (boot messages, crashes, restart events)

```bash
# All output since last boot
sudo journalctl -u chickup.service -b

# Follow live output
sudo journalctl -u chickup.service -f

# Last 100 lines
sudo journalctl -u chickup.service -n 100

# Output from a specific boot (--list-boots to find boot index)
sudo journalctl --list-boots
sudo journalctl -u chickup.service -b -1    # previous boot
```

---

## 4. Updating the Code

After pulling new code or editing files, restart the service to apply changes:

```bash
cd /home/pi/chick-up

# Pull updates (if using git)
git pull

# Restart the service — this sends SIGTERM so GPIO cleanup runs
sudo systemctl restart chickup.service

# Confirm it came back up
sudo systemctl status chickup.service
```

> **Do not** use `sudo kill` or `sudo pkill python3` directly.
> Always use `sudo systemctl stop/restart chickup.service` so systemd
> sends SIGTERM cleanly and GPIO.cleanup() has a chance to run.

---

## 5. Temporarily Stopping the Service

This stops the service until the next reboot. It does **not** disable auto-run.

```bash
sudo systemctl stop chickup.service
```

To start it again without rebooting:

```bash
sudo systemctl start chickup.service
```

---

## 6. Permanently Disabling Auto-Run

This removes the service from startup but keeps the service file on disk.

```bash
# Stop if currently running
sudo systemctl stop chickup.service

# Disable auto-run on boot
sudo systemctl disable chickup.service

# Confirm
sudo systemctl status chickup.service   # should show "disabled"
```

To fully remove the service:

```bash
sudo systemctl stop chickup.service
sudo systemctl disable chickup.service
sudo rm /etc/systemd/system/chickup.service
sudo systemctl daemon-reload
```

---

## 7. Troubleshooting

### Service fails to start — `status` shows `failed`

```bash
# See the exact error
sudo journalctl -u chickup.service -n 50 --no-pager
```

**Common causes:**

| Symptom in journal | Cause | Fix |
|--------------------|-------|-----|
| `No such file or directory: main.py` | Wrong `WorkingDirectory` or `ExecStart` path | Check both paths in the service file match your actual install location |
| `ModuleNotFoundError: No module named 'firebase_admin'` | Dependencies not installed for the `pi` user | Run `pip3 install -r requirements.txt` as the `pi` user (not root) |
| `FileNotFoundError: credentials/.env` | `.env` file missing or wrong `WorkingDirectory` | Confirm `WorkingDirectory` is the project root, not a subdirectory |
| `PermissionError: /dev/i2c-1` | I2C not enabled or wrong group | Run `sudo raspi-config` → Interface Options → I2C → Enable |
| `PermissionError: /dev/video0` | Camera not enabled or wrong group | Run `sudo raspi-config` → Interface Options → Camera → Enable |
| `firebase_admin.exceptions.FirebaseError` | Firebase init fails | Check `credentials/serviceAccountKey.json` exists and is valid |
| `RTDB read failed: network` | No internet at startup | The service waits for `network-online.target`; check Wi-Fi is configured |

### Service starts but LCD stays blank

The LCD I2C address may not match. SSH in, stop the service, and test manually:

```bash
sudo systemctl stop chickup.service
sudo i2cdetect -y 1    # should show 0x27 (or 0x3f for some displays)
python3 main.py        # run manually to see error output directly
```

### Service restarts in a loop

```bash
sudo journalctl -u chickup.service -n 100 --no-pager
```

Look for the crash reason. Common causes: missing `.env` value, GPIO
already in use (another python3 process running), or Firebase credential error.

Check for leftover processes:

```bash
ps aux | grep python3
# Kill any orphan processes if found
sudo kill <PID>
```

### Python packages installed but service can't find them

This happens if packages were installed with `sudo pip3` (system python) but
the service runs as `pi` with a user-level site-packages, or vice versa.

```bash
# Check which python3 the service is using
which python3        # /usr/bin/python3

# Check packages visible to that python
/usr/bin/python3 -c "import firebase_admin; print('OK')"

# If it fails, install for the correct python
pip3 install firebase-admin    # user install (no sudo)
# OR
sudo pip3 install firebase-admin --break-system-packages   # system install
```

### `network-online.target` delays boot too long

If the Pi is on Ethernet (not Wi-Fi), or you want faster boot, you can change
`After=network-online.target` to `After=network.target`. This is less strict —
it waits for the network interface to be up but not for a successful DNS
resolution. Suitable for wired connections with DHCP.

---

## 8. Appendix: Full Service File Reference

```ini
[Unit]
Description=Chick-Up Poultry Automation System
After=network-online.target
Wants=network-online.target

[Service]
User=pi
Group=pi
WorkingDirectory=/home/pi/chick-up
ExecStart=/usr/bin/python3 /home/pi/chick-up/main.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
TimeoutStopSec=10

[Install]
WantedBy=multi-user.target
```

**Virtualenv variant** (if you use `python3 -m venv venv`):

```ini
[Unit]
Description=Chick-Up Poultry Automation System
After=network-online.target
Wants=network-online.target

[Service]
User=pi
Group=pi
WorkingDirectory=/home/pi/chick-up
ExecStart=/home/pi/chick-up/venv/bin/python3 /home/pi/chick-up/main.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
TimeoutStopSec=10

[Install]
WantedBy=multi-user.target
```

---

## Quick Reference

```bash
# Install / update
sudo systemctl daemon-reload
sudo systemctl enable chickup.service

# Control
sudo systemctl start   chickup.service
sudo systemctl stop    chickup.service
sudo systemctl restart chickup.service
sudo systemctl status  chickup.service

# Logs
sudo journalctl -u chickup.service -f          # live
sudo journalctl -u chickup.service -b          # this boot
tail -f /home/pi/chick-up/logs/all.log         # application logs

# Disable
sudo systemctl disable chickup.service
```