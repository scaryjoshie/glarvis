/**
 * Popup entry point (Tauri overlay window).
 * Reads popup type + data from URL hash, mounts the appropriate Svelte component.
 */
import { mount } from 'svelte';
import './app.css';
import MultiChoice from './lib/popups/MultiChoice.svelte';

const el = document.getElementById('popup');

const components = {
  multi_choice: MultiChoice,
};

try {
  const hash = window.location.hash.slice(1);
  if (!hash) {
    el.innerHTML = '<p style="color:red;padding:20px;">No hash data in URL</p>';
  } else {
    const { popupType, toolName, data } = JSON.parse(decodeURIComponent(hash));

    const Component = components[popupType];
    if (Component) {
      mount(Component, {
        target: el,
        props: { ...data, toolName },
      });
    }
  }
} catch (e) {
  console.error('[Popup] Failed to initialize:', e);
  el.innerHTML = `<p style="color:red;padding:20px;">Error: ${e.message}</p>`;
}
