// src/services/webrtcService.ts
import { 
  RTCPeerConnection, 
  RTCIceCandidate, 
  RTCSessionDescription,
  MediaStream,
  mediaDevices
} from 'react-native-webrtc';
import { database } from '../config/firebase.config';
import { ref, set, onValue, push, remove, off } from 'firebase/database';

/**
 * WebRTC Service for React Native
 * Handles peer-to-peer video streaming with Raspberry Pi
 * Uses Firebase Realtime Database for signaling
 * NOW WITH TURN SERVER SUPPORT FOR BETTER NAT TRAVERSAL
 */

interface WebRTCConfig {
  iceServers: Array<{
    urls: string | string[];
    username?: string;
    credential?: string;
  }>;
}

// UPDATED: Added TURN server configuration
// REPLACE THESE VALUES WITH YOUR TURN SERVER DETAILS
const TURN_SERVER_URL = 'turn:YOUR_VPS_PUBLIC_IP:3478';
const TURN_USERNAME = 'webrtc';
const TURN_PASSWORD = 'YOUR_STRONG_PASSWORD';

const WEBRTC_CONFIG: WebRTCConfig = {
  iceServers: [
    // Google's free STUN servers (for NAT traversal detection)
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' },
    
    // YOUR TURN SERVER (relay fallback for difficult NAT situations)
    { 
      urls: TURN_SERVER_URL,
      username: TURN_USERNAME,
      credential: TURN_PASSWORD
    },
    
    // Optional: Add more public TURN servers as backup
    // WARNING: Free public TURN servers are unreliable, use your own
  ],
};

class WebRTCService {
  private peerConnection: RTCPeerConnection | null = null;
  private remoteStream: MediaStream | null = null;
  private userId: string | null = null;
  private deviceUid: string | null = null;
  private isInitialized: boolean = false;
  
  // Firebase listeners
  private answerListener: (() => void) | null = null;
  private raspiIceListener: (() => void) | null = null;
  
  // Callbacks
  private onRemoteStreamCallback: ((stream: MediaStream) => void) | null = null;
  private onConnectionStateCallback: ((state: string) => void) | null = null;
  private onErrorCallback: ((error: Error) => void) | null = null;

  // NEW: Track ICE candidate types for diagnostics
  private iceStats = {
    host: 0,
    srflx: 0,
    relay: 0,
  };

