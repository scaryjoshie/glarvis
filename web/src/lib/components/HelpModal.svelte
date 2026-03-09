<script>
  export let visible = false;
  export let onClose = () => {};

  const shortcuts = [
    { category: 'Navigation', items: [
      { keys: 'Ctrl + K', desc: 'Open Command Palette' },
      { keys: 'Ctrl + Shift + S', desc: 'Toggle System Context' },
      { keys: '?', desc: 'Show this help' },
      { keys: 'Escape', desc: 'Close overlays' },
    ]},
    { category: 'Voice', items: [
      { keys: 'Click Connect', desc: 'Start voice session' },
      { keys: 'Mic Button', desc: 'Toggle mute' },
      { keys: 'Speaker Button', desc: 'Toggle deafen' },
    ]},
    { category: 'Transcript', items: [
      { keys: 'Enter', desc: 'Send message' },
      { keys: 'Shift + Enter', desc: 'New line' },
    ]},
    { category: 'Board', items: [
      { keys: 'Click pin icon', desc: 'Pin/unpin board post' },
      { keys: 'Click copy icon', desc: 'Copy board content' },
      { keys: 'Click stream item', desc: 'Focus board post' },
    ]},
    { category: 'Quick Tools', items: [
      { keys: 'Ctrl+K → search', desc: 'Search files' },
      { keys: 'Ctrl+K → terminal', desc: 'Open terminal' },
      { keys: 'Ctrl+K → time', desc: 'Get current time' },
    ]},
  ];

  function handleKeydown(e) {
    if (e.key === 'Escape') {
      onClose();
    }
  }
</script>

{#if visible}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="help-backdrop" on:click={onClose} on:keydown={handleKeydown}>
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="help-modal" on:click|stopPropagation={() => {}}>
      <div class="help-header">
        <h2 class="help-title">Keyboard Shortcuts</h2>
        <button class="help-close" on:click={onClose} aria-label="Close help">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <div class="help-body">
        {#each shortcuts as group}
          <div class="shortcut-group">
            <h3 class="group-title">{group.category}</h3>
            <div class="group-items">
              {#each group.items as item}
                <div class="shortcut-row">
                  <kbd class="shortcut-keys">{item.keys}</kbd>
                  <span class="shortcut-desc">{item.desc}</span>
                </div>
              {/each}
            </div>
          </div>
        {/each}
      </div>

      <div class="help-footer">
        <span class="footer-hint">Press <kbd>?</kbd> to toggle this overlay</span>
      </div>
    </div>
  </div>
{/if}

<style>
  .help-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    animation: fadeIn 0.15s ease;
  }

  .help-modal {
    width: 540px;
    max-height: 80vh;
    background: var(--color-bg);
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    animation: fadeInScale 0.2s ease;
  }

  .help-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--color-border);
  }

  .help-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--color-text);
    margin: 0;
  }

  .help-close {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--color-muted);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .help-close:hover {
    background: var(--color-surface);
    color: var(--color-text);
  }

  .help-body {
    overflow-y: auto;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .shortcut-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .group-title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--color-muted);
    margin: 0;
  }

  .group-items {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .shortcut-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 10px;
    border-radius: var(--radius-sm);
    transition: background var(--transition-fast);
  }

  .shortcut-row:hover {
    background: var(--color-surface);
  }

  .shortcut-keys {
    font-family: var(--font-mono);
    font-size: 11px;
    padding: 3px 8px;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 4px;
    color: var(--color-text);
    white-space: nowrap;
  }

  .shortcut-desc {
    font-size: 13px;
    color: var(--color-text-secondary);
  }

  .help-footer {
    padding: 12px 20px;
    border-top: 1px solid var(--color-border);
    text-align: center;
  }

  .footer-hint {
    font-size: 11px;
    color: var(--color-muted);
  }

  .footer-hint kbd {
    font-family: var(--font-mono);
    padding: 1px 5px;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 3px;
    font-size: 10px;
  }
</style>
