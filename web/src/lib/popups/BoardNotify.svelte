<script>
  import { emit } from '@tauri-apps/api/event';
  import { getCurrentWindow } from '@tauri-apps/api/window';
  import { onMount } from 'svelte';

  export let author = '';
  export let content = '';
  export let toolName = '';

  let message = '';

  onMount(async () => {
    try {
      await getCurrentWindow().setFocus();
    } catch (e) {
      console.warn('[BoardNotify] Could not focus:', e);
    }
  });

  async function dismiss() {
    try { await getCurrentWindow().close(); } catch {}
  }

  async function send() {
    if (!message.trim()) return;
    await emit('popup-action', {
      tool_name: toolName,
      action: 'board_reply',
      data: { message: message.trim() },
    });
    message = '';
    await dismiss();
  }

  function onKeydown(e) {
    if (e.key === 'Escape') dismiss();
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }
</script>

<svelte:window on:keydown={onKeydown} />

<div class="popup">
  <div class="header" data-tauri-drag-region>
    <span class="author" data-tauri-drag-region>{author}</span>
    <button class="dismiss-btn" on:click={dismiss}>&times;</button>
  </div>
  <div class="content">{content}</div>
  <div class="reply-row">
    <input
      type="text"
      bind:value={message}
      placeholder="Reply..."
      autofocus
    />
    <button class="send-btn" on:click={send} disabled={!message.trim()}>Send</button>
  </div>
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
    padding: 0;
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

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
    flex-shrink: 0;
    cursor: grab;
  }

  .author {
    font-size: 12px;
    font-weight: 600;
    color: #a1a1aa;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .dismiss-btn {
    background: none;
    border: none;
    color: #71717a;
    font-size: 20px;
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
    font-family: inherit;
  }

  .dismiss-btn:hover {
    color: #a1a1aa;
  }

  .content {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 14px 20px;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
    color: #d4d4d8;
  }

  .reply-row {
    display: flex;
    gap: 8px;
    padding: 10px 20px;
    border-top: 1px solid rgba(255, 255, 255, 0.07);
    flex-shrink: 0;
  }

  .reply-row input {
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

  .reply-row input:focus {
    border-color: rgba(255, 255, 255, 0.25);
  }

  .reply-row input::placeholder {
    color: #52525b;
  }

  .send-btn {
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

  .send-btn:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.12);
  }

  .send-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }
</style>
