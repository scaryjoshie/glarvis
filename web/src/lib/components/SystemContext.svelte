<script>
  import { onMount, onDestroy } from 'svelte';

  export let visible = false;
  export let onClose = () => {};

  let systemData = null;
  let loading = false;
  let pollTimer = null;

  async function fetchContext() {
    loading = true;
    try {
      const res = await fetch('/api/system-context');
      if (res.ok) {
        systemData = await res.json();
      }
    } catch (e) {
      // Endpoint may not exist yet — that's fine
      systemData = null;
    }
    loading = false;
  }

  $: if (visible) {
    fetchContext();
    pollTimer = setInterval(fetchContext, 3000);
  } else {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  }

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });
</script>

{#if visible}
  <div class="context-panel">
    <div class="context-header">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
      </svg>
      <span class="context-title">Minerva's View</span>
      <button class="close-btn" on:click={onClose} aria-label="Close system context">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>

    <div class="context-body">
      {#if loading && !systemData}
        <div class="context-loading">
          <div class="loading-ring"></div>
          <span>Scanning system...</span>
        </div>
      {:else if systemData}
        <!-- Active Windows -->
        {#if systemData.windows?.length > 0}
          <div class="context-section">
            <span class="section-label">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
              </svg>
              Open Windows
            </span>
            <div class="context-list">
              {#each systemData.windows.slice(0, 8) as win}
                <div class="context-item" class:focused={win.focused}>
                  <span class="item-process">{win.process || 'Unknown'}</span>
                  <span class="item-title">{(win.title || '').slice(0, 40)}</span>
                </div>
              {/each}
              {#if systemData.windows.length > 8}
                <span class="context-more">+{systemData.windows.length - 8} more</span>
              {/if}
            </div>
          </div>
        {/if}

        <!-- Clipboard -->
        {#if systemData.clipboard}
          <div class="context-section">
            <span class="section-label">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
              </svg>
              Clipboard
            </span>
            <div class="clipboard-preview">{systemData.clipboard.slice(0, 120)}{systemData.clipboard.length > 120 ? '...' : ''}</div>
          </div>
        {/if}

        <!-- Time -->
        {#if systemData.time}
          <div class="context-section">
            <span class="section-label">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
              </svg>
              System Time
            </span>
            <span class="context-value">{systemData.time}</span>
          </div>
        {/if}
      {:else}
        <div class="context-empty">
          <span>System context unavailable</span>
          <span class="context-hint">Connect to voice to enable monitoring</span>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .context-panel {
    background: var(--color-bg);
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    width: 320px;
    max-height: 400px;
    overflow: hidden;
    animation: fadeInScale 0.2s ease;
  }

  .context-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border-bottom: 1px solid var(--color-border);
    color: var(--color-cyan);
  }

  .context-title {
    font-size: 12px;
    font-weight: 600;
    flex: 1;
  }

  .close-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border: none;
    border-radius: 4px;
    background: transparent;
    color: var(--color-muted);
    cursor: pointer;
  }

  .close-btn:hover {
    background: var(--color-surface);
    color: var(--color-text);
  }

  .context-body {
    padding: 10px 14px;
    overflow-y: auto;
    max-height: 340px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .context-section {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .section-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--color-muted);
  }

  .context-list {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .context-item {
    display: flex;
    flex-direction: column;
    gap: 1px;
    padding: 5px 8px;
    border-radius: var(--radius-sm);
    background: var(--color-surface);
    border: 1px solid transparent;
  }

  .context-item.focused {
    border-color: var(--color-cyan);
    background: var(--color-cyan-glow);
  }

  .item-process {
    font-size: 11px;
    font-weight: 600;
    font-family: var(--font-mono);
    color: var(--color-text);
  }

  .item-title {
    font-size: 10px;
    color: var(--color-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .context-more {
    font-size: 10px;
    color: var(--color-muted);
    padding: 2px 8px;
  }

  .clipboard-preview {
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--color-text-secondary);
    padding: 6px 8px;
    background: var(--color-surface);
    border-radius: var(--radius-sm);
    word-break: break-all;
    line-height: 1.4;
  }

  .context-value {
    font-size: 12px;
    font-family: var(--font-mono);
    color: var(--color-text);
  }

  .context-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 20px;
    color: var(--color-muted);
    font-size: 12px;
  }

  .loading-ring {
    width: 20px;
    height: 20px;
    border: 2px solid var(--color-border);
    border-top-color: var(--color-cyan);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  .context-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: 20px;
    font-size: 12px;
    color: var(--color-text-secondary);
  }

  .context-hint {
    font-size: 11px;
    color: var(--color-muted);
  }
</style>