  /**
   * Initialize WebRTC service
   */
  async initialize(
    userId: string,
    deviceUid: string,
    onRemoteStream: (stream: MediaStream) => void,
    onConnectionState?: (state: string) => void,
    onError?: (error: Error) => void
  ): Promise<void> {
    try {
      console.log('[WebRTC] Initializing service with TURN support...');
      
      this.userId = userId;
      this.deviceUid = deviceUid;
      this.onRemoteStreamCallback = onRemoteStream;
      this.onConnectionStateCallback = onConnectionState || null;
      this.onErrorCallback = onError || null;
      
      // Create peer connection
      this.peerConnection = new RTCPeerConnection(WEBRTC_CONFIG);
      
      // Cast to any to satisfy TypeScript
      const pc = this.peerConnection as any;
      
      // Handle ICE candidates
      pc.onicecandidate = (event: any) => {
        if (event.candidate) {
          // NEW: Track candidate types for diagnostics
          const candidateStr = event.candidate.candidate;
          if (candidateStr.includes('typ host')) {
            this.iceStats.host++;
            console.log('[WebRTC] 🏠 Host candidate generated');
          } else if (candidateStr.includes('typ srflx')) {
            this.iceStats.srflx++;
            console.log('[WebRTC] 🌐 Server reflexive candidate generated (STUN)');
          } else if (candidateStr.includes('typ relay')) {
            this.iceStats.relay++;
            console.log('[WebRTC] 🔄 Relay candidate generated (TURN) - Good for difficult NATs!');
          }
          
          this.sendIceCandidate(event.candidate);
        }
      };
      
      // NEW: Handle ICE gathering state
      pc.onicegatheringstatechange = () => {
        const state = this.peerConnection?.iceGatheringState || 'unknown';
        console.log('[WebRTC] ICE gathering state:', state);
        
        if (state === 'complete') {
          console.log('[WebRTC] 📊 ICE gathering complete. Stats:', this.iceStats);
          
          // Warning if no relay candidates (TURN might not be working)
          if (this.iceStats.relay === 0) {
            console.warn('[WebRTC] ⚠️ No TURN relay candidates! Check TURN server config.');
            console.warn('[WebRTC] Connection may fail on strict NATs/firewalls.');
          }
        }
      };
      
      // Handle remote tracks
      pc.ontrack = (event: any) => {
        console.log('[WebRTC] 🎥 Remote track received:', event.track.kind);
        
        if (event.streams && event.streams.length > 0) {
          console.log('[WebRTC] ✅ Remote stream available');
          this.remoteStream = event.streams[0];
          
          if (this.onRemoteStreamCallback) {
            this.onRemoteStreamCallback(event.streams[0]);
          }
        } else {
          console.log('[WebRTC] Creating stream from track');
          if (!this.remoteStream) {
            this.remoteStream = new MediaStream();
          }
          this.remoteStream.addTrack(event.track);
          
          if (this.onRemoteStreamCallback) {
            this.onRemoteStreamCallback(this.remoteStream);
          }
        }
      };
      
      // Handle connection state changes
      pc.onconnectionstatechange = () => {
        const state = this.peerConnection?.connectionState || 'unknown';
        console.log('[WebRTC] Connection state:', state);
        
        if (this.onConnectionStateCallback) {
          this.onConnectionStateCallback(state);
        }
        
        // Auto-cleanup on failure
        if (state === 'failed' || state === 'closed') {
          console.log('[WebRTC] 📊 Final ICE stats:', this.iceStats);
          this.cleanup();
        }
        
        // NEW: Log success with candidate info
        if (state === 'connected') {
          console.log('[WebRTC] 🎉 Connected! Used candidates:', this.iceStats);
        }
      };
      
      // Handle ICE connection state
      pc.oniceconnectionstatechange = () => {
        const state = this.peerConnection?.iceConnectionState || 'unknown';
        console.log('[WebRTC] ICE connection state:', state);
        
        // NEW: Detailed diagnostics for failed connections
        if (state === 'failed') {
          console.error('[WebRTC] ❌ ICE connection failed!');
          console.error('[WebRTC] Candidates generated:', this.iceStats);
          console.error('[WebRTC] Possible issues:');
          if (this.iceStats.relay === 0) {
            console.error('  - TURN server not reachable or misconfigured');
          }
          console.error('  - Firewall blocking UDP ports');
          console.error('  - Symmetric NAT on both sides');
        }
      };
      
      this.isInitialized = true;
      console.log('[WebRTC] Service initialized successfully with TURN support');
      
    } catch (error) {
      console.error('[WebRTC] Initialization error:', error);
      if (this.onErrorCallback) {
        this.onErrorCallback(error as Error);
      }
      throw error;
    }
  }

  /**
   * Start WebRTC connection
   * Creates offer and sends to Raspberry Pi via Firebase
   */
  async startConnection(): Promise<void> {
    if (!this.isInitialized || !this.peerConnection) {
      throw new Error('WebRTC service not initialized');
    }
    
    if (!this.userId || !this.deviceUid) {
      throw new Error('User ID or Device UID not set');
    }
    
    try {
      console.log('[WebRTC] Starting connection...');
      
      // Reset ICE stats
      this.iceStats = { host: 0, srflx: 0, relay: 0 };
      
      // Clean up any existing signaling data
      await this.cleanupFirebaseSignaling();
      
      // Update connection state
      await this.updateConnectionState('connecting');
      
      // Create offer
      const offer = await this.peerConnection.createOffer({
        offerToReceiveVideo: true,
        offerToReceiveAudio: false,
      });
      
      await this.peerConnection.setLocalDescription(offer);
      console.log('[WebRTC] Offer created and set as local description');
      
      // Send offer to Raspberry Pi via Firebase
      const offerRef = ref(
        database,
        `liveStream/${this.userId}/${this.deviceUid}/offer`
      );
      
      await set(offerRef, {
        sdp: offer.sdp,
        type: offer.type,
        timestamp: Date.now(),
      });
      
      console.log('[WebRTC] Offer sent to Firebase');
      
      // Listen for answer from Raspberry Pi
      this.listenForAnswer();
      
      // Listen for ICE candidates from Raspberry Pi
      this.listenForRaspiIceCandidates();
      
    } catch (error) {
      console.error('[WebRTC] Error starting connection:', error);
      await this.updateConnectionState('failed');
      if (this.onErrorCallback) {
        this.onErrorCallback(error as Error);
      }
      throw error;
    }
  }

