<script>
  import { onMount, onDestroy } from 'svelte';
  import {
    connectionState, sendText, openSettings,
    toggleMute, toggleDeafen, connectWebSocket, connectWebRTC, disconnect,
  } from '../stores/connection.js';
  import { downloadConversation, saveCurrentSession } from '../stores/history.js';

  export let visible = false;
  export let onClose = () => {};

  let query = '';
  let selectedIndex = 0;
  let inputEl;

  $: connected = $connectionState === 'connected';

  const commands = [
    { id: 'search-files', label: 'Search Files', icon: 'search', category: 'Tools', action: () => sendText('search files'), requiresConnection: true },
    { id: 'list-dir', label: 'List Directory', icon: 'folder', category: 'Tools', action: () => sendText('list directory'), requiresConnection: true },
    { id: 'get-time', label: 'Get Time', icon: 'clock', category: 'Tools', action: () => sendText('what time is it'), requiresConnection: true },
    { id: 'list-tools', label: 'List All Tools', icon: 'grid', category: 'Tools', action: () => sendText('list my tools'), requiresConnection: true },
    { id: 'open-terminal', label: 'Open Terminal', icon: 'terminal', category: 'Tools', action: () => sendText('open terminal'), requiresConnection: true },
    { id: 'search-programs', label: 'Search Programs', icon: 'app', category: 'Tools', action: () => sendText('search programs'), requiresConnection: true },
    { id: 'switch-window', label: 'Switch Window', icon: 'window', category: 'Tools', action: () => sendText('switch window'), requiresConnection: true },
    { id: 'read-clipboard', label: 'Read Clipboard', icon: 'clipboard', category: 'Tools', action: () => sendText('read my clipboard'), requiresConnection: true },

    { id: 'connect', label: 'Connect Voice', icon: 'play', category: 'Control', action: () => { connectWebSocket(); connectWebRTC(); }, requiresConnection: false, hideWhenConnected: true },
    { id: 'disconnect', label: 'Disconnect Voice', icon: 'stop', category: 'Control', action: () => disconnect(), requiresConnection: true },
    { id: 'mute', label: 'Toggle Mute', icon: 'mic', category: 'Control', action: () => toggleMute(), requiresConnection: true },
    { id: 'deafen', label: 'Toggle Deafen', icon: 'headphones', category: 'Control', action: () => toggleDeafen(), requiresConnection: true },
    { id: 'settings', label: 'Open Settings', icon: 'settings', category: 'App', action: () => openSettings() },
    { id: 'export', label: 'Export Conversation', icon: 'download', category: 'App', action: () => downloadConversation() },
    { id: 'save-session', label: 'Save Session Snapshot', icon: 'save', category: 'App', action: () => { saveCurrentSession(); if (window.__minerva_toast) window.__minerva_toast('Session saved', 'success', 2000); } },
  ];

  $: filtered = commands.filter(cmd => {
    if (cmd.requiresConnection && !connected) return false;
    if (cmd.hideWhenConnected && connected) return false;
    if (!query) return true;
    return cmd.label.toLowerCase().includes(query.toLowerCase()) ||
           cmd.category.toLowerCase().includes(query.toLowerCase());
  });

  $: if (selectedIndex >= filtered.length) selectedIndex = Math.max(0, filtered.length - 1);

  $: grouped = filtered.reduce((acc, cmd) => {
    if (!acc[cmd.category]) acc[cmd.category] = [];
    acc[cmd.category].push(cmd);
    return acc;
  }, {});

  function executeSelected() {
    const cmd = filtered[selectedIndex];
    if (cmd) {
      cmd.action();
      close();
    }
  }

  function close() {
    visible = false;
    query = '';
    selectedIndex = 0;
    onClose();
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      close();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIndex = (selectedIndex + 1) % filtered.length;
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIndex = (selectedIndex - 1 + filtered.length) % filtered.length;
    } else if (e.key === 'Enter') {
      e.preventDefault();
      executeSelected();
    }
  }

  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) close();
  }

  $: if (visible && inputEl) {
    setTimeout(() => inputEl?.focus(), 50);
  }
</script>

{#if visible}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="palette-backdrop" on:click={handleBackdropClick} on:keydown={handleKeydown}>
    <div class="palette">
      <div class="palette-input-row">
        <svg class="palette-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input
          bind:this={inputEl}
          type="text"
          bind:value={query}
          on:keydown={handleKeydown}
          placeholder="Type a command..."
          class="palette-input"
        />
        <kbd class="palette-esc">ESC</kbd>
      </div>

      <div class="palette-results">
        {#if filtered.length === 0}
          <div class="palette-empty">No matching commands</div>
        {:else}
          {#each Object.entries(grouped) as [category, cmds]}
            <div class="palette-group">
              <div class="palette-group-label">{category}</div>
              {#each cmds as cmd, i}
                {@const globalIdx = filtered.indexOf(cmd)}
                <button
                  class="palette-item"
                  class:selected={globalIdx === selectedIndex}
                  on:click={() => { selectedIndex = globalIdx; executeSelected(); }}
                  on:mouseenter={() => selectedIndex = globalIdx}
                >
                  <span class="item-label">{cmd.label}</span>
                  {#if cmd.shortcut}
                    <kbd class="item-shortcut">{cmd.shortcut}</kbd>
                  {/if}
                </button>
              {/each}
            </div>
          {/each}
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .palette-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 15vh;
    z-index: 10000;
    animation: fadeIn 0.15s ease;
  }

  .palette {
    width: 480px;
    max-height: 420px;
    background: var(--color-bg);
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg), 0 0 60px rgba(74, 158, 255, 0.05);
    overflow: hidden;
    animation: fadeInScale 0.2s ease;
  }

  .palette-input-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 16px;
    border-bottom: 1px solid var(--color-border);
  }

  .palette-icon {
    color: var(--color-muted);
    flex-shrink: 0;
  }

  .palette-input {
    flex: 1;
    background: none;
    border: none;
    color: var(--color-text);
    font-size: 15px;
    font-family: inherit;
    outline: none;
  }

  .palette-input::placeholder {
    color: var(--color-muted);
  }

  .palette-esc {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--color-muted);
    padding: 2px 6px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: var(--color-surface);
  }

  .palette-results {
    overflow-y: auto;
    max-height: 340px;
    padding: 6px;
  }

  .palette-empty {
    padding: 20px;
    text-align: center;
    color: var(--color-muted);
    font-size: 13px;
  }

  .palette-group {
    margin-bottom: 4px;
  }

  .palette-group-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--color-muted);
    padding: 6px 10px 4px;
  }

  .palette-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 8px 12px;
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--color-text);
    font-size: 13px;
    font-family: inherit;
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .palette-item:hover,
  .palette-item.selected {
    background: var(--color-surface);
  }

  .palette-item.selected {
    background: var(--color-blue-glow);
    border: 1px solid rgba(74, 158, 255, 0.15);
  }

  .item-label {
    font-weight: 500;
  }

  .item-shortcut {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--color-muted);
    padding: 1px 5px;
    border: 1px solid var(--color-border);
    border-radius: 3px;
    background: var(--color-surface);
  }
</style>
