// src/services/liveStreamService.ts
import { database } from '../config/firebase.config';
import { ref, onValue, update, Unsubscribe } from 'firebase/database';

class LiveStreamService {
  subscribeLiveStream(
    userId: string,
    deviceUid: string,
    onData: (data: any) => void,
    onError: (error: Error) => void
  ): Unsubscribe {
    const streamRef = ref(database, `liveStream/${userId}/${deviceUid}`);
    
    return onValue(
      streamRef,
      (snapshot) => {
        const data = snapshot.val();
        onData(data);
      },
      onError
    );
  }

  async toggleLiveStream(userId: string, deviceUid: string, enabled: boolean): Promise<void> {
    const streamRef = ref(database, `liveStream/${userId}/${deviceUid}`);
    const now = new Date();
    const timestamp = `${now.toLocaleDateString()} ${now.toLocaleTimeString()}`;

    await update(streamRef, {
      liveStreamButton: enabled,
      lastUpdateAt: timestamp,
      ...(enabled ? {} : { base64: '' })
    });
  }
}

export default new LiveStreamService();