  /**
   * Listen for answer from Raspberry Pi
   */
  private listenForAnswer(): void {
    if (!this.userId || !this.deviceUid) return;
    
    const answerRef = ref(
      database,
      `liveStream/${this.userId}/${this.deviceUid}/answer`
    );
    
    this.answerListener = onValue(answerRef, async (snapshot) => {
      const answer = snapshot.val();
      
      if (answer && answer.sdp && this.peerConnection) {
        try {
          console.log('[WebRTC] Answer received from Raspberry Pi');
          
          const remoteDescription = new RTCSessionDescription({
            sdp: answer.sdp,
            type: answer.type,
          });
          
          await this.peerConnection.setRemoteDescription(remoteDescription);
          console.log('[WebRTC] ✅ Remote description set successfully');
          
          // Stop listening for answer once received
          if (this.answerListener) {
            off(answerRef);
            this.answerListener = null;
          }
          
        } catch (error) {
          console.error('[WebRTC] Error setting remote description:', error);
          if (this.onErrorCallback) {
            this.onErrorCallback(error as Error);
          }
        }
      }
    });
  }

  /**
   * Listen for ICE candidates from Raspberry Pi
   */
  private listenForRaspiIceCandidates(): void {
    if (!this.userId || !this.deviceUid) return;
    
    const iceCandidatesRef = ref(
      database,
      `liveStream/${this.userId}/${this.deviceUid}/iceCandidates/raspi`
    );
    
    this.raspiIceListener = onValue(iceCandidatesRef, async (snapshot) => {
      const candidates = snapshot.val();
      
      if (candidates && this.peerConnection) {
        // Process each candidate
        for (const key in candidates) {
          const candidateData = candidates[key];
          
          if (candidateData && candidateData.candidate) {
            try {
              const candidate = new RTCIceCandidate({
                candidate: candidateData.candidate,
                sdpMid: candidateData.sdpMid,
                sdpMLineIndex: candidateData.sdpMLineIndex,
              });
              
              await this.peerConnection.addIceCandidate(candidate);
              
              // NEW: Log candidate type from Raspberry Pi
              const candidateStr = candidateData.candidate;
              if (candidateStr.includes('typ relay')) {
                console.log('[WebRTC] ✅ Added TURN relay candidate from Raspberry Pi');
              } else {
                console.log('[WebRTC] ✅ Added ICE candidate from Raspberry Pi');
              }
              
            } catch (error) {
              console.error('[WebRTC] Error adding ICE candidate:', error);
            }
          }
        }
        
        // Stop listening once connected
        if (this.peerConnection.connectionState === 'connected') {
          if (this.raspiIceListener) {
            off(iceCandidatesRef);
            this.raspiIceListener = null;
          }
        }
      }
    });
  }

  /**
   * Send ICE candidate to Raspberry Pi via Firebase
   */
  private async sendIceCandidate(candidate: RTCIceCandidate): Promise<void> {
    if (!this.userId || !this.deviceUid) return;
    
    try {
      const iceCandidatesRef = ref(
        database,
        `liveStream/${this.userId}/${this.deviceUid}/iceCandidates/mobile`
      );
      
      const candidateRef = push(iceCandidatesRef);
      
      await set(candidateRef, {
        candidate: candidate.candidate,
        sdpMid: candidate.sdpMid,
        sdpMLineIndex: candidate.sdpMLineIndex,
        timestamp: Date.now(),
      });
      
      console.log('[WebRTC] ✅ ICE candidate sent to Firebase');
      
    } catch (error) {
      console.error('[WebRTC] Error sending ICE candidate:', error);
    }
  }

