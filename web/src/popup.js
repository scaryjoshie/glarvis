/**
 * Popup entry point (Tauri overlay window).
 * Reads popup type from URL hash, requests data from main window via event.
 */
import { mount } from 'svelte';
import { emit, listen } from '@tauri-apps/api/event';
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow';
import './app.css';
import MultiChoice from './lib/popups/MultiChoice.svelte';
import BoardNotify from './lib/popups/BoardNotify.svelte';
import Transcriber from './lib/popups/Transcriber.svelte';
import SettingsModal from './lib/components/SettingsModal.svelte';
const el = document.getElementById('popup');

const components = {
  multi_choice: MultiChoice,
  board_notify: BoardNotify,
  transcriber: Transcriber,
  settings: SettingsModal,
};

// Settings popup is self-contained (fetches via REST), doesn't need data from main window
const selfContained = new Set(['settings']);

try {
  const hash = window.location.hash.slice(1);
  if (!hash) {
    el.innerHTML = '<p style="color:red;padding:20px;">No hash data in URL</p>';
  } else {
    const { popupType, toolName } = JSON.parse(decodeURIComponent(hash));
    const Component = components[popupType];
    if (!Component) {
      el.innerHTML = `<p style="color:red;padding:20px;">Unknown popup type: ${popupType}</p>`;
    } else if (selfContained.has(popupType)) {
      // Self-contained popups fetch their own data (e.g. settings via REST)
      mount(Component, {
        target: el,
        props: { popupMode: true, toolName },
      });
    } else {
      // Listen for data, then request it from main window
      listen('popup-data', (event) => {
        mount(Component, {
          target: el,
          props: { ...event.payload, toolName },
        });
      });
      const label = getCurrentWebviewWindow().label;
      emit('popup-request-data', { label });
    }
  }
} catch (e) {
  console.error('[Popup] Failed to initialize:', e);
  el.innerHTML = `<p style="color:red;padding:20px;">Error: ${e.message}</p>`;
}
