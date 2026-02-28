// src/services/deviceService.ts
import { database } from '../config/firebase.config';
import { ref, get, set, update } from 'firebase/database';
import { auth } from '../config/firebase.config';
import { DeviceCodeEntry, PairingAppWrite, LinkedDevice } from '../types/types';

/**
 * Pairing contract (must match auth.py on the raspi exactly):
 *
 *  1. Raspi generates a 6-char code and writes to:
 *       /device_code/{code}/
 *         deviceUid : string   — raspi's device UID
 *         createdAt : number   — Unix ms (code expires after 60 s)
 *         status    : "pending"
 *
 *  2. App enters the 6-char code, reads /device_code/{code}/, validates:
 *       - status === "pending"
 *       - not expired (createdAt within last 60 s)
 *
 *  3. App writes back to /device_code/{code}/:
 *       userUid  : string
 *       username : string
 *       status   : "paired"
 *
 *  4. App saves { deviceUid, linkedAt } to users/{userId}/linkedDevice
 *     so it can look up deviceUid on future boots without re-pairing.
 *
 *  5. Raspi polls, sees status === "paired", reads userUid + username,
 *     saves credentials locally, and boots normally.
 */

const CODE_EXPIRY_MS = 60_000; // must match CODE_EXPIRY_SECONDS = 60 in auth.py

class DeviceService {

  // ─────────────────────────── PAIRING ───────────────────────────────────────

  /**
   * Step 1 — Look up the 6-char code the raspi wrote to Firebase.
   *
   * Returns the DeviceCodeEntry so the UI can show which device will be paired.
   * Throws a descriptive error if the code doesn't exist, is already used, or
   * has expired — the UI should display these directly to the user.
   */
  async lookupPairingCode(code: string): Promise<DeviceCodeEntry> {
    const normalized = code.trim().toUpperCase();

    const snap = await get(ref(database, `device_code/${normalized}`));

    if (!snap.exists()) {
      throw new Error('Code not found. Check the code shown on your device and try again.');
    }

    const entry = snap.val() as DeviceCodeEntry;

    if (entry.status === 'expired') {
      throw new Error('This code has expired. Press A on your device to generate a new one.');
    }

    if (entry.status === 'paired') {
      throw new Error('This code has already been used. Press A on your device to generate a new one.');
    }

    const ageMs = Date.now() - entry.createdAt;
    if (ageMs > CODE_EXPIRY_MS) {
      throw new Error('Code expired. Press A on your device to generate a new one.');
    }

    return entry;  // { deviceUid, createdAt, status: "pending" }
  }

  /**
   * Step 2 — Complete pairing.
   *
   * Writes userUid + username + status:"paired" back to /device_code/{code}/
   * so the raspi poll sees it. Then saves deviceUid to the user's Firebase
   * profile so getLinkedDevice() works on future app launches.
   */
  async completePairing(code: string, deviceUid: string): Promise<void> {
    const normalized = code.trim().toUpperCase();
    const user = auth.currentUser;

    if (!user) throw new Error('Not authenticated.');

    // Get username from users/{uid}
    const userSnap = await get(ref(database, `users/${user.uid}/username`));
    const username: string = userSnap.exists() ? userSnap.val() : user.email ?? 'unknown';

    // Write pairing completion — raspi polls for this
    const pairingWrite: PairingAppWrite = {
      userUid:  user.uid,
      username: username,
      status:   'paired',
    };
    await update(ref(database, `device_code/${normalized}`), pairingWrite);

    // Persist deviceUid in user profile for future app launches
    const linkedDevice: LinkedDevice = {
      deviceUid: deviceUid,
      linkedAt:  Date.now(),
    };
    await set(ref(database, `users/${user.uid}/linkedDevice`), linkedDevice);
  }

  // ─────────────────────────── DEVICE LOOKUP ─────────────────────────────────

  /**
   * Get the deviceUid linked to this user (saved during completePairing).
   * Returns null if the user hasn't paired yet.
   */
  async getLinkedDevice(userId: string): Promise<string | null> {
    try {
      const snap = await get(ref(database, `users/${userId}/linkedDevice/deviceUid`));
      return snap.exists() ? (snap.val() as string) : null;
    } catch {
      return null;
    }
  }

  /**
   * Unlink the device from this user's profile.
   * Does NOT write anything to the raspi — the raspi keeps its own credentials
   * until it re-pairs. Use this when the user wants to pair a different device.
   */
  async unlinkDevice(userId: string): Promise<void> {
    await set(ref(database, `users/${userId}/linkedDevice`), null);
  }
}

export default new DeviceService();