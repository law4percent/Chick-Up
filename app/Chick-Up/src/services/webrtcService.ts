// src/services/webrtcService.ts
import {
  RTCPeerConnection,
  RTCIceCandidate,
  RTCSessionDescription,
  MediaStream,
} from 'react-native-webrtc';
import { database } from '../config/firebase.config';
import { ref, set, onValue, push, remove, off, get } from 'firebase/database';
import { TurnServerConfig } from '../types/types';

/**
 * WebRTC Service — signaling via Firebase RTDB, video relay via TURN.
 *
 * TURN config is loaded from Firebase at stream-start, NOT hardcoded.
 * Path: settings/{userId}/turnServer/  (TurnServerConfig shape)
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

// ─────────────────────────── TURN URL NORMALIZATION ──────────────────────────

/**
 * Strip any scheme prefix (turn: / turns: / stun:) then rebuild correctly.
 * Matches the normalization in webrtc_peer.py so both sides produce valid URIs
 * regardless of how the URL is stored in Firebase.
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

interface RTCIceServer {
  urls: string | string[];
  username?: string;
  credential?: string;
}

function buildIceServers(turn: TurnServerConfig | null): RTCIceServer[] {
  const servers: RTCIceServer[] = [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' },
  ];

  if (turn) {
    const host = normalizeTurnHost(turn.serverUrl);
    servers.push({
      urls: [
        `turn:${host}?transport=udp`,  // UDP first — lower latency
        `turn:${host}?transport=tcp`,  // TCP fallback for CGNAT / strict firewall
      ],
      username:   turn.username,
      credential: turn.password,
    });
  }

  return servers;
}

// ─────────────────────────── SERVICE ─────────────────────────────────────────

class WebRTCService {
  private peerConnection: RTCPeerConnection | null = null;
  private remoteStream:   MediaStream | null = null;
  private userId:         string | null = null;
  private deviceUid:      string | null = null;
  private isInitialized:  boolean = false;

  private answerListener:   (() => void) | null = null;
  private raspiIceListener: (() => void) | null = null;

  private onRemoteStreamCallback:    ((stream: MediaStream) => void) | null = null;
  private onConnectionStateCallback: ((state: string) => void) | null = null;
  private onErrorCallback:           ((error: Error) => void) | null = null;

  private iceStats = { host: 0, srflx: 0, relay: 0 };

  // ── Path helper ──────────────────────────────────────────────────────────────

  private liveStreamRef(subpath: string) {
    return ref(database, `liveStream/${this.userId}/${this.deviceUid}/${subpath}`);
  }

  // ── Load TURN config from Firebase ───────────────────────────────────────────

  /**
   * Reads TurnServerConfig from settings/{userId}/turnServer/.
   * Returns null silently if not configured — gracefully falls back to STUN only.
   */
  private async loadTurnConfig(): Promise<TurnServerConfig | null> {
    if (!this.userId) return null;
    try {
      const snap = await get(ref(database, `settings/${this.userId}/turnServer`));
      if (!snap.exists()) {
        console.warn('[WebRTC] ⚠️ No TURN config found at settings/{userId}/turnServer');
        console.warn('[WebRTC]   Connection may fail on CGNAT mobile networks.');
        return null;
      }
      const cfg = snap.val() as TurnServerConfig;
      if (!cfg.serverUrl || !cfg.username || !cfg.password) {
        console.warn('[WebRTC] ⚠️ TURN config is incomplete — missing serverUrl/username/password');
        return null;
      }
      console.log('[WebRTC] ✅ TURN config loaded:', cfg.serverUrl);
      return cfg;
    } catch (e) {
      console.warn('[WebRTC] ⚠️ Could not load TURN config from Firebase:', e);
      return null;
    }
  }

  // ── Initialize ────────────────────────────────────────────────────────────────

  async initialize(
    userId:             string,
    deviceUid:          string,
    onRemoteStream:     (stream: MediaStream) => void,
    onConnectionState?: (state: string) => void,
    onError?:           (error: Error) => void,
  ): Promise<void> {
    try {
      console.log('[WebRTC] Initializing with Firebase TURN config...');

      this.userId    = userId;
      this.deviceUid = deviceUid;
      this.onRemoteStreamCallback    = onRemoteStream;
      this.onConnectionStateCallback = onConnectionState ?? null;
      this.onErrorCallback           = onError ?? null;

      // Load TURN from Firebase — never hardcoded
      const turnConfig = await this.loadTurnConfig();

      this.peerConnection = new RTCPeerConnection({
        iceServers: buildIceServers(turnConfig),
      });
      const pc = this.peerConnection as any;

      pc.onicecandidate = (event: any) => {
        if (!event.candidate) return;
        const c: string = event.candidate.candidate;
        if (c.includes('typ host'))  { this.iceStats.host++;  console.log('[WebRTC] 🏠 host candidate'); }
        if (c.includes('typ srflx')) { this.iceStats.srflx++; console.log('[WebRTC] 🌐 srflx (STUN)'); }
        if (c.includes('typ relay')) { this.iceStats.relay++; console.log('[WebRTC] 🔄 relay (TURN) ✅'); }
        this.sendIceCandidate(event.candidate);
      };

      pc.onicegatheringstatechange = () => {
        console.log('[WebRTC] ICE gathering:', pc.iceGatheringState);
        if (pc.iceGatheringState === 'complete') {
          console.log('[WebRTC] 📊 ICE stats:', this.iceStats);
          if (this.iceStats.relay === 0) {
            console.warn('[WebRTC] ⚠️ No relay candidates — TURN server may be unreachable or misconfigured.');
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
          this.cleanup();
        }
      };

      pc.oniceconnectionstatechange = () => {
        const state: string = pc.iceConnectionState ?? 'unknown';
        console.log('[WebRTC] ICE connection:', state);
        if (state === 'failed') {
          console.error('[WebRTC] ❌ ICE failed. Stats:', this.iceStats);
          if (this.iceStats.relay === 0) {
            console.error('[WebRTC]   → No relay candidates — add TURN config to Firebase: settings/{userId}/turnServer');
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
      console.log('[WebRTC] Offer sent to Firebase');

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
    }) as any;
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
          console.log(`[WebRTC] ✅ Added raspi ICE${isRelay ? ' 🔄 TURN relay' : ''}`);
        } catch (e) {
          console.error('[WebRTC] addIceCandidate error:', e);
        }
      }

      if ((this.peerConnection as any).connectionState === 'connected') {
        off(iceCandidatesRef);
        this.raspiIceListener = null;
      }
    }) as any;
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

  async stopConnection(): Promise<void> {
    console.log('[WebRTC] Stopping...');
    try {
      if (this.userId && this.deviceUid) {
        await set(this.liveStreamRef('liveStreamButton'), false);
        await this.updateConnectionState('disconnected');
      }
      await this.cleanup();
    } catch (e) {
      console.error('[WebRTC] stopConnection error:', e);
    }
  }

  // ── Cleanup ───────────────────────────────────────────────────────────────────

  private async cleanup(): Promise<void> {
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
    console.log('[WebRTC] Cleanup complete');
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