  /**
   * Update connection state in Firebase
   */
  private async updateConnectionState(state: string): Promise<void> {
    if (!this.userId || !this.deviceUid) return;
    
    try {
      const stateRef = ref(
        database,
        `liveStream/${this.userId}/${this.deviceUid}/connectionState`
      );
      
      await set(stateRef, state);
      
    } catch (error) {
      console.error('[WebRTC] Error updating connection state:', error);
    }
  }

  /**
   * Clean up Firebase signaling data
   */
  private async cleanupFirebaseSignaling(): Promise<void> {
    if (!this.userId || !this.deviceUid) return;
    
    try {
      const offerRef = ref(database, `liveStream/${this.userId}/${this.deviceUid}/offer`);
      const answerRef = ref(database, `liveStream/${this.userId}/${this.deviceUid}/answer`);
      const mobileIceRef = ref(database, `liveStream/${this.userId}/${this.deviceUid}/iceCandidates/mobile`);
      const raspiIceRef = ref(database, `liveStream/${this.userId}/${this.deviceUid}/iceCandidates/raspi`);
      
      await Promise.all([
        remove(offerRef),
        remove(answerRef),
        remove(mobileIceRef),
        remove(raspiIceRef)
      ]);
      
      console.log('[WebRTC] Firebase signaling data cleaned up');
      
    } catch (error) {
      console.error('[WebRTC] Error cleaning up Firebase signaling:', error);
    }
  }

  /**
   * Stop WebRTC connection and cleanup
   */
  async stopConnection(): Promise<void> {
    console.log('[WebRTC] Stopping connection...');
    
    try {
      // Update connection state
      await this.updateConnectionState('disconnected');
      
      // Clean up
      await this.cleanup();
      
      console.log('[WebRTC] Connection stopped');
      
    } catch (error) {
      console.error('[WebRTC] Error stopping connection:', error);
    }
  }

  /**
   * Cleanup WebRTC resources
   */
  private async cleanup(): Promise<void> {
    console.log('[WebRTC] Cleaning up resources...');
    
    // Remove Firebase listeners
    if (this.answerListener && this.userId && this.deviceUid) {
      const answerRef = ref(
        database,
        `liveStream/${this.userId}/${this.deviceUid}/answer`
      );
      off(answerRef);
      this.answerListener = null;
    }
    
    if (this.raspiIceListener && this.userId && this.deviceUid) {
      const iceCandidatesRef = ref(
        database,
        `liveStream/${this.userId}/${this.deviceUid}/iceCandidates/raspi`
      );
      off(iceCandidatesRef);
      this.raspiIceListener = null;
    }
    
    // Close peer connection
    if (this.peerConnection) {
      this.peerConnection.close();
      this.peerConnection = null;
    }
    
    // Clear remote stream
    this.remoteStream = null;
    
    // Clean up Firebase signaling data
    await this.cleanupFirebaseSignaling();
    
    // Reset stats
    this.iceStats = { host: 0, srflx: 0, relay: 0 };
    
    this.isInitialized = false;
    
    console.log('[WebRTC] Cleanup complete');
  }

  /**
   * Get current remote stream
   */
  getRemoteStream(): MediaStream | null {
    return this.remoteStream;
  }

  /**
   * Get current connection state
   */
  getConnectionState(): string {
    return this.peerConnection?.connectionState || 'unknown';
  }

  /**
   * Check if service is initialized
   */
  isServiceInitialized(): boolean {
    return this.isInitialized;
  }
  
  /**
   * NEW: Get ICE candidate statistics
   */
  getIceStats() {
    return { ...this.iceStats };
  }
}

// Export singleton instance
export default new WebRTCService();