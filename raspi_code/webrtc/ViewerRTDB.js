import React, { useEffect, useState } from "react";
import { View } from "react-native";
import { RTCPeerConnection, RTCView } from "react-native-webrtc";
import database from "@react-native-firebase/database";

export default function ViewerRTDB() {
  const [stream, setStream] = useState(null);

  useEffect(() => {
    const pc = new RTCPeerConnection();

    pc.onaddstream = (event) => {
      setStream(event.stream);
    };

    const run = async () => {
      // Create offer
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      await database().ref("webrtc/offer").set({
        sdp: offer.sdp,
      });

      // Listen for answer
      database()
        .ref("webrtc/answer/sdp")
        .on("value", async (snapshot) => {
          const sdp = snapshot.val();
          if (sdp) {
            await pc.setRemoteDescription({
              type: "answer",
              sdp: sdp,
            });
          }
        });

      // Send ICE to Pi
      pc.onicecandidate = (event) => {
        if (event.candidate) {
          database()
            .ref("webrtc/ice/viewer")
            .push(event.candidate.toJSON());
        }
      };

      // Listen for Pi ICE candidates
      database()
        .ref("webrtc/ice/raspi")
        .on("child_added", (snapshot) => {
          const cand = snapshot.val();
          pc.addIceCandidate(cand);
        });
    };

    run();
  }, []);

  return (
    <View style={{ flex: 1 }}>
      {stream && (
        <RTCView streamURL={stream.toURL()} style={{ flex: 1 }} />
      )}
    </View>
  );
}
