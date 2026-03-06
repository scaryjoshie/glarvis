<script>
  import { emit } from '@tauri-apps/api/event';
  import { getCurrentWindow, Effect } from '@tauri-apps/api/window';
  import { onMount } from 'svelte';

  export let prompt = '';
  export let options = [];
  export let toolName = '';

  let actionSent = false;
  let showOtherInput = false;
  let otherText = '';

  onMount(async () => {
    try {
      const win = getCurrentWindow();
      await win.setEffects({ effects: [Effect.Acrylic], color: [24, 24, 27, 120] });
    } catch (e) {
      console.warn('[Popup] Could not set acrylic effect:', e);
    }
  });

  async function send(action, data = {}) {
    if (actionSent) return;
    actionSent = true;
    await emit('popup-action', { tool_name: toolName, action, data });
    try { await getCurrentWindow().close(); } catch {}
  }

  function select(index) {
    send('select_option', { number: index + 1 });
  }

  function submitOther() {
    if (otherText.trim()) {
      send('select_other', { text: otherText.trim() });
    }
  }

  function dismiss() {
    send('dismiss');
  }

  function onKeydown(e) {
    if (e.key === 'Escape') {
      if (showOtherInput) {
        showOtherInput = false;
        otherText = '';
      } else {
        dismiss();
      }
      return;
    }
    if (showOtherInput) {
      if (e.key === 'Enter') submitOther();
      return;
    }
    const n = parseInt(e.key);
    if (n >= 1 && n <= options.length) select(n - 1);
  }
</script>

<svelte:window on:keydown={onKeydown} />

<div class="popup">
  {#if prompt}
    <p class="prompt">{prompt}</p>
  {/if}
  <div class="options">
    {#each options as option, i}
      <button class="option" on:click={() => select(i)}>
        <span class="number">{i + 1}</span>
        <span class="label">{option}</span>
      </button>
    {/each}
  </div>
  {#if showOtherInput}
    <div class="other-input">
      <input
        type="text"
        bind:value={otherText}
        placeholder="Type your option..."
        autofocus
      />
      <button class="submit-btn" on:click={submitOther} disabled={!otherText.trim()}>Go</button>
    </div>
  {:else}
    <div class="bottom-row">
      <button class="other-btn" on:click={() => { showOtherInput = true; }}>Other...</button>
      <button class="dismiss-btn" on:click={dismiss}>Dismiss</button>
    </div>
  {/if}
</div>

<style>
  :global(html), :global(body) {
    background: transparent;
    margin: 0;
    padding: 0;
  }

  .popup {
    padding: 20px;
    max-height: 100vh;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    justify-content: center;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    color: #e4e4e7;
    overflow: hidden;
  }

  .prompt {
    font-size: 14px;
    margin: 0 0 14px;
    color: #a1a1aa;
  }

  .options {
    display: flex;
    flex-direction: column;
    gap: 6px;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .option {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.06);
    color: #e4e4e7;
    font-size: 13px;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
    text-align: left;
    font-family: inherit;
  }

  .option:hover {
    border-color: rgba(59, 130, 246, 0.5);
    background: rgba(59, 130, 246, 0.12);
  }

  .number {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.08);
    font-size: 11px;
    font-weight: 600;
    flex-shrink: 0;
    color: #a1a1aa;
  }

  .option:hover .number {
    background: rgba(59, 130, 246, 0.2);
    color: #3b82f6;
  }

  .label {
    flex: 1;
  }

  .bottom-row {
    display: flex;
    gap: 8px;
    margin-top: 14px;
  }

  .other-btn {
    flex: 1;
    padding: 7px 16px;
    border: 1px solid rgba(139, 92, 246, 0.25);
    border-radius: 8px;
    background: rgba(139, 92, 246, 0.08);
    color: #a78bfa;
    font-size: 12px;
    cursor: pointer;
    font-family: inherit;
    transition: background 0.15s, border-color 0.15s;
  }

  .other-btn:hover {
    background: rgba(139, 92, 246, 0.15);
    border-color: rgba(139, 92, 246, 0.4);
  }

  .dismiss-btn {
    padding: 7px 16px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.04);
    color: #71717a;
    font-size: 12px;
    cursor: pointer;
    font-family: inherit;
    transition: color 0.15s, border-color 0.15s;
  }

  .dismiss-btn:hover {
    color: #a1a1aa;
    border-color: rgba(255, 255, 255, 0.12);
  }

  .other-input {
    display: flex;
    gap: 8px;
    margin-top: 14px;
  }

  .other-input input {
    flex: 1;
    padding: 8px 12px;
    border: 1px solid rgba(139, 92, 246, 0.3);
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.06);
    color: #e4e4e7;
    font-size: 13px;
    font-family: inherit;
    outline: none;
    transition: border-color 0.15s;
  }

  .other-input input:focus {
    border-color: #8b5cf6;
  }

  .other-input input::placeholder {
    color: #52525b;
  }

  .submit-btn {
    padding: 8px 16px;
    border: 1px solid rgba(139, 92, 246, 0.35);
    border-radius: 8px;
    background: rgba(139, 92, 246, 0.12);
    color: #a78bfa;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
    transition: background 0.15s, border-color 0.15s;
  }

  .submit-btn:hover:not(:disabled) {
    background: rgba(139, 92, 246, 0.22);
    border-color: rgba(139, 92, 246, 0.5);
  }

  .submit-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }
</style>
