<script>
  import { emit, listen } from '@tauri-apps/api/event';
  import { getCurrentWindow, LogicalSize, LogicalPosition } from '@tauri-apps/api/window';
  import { onMount, onDestroy } from 'svelte';

  export let text = '';
  export let mode = 'minimized';
  export let paused = false;
  export let toolName = '';

  let currentText = text || '';
  let expanded = mode === 'maximized';
  let recording = !paused;
  let scrollContainer;
  let unlistenUpdate;
  let unlistenState;

  $: words = currentText ? currentText.split(/\s+/).filter(Boolean) : [];
  $: visibleWords = words.slice(-12);

  onMount(async () => {
    unlistenUpdate = await listen('transcriber-update', (event) => {
      currentText = event.payload.text || '';
      if (expanded && scrollContainer) {
        requestAnimationFrame(() => {
          scrollContainer.scrollTop = scrollContainer.scrollHeight;
        });
      }
    });
    unlistenState = await listen('transcriber-state', (event) => {
      recording = !event.payload.paused;
    });
  });

  onDestroy(() => {
    if (unlistenUpdate) unlistenUpdate();
    if (unlistenState) unlistenState();
  });

  async function action(name, data = {}) {
    await emit('popup-action', { tool_name: toolName, action: name, data });
  }

  function doSend() { action('transcriber_send'); }
  function doCopy() { action('transcriber_copy'); }
  function doClear() { action('transcriber_clear'); }
  function doStop() {
    action('transcriber_stop');
    try { getCurrentWindow().close(); } catch {}
  }
  function toggleRecording() {
    if (recording) {
      action('transcriber_pause');
      recording = false;  // optimistic update
    } else {
      action('transcriber_resume');
      recording = true;
    }
  }

  async function toggleExpand() {
    expanded = !expanded;
    try {
      const win = getCurrentWindow();
      if (expanded) {
        const w = 520, h = 360;
        await win.setSize(new LogicalSize(w, h));
        const x = Math.round(screen.width / 2 - w / 2);
        const y = Math.round(screen.height / 2 - h / 2);
        await win.setPosition(new LogicalPosition(x, y));
      } else {
        const w = 520, h = 56;
        await win.setSize(new LogicalSize(w, h));
        const x = Math.round(screen.width / 2 - w / 2);
        const y = screen.height - 120;
        await win.setPosition(new LogicalPosition(x, y));
      }
    } catch (e) {
      console.warn('[Transcriber] Resize failed:', e);
    }
  }

  function onKeydown(e) {
    if (e.key === 'Escape') doStop();
  }
</script>

<svelte:window on:keydown={onKeydown} />

