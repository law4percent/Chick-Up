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
 */

interface WebRTCConfig {
  iceServers: Array<{
    urls: string | string[];
  }>;
}

// Google's free STUN servers for NAT traversal
const WEBRTC_CONFIG: WebRTCConfig = {
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' },
    { urls: 'stun:stun2.l.google.com:19302' },
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
      console.log('[WebRTC] Initializing service...');
      
      this.userId = userId;
      this.deviceUid = deviceUid;
      this.onRemoteStreamCallback = onRemoteStream;
      this.onConnectionStateCallback = onConnectionState || null;
      this.onErrorCallback = onError || null;
      
      // Create peer connection
      this.peerConnection = new RTCPeerConnection(WEBRTC_CONFIG);
      
      // Handle ICE candidates - Using _pc internal property for events
      (this.peerConnection as any)._pc.onicecandidate = (event: any) => {
        if (event.candidate) {
          this.sendIceCandidate(event.candidate);
        }
      };
      
      // Handle remote stream
      (this.peerConnection as any)._pc.onaddstream = (event: any) => {
        console.log('[WebRTC] Remote stream received');
        this.remoteStream = event.stream;
        if (this.onRemoteStreamCallback) {
          this.onRemoteStreamCallback(event.stream);
        }
      };
      
      // Handle connection state changes
      (this.peerConnection as any)._pc.onconnectionstatechange = () => {
        const state = this.peerConnection?.connectionState || 'unknown';
        console.log('[WebRTC] Connection state:', state);
        
        if (this.onConnectionStateCallback) {
          this.onConnectionStateCallback(state);
        }
        
        // Auto-cleanup on failure
        if (state === 'failed' || state === 'closed') {
          this.cleanup();
        }
      };
      
      // Handle ICE connection state
      (this.peerConnection as any)._pc.oniceconnectionstatechange = () => {
        const state = this.peerConnection?.iceConnectionState || 'unknown';
        console.log('[WebRTC] ICE connection state:', state);
      };
      
      this.isInitialized = true;
      console.log('[WebRTC] Service initialized successfully');
      
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
      
      // Clean up any existing signaling data
      await this.cleanupFirebaseSignaling();
      
      // Update connection state
      await this.updateConnectionState('connecting');
      
      // Create offer
      const offer = await this.peerConnection.createOffer({
        offerToReceiveVideo: true,
        offerToReceiveAudio: false, // We're only doing video
      });
      
      await this.peerConnection.setLocalDescription(offer);
      console.log('[WebRTC] Offer created');
      
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
          console.log('[WebRTC] Remote description set');
          
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
              console.log('[WebRTC] Added ICE candidate from Raspberry Pi');
              
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
      
      console.log('[WebRTC] ICE candidate sent to Firebase');
      
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
      const baseRef = ref(
        database,
        `liveStream/${this.userId}/${this.deviceUid}`
      );
      
      // Remove offer, answer, and ICE candidates
      await set(ref(database, `${baseRef.toString()}/offer`), null);
      await set(ref(database, `${baseRef.toString()}/answer`), null);
      await set(ref(database, `${baseRef.toString()}/iceCandidates/mobile`), null);
      await set(ref(database, `${baseRef.toString()}/iceCandidates/raspi`), null);
      
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
}

// Export singleton instance
export default new WebRTCService();