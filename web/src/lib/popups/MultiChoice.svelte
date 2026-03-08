<script>
  import { emit } from '@tauri-apps/api/event';
  import { getCurrentWindow } from '@tauri-apps/api/window';
  import { onMount } from 'svelte';

  export let prompt = '';
  export let options = [];
  export let toolName = '';

  let actionSent = false;
  let showOtherInput = false;
  let otherText = '';

  onMount(async () => {
    try {
      await getCurrentWindow().setFocus();
    } catch (e) {
      console.warn('[Popup] Could not focus:', e);
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
        {#if option.icon}
          <img class="icon" src="data:image/png;base64,{option.icon}" alt="" />
        {/if}
        <span class="number">{i + 1}</span>
        <span class="label">{typeof option === 'string' ? option : option.text}</span>
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
    background: transparent !important;
    margin: 0;
    padding: 0;
    height: 100%;
  }

  :global(#popup) {
    height: 100%;
  }

  .popup {
    padding: 8px 0;
    height: 100%;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    color: #e4e4e7;
    overflow: hidden;
    background: #0a0a0c;
    border-radius: 0;
  }

  .prompt {
    font-size: 13px;
    margin: 0;
    padding: 12px 20px;
    color: #a1a1aa;
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  }

  .options {
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .option {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 14px 20px;
    border: none;
    border-radius: 0;
    background: transparent;
    color: #e4e4e7;
    font-size: 14px;
    cursor: pointer;
    transition: background 0.1s;
    text-align: left;
    font-family: inherit;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }

  .option:last-child {
    border-bottom: none;
  }

  .option:hover {
    background: rgba(255, 255, 255, 0.06);
  }

  .icon {
    width: 22px;
    height: 22px;
    flex-shrink: 0;
    border-radius: 4px;
  }

  .number {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.08);
    font-size: 11px;
    font-weight: 600;
    flex-shrink: 0;
    color: #71717a;
  }

  .option:hover .number {
    background: rgba(255, 255, 255, 0.12);
    color: #a1a1aa;
  }

  .label {
    flex: 1;
  }

  .bottom-row {
    display: flex;
    gap: 8px;
    padding: 10px 20px;
    border-top: 1px solid rgba(255, 255, 255, 0.07);
  }

  .other-btn {
    flex: 1;
    padding: 8px 16px;
    border: none;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.06);
    color: #a1a1aa;
    font-size: 12px;
    cursor: pointer;
    font-family: inherit;
    transition: background 0.1s;
  }

  .other-btn:hover {
    background: rgba(255, 255, 255, 0.1);
  }

  .dismiss-btn {
    padding: 8px 16px;
    border: none;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.06);
    color: #71717a;
    font-size: 12px;
    cursor: pointer;
    font-family: inherit;
    transition: color 0.1s;
  }

  .dismiss-btn:hover {
    color: #a1a1aa;
  }

  .other-input {
    display: flex;
    gap: 8px;
    padding: 10px 20px;
    border-top: 1px solid rgba(255, 255, 255, 0.07);
  }

  .other-input input {
    flex: 1;
    padding: 8px 12px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.04);
    color: #e4e4e7;
    font-size: 13px;
    font-family: inherit;
    outline: none;
    transition: border-color 0.15s;
  }

  .other-input input:focus {
    border-color: rgba(255, 255, 255, 0.25);
  }

  .other-input input::placeholder {
    color: #52525b;
  }

  .submit-btn {
    padding: 8px 16px;
    border: none;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.08);
    color: #a1a1aa;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
    transition: background 0.1s;
  }

  .submit-btn:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.12);
  }

  .submit-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }
</style>
