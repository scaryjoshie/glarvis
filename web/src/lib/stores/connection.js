import { writable } from 'svelte/store';

export const connectionState = writable('disconnected'); // disconnected | connecting | connected
export const agentState = writable('idle'); // idle | listening | thinking | speaking

export const tasks = writable([]);
export const transcript = writable([]);
export const boardContent = writable('');

let ws = null;
let pc = null;
let localStream = null;
let pcId = null;

export function connectWebSocket() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${protocol}//${location.host}/ws`);

  ws.onopen = () => console.log('[WS] Connected');

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    switch (msg.type) {
      case 'task_update':
        tasks.set(msg.tasks);
        break;
      case 'board_post':
        boardContent.set(msg.content);
        break;
      case 'transcript_add':
        transcript.update(t => [...t, msg.entry]);
        break;
      case 'agent_state':
        agentState.set(msg.state);
        break;
    }
  };

  ws.onclose = () => {
    console.log('[WS] Disconnected');
  };
}

export async function connectWebRTC() {
  connectionState.set('connecting');

  try {
    localStream = await navigator.mediaDevices.getUserMedia({ audio: true });

    pc = new RTCPeerConnection();

    // Add mic track
    localStream.getTracks().forEach(track => pc.addTrack(track, localStream));

    // Play received audio
    pc.ontrack = (event) => {
      console.log('[WebRTC] Got remote track');
      const audio = new Audio();
      audio.srcObject = event.streams[0];
      audio.play().catch(e => console.warn('[WebRTC] Audio autoplay blocked:', e));
    };

    // Collect ICE candidates to send to server
    const pendingCandidates = [];
    let canSendCandidates = false;

    pc.onicecandidate = (event) => {
      if (event.candidate) {
        const candidate = {
          candidate: event.candidate.candidate,
          sdpMid: event.candidate.sdpMid,
          sdpMLineIndex: event.candidate.sdpMLineIndex,
        };
        if (canSendCandidates && pcId) {
          // Send immediately
          fetch('/webrtc/ice', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pc_id: pcId, candidates: [candidate] }),
          }).catch(e => console.error('[WebRTC] Failed to send ICE candidate:', e));
        } else {
          pendingCandidates.push(candidate);
        }
      }
    };

    pc.onconnectionstatechange = () => {
      console.log('[WebRTC] Connection state:', pc.connectionState);
      if (pc.connectionState === 'connected') {
        connectionState.set('connected');
      } else if (pc.connectionState === 'failed' || pc.connectionState === 'closed') {
        connectionState.set('disconnected');
      }
    };

    // Create offer
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    // Send offer to server
    const response = await fetch('/webrtc/offer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sdp: offer.sdp,
        type: offer.type,
      }),
    });

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }

    const answer = await response.json();
    pcId = answer.pc_id;

    await pc.setRemoteDescription(new RTCSessionDescription({
      sdp: answer.sdp,
      type: answer.type,
    }));

    // Now send any buffered ICE candidates
    canSendCandidates = true;
    if (pendingCandidates.length > 0 && pcId) {
      fetch('/webrtc/ice', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pc_id: pcId, candidates: pendingCandidates }),
      }).catch(e => console.error('[WebRTC] Failed to send buffered ICE candidates:', e));
    }

  } catch (err) {
    console.error('[WebRTC] Connection failed:', err);
    connectionState.set('disconnected');
  }
}

export function sendText(text) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'user_text', text }));
  }
}

export function disconnect() {
  if (pc) {
    pc.close();
    pc = null;
  }
  if (localStream) {
    localStream.getTracks().forEach(t => t.stop());
    localStream = null;
  }
  if (ws) {
    ws.close();
    ws = null;
  }
  pcId = null;
  connectionState.set('disconnected');
}
