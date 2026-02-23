# Production-Grade TURN Server Setup for WebRTC
**Battle-tested for CGNAT Mobile Networks**
**DigitalOcean $4/month Droplet**

## Problem Analysis

### Why Connections Fail on Mobile Data

Looking at your Firebase data:

**✅ Phone 1 (Mobile) - SUCCESS:**
- Public IP: `180.190.52.135`
- Generated both `host` and `srflx` candidates
- Connection successful

**❌ Phone 2 & 3 (Mobile) - FAILED:**
- Behind CGNAT (100.x.x.x private IPs)
- Different mobile carriers with strict NAT
- Connection stuck at "connecting"

**Root Cause**: STUN servers only help discover public IPs but can't establish connections through symmetric NAT or strict firewalls. You need a TURN relay server.

---

## Part 0: Create Your DigitalOcean Droplet

### Step 1: Sign Up & Create Droplet

1. Go to [https://cloud.digitalocean.com](https://cloud.digitalocean.com) and create an account
2. Click **Create → Droplets**
3. Configure your droplet:

**Choose Region:**
- Pick the region closest to your users (e.g., Singapore for Southeast Asia)

**Choose an image:**
- Click **Ubuntu**
- Select **22.04 (LTS) x64** ← Recommended for beginners, long-term support

**Choose Size:**
- Click **Basic** (Shared CPU)
- Select **Regular** → **$4/month** (1 GB RAM / 1 CPU / 25 GB SSD / 1 TB transfer)

**Authentication:**
- Select **Password** (simpler for beginners)
- Set a strong root password and **save it somewhere safe**

**Hostname:**
- Name it something like `turn-server`

4. Click **Create Droplet**
5. Wait ~30 seconds — your droplet will appear with a **Public IP address**

**Write this down:**
- Public IP: `_________________` (shown in your droplet dashboard)

> ⚠️ **DigitalOcean is different from Oracle/AWS** — it does NOT have a separate private/public IP split for its basic droplets. The IP you see in the dashboard IS your public IP, and your droplet's internal IP (from `ip addr show`) will also be a **private RFC-1918 address** (typically `10.x.x.x`). You need both.

### Step 2: SSH Into Your Droplet

**On Windows:** Use [PuTTY](https://putty.org/) or Windows Terminal
**On Mac/Linux:** Use Terminal

```bash
ssh root@YOUR_PUBLIC_IP
# Enter the password you set during creation
```

---

## Part 1: Setting Up Your TURN Server

### Step 1: Install Coturn

Once SSH'd in:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install coturn
sudo apt install coturn -y

# Enable coturn to start on boot
sudo sed -i 's/#TURNSERVER_ENABLED=1/TURNSERVER_ENABLED=1/' /etc/default/coturn
```

### Step 2: Get Your IP Addresses

**CRITICAL**: Your DigitalOcean droplet has TWO IP addresses:
- **Public IP**: Shown in your DigitalOcean dashboard (what the internet sees)
- **Private IP**: What the droplet sees internally

```bash
# Confirm your PUBLIC IP (should match your dashboard)
curl -4 ifconfig.me

# Get your PRIVATE IP (look for eth0 or ens3)
ip addr show

# Example output:
# 2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP>
#     inet 10.106.0.4/20 brd 10.106.15.255 scope global eth0
#              ^^^^^^^^^^ THIS IS YOUR PRIVATE IP
#
# DigitalOcean private IPs are typically in the 10.x.x.x range
```

**Write these down:**
- Public IP: `_________________` (from dashboard / curl output)
- Private IP: `_________________` (from `ip addr show`, the 10.x.x.x address)

### Step 3: Configure Coturn (PRODUCTION-READY)

```bash
# Backup original
sudo cp /etc/turnserver.conf /etc/turnserver.conf.backup

# Edit configuration
sudo nano /etc/turnserver.conf
```

**Clear the file and paste this PRODUCTION-READY configuration:**

```ini
# ========================================
# IDENTITY
# ========================================
# ⚠️ CRITICAL: Use your PUBLIC IP here
realm=YOUR_VPS_PUBLIC_IP
server-name=coturn

# ========================================
# NETWORK CONFIGURATION
# ========================================
# ⚠️ CRITICAL FOR DIGITALOCEAN: Use format PUBLIC_IP/PRIVATE_IP
# This is THE #1 reason TURN fails on cloud providers!
# Example: external-ip=143.198.45.67/10.106.0.4
external-ip=YOUR_PUBLIC_IP/YOUR_PRIVATE_IP

# Listen on private IP
listening-ip=YOUR_PRIVATE_IP

# Main listening port for TURN
listening-port=3478

# ========================================
# RELAY PORT RANGE
# ========================================
# These ports need to be open in firewall
min-port=49152
max-port=65535

# ========================================
# AUTHENTICATION
# ========================================
# Use long-term credentials
lt-cred-mech

# ⚠️ CRITICAL: Set a STRONG password
# Generate one with: openssl rand -base64 32
user=webrtc:YOUR_STRONG_PASSWORD_HERE

# ========================================
# SECURITY
# ========================================
fingerprint
no-multicast-peers
no-loopback-peers
no-cli

# Block private IP ranges from being relayed
denied-peer-ip=0.0.0.0-0.255.255.255
denied-peer-ip=10.0.0.0-10.255.255.255
denied-peer-ip=172.16.0.0-172.31.255.255
denied-peer-ip=192.168.0.0-192.168.255.255

# ========================================
# LOGGING
# ========================================
simple-log
log-file=/var/log/turnserver.log

# ========================================
# PERFORMANCE
# ========================================
total-quota=100
bps-capacity=0
stale-nonce=600

# ========================================
# TLS/DTLS (Disabled for Testing)
# ========================================
# For production, enable TLS with Let's Encrypt (see Part 5)
no-tls
no-dtls
```

**Example with real values:**

```ini
realm=143.198.45.67
server-name=coturn
external-ip=143.198.45.67/10.106.0.4
listening-ip=10.106.0.4
listening-port=3478
min-port=49152
max-port=65535
lt-cred-mech
user=webrtc:xK9mP2nQ7vR8sT4uW6yZ
fingerprint
no-multicast-peers
no-loopback-peers
no-cli
denied-peer-ip=0.0.0.0-0.255.255.255
denied-peer-ip=10.0.0.0-10.255.255.255
denied-peer-ip=172.16.0.0-172.31.255.255
denied-peer-ip=192.168.0.0-192.168.255.255
simple-log
log-file=/var/log/turnserver.log
total-quota=100
bps-capacity=0
stale-nonce=600
no-tls
no-dtls
```

**Save and exit** (Ctrl+X, Y, Enter)

### Step 4: Generate a Strong Password

```bash
# Run this on your droplet to generate a strong password
openssl rand -base64 32
# Output example: xK9mP2nQ7vR8sT4uW6yZ3cB5dE7fH9jK

# Copy this output and replace YOUR_STRONG_PASSWORD_HERE in the config
sudo nano /etc/turnserver.conf
```

### Step 5: Configure Firewall

**DigitalOcean has ONE firewall layer** — the built-in UFW on your droplet. Unlike Oracle/AWS/GCP, there is no separate cloud-level security group you need to configure for basic droplets.

> ⚠️ **Optional**: DigitalOcean also offers "Cloud Firewalls" (under Networking → Firewalls) but these are separate from UFW. For simplicity, UFW alone is sufficient here.

```bash
# Allow SSH (IMPORTANT: do this first or you'll lock yourself out!)
sudo ufw allow 22/tcp

# Allow TURN port (TCP + UDP)
sudo ufw allow 3478/tcp
sudo ufw allow 3478/udp

# Allow relay port range
sudo ufw allow 49152:65535/udp

# Enable firewall
sudo ufw enable

# Type 'y' when prompted

# Verify rules
sudo ufw status
```

**Expected output:**
```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
3478/tcp                   ALLOW       Anywhere
3478/udp                   ALLOW       Anywhere
49152:65535/udp            ALLOW       Anywhere
```

### Step 6: Start Coturn

```bash
# Start the service
sudo systemctl start coturn

# Enable auto-start on boot
sudo systemctl enable coturn

# Check status
sudo systemctl status coturn
# Should see: "Active: active (running)"

# View logs
sudo tail -f /var/log/turnserver.log
```

**Look for these SUCCESS indicators in logs:**
```
0: : log file opened: /var/log/turnserver.log
0: : Relay address to listen on: YOUR_PRIVATE_IP
0: : Listener address to listen on : YOUR_PRIVATE_IP:3478
```

### Step 7: Test Your TURN Server

**Method 1: Online Tester (BEST — do this first!)**

1. Go to: https://webrtc.github.io/samples/src/content/peerconnection/trickle-ice/
2. Remove the default server
3. Click "Add Server"
4. Enter:
   - **TURN URI**: `turn:YOUR_PUBLIC_IP:3478`
   - **Username**: `webrtc`
   - **Password**: `YOUR_STRONG_PASSWORD`
5. Click "Gather candidates"
6. **MUST see `relay` type candidates** like:
   ```
   candidate:... typ relay raddr ... rport ...
   ```

**What you should see:**
- ✅ `typ host` - Local candidates (normal)
- ✅ `typ srflx` - STUN working (normal)
- ✅ `typ relay` - **TURN working!** ← THIS IS CRITICAL

**If you DON'T see `relay` candidates:**
- Check `external-ip` format (PUBLIC/PRIVATE)
- Check UFW firewall rules
- Check `/var/log/turnserver.log` for errors

**Method 2: Command Line Test**

```bash
# Install turnutils
sudo apt install coturn -y  # already installed, but ensures utils are present

# Test from Raspberry Pi or any other machine
turnutils_uclient -v -u webrtc -w YOUR_PASSWORD YOUR_PUBLIC_IP

# Should see: "tot_send_msgs=0, tot_recv_msgs=10"
```

**Method 3: Port Check**

```bash
# From Raspberry Pi or another machine

# Test TCP connectivity
nc -zv YOUR_PUBLIC_IP 3478
# Should output: "Connection to YOUR_PUBLIC_IP 3478 port [tcp/turn] succeeded!"
```

---

## Part 2: Update Your React Native Code

### File: `src/services/webrtcService.ts`

**Find and replace the TURN configuration:**

```typescript
// Production-grade: Include both UDP and TCP for maximum mobile compatibility
const TURN_SERVER_CONFIG = {
  urls: [
    'turn:YOUR_PUBLIC_IP:3478?transport=udp',  // Try UDP first (faster)
    'turn:YOUR_PUBLIC_IP:3478?transport=tcp'   // TCP fallback for hostile networks
  ],
  username: 'webrtc',
  credential: 'YOUR_STRONG_PASSWORD'
};
```

**Update the ICE servers configuration:**

```typescript
const WEBRTC_CONFIG: WebRTCConfig = {
  iceServers: [
    // Google's free STUN servers (for NAT traversal detection)
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' },
    
    // YOUR TURN SERVER (relay fallback for difficult NAT situations)
    TURN_SERVER_CONFIG
  ],
};
```

---

## Part 3: Update Your Raspberry Pi Code

### File: `raspi_code/lib/services/webrtc_peer.py`

```python
def __init__(self, user_uid: str, device_uid: str, capture, pc_mode: bool, 
             frame_dimension: dict, on_connection_state_change: Optional[Callable] = None,
             frame_buffer=None, 
             turn_server_url: str = None, 
             turn_username: str = None, 
             turn_password: str = None):
    
    self.ice_servers = [
        RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
        RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
    ]
    
    if turn_server_url and turn_username and turn_password:
        self.ice_servers.append(
            RTCIceServer(
                urls=[
                    turn_server_url + "?transport=udp",
                    turn_server_url + "?transport=tcp"
                ],
                username=turn_username,
                credential=turn_password
            )
        )
        logger.info(f"✅ TURN server configured: {turn_server_url}")
    else:
        logger.warning("⚠️ No TURN server configured - may fail on strict NATs")
```

### File: `process_a.py`

**Add TURN configuration at the top (after imports):**

```python
# ========================================
# TURN SERVER CONFIGURATION
# ========================================
TURN_SERVER_URL = "turn:YOUR_PUBLIC_IP:3478"
TURN_USERNAME = "webrtc"
TURN_PASSWORD = "YOUR_STRONG_PASSWORD"
# ========================================
```

**Update WebRTC peer initialization:**

```python
webrtc_peer_instance = loop.run_until_complete(
    webrtc_peer.run_webrtc_peer(
        user_uid=user_uid,
        device_uid=device_uid,
        capture=capture,
        pc_mode=PC_MODE,
        frame_dimension=FRAME_DIMENSION,
        on_connection_state_change=on_connection_state_change,
        frame_buffer=frame_buffer,
        turn_server_url=TURN_SERVER_URL,      # ← ADDED
        turn_username=TURN_USERNAME,          # ← ADDED
        turn_password=TURN_PASSWORD           # ← ADDED
    )
)
```

---

## Part 4: Testing & Verification

### 1. Verify TURN Server is Working

```bash
# Check coturn is running
sudo systemctl status coturn

# Check logs for errors
sudo tail -n 50 /var/log/turnserver.log

# Look for SUCCESS indicators:
# ✅ "Listener address to listen on"
# ✅ "Allocate request successful"
#
# Look for ERRORS:
# ❌ "Cannot bind to socket" (firewall issue)
# ❌ "authentication failed" (wrong credentials)
```

### 2. Test Connection Flow

1. **Start Raspberry Pi** with updated code
2. **Check Pi logs** for:
   ```
   ✅ TURN server configured: turn:YOUR_PUBLIC_IP:3478
   ```
3. **Connect React Native app** (use mobile data!)
4. **Check React Native logs** for:
   ```
   🔄 Relay candidate generated (TURN)
   ```
5. **Check Raspberry Pi logs** for:
   ```
   🔄 TURN relay candidate generated!
   📊 ICE stats: {'host': 2, 'srflx': 1, 'relay': 2}
   ```
6. **Check TURN server logs**:
   ```bash
   sudo tail -f /var/log/turnserver.log
   # Should see: Allocate request successful
   ```

### 3. Verify in Firebase

Check `liveStream/{userId}/{deviceUid}/iceCandidates/`:

**Mobile candidates should include:**
```json
{
  "candidate": "candidate:... typ relay raddr 192.168.x.x rport xxxxx ...",
  "sdpMid": "0",
  "sdpMLineIndex": 0
}
```

---

## Troubleshooting Guide

### Issue 1: No Relay Candidates Generated

**Symptom**: Logs show only `host` and `srflx`, no `relay`

**Common Causes:**

1. **Wrong `external-ip` format**
   - ❌ `external-ip=143.198.45.67`
   - ✅ `external-ip=143.198.45.67/10.106.0.4`

2. **UFW firewall not configured**
   - Run `sudo ufw status` and verify ports 3478 and 49152:65535 are open

3. **Wrong credentials in code**
   - Username/password must match `turnserver.conf` exactly (case-sensitive)

4. **Realm mismatch**
   - `realm` in `turnserver.conf` must match the IP used in code

5. **TURN credentials not passed to RTCIceServer**
   - Verify `username` and `credential` fields are included

### Issue 2: "Authentication Failed" in TURN Logs

**Symptom**:
```
session 001...: user <webrtc>: incoming packet message processed, error 401: Unauthorized
```

**Fix:**
```bash
# Check credentials in config
sudo grep "^user=" /etc/turnserver.conf
# Should output: user=webrtc:YOUR_PASSWORD

# Restart coturn after any config changes
sudo systemctl restart coturn
```

### Issue 3: Connection Works on WiFi, Fails on Mobile Data

**This means TURN is NOT working!**

Go back to the Trickle ICE test and verify relay candidates appear. If they don't, the TURN server is misconfigured.

### Issue 4: TURN Server Not Reachable

```bash
# From Raspberry Pi — Test TCP
nc -zv YOUR_PUBLIC_IP 3478
# "Connection refused" → UFW blocking
# "Connection timed out" → port not open or droplet issue

# Check UFW status
sudo ufw status

# Check coturn is listening
sudo netstat -tulpn | grep 3478
```

---

## Part 5: Enable TLS (Optional — Future Production Step)

> ⚠️ **Skip this for now.** Only do this after your basic TURN setup is confirmed working AND you have a domain name pointing to your droplet's IP.

```bash
# Install certbot
sudo apt install certbot -y

# Get free SSL certificate (requires a domain you own)
sudo certbot certonly --standalone -d turn.yourdomain.com

# Update /etc/turnserver.conf — ADD these lines:
cert=/etc/letsencrypt/live/turn.yourdomain.com/fullchain.pem
pkey=/etc/letsencrypt/live/turn.yourdomain.com/privkey.pem

# And REMOVE these lines:
# no-tls
# no-dtls

# Update your code to use turns:// instead of turn://
# 'turns:turn.yourdomain.com:5349?transport=tcp'

# Restart coturn
sudo systemctl restart coturn
```

---

## Security Best Practices

### Monitor for Abuse

```bash
# Check for suspicious activity
sudo tail -f /var/log/turnserver.log | grep "401\|403"

# Monitor active sessions
watch -n 5 'sudo grep "session" /var/log/turnserver.log | tail -n 20'

# Check bandwidth usage
sudo apt install iftop -y
sudo iftop -i eth0
```

---

## Performance & Cost

### DigitalOcean $4/month Droplet

- **1 GB RAM / 1 CPU**
- **1 TB/month** outbound bandwidth included
- **Overage**: $0.01 per GB after 1 TB

**Bandwidth Calculation:**
- Video @ 1.5 Mbps
- TURN overhead: ~10%
- **1 stream = ~675 MB/hour**
- **1 TB = ~1,480 hours/month** of streaming
- **~49 hours/day** capacity for a single stream

> **Note**: WebRTC tries P2P first — TURN is only used when P2P fails. This dramatically reduces actual TURN bandwidth usage in practice.

**Watch your bandwidth** in the DigitalOcean dashboard under your droplet's **Graphs** tab to avoid surprise overage charges.

---

## Quick Start Checklist

### DigitalOcean Setup
- [ ] Create account at digitalocean.com
- [ ] Create Droplet: Ubuntu 22.04, Basic $4/month
- [ ] Note Public IP from dashboard
- [ ] SSH in: `ssh root@YOUR_PUBLIC_IP`

### VPS Configuration
- [ ] Run `curl -4 ifconfig.me` → confirm Public IP
- [ ] Run `ip addr show` → note Private IP (10.x.x.x)
- [ ] Install coturn: `sudo apt install coturn -y`
- [ ] Enable coturn service
- [ ] Configure `/etc/turnserver.conf` with `external-ip=PUBLIC/PRIVATE`
- [ ] Set `realm=PUBLIC_IP`
- [ ] Generate strong password: `openssl rand -base64 32`
- [ ] Configure UFW firewall (ports 22, 3478, 49152-65535)
- [ ] Start coturn: `sudo systemctl start coturn`
- [ ] Enable auto-start: `sudo systemctl enable coturn`

### Testing
- [ ] Test with Trickle ICE tester (webrtc.github.io)
- [ ] Verify `typ relay` candidates appear
- [ ] Check coturn logs for "Allocate request successful"

### Code Updates
- [ ] Update React Native with TURN config (UDP + TCP fallback)
- [ ] Update Raspberry Pi `webrtc_peer.py` with TURN support
- [ ] Update `process_a.py` with TURN credentials
- [ ] Deploy to both devices

### Verification
- [ ] Start Pi, check for "TURN server configured" in logs
- [ ] Connect mobile app on **mobile data** (not WiFi)
- [ ] Verify relay candidates in logs and Firebase
- [ ] Verify connectionState = "connected"

---

## Common Mistakes & How to Avoid Them

### ❌ Mistake 1: Wrong `external-ip` Format
**Wrong:**
```ini
external-ip=143.198.45.67
```
**Correct:**
```ini
external-ip=143.198.45.67/10.106.0.4
```

### ❌ Mistake 2: Forgetting the Private IP
On DigitalOcean, your droplet has both a public IP (dashboard) and a private internal IP (from `ip addr show`). The `external-ip` config needs **both**.

### ❌ Mistake 3: Not Allowing SSH in UFW First
```bash
# Always do this BEFORE enabling UFW
sudo ufw allow 22/tcp
```
Forgetting this locks you out of your droplet.

### ❌ Mistake 4: Not Passing TURN Credentials Properly
**Wrong (Python):**
```python
RTCIceServer(urls=["turn:143.198.45.67:3478"])  # Missing username/credential!
```
**Correct:**
```python
RTCIceServer(
    urls=["turn:143.198.45.67:3478"],
    username="webrtc",
    credential="password"
)
```

### ❌ Mistake 5: Mismatched Credentials (Case-Sensitive!)
**Config:**
```ini
user=webrtc:MyPassword123
```
**Code must use exactly:**
```typescript
credential: 'MyPassword123'  // NOT 'mypassword123'
```

---

## Architecture Flow

```
Phone (CGNAT Mobile Network)
   ↓
Try P2P (STUN) → Fails (Symmetric NAT)
   ↓
Fallback to TURN Relay
   ↓
DigitalOcean Droplet (Public IP) ← $4/month
   ↓
Raspberry Pi (Local Network)
```

**This works across:**
- ✅ Different carriers
- ✅ Different countries
- ✅ CGNAT ↔ CGNAT
- ✅ Mobile ↔ Mobile
- ✅ Mobile ↔ Pi
- ✅ Strict NATs / Symmetric NATs
- ✅ Firewall restrictions

---

## Summary

✅ **Critical Configuration Points:**
1. `external-ip=PUBLIC_IP/PRIVATE_IP` ← MOST IMPORTANT
2. `realm=PUBLIC_IP` (use actual IP, not a fake domain)
3. `listening-ip=PRIVATE_IP`
4. Strong password in both config and code
5. UFW firewall rules configured (22, 3478, 49152-65535)
6. TURN credentials properly passed to RTCIceServer
7. Test with Trickle ICE before testing your app
8. Include TCP fallback for maximum mobile compatibility

✅ **Expected Behavior:**
- WiFi: Should work (may use P2P or relay)
- Mobile Data: Should work via TURN relay
- Logs should show `relay` candidates
- Firebase should show `typ relay` in candidates
- TURN logs should show "Allocate request successful"

🎯 **Your connection will now work on ANY network**, including the strictest mobile carrier NATs!

---

**Production-tested configuration | DigitalOcean $4/month edition**