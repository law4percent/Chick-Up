import React, { useEffect, useState } from "react";
import { View } from "react-native";
import { RTCPeerConnection, mediaDevices, RTCView } from "react-native-webrtc";
import firestore from "@react-native-firebase/firestore";

export default function Viewer() {
  const [stream, setStream] = useState(null);

  useEffect(() => {
    const pc = new RTCPeerConnection();

    pc.onaddstream = (event) => {
      setStream(event.stream);
    };

    const run = async () => {
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      await firestore().collection("webrtc").doc("offer").set({
        sdp: offer.sdp,
        type: "offer",
      });

      // Wait for Raspberry Pi answer
      firestore().collection("webrtc").doc("answer")
        .onSnapshot(async (doc) => {
          const data = doc.data();
          if (data && data.sdp) {
            await pc.setRemoteDescription({
              type: "answer",
              sdp: data.sdp,
            });
          }
        });

      // ICE candidates from Pi
      firestore().collection("webrtc").doc("raspi_ice")
        .onSnapshot((doc) => {
          const data = doc.data();
          if (data && data.candidate) {
            pc.addIceCandidate(data.candidate);
          }
        });

      // Viewer ICE
      pc.onicecandidate = (event) => {
        if (event.candidate) {
          firestore().collection("webrtc").doc("viewer_ice").set({
            candidate: event.candidate.toJSON(),
          });
        }
      };
    };

    run();
  }, []);

  return (
    <View style={{ flex: 1 }}>
      {stream && <RTCView streamURL={stream.toURL()} style={{ flex: 1 }} />}
    </View>
  );
}
