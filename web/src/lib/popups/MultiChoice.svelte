<script>
  import { emit } from '@tauri-apps/api/event';
  import { getCurrentWindow } from '@tauri-apps/api/window';

  export let prompt = '';
  export let options = [];
  export let toolName = '';

  let actionSent = false;
  let showOtherInput = false;
  let otherText = '';

  async function send(action, data = {}) {
    if (actionSent) return;
    actionSent = true;
    await emit('popup-action', { tool_name: toolName, action, data });
    // Close self after sending
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
    // Number keys 1-9 select options
    const n = parseInt(e.key);
    if (n >= 1 && n <= options.length) select(n - 1);
  }
</script>

<svelte:window on:keydown={onKeydown} />

<div class="overlay">
  <div class="card">
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
</div>

<style>
  :global(html), :global(body) {
    background: #18181b;
    margin: 0;
    padding: 0;
  }

  .overlay {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 24px;
    box-sizing: border-box;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #18181b;
  }

  .card {
    background: #1f1f23;
    border: 1px solid #3f3f46;
    border-radius: 14px;
    padding: 20px;
    width: 100%;
    max-width: 360px;
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
  }

  .option {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border: 1px solid rgba(63, 63, 70, 0.5);
    border-radius: 10px;
    background: rgba(39, 39, 42, 0.5);
    color: #e4e4e7;
    font-size: 13px;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
    text-align: left;
    font-family: inherit;
  }

  .option:hover {
    border-color: #3b82f6;
    background: rgba(59, 130, 246, 0.1);
  }

  .number {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: rgba(63, 63, 70, 0.6);
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
    margin-top: 12px;
  }

  .other-btn {
    flex: 1;
    padding: 6px 16px;
    border: 1px solid rgba(139, 92, 246, 0.4);
    border-radius: 8px;
    background: none;
    color: #a78bfa;
    font-size: 12px;
    cursor: pointer;
    font-family: inherit;
    transition: color 0.15s, border-color 0.15s, background 0.15s;
  }

  .other-btn:hover {
    color: #c4b5fd;
    border-color: rgba(139, 92, 246, 0.6);
    background: rgba(139, 92, 246, 0.08);
  }

  .dismiss-btn {
    padding: 6px 16px;
    border: 1px solid rgba(63, 63, 70, 0.4);
    border-radius: 8px;
    background: none;
    color: #71717a;
    font-size: 12px;
    cursor: pointer;
    font-family: inherit;
    transition: color 0.15s, border-color 0.15s;
  }

  .dismiss-btn:hover {
    color: #e4e4e7;
    border-color: #71717a;
  }

  .other-input {
    display: flex;
    gap: 8px;
    margin-top: 12px;
  }

  .other-input input {
    flex: 1;
    padding: 8px 12px;
    border: 1px solid rgba(139, 92, 246, 0.4);
    border-radius: 8px;
    background: rgba(39, 39, 42, 0.8);
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
    border: 1px solid rgba(139, 92, 246, 0.5);
    border-radius: 8px;
    background: rgba(139, 92, 246, 0.15);
    color: #a78bfa;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
    transition: background 0.15s, border-color 0.15s;
  }

  .submit-btn:hover:not(:disabled) {
    background: rgba(139, 92, 246, 0.25);
    border-color: #8b5cf6;
  }

  .submit-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }
</style>
