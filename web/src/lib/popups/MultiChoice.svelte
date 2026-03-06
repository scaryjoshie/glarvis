<script>
  export let prompt = '';
  export let options = [];
  export let toolName = '';

  let actionSent = false;

  function send(action, data = {}) {
    if (actionSent) return;
    actionSent = true;
    window.opener?.postMessage({
      type: 'popup_action',
      tool_name: toolName,
      action,
      data,
    }, '*');
  }

  function select(index) {
    send('select_option', { number: index + 1 });
  }

  function dismiss() {
    send('dismiss');
  }

  // If user closes the window without picking, dismiss
  window.addEventListener('beforeunload', () => {
    if (!actionSent) {
      send('dismiss');
    }
  });
</script>

<div class="multi-choice">
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

<style>
  .multi-choice {
    padding: 16px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    color: var(--color-text, #e4e4e7);
    background: var(--color-bg, #18181b);
    min-height: 100vh;
    box-sizing: border-box;
  }

  .prompt {
    font-size: 14px;
    margin: 0 0 12px;
    color: var(--color-muted, #a1a1aa);
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
    border: 1px solid var(--color-border, #27272a);
    border-radius: 8px;
    background: var(--color-surface, #1f1f23);
    color: inherit;
    font-size: 13px;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
    text-align: left;
    font-family: inherit;
  }

  .option:hover {
    border-color: var(--color-blue, #3b82f6);
    background: var(--color-surface-hover, #27272a);
  }

  .number {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: var(--color-border, #27272a);
    font-size: 11px;
    font-weight: 600;
    flex-shrink: 0;
  }

  .label {
    flex: 1;
  }

  .dismiss-btn {
    margin-top: 12px;
    padding: 6px 16px;
    border: 1px solid var(--color-border, #27272a);
    border-radius: 6px;
    background: none;
    color: var(--color-muted, #a1a1aa);
    font-size: 12px;
    cursor: pointer;
    font-family: inherit;
  }

  .dismiss-btn:hover {
    color: var(--color-text, #e4e4e7);
    border-color: var(--color-muted, #a1a1aa);
  }
</style>
