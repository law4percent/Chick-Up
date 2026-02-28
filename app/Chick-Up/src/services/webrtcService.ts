// src/services/webrtcService.ts
import {
  RTCPeerConnection,
  RTCIceCandidate,
  RTCSessionDescription,
  MediaStream,
} from 'react-native-webrtc';
import { database } from '../config/firebase.config';
import { ref, set, onValue, push, remove, off } from 'firebase/database';

/**
 * WebRTC Service — signaling via Firebase RTDB, video relay via TURN.
 *
 * TURN config is loaded from .env at build time — NOT from Firebase.
 * This keeps credentials out of the database entirely.
 *
 * Add to your .env file:
 *   EXPO_PUBLIC_TURN_SERVER_URL=143.198.45.67:3478
 *   EXPO_PUBLIC_TURN_USERNAME=webrtc
 *   EXPO_PUBLIC_TURN_PASSWORD=your_strong_password
 *
 * URL normalization mirrors webrtc_peer.py exactly:
 *   strips any existing turn:/turns:/stun: prefix, rebuilds as
 *   turn:{host}?transport=udp  and  turn:{host}?transport=tcp
 *
 * Firebase signaling paths:
 *   liveStream/{userId}/{deviceUid}/offer                        ← app writes
 *   liveStream/{userId}/{deviceUid}/answer                       ← app reads
 *   liveStream/{userId}/{deviceUid}/iceCandidates/mobile/{push}  ← app writes
 *   liveStream/{userId}/{deviceUid}/iceCandidates/raspi/{push}   ← app reads
 *   liveStream/{userId}/{deviceUid}/connectionState              ← app writes
 *   liveStream/{userId}/{deviceUid}/liveStreamButton             ← app writes
 */

// ─────────────────────────── TURN FROM .ENV ──────────────────────────────────

/**
 * Strip any scheme prefix (turn: / turns: / stun:) then rebuild correctly.
 * Matches the normalization in webrtc_peer.py so both sides produce valid URIs
 * regardless of how the URL is stored.
 */
function normalizeTurnHost(raw: string): string {
  let host = raw.trim();
  for (const prefix of ['turns:', 'turn:', 'stun:']) {
    if (host.startsWith(prefix)) {
      host = host.slice(prefix.length);
      break;
    }
  }
  return host;
}

const TURN_URL  = process.env.EXPO_PUBLIC_TURN_SERVER_URL ?? '';
const TURN_USER = process.env.EXPO_PUBLIC_TURN_USERNAME   ?? '';
const TURN_PASS = process.env.EXPO_PUBLIC_TURN_PASSWORD   ?? '';

function buildIceServers() {
  const servers: any[] = [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' },
  ];

  if (TURN_URL && TURN_USER && TURN_PASS) {
    const host = normalizeTurnHost(TURN_URL);
    servers.push({
      urls: [
        `turn:${host}?transport=udp`,  // UDP first — lower latency
        `turn:${host}?transport=tcp`,  // TCP fallback for CGNAT / strict firewall
      ],
      username:   TURN_USER,
      credential: TURN_PASS,
    });
    console.log('[WebRTC] TURN loaded from .env:', `turn:${host}`);
  } else {
    console.warn('[WebRTC] ⚠️ TURN not configured in .env — may fail on mobile data (CGNAT).');
    console.warn('[WebRTC]   Set EXPO_PUBLIC_TURN_SERVER_URL, EXPO_PUBLIC_TURN_USERNAME, EXPO_PUBLIC_TURN_PASSWORD');
  }

  return servers;
}

// Build once at module load — env vars are static at runtime
const ICE_SERVERS = buildIceServers();

// ─────────────────────────── SERVICE ─────────────────────────────────────────

class WebRTCService {
  private peerConnection: RTCPeerConnection | null = null;
  private remoteStream:   MediaStream | null = null;
  private userId:         string | null = null;
  private deviceUid:      string | null = null;
  private isInitialized:  boolean = false;

  private answerListener:   any = null;
  private raspiIceListener: any = null;

  private onRemoteStreamCallback:    ((stream: MediaStream) => void) | null = null;
  private onConnectionStateCallback: ((state: string) => void) | null = null;
  private onErrorCallback:           ((error: Error) => void) | null = null;

  private iceStats = { host: 0, srflx: 0, relay: 0 };

  // ── Path helper ──────────────────────────────────────────────────────────────

  private liveStreamRef(subpath: string) {
    return ref(database, `liveStream/${this.userId}/${this.deviceUid}/${subpath}`);
  }

  // ── Initialize ────────────────────────────────────────────────────────────────

