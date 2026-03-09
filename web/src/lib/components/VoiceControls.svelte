<script>
  import {
    connectionState, muted, deafened, voiceMuted, modelDisplay, agentState,
    connectWebSocket, connectWebRTC, disconnect,
    toggleMute, toggleDeafen, sendText, openSettings, sfxVolume, voiceVolume,
  } from '../stores/connection.js';

  $: connected = $connectionState === 'connected';
  $: connecting = $connectionState === 'connecting';
  $: state = $agentState;

  let showVolume = false;

  function handleToggleConnection() {
    if (connected) {
      disconnect();
    } else {
      connectWebSocket();
      connectWebRTC();
    }
  }

  $: micStatusText = $muted ? 'Muted' : $voiceMuted ? 'Soft Muted' : connected ? 'Live' : 'Off';
  $: micStatusColor = $muted ? 'var(--color-red)' : $voiceMuted ? 'var(--color-yellow)' : connected ? 'var(--color-green)' : 'var(--color-muted)';
</script>

<div class="controls-wrapper">
  <!-- Connection + Status row -->
  <div class="status-row">
    <div class="status-left">
      <span class="status-dot" style="background: {micStatusColor}; box-shadow: 0 0 8px {micStatusColor};"></span>
      <div class="status-info">
        <span class="status-label" style="color: {micStatusColor}">{micStatusText}</span>
        <span class="status-sub">{$modelDisplay || 'Voice Assistant'}</span>
      </div>
    </div>
    <button
      class="connect-btn"
      class:connected
      class:connecting
      on:click={handleToggleConnection}
      disabled={connecting}
    >
      {#if connected}
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18.36 6.64a9 9 0 0 1-12.73 0"/><path d="M5.64 17.36a9 9 0 0 1 12.73 0"/><line x1="12" y1="2" x2="12" y2="22"/>
        </svg>
        <span>End</span>
      {:else if connecting}
        <div class="connect-spinner"></div>
      {:else}
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="5 3 19 12 5 21 5 3"/>
        </svg>
        <span>Connect</span>
      {/if}
    </button>
  </div>

  <!-- Quick tools -->
  <div class="quick-row">
    <button class="qtool" disabled={!connected} on:click={() => sendText('list my tools')} title="List Tools">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
      </svg>
    </button>
    <button class="qtool" disabled={!connected} on:click={() => sendText('search files')} title="Search Files">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
    </button>
    <button class="qtool" disabled={!connected} on:click={() => sendText('list directory')} title="List Directory">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
      </svg>
    </button>
    <button class="qtool" disabled={!connected} on:click={() => sendText('what time is it')} title="Get Time">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
      </svg>
    </button>
    <button class="qtool" disabled={!connected} on:click={() => sendText('open terminal')} title="Terminal">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>
      </svg>
    </button>
  </div>

  <!-- Control buttons -->
  <div class="controls-row">
    <button
      class="ctrl-btn mic-btn"
      class:active={$muted}
      class:soft-active={!$muted && $voiceMuted}
      on:click={toggleMute}
      disabled={!connected}
      title={$muted ? 'Unmute' : $voiceMuted ? 'Unmute (soft)' : 'Mute'}
    >
      {#if $muted || $voiceMuted}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="1" y1="1" x2="23" y2="23"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/><path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2c0 .76-.13 1.49-.36 2.18"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>
        </svg>
      {:else}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>
        </svg>
      {/if}
    </button>

    <button
      class="ctrl-btn"
      class:active={$deafened}
      on:click={toggleDeafen}
      disabled={!connected}
      title={$deafened ? 'Undeafen' : 'Deafen'}
    >
      {#if $deafened}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="1" y1="1" x2="23" y2="23"/>
          <path d="M3 14h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a9 9 0 0 1 14.77-6.9"/>
          <path d="M21 14h-1a2 2 0 0 0-2 2v3a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-7a9 9 0 0 0-.8-3.7"/>
        </svg>
      {:else}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/>
        </svg>
      {/if}
    </button>

    <button class="ctrl-btn" on:click={() => showVolume = !showVolume} class:active={showVolume} title="Volume">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
      </svg>
    </button>

    <button class="ctrl-btn settings-btn" on:click={openSettings} title="Settings">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
    </button>
  </div>

  <!-- Volume panel (collapsible) -->
  {#if showVolume}
    <div class="volume-panel">
      <div class="vol-row">
        <span class="vol-label">Voice</span>
        <input type="range" min="0" max="1" step="0.05" bind:value={$voiceVolume} class="vol-slider" />
        <span class="vol-val">{Math.round($voiceVolume * 100)}%</span>
      </div>
      <div class="vol-row">
        <span class="vol-label">SFX</span>
        <input type="range" min="0" max="1" step="0.05" bind:value={$sfxVolume} class="vol-slider" />
        <span class="vol-val">{Math.round($sfxVolume * 100)}%</span>
      </div>
    </div>
  {/if}
</div>

<style>
  .controls-wrapper {
    border-top: 1px solid var(--color-border);
    background: var(--color-bg-deep);
  }

  /* ── Status row ──────────────────────────── */
  .status-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    border-bottom: 1px solid var(--color-border);
  }

  .status-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
    transition: all var(--transition-normal);
  }

  .status-info {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .status-label {
    font-size: 12px;
    font-weight: 600;
    transition: color var(--transition-normal);
  }

  .status-sub {
    font-size: 10px;
    color: var(--color-muted);
    font-family: var(--font-mono);
  }

  .connect-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 14px;
    border-radius: var(--radius-full);
    font-size: 12px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    border: 1px solid var(--color-border);
    background: none;
    color: var(--color-text);
    transition: all var(--transition-fast);
  }

  .connect-btn:not(.connected):not(.connecting) {
    background: var(--color-green);
    border-color: var(--color-green);
    color: #0a0a0a;
  }

  .connect-btn:not(.connected):not(.connecting):hover {
    box-shadow: var(--shadow-glow-green);
  }

  .connect-btn.connected {
    color: var(--color-text-secondary);
  }

  .connect-btn.connected:hover {
    color: var(--color-red);
    border-color: var(--color-red);
    box-shadow: 0 0 12px var(--color-red-glow);
  }

  .connect-btn.connecting {
    color: var(--color-yellow);
    border-color: rgba(250, 204, 21, 0.3);
    cursor: default;
  }

  .connect-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid transparent;
    border-top-color: var(--color-yellow);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  /* ── Quick tools ─────────────────────────── */
  .quick-row {
    display: flex;
    gap: 4px;
    padding: 6px 10px;
    border-bottom: 1px solid var(--color-border);
  }

  .qtool {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 7px;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    color: var(--color-muted);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .qtool:hover:not(:disabled) {
    color: var(--color-text);
    border-color: var(--color-border-strong);
    background: var(--color-surface-hover);
    transform: translateY(-1px);
  }

  .qtool:disabled {
    opacity: 0.2;
    cursor: default;
  }

  /* ── Control buttons ─────────────────────── */
  .controls-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 3px;
    padding: 6px 10px;
  }

  .ctrl-btn {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 7px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--radius-md);
    color: var(--color-text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .ctrl-btn:hover:not(:disabled) {
    background: var(--color-surface);
    color: var(--color-text);
  }

  .ctrl-btn:disabled {
    opacity: 0.2;
    cursor: default;
  }

  .ctrl-btn.active {
    color: var(--color-red);
    background: var(--color-red-glow);
    border-color: rgba(248, 113, 113, 0.15);
  }

  .ctrl-btn.soft-active {
    color: var(--color-yellow);
    background: var(--color-yellow-glow);
    border-color: rgba(250, 204, 21, 0.15);
  }

  /* ── Volume panel ────────────────────────── */
  .volume-panel {
    padding: 8px 12px;
    border-top: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    gap: 6px;
    animation: slideUp 0.15s ease;
  }

  .vol-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .vol-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--color-muted);
    width: 36px;
  }

  .vol-slider {
    flex: 1;
    height: 4px;
    -webkit-appearance: none;
    appearance: none;
    background: var(--color-border);
    border-radius: 2px;
    outline: none;
  }

  .vol-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--color-blue);
    cursor: pointer;
    box-shadow: 0 0 6px var(--color-blue-glow);
  }

  .vol-val {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--color-text-secondary);
    width: 30px;
    text-align: right;
  }
</style>
