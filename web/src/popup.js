/**
 * Popup entry point (Tauri overlay window).
 * Reads popup type + data from URL hash, mounts the appropriate Svelte component.
 */
import './app.css';
import MultiChoice from './lib/popups/MultiChoice.svelte';

const components = {
  multi_choice: MultiChoice,
};

try {
  const hash = window.location.hash.slice(1);
  const { popupType, toolName, data } = JSON.parse(decodeURIComponent(hash));

  const Component = components[popupType];
  if (Component) {
    new Component({
      target: document.getElementById('popup'),
      props: { ...data, toolName },
    });
  }
} catch (e) {
  console.error('[Popup] Failed to initialize:', e);
}