  /**
   * Create RTCPeerConnection with ICE servers from .env.
   *
   * Safe to call multiple times — if already initialized, cleans up first.
   * This prevents the "Call initialize() before startConnection()" error
   * that can occur when stop → start happens quickly (cleanup sets
   * isInitialized=false, but the UI calls startConnection before initialize).
   */
  async initialize(
    userId:             string,
    deviceUid:          string,
    onRemoteStream:     (stream: MediaStream) => void,
    onConnectionState?: (state: string) => void,
    onError?:           (error: Error) => void,
  ): Promise<void> {
    // If already initialized with same userId+deviceUid, no-op
    if (this.isInitialized && this.userId === userId && this.deviceUid === deviceUid) {
      console.log('[WebRTC] Already initialized for this session, skipping re-init');
      return;
    }

    // If initialized for a different session, clean up first
    if (this.isInitialized) {
      await this._internalCleanup();
    }

    try {
      console.log('[WebRTC] Initializing...');

      this.userId    = userId;
      this.deviceUid = deviceUid;
      this.onRemoteStreamCallback    = onRemoteStream;
      this.onConnectionStateCallback = onConnectionState ?? null;
      this.onErrorCallback           = onError ?? null;

      this.peerConnection = new RTCPeerConnection({ iceServers: ICE_SERVERS });
      const pc = this.peerConnection as any;

      pc.onicecandidate = (event: any) => {
        if (!event.candidate) return;
        const c: string = event.candidate.candidate;
        if (c.includes('typ host'))  { this.iceStats.host++;  console.log('[WebRTC] 🏠 host'); }
        if (c.includes('typ srflx')) { this.iceStats.srflx++; console.log('[WebRTC] 🌐 srflx (STUN)'); }
        if (c.includes('typ relay')) { this.iceStats.relay++; console.log('[WebRTC] 🔄 relay (TURN) ✅'); }
        this.sendIceCandidate(event.candidate);
      };

      pc.onicegatheringstatechange = () => {
        console.log('[WebRTC] ICE gathering:', pc.iceGatheringState);
        if (pc.iceGatheringState === 'complete') {
          console.log('[WebRTC] 📊 ICE stats:', this.iceStats);
          if (this.iceStats.relay === 0) {
            console.warn('[WebRTC] ⚠️ No relay candidates. Check TURN .env vars and VPS firewall.');
          }
        }
      };

      pc.ontrack = (event: any) => {
        console.log('[WebRTC] 🎥 Remote track:', event.track.kind);
        if (event.streams?.[0]) {
          this.remoteStream = event.streams[0];
        } else {
          if (!this.remoteStream) this.remoteStream = new MediaStream();
          (this.remoteStream as any).addTrack(event.track);
        }
        this.onRemoteStreamCallback?.(this.remoteStream!);
      };

      pc.onconnectionstatechange = () => {
        const state: string = pc.connectionState ?? 'unknown';
        console.log('[WebRTC] Connection state:', state);
        this.onConnectionStateCallback?.(state);
        if (state === 'connected') console.log('[WebRTC] 🎉 Connected! Stats:', this.iceStats);
        if (state === 'failed' || state === 'closed') {
          console.log('[WebRTC] 📊 Final stats:', this.iceStats);
          this._internalCleanup();
        }
      };

      pc.oniceconnectionstatechange = () => {
        const state: string = pc.iceConnectionState ?? 'unknown';
        console.log('[WebRTC] ICE connection:', state);
        if (state === 'failed') {
          console.error('[WebRTC] ❌ ICE failed. Stats:', this.iceStats);
          if (this.iceStats.relay === 0) {
            console.error('[WebRTC]   → No relay candidates. Verify TURN server .env and VPS is running.');
          }
        }
      };

      this.isInitialized = true;
      console.log('[WebRTC] ✅ Initialized');

    } catch (error) {
      console.error('[WebRTC] Init error:', error);
      this.onErrorCallback?.(error as Error);
      throw error;
    }
  }

  // ── Start connection ──────────────────────────────────────────────────────────

  async startConnection(): Promise<void> {
    if (!this.isInitialized || !this.peerConnection) {
      throw new Error('Call initialize() before startConnection().');
    }
    if (!this.userId || !this.deviceUid) {
      throw new Error('userId / deviceUid not set.');
    }

    try {
      console.log('[WebRTC] Starting connection...');
      this.iceStats = { host: 0, srflx: 0, relay: 0 };

      await this.cleanupFirebaseSignaling();
      await this.updateConnectionState('connecting');

      // Tell raspi to start streaming
      await set(this.liveStreamRef('liveStreamButton'), true);

      const offer = await this.peerConnection.createOffer({
        offerToReceiveVideo: true,
        offerToReceiveAudio: false,
      });
      await this.peerConnection.setLocalDescription(offer);
      await set(this.liveStreamRef('offer'), {
        sdp: offer.sdp, type: offer.type, timestamp: Date.now(),
      });
      console.log('[WebRTC] Offer sent');

      this.listenForAnswer();
      this.listenForRaspiIceCandidates();

    } catch (error) {
      console.error('[WebRTC] startConnection error:', error);
      await this.updateConnectionState('failed');
      this.onErrorCallback?.(error as Error);
      throw error;
    }
  }

