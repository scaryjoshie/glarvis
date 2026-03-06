<script>
  import { emit } from '@tauri-apps/api/event';
  import { getCurrentWindow } from '@tauri-apps/api/window';

  export let prompt = '';
  export let options = [];
  export let toolName = '';

  let actionSent = false;

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

  function dismiss() {
    send('dismiss');
  }
</script>

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
    <button class="dismiss-btn" on:click={dismiss}>Dismiss</button>
  </div>
</div>

<style>
  :global(html), :global(body) {
    background: transparent !important;
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
  }

  .card {
    background: rgba(24, 24, 27, 0.92);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(63, 63, 70, 0.6);
    border-radius: 14px;
    padding: 20px;
    width: 100%;
    max-width: 360px;
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
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

  .dismiss-btn {
    margin-top: 12px;
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
</style>
