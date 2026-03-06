<script>
  import { connectionState, muted, deafened } from '../stores/connection.js';
  import { connectWebSocket, connectWebRTC, disconnect, toggleMute, toggleDeafen, sendText } from '../stores/connection.js';

  $: connected = $connectionState === 'connected';
  $: connecting = $connectionState === 'connecting';

  function handleToggleConnection() {
    if (connected) {
      disconnect();
    } else {
      connectWebSocket();
      connectWebRTC();
    }
  }
</script>

<div class="voice-controls">
  <!-- Voice connection status -->
  <div class="voice-status">
    <div class="voice-status-left">
      <span class="voice-dot" class:connected class:connecting></span>
      <div class="voice-info">
        <span class="voice-label" class:connected class:connecting>
          {#if connected}Voice Connected{:else if connecting}Connecting...{:else}Voice Disconnected{/if}
        </span>
        <span class="voice-sub">Claude Haiku 4.5</span>
      </div>
    </div>
    <button
      class="connection-btn"
      class:connected
      class:connecting
      on:click={handleToggleConnection}
      disabled={connecting}
    >
      {#if connected}
        Disconnect
      {:else if connecting}
        ...
      {:else}
        Connect
      {/if}
    </button>
  </div>

  <!-- Quick tool buttons -->
  <div class="quick-tools">
    <button class="tool-btn" disabled={!connected} on:click={() => sendText('list my tools')} title="List Tools">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
      </svg>
    </button>
    <button class="tool-btn" disabled={!connected} on:click={() => sendText('search files')} title="Search Files">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
    </button>
    <button class="tool-btn" disabled={!connected} on:click={() => sendText('list directory')} title="List Directory">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
      </svg>
    </button>
    <button class="tool-btn" disabled={!connected} on:click={() => sendText('what time is it')} title="Get Time">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
      </svg>
    </button>
  </div>

  <!-- User controls: mute, deafen, settings -->
  <div class="user-controls">
    <button class="ctrl-btn" class:active={$muted} on:click={toggleMute} disabled={!connected} title={$muted ? 'Unmute' : 'Mute'}>
      {#if $muted}
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="1" y1="1" x2="23" y2="23"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/><path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2c0 .76-.13 1.49-.36 2.18"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>
        </svg>
      {:else}
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>
        </svg>
      {/if}
    </button>
    <button class="ctrl-btn" class:active={$deafened} on:click={toggleDeafen} disabled={!connected} title={$deafened ? 'Undeafen' : 'Deafen'}>
      {#if $deafened}
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="1" y1="1" x2="23" y2="23"/>
          <path d="M3 14h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a9 9 0 0 1 14.77-6.9"/>
          <path d="M21 14h-1a2 2 0 0 0-2 2v3a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-7a9 9 0 0 0-.8-3.7"/>
        </svg>
      {:else}
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/>
        </svg>
      {/if}
    </button>
    <button class="ctrl-btn" title="Settings">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
    </button>
  </div>
</div>

<style>
  .voice-controls {
    border-top: 1px solid var(--color-border);
    background: var(--color-surface);
  }

  /* ── Voice status bar ─────────────────────────── */
  .voice-status {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    border-bottom: 1px solid var(--color-border);
  }

  .voice-status-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .voice-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--color-muted);
    flex-shrink: 0;
  }

  .voice-dot.connected {
    background: var(--color-green);
  }

  .voice-dot.connecting {
    background: var(--color-yellow);
    animation: pulse 1s infinite;
  }

  .voice-info {
    display: flex;
    flex-direction: column;
  }

  .voice-label {
    font-size: 13px;
    font-weight: 600;
    color: var(--color-muted);
  }

  .voice-label.connected {
    color: var(--color-green);
  }

  .voice-label.connecting {
    color: var(--color-yellow);
  }

  .voice-sub {
    font-size: 11px;
    color: var(--color-muted);
  }

  .connection-btn {
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 12px;
    font-family: inherit;
    cursor: pointer;
    border: 1px solid var(--color-border);
    background: none;
    color: var(--color-text);
  }

  .connection-btn:hover {
    background: var(--color-bg);
  }

  .connection-btn.connected {
    color: var(--color-muted);
  }

  .connection-btn.connected:hover {
    color: var(--color-red);
    border-color: var(--color-red);
  }

  .connection-btn:not(.connected):not(.connecting) {
    background: var(--color-green);
    border-color: var(--color-green);
    color: #0f0f0f;
    font-weight: 600;
  }

  .connection-btn:not(.connected):not(.connecting):hover {
    opacity: 0.9;
  }

  .connection-btn.connecting {
    color: var(--color-yellow);
    border-color: var(--color-yellow);
    cursor: default;
    opacity: 0.7;
  }

  /* ── Quick tool buttons ───────────────────────── */
  .quick-tools {
    display: flex;
    gap: 6px;
    padding: 8px 12px;
    border-bottom: 1px solid var(--color-border);
  }

  .tool-btn {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 8px;
    background: var(--color-bg);
    border: 1px solid var(--color-border);
    border-radius: 6px;
    color: var(--color-muted);
    cursor: pointer;
  }

  .tool-btn:hover:not(:disabled) {
    color: var(--color-text);
    border-color: var(--color-muted);
    background: var(--color-surface-hover);
  }

  .tool-btn:disabled {
    opacity: 0.3;
    cursor: default;
  }

  /* ── User controls (mute, deafen, settings) ──── */
  .user-controls {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 8px 12px;
  }

  .ctrl-btn {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 6px;
    background: none;
    border: none;
    border-radius: 4px;
    color: var(--color-text);
    cursor: pointer;
  }

  .ctrl-btn:hover:not(:disabled) {
    background: var(--color-bg);
  }

  .ctrl-btn:disabled {
    opacity: 0.3;
    cursor: default;
  }

  .ctrl-btn.active {
    color: var(--color-red);
    background: rgba(248, 113, 113, 0.1);
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
</style>