  // ── Answer listener ───────────────────────────────────────────────────────────

  private listenForAnswer(): void {
    const answerRef = this.liveStreamRef('answer');
    this.answerListener = onValue(answerRef, async (snap) => {
      const answer = snap.val();
      if (!answer?.sdp || !this.peerConnection) return;
      if (this.peerConnection.remoteDescription) return;
      try {
        await this.peerConnection.setRemoteDescription(
          new RTCSessionDescription({ sdp: answer.sdp, type: answer.type }),
        );
        console.log('[WebRTC] ✅ Remote description set');
        off(answerRef);
        this.answerListener = null;
      } catch (e) {
        console.error('[WebRTC] setRemoteDescription error:', e);
        this.onErrorCallback?.(e as Error);
      }
    });
  }

  // ── Raspi ICE candidates listener ─────────────────────────────────────────────

  private listenForRaspiIceCandidates(): void {
    const iceCandidatesRef = this.liveStreamRef('iceCandidates/raspi');
    this.raspiIceListener = onValue(iceCandidatesRef, async (snap) => {
      const candidates = snap.val();
      if (!candidates || !this.peerConnection) return;

      for (const key of Object.keys(candidates)) {
        const d = candidates[key];
        if (!d?.candidate) continue;
        try {
          await this.peerConnection.addIceCandidate(
            new RTCIceCandidate({
              candidate: d.candidate, sdpMid: d.sdpMid, sdpMLineIndex: d.sdpMLineIndex,
            }),
          );
          const isRelay = (d.candidate as string).includes('typ relay');
          console.log(`[WebRTC] ✅ raspi ICE${isRelay ? ' 🔄 TURN relay' : ''}`);
        } catch (e) {
          console.error('[WebRTC] addIceCandidate error:', e);
        }
      }

      if ((this.peerConnection as any)?.connectionState === 'connected') {
        off(iceCandidatesRef);
        this.raspiIceListener = null;
      }
    });
  }

  // ── Send local ICE to Firebase ────────────────────────────────────────────────

  private async sendIceCandidate(candidate: RTCIceCandidate): Promise<void> {
    try {
      await set(push(this.liveStreamRef('iceCandidates/mobile')), {
        candidate: candidate.candidate, sdpMid: candidate.sdpMid,
        sdpMLineIndex: candidate.sdpMLineIndex, timestamp: Date.now(),
      });
    } catch (e) {
      console.error('[WebRTC] sendIceCandidate error:', e);
    }
  }

  private async updateConnectionState(state: string): Promise<void> {
    try { await set(this.liveStreamRef('connectionState'), state); } catch { /* non-fatal */ }
  }

  // ── Stop ──────────────────────────────────────────────────────────────────────

  /**
   * Stop the stream and clean up.
   *
   * Guards against being called when never started (e.g. component unmount
   * before any stream was opened) — avoids orphan Firebase writes.
   */
  async stopConnection(): Promise<void> {
    if (!this.userId || !this.deviceUid) {
      // Never started — nothing to clean up in Firebase
      return;
    }
    console.log('[WebRTC] Stopping...');
    try {
      await set(this.liveStreamRef('liveStreamButton'), false);
      await this.updateConnectionState('disconnected');
    } catch { /* non-fatal */ }
    await this._internalCleanup();
  }

  // ── Internal cleanup (no Firebase writes) ────────────────────────────────────

  private async _internalCleanup(): Promise<void> {
    if (this.answerListener && this.userId && this.deviceUid) {
      off(this.liveStreamRef('answer'));
      this.answerListener = null;
    }
    if (this.raspiIceListener && this.userId && this.deviceUid) {
      off(this.liveStreamRef('iceCandidates/raspi'));
      this.raspiIceListener = null;
    }
    this.peerConnection?.close();
    this.peerConnection = null;
    this.remoteStream   = null;
    await this.cleanupFirebaseSignaling();
    this.iceStats      = { host: 0, srflx: 0, relay: 0 };
    this.isInitialized = false;
  }

  private async cleanupFirebaseSignaling(): Promise<void> {
    if (!this.userId || !this.deviceUid) return;
    try {
      await Promise.all([
        remove(this.liveStreamRef('offer')),
        remove(this.liveStreamRef('answer')),
        remove(this.liveStreamRef('iceCandidates/mobile')),
      ]);
    } catch { /* best-effort */ }
  }

  // ── Accessors ─────────────────────────────────────────────────────────────────

  getRemoteStream():      MediaStream | null { return this.remoteStream; }
  getConnectionState():   string { return (this.peerConnection as any)?.connectionState ?? 'unknown'; }
  isServiceInitialized(): boolean { return this.isInitialized; }
  getIceStats():          typeof this.iceStats { return { ...this.iceStats }; }
}

export default new WebRTCService();