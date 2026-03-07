import { writable } from 'svelte/store';
import { WebviewWindow, getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow';
import { listen, emitTo } from '@tauri-apps/api/event';

export const connectionState = writable('disconnected'); // disconnected | connecting | connected
export const agentState = writable('idle'); // idle | listening | thinking | speaking
export const muted = writable(false);
export const deafened = writable(false);
export const voiceMuted = writable(false); // server-side voice gate (say "mute"/"unmute")

export const tasks = writable([]);
export const transcript = writable([]);
export const boardStream = writable([]);    // array of {author, content, timestamp}
export const boardFocused = writable(null);  // currently focused item index
export const modelDisplay = writable('');    // current model name for status bar
export const settingsOpen = writable(false); // settings modal visibility
export const settingsData = writable({ llm: {}, tts: {}, stt: {}, services: {} }); // cached settings

// ── Volume stores (persisted in localStorage) ────────────────────────────────

function storedVolume(key, defaultVal) {
  const stored = localStorage.getItem(key);
  const initial = stored !== null ? parseFloat(stored) : defaultVal;
  const store = writable(isNaN(initial) ? defaultVal : initial);
  store.subscribe(v => { try { localStorage.setItem(key, v.toString()); } catch {} });
  return store;
}

export const sfxVolume = storedVolume('minerva_sfx_vol', 0.5);
export const voiceVolume = storedVolume('minerva_voice_vol', 1.0);

// ── Sound effects ────────────────────────────────────────────────────────────

function playSound(name) {
  try {
    let vol;
    const unsub = sfxVolume.subscribe(v => vol = v);
    unsub();
    if (vol === 0) return;
    const audio = new Audio(`/sounds/${name}.mp3`);
    audio.volume = Math.min(vol, 1.0);
    audio.play().catch(e => {
      // Ignore aborts from rapid interaction and autoplay blocks
      if (e.name !== 'AbortError' && e.name !== 'NotAllowedError') {
        console.warn(`[Sound] Failed to play ${name}:`, e);
      }
    });
  } catch (e) {
    console.warn(`[Sound] Error setting up audio:`, e);
  }
}

let ws = null;

// ── Popup management (Tauri native windows) ──────────────────────────────────

const openPopups = new Map(); // tool_name → WebviewWindow
const pendingPopupData = new Map(); // label → data (held until popup requests it)

// Popup requests its data after JS loads
listen('popup-request-data', async (event) => {
  const { label } = event.payload;
  const data = pendingPopupData.get(label);
  if (data) {
    await emitTo(label, 'popup-data', data);
    pendingPopupData.delete(label);
  }
});

// Listen for popup actions from overlay windows via Tauri events
listen('popup-action', (event) => {
  const { tool_name, action, data } = event.payload;
  if (action === 'board_reply' && data?.message) {
    sendText(data.message);
  } else {
    sendPopupAction(tool_name, action, data || {});
  }
});

export async function openPopup(popupType, toolName, data) {
  await closePopup(toolName);
  const routeStr = encodeURIComponent(JSON.stringify({ popupType, toolName }));
  const label = `popup_${toolName}`;

  // Scale height to content: ~49px per option + prompt(45) + bottom row(46) + popup padding(16)
  const optionCount = data?.options?.length || 3;
  const height = Math.min(optionCount * 49 + 120, 640);

  console.log('[Popup] Opening Tauri window:', popupType, toolName);
  const overlay = new WebviewWindow(label, {
    url: `popup.html#${routeStr}`,
    title: 'Minerva',
    width: 520,
    height,
    decorations: false,
    alwaysOnTop: true,
    center: true,
    resizable: false,
    skipTaskbar: true,
    focus: true,
  });

  pendingPopupData.set(label, data);
  overlay.once('tauri://created', () => overlay.setFocus());

  openPopups.set(toolName, overlay);
}

export async function closePopup(toolName) {
  const win = openPopups.get(toolName);
  if (win) {
    try { await win.close(); } catch {}
  }
  openPopups.delete(toolName);
}

async function showBoardNotifyIfUnfocused(author, content) {
  try {
    const focused = await getCurrentWebviewWindow().isFocused();
    if (focused) return;
  } catch {
    console.warn('[BoardNotify] Focus check failed, assuming unfocused');
  }

  try {
    const label = 'popup_board_notify';
    const routeStr = encodeURIComponent(JSON.stringify({
      popupType: 'board_notify',
      toolName: 'board_notify',
    }));
    await closePopup('board_notify');
    const overlay = new WebviewWindow(label, {
      url: `popup.html#${routeStr}`,
      title: 'Minerva',
      width: 720,
      height: 420,
      decorations: false,
      alwaysOnTop: true,
      x: Math.round(screen.width / 2 - 360),
      y: 40,
      resizable: true,
      skipTaskbar: true,
      focus: true,
    });
    pendingPopupData.set(label, { author, content });
    overlay.once('tauri://created', () => overlay.setFocus());
    openPopups.set('board_notify', overlay);
  } catch (e) {
    console.warn('[BoardNotify] Failed to open popup:', e);
  }
}

function sendPopupAction(toolName, action, data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'popup_action', tool_name: toolName, action, data }));
  }
}
let pc = null;
let localStream = null;
let pcId = null;
let wsIntentionallyClosed = false;
let wsReconnectDelay = 1000;
let wsReconnectTimer = null;

export function connectWebSocket() {
  wsIntentionallyClosed = false;
  wsReconnectDelay = 1000;
  _connectWs();
}