{#if expanded}
  <div class="popup expanded">
    <div class="header" data-tauri-drag-region>
      <button
        class="rec-btn"
        class:recording
        class:paused={!recording}
        on:click={toggleRecording}
        title={recording ? 'Pause' : 'Resume'}
      >
        {#if recording}
          <div class="rec-dot"></div>
        {:else}
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="6,4 20,12 6,20"/>
          </svg>
        {/if}
      </button>
      <span class="title" data-tauri-drag-region>
        {recording ? 'Transcribing' : 'Paused'}
      </span>
      <div class="header-actions">
        <button class="icon-btn" on:click={toggleExpand} title="Minimize">&#x2013;</button>
        <button class="icon-btn close" on:click={doStop} title="Close">&times;</button>
      </div>
    </div>
    <div class="text-body" bind:this={scrollContainer}>
      {#if currentText}
        <p class="transcript-text">{currentText}</p>
      {:else}
        <p class="placeholder-text">
          {recording ? 'Speak to start transcribing...' : 'Paused — click record to resume'}
        </p>
      {/if}
    </div>
    <div class="action-bar">
      <button class="action-btn primary" on:click={doSend} disabled={!currentText}>
        Send
      </button>
      <button class="action-btn" on:click={doCopy} disabled={!currentText}>
        Copy
      </button>
      <button class="action-btn" on:click={doClear} disabled={!currentText}>
        Clear
      </button>
      <div class="spacer"></div>
      <button class="action-btn stop" on:click={doStop}>
        Close
      </button>
    </div>
  </div>
{:else}
  <!-- Minimized pill -->
  <div class="popup minimized" data-tauri-drag-region>
    <div class="mini-left" data-tauri-drag-region>
      <button
        class="rec-btn mini"
        class:recording
        class:paused={!recording}
        on:click={toggleRecording}
        title={recording ? 'Pause' : 'Resume'}
      >
        {#if recording}
          <div class="rec-dot"></div>
        {:else}
          <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="6,4 20,12 6,20"/>
          </svg>
        {/if}
      </button>
      <div class="ticker" data-tauri-drag-region>
        {#each visibleWords as word, i}
          <span
            class="ticker-word"
            style="opacity: {0.3 + 0.7 * ((i + 1) / visibleWords.length)}"
          >{word}</span>
        {/each}
        {#if !visibleWords.length}
          <span class="ticker-placeholder">
            {recording ? 'Listening...' : 'Paused'}
          </span>
        {/if}
      </div>
    </div>
    <div class="mini-actions">
      <!-- Send -->
      <button class="mini-btn" on:click={doSend} disabled={!currentText} title="Send">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 2L11 13M22 2L15 22L11 13L2 9L22 2Z"/>
        </svg>
      </button>
      <!-- Copy -->
      <button class="mini-btn" on:click={doCopy} disabled={!currentText} title="Copy">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
          <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
        </svg>
      </button>
      <!-- Expand -->
      <button class="mini-btn" on:click={toggleExpand} title="Expand">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="15 3 21 3 21 9"/>
          <polyline points="9 21 3 21 3 15"/>
          <line x1="21" y1="3" x2="14" y2="10"/>
          <line x1="3" y1="21" x2="10" y2="14"/>
        </svg>
      </button>
      <!-- Close -->
      <button class="mini-btn close" on:click={doStop} title="Close">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>
  </div>
{/if}

<style>
  :global(html), :global(body) {
    background: transparent !important;
    margin: 0;
    padding: 0;
    height: 100%;
    overflow: hidden;
  }

  :global(#popup) {
    height: 100%;
  }

  .popup {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    color: #e4e4e7;
    box-sizing: border-box;
    height: 100%;
  }

  /* ── Record button ──────────────────────────────────────────────── */

  .rec-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 50%;
    cursor: pointer;
    padding: 0;
    flex-shrink: 0;
    transition: background 0.15s;
  }

  .rec-btn.mini {
    width: 26px;
    height: 26px;
  }

  .rec-btn.recording {
    background: rgba(239, 68, 68, 0.15);
  }

  .rec-btn.recording:hover {
    background: rgba(239, 68, 68, 0.25);
  }

  .rec-btn.paused {
    background: rgba(255, 255, 255, 0.08);
    color: #a1a1aa;
  }

  .rec-btn.paused:hover {
    background: rgba(255, 255, 255, 0.14);
    color: #e4e4e7;
  }

  .rec-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #ef4444;
    animation: pulse 1.5s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }

  /* ── Minimized mode ─────────────────────────────────────────────── */

  .minimized {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 10px;
    background: rgba(10, 10, 12, 0.95);
    border-radius: 28px;
    height: 100%;
    gap: 8px;
    cursor: grab;
  }

  .mini-left {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;
    cursor: grab;
  }

  .ticker {
    display: flex;
    gap: 5px;
    overflow: hidden;
    white-space: nowrap;
    flex: 1;
    min-width: 0;
    mask-image: linear-gradient(to right, transparent, black 15%, black);
    -webkit-mask-image: linear-gradient(to right, transparent, black 15%, black);
    cursor: grab;
  }

  .ticker-word {
    font-size: 13px;
    color: #a1a1aa;
    transition: opacity 0.3s ease;
    flex-shrink: 0;
  }

  .ticker-placeholder {
    font-size: 13px;
    color: #52525b;
    font-style: italic;
  }

  .mini-actions {
    display: flex;
    gap: 3px;
    flex-shrink: 0;
  }

  .mini-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border: none;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.06);
    color: #a1a1aa;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
    padding: 0;
  }

  .mini-btn:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.12);
    color: #e4e4e7;
  }

  .mini-btn:disabled {
    opacity: 0.3;
    cursor: default;
  }

  .mini-btn.close {
    color: #71717a;
  }

  .mini-btn.close:hover {
    color: #ef4444;
    background: rgba(239, 68, 68, 0.12);
  }

  /* ── Expanded mode ──────────────────────────────────────────────── */

  .expanded {
    display: flex;
    flex-direction: column;
    background: #0a0a0c;
    border-radius: 12px;
    overflow: hidden;
  }

  .header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
    flex-shrink: 0;
    cursor: grab;
  }

  .title {
    font-size: 13px;
    font-weight: 600;
    color: #a1a1aa;
    flex: 1;
    cursor: grab;
  }

  .header-actions {
    display: flex;
    gap: 4px;
  }

  .icon-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: #71717a;
    font-size: 18px;
    cursor: pointer;
    font-family: inherit;
    line-height: 1;
    padding: 0;
    transition: background 0.15s, color 0.15s;
  }

  .icon-btn:hover {
    background: rgba(255, 255, 255, 0.08);
    color: #a1a1aa;
  }

  .icon-btn.close:hover {
    color: #ef4444;
  }

  .text-body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 16px;
  }

  .transcript-text {
    margin: 0;
    font-size: 14px;
    line-height: 1.7;
    color: #d4d4d8;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .placeholder-text {
    margin: 0;
    font-size: 14px;
    color: #52525b;
    font-style: italic;
  }

  .action-bar {
    display: flex;
    gap: 8px;
    padding: 12px 16px;
    border-top: 1px solid rgba(255, 255, 255, 0.07);
    flex-shrink: 0;
  }

  .spacer {
    flex: 1;
  }

  .action-btn {
    padding: 7px 16px;
    border: none;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.06);
    color: #a1a1aa;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
    transition: background 0.15s, color 0.15s;
  }

  .action-btn:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    color: #e4e4e7;
  }

  .action-btn:disabled {
    opacity: 0.35;
    cursor: default;
  }

  .action-btn.primary {
    background: rgba(99, 102, 241, 0.2);
    color: #818cf8;
  }

  .action-btn.primary:hover:not(:disabled) {
    background: rgba(99, 102, 241, 0.3);
  }

  .action-btn.stop {
    color: #ef4444;
  }

  .action-btn.stop:hover {
    background: rgba(239, 68, 68, 0.12);
  }
</style>