function _connectWs() {
  if (wsReconnectTimer) {
    clearTimeout(wsReconnectTimer);
    wsReconnectTimer = null;
  }
  if (ws) {
    ws.onclose = null; // detach so old close doesn't null out the new ws
    ws.close();
    ws = null;
  }
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${protocol}//${location.host}/ws`);

  ws.onopen = () => {
    console.log('[WS] Connected');
    wsReconnectDelay = 1000; // reset backoff on success
    requestSettings();
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    switch (msg.type) {
      case 'task_update':
        tasks.set(msg.tasks);
        break;
      case 'board_post':
        boardStream.update(s => {
          const next = [...s, {
            author: msg.author,
            content: msg.content,
            timestamp: msg.timestamp,
          }];
          boardFocused.set(next.length - 1);
          return next;
        });
        if (msg.notify) {
          showBoardNotifyIfUnfocused(msg.author, msg.content);
        }
        break;
      case 'transcript_add':
        transcript.update(t => [...t, msg.entry]);
        break;
      case 'agent_state':
        agentState.set(msg.state);
        break;
      case 'mute_state':
        voiceMuted.set(msg.muted);
        playSound(msg.muted ? 'mute' : 'unmute');
        break;
      case 'popup_open':
        openPopup(msg.popup_type, msg.tool_name, msg.data);
        break;
      case 'popup_close':
        closePopup(msg.tool_name);
        break;
      case 'model_info':
        modelDisplay.set(msg.model_display);
        break;
      case 'settings':
        settingsData.set({
          llm: msg.llm || {},
          tts: msg.tts || {},
          stt: msg.stt || {},
          services: msg.services || {},
        });
        break;
      case 'settings_saved':
        modelDisplay.set(msg.model_display);
        break;
    }
  };

  ws.onclose = () => {
    console.log('[WS] Disconnected');
    ws = null;
    if (!wsIntentionallyClosed) {
      // Always reconnect WS unless user explicitly disconnected
      console.log(`[WS] Reconnecting in ${wsReconnectDelay}ms...`);
      wsReconnectTimer = setTimeout(() => {
        _connectWs();
        wsReconnectDelay = Math.min(wsReconnectDelay * 2, 16000);
      }, wsReconnectDelay);
    }
  };
}

export async function connectWebRTC() {
  clearSessionState();
  connectionState.set('connecting');

  try {
    localStream = await navigator.mediaDevices.getUserMedia({ audio: true });

    pc = new RTCPeerConnection();

    // Add mic track
    localStream.getTracks().forEach(track => pc.addTrack(track, localStream));

    // Play received audio
    pc.ontrack = (event) => {
      console.log('[WebRTC] Got remote track');
      remoteAudio = new Audio();
      remoteAudio.srcObject = event.streams[0];
      let vol;
      const unsub = voiceVolume.subscribe(v => vol = v);
      unsub();
      remoteAudio.volume = Math.min(vol, 1.0);
      remoteAudio.play().catch(err => console.warn('[WebRTC] Audio autoplay blocked:', err));
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
        playSound('join');
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

let remoteAudio = null;

// Live-update volume when slider moves
voiceVolume.subscribe(v => {
  if (remoteAudio) remoteAudio.volume = Math.min(v, 1.0);
});

export function toggleMute() {
  if (!localStream) return;

  // If soft-muted, clicking unmutes the server gate (not a local mic toggle)
  let vm = false;
  const unsub = voiceMuted.subscribe(v => vm = v);
  unsub();
  if (vm) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'soft_unmute' }));
    }
    playSound('unmute');
    return;
  }

  // Normal hard mute toggle
  muted.update(m => {
    const next = !m;
    localStream.getAudioTracks().forEach(t => t.enabled = !next);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'hard_mute', muted: next }));
    }
    playSound(next ? 'mute' : 'unmute');
    return next;
  });
}

export function toggleDeafen() {
  deafened.update(d => {
    const next = !d;
    if (remoteAudio) remoteAudio.muted = next;
    // Deafen implies mute
    if (next && localStream) {
      muted.set(true);
      localStream.getAudioTracks().forEach(t => t.enabled = false);
    }
    return next;
  });
}

export function sendText(text) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'user_text', text }));
  }
}

export function sendContextToggle(taskId) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'context_toggle', task_id: taskId }));
  }
}

export async function openSettings() {
  requestSettings();
  settingsOpen.set(true);
  // If WS isn't connected, fetch via REST so providers still load
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    try {
      const res = await fetch('/api/settings');
      if (res.ok) {
        const data = await res.json();
        settingsData.set({
          llm: data.llm || {},
          tts: data.tts || {},
          stt: data.stt || {},
          services: data.services || {},
        });
      }
    } catch {}
  }
}

export function requestSettings() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'get_settings' }));
  }
}

export function saveSettings({ llm, tts, stt }) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'save_settings', llm, tts, stt }));
  }
}

export async function reloadSettings() {
  try {
    const res = await fetch('/api/settings?reload=true');
    if (res.ok) {
      const data = await res.json();
      settingsData.set({
        llm: data.llm || {},
        tts: data.tts || {},
        stt: data.stt || {},
        services: data.services || {},
      });
    }
  } catch {}
}

async function clearSessionState() {
  transcript.set([]);
  boardStream.set([]);
  boardFocused.set(null);
  tasks.set([]);
  agentState.set('idle');
  voiceMuted.set(false);
  // Close all open popups — snapshot keys first to avoid mutating Map during iteration
  const popupKeys = [...openPopups.keys()];
  await Promise.all(popupKeys.map(toolName => closePopup(toolName)));
}

export function disconnect() {
  playSound('leave');
  if (pc) {
    pc.close();
    pc = null;
  }
  if (localStream) {
    localStream.getTracks().forEach(t => t.stop());
    localStream = null;
  }
  if (remoteAudio) {
    remoteAudio.pause();
    remoteAudio = null;
  }
  pcId = null;
  muted.set(false);
  deafened.set(false);
  clearSessionState();
  connectionState.set('disconnected');
}
