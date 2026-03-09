<script>
  import { transcript, sendText, agentState, connectionState } from '../stores/connection.js';
  import { afterUpdate } from 'svelte';
  import VoiceControls from './VoiceControls.svelte';

  let container;
  let inputText = '';
  let inputEl;
  let autoScroll = true;
  let searchMode = false;
  let searchText = '';
  let collapsedToolGroups = new Set();

  $: connected = $connectionState === 'connected';
  $: thinking = $agentState === 'thinking';

  $: filteredTranscript = searchText
    ? $transcript.filter(e => {
        const text = e.text || e.tool || e.tool_result || '';
        return text.toLowerCase().includes(searchText.toLowerCase());
      })
    : $transcript;

  // Group consecutive tool_call/tool_result entries together
  $: groupedTranscript = groupEntries(filteredTranscript);

  function groupEntries(entries) {
    const groups = [];
    let i = 0;
    while (i < entries.length) {
      const entry = entries[i];
      if (entry.type === 'tool_call' || entry.type === 'tool_result') {
        // Collect consecutive tool entries
        const toolGroup = [];
        while (i < entries.length && (entries[i].type === 'tool_call' || entries[i].type === 'tool_result')) {
          toolGroup.push(entries[i]);
          i++;
        }
        if (toolGroup.length > 2) {
          // Group them
          groups.push({ type: 'tool_group', entries: toolGroup, id: toolGroup[0].id + '_group' });
        } else {
          // Too few to group — keep individual
          for (const te of toolGroup) groups.push(te);
        }
      } else {
        groups.push(entry);
        i++;
      }
    }
    return groups;
  }

  function toggleToolGroup(groupId) {
    if (collapsedToolGroups.has(groupId)) {
      collapsedToolGroups.delete(groupId);
    } else {
      collapsedToolGroups.add(groupId);
    }
    collapsedToolGroups = collapsedToolGroups; // trigger reactivity
  }

  afterUpdate(() => {
    if (container && autoScroll) {
      container.scrollTop = container.scrollHeight;
    }
  });

  function handleScroll() {
    if (!container) return;
    const atBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 60;
    autoScroll = atBottom;
  }

  function scrollToBottom() {
    if (container) {
      container.scrollTop = container.scrollHeight;
      autoScroll = true;
    }
  }

  function scrollToMessage(index) {
    if (!container) return;
    const messages = container.querySelectorAll('.message, .tool-group');
    if (messages[index]) {
      messages[index].scrollIntoView({ behavior: 'smooth', block: 'center' });
      autoScroll = false;
    }
  }

  function handleSubmit() {
    const text = inputText.trim();
    if (!text) return;
    sendText(text);
    inputText = '';
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
    if (e.key === 'Escape' && searchMode) {
      searchMode = false;
      searchText = '';
    }
  }

  function toggleSearch() {
    searchMode = !searchMode;
    if (!searchMode) searchText = '';
  }

  function formatToolArgs(args) {
    if (!args || Object.keys(args).length === 0) return '';
    const entries = Object.entries(args);
    if (entries.length === 1) return `${entries[0][0]}: ${entries[0][1]}`;
    return entries.map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`).join(', ');
  }
</script>

<div class="transcript-wrapper">
  <!-- Header -->
  <div class="transcript-header">
    <span class="header-title">Conversation</span>
    <div class="header-actions">
      <button class="header-btn" class:active={searchMode} on:click={toggleSearch} title="Search (Ctrl+F)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
      </button>
      {#if !autoScroll}
        <button class="header-btn scroll-btn" on:click={scrollToBottom} title="Scroll to bottom">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>
      {/if}
    </div>
  </div>

  {#if searchMode}
    <div class="search-bar">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      <input
        type="text"
        bind:value={searchText}
        placeholder="Search messages..."
        class="search-input"
        on:keydown={handleKeydown}
      />
      {#if searchText}
        <span class="search-count">{filteredTranscript.length}</span>
      {/if}
    </div>
  {/if}

  <!-- Messages -->
  <div class="transcript" bind:this={container} on:scroll={handleScroll}>
    {#each groupedTranscript as entry, i (entry.id)}
      {#if entry.type === 'tool_group'}
        <!-- Collapsible tool group -->
        <div class="tool-group" style="animation-delay: {Math.min(i * 0.02, 0.3)}s">
          <button class="tool-group-header" on:click={() => toggleToolGroup(entry.id)}>
            <svg class="tool-group-chevron" class:expanded={!collapsedToolGroups.has(entry.id)} width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
            <span class="tool-group-label">{entry.entries.length} tool operations</span>
            <span class="tool-group-names">{[...new Set(entry.entries.filter(e => e.type === 'tool_call').map(e => e.tool))].join(', ')}</span>
          </button>
          {#if !collapsedToolGroups.has(entry.id)}
            <div class="tool-group-body">
              {#each entry.entries as te}
                {#if te.type === 'tool_call'}
                  <div class="tool-message">
                    <div class="tool-icon">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>
                      </svg>
                    </div>
                    <div class="tool-content">
                      <span class="tool-name">{te.tool}</span>
                      {#if te.tool_args && Object.keys(te.tool_args).length > 0}
                        <span class="tool-args">{formatToolArgs(te.tool_args)}</span>
                      {/if}
                    </div>
                  </div>
                {:else}
                  <div class="tool-message result">
                    <div class="tool-icon result">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                    </div>
                    <div class="tool-content">
                      <span class="tool-name">{te.tool}</span>
                      {#if te.tool_result}
                        <span class="tool-result-text">{te.tool_result}</span>
                      {/if}
                    </div>
                  </div>
                {/if}
              {/each}
            </div>
          {/if}
        </div>
      {:else if entry.type === 'tool_call'}
        <div class="message" style="animation-delay: {Math.min(i * 0.02, 0.3)}s">
          <div class="tool-message">
            <div class="tool-icon">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>
              </svg>
            </div>
            <div class="tool-content">
              <span class="tool-name">{entry.tool}</span>
              {#if entry.tool_args && Object.keys(entry.tool_args).length > 0}
                <span class="tool-args">{formatToolArgs(entry.tool_args)}</span>
              {/if}
            </div>
          </div>
        </div>
      {:else if entry.type === 'tool_result'}
        <div class="message" style="animation-delay: {Math.min(i * 0.02, 0.3)}s">
          <div class="tool-message result">
            <div class="tool-icon result">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            </div>
            <div class="tool-content">
              <span class="tool-name">{entry.tool}</span>
              {#if entry.tool_result}
                <span class="tool-result-text">{entry.tool_result}</span>
              {/if}
            </div>
          </div>
        </div>
      {:else}
        <div class="message message-{entry.role}" style="animation-delay: {Math.min(i * 0.02, 0.3)}s">
          <div class="bubble" class:user={entry.role === 'user'} class:agent={entry.role === 'assistant'}>
            <span class="bubble-text">{entry.text}</span>
          </div>
        </div>
      {/if}
    {/each}

    {#if thinking}
      <div class="message message-assistant" style="animation: fadeIn 0.3s ease">
        <div class="bubble agent thinking-bubble">
          <div class="thinking-dots">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
        </div>
      </div>
    {/if}

    {#if $transcript.length === 0 && !thinking}
      <div class="empty-state">
        <div class="empty-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
        </div>
        <span class="empty-text">Connect and start talking</span>
        <span class="empty-sub">or type a message below</span>
      </div>
    {/if}
  </div>

  <!-- Timeline scrubber -->
  {#if $transcript.length > 3}
    <div class="timeline-bar">
      <div class="timeline-track">
        {#each $transcript as entry, i}
          <button
            class="timeline-marker"
            class:user={entry.role === 'user'}
            class:agent={entry.role === 'assistant'}
            class:tool={entry.type === 'tool_call' || entry.type === 'tool_result'}
            style="left: {(i / ($transcript.length - 1)) * 100}%"
            on:click={() => scrollToMessage(i)}
            title="{entry.role === 'user' ? 'You' : entry.type === 'tool_call' ? entry.tool : 'Minerva'}: {(entry.text || entry.tool || '').slice(0, 30)}"
          ></button>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Input -->
  <div class="input-area">
    <div class="input-row">
      <input
        bind:this={inputEl}
        type="text"
        bind:value={inputText}
        on:keydown={handleKeydown}
        placeholder={connected ? "Message Minerva..." : "Connect to send messages..."}
        disabled={!connected}
        class="message-input"
      />
      <button
        class="send-btn"
        disabled={!inputText.trim() || !connected}
        on:click={handleSubmit}
        aria-label="Send message"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
        </svg>
      </button>
    </div>
  </div>

  <VoiceControls />
</div>

<style>
  .transcript-wrapper {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--color-bg-deep);
  }

  /* ── Header ──────────────────────────────── */
  .transcript-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 14px;
    border-bottom: 1px solid var(--color-border);
    min-height: 42px;
  }

  .header-title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--color-muted);
  }

  .header-actions {
    display: flex;
    gap: 4px;
  }

  .header-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--color-muted);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .header-btn:hover {
    background: var(--color-surface);
    color: var(--color-text);
  }

  .header-btn.active {
    background: var(--color-blue-glow);
    color: var(--color-blue);
  }

  .scroll-btn {
    animation: breathe 2s ease-in-out infinite;
  }

  /* ── Search ──────────────────────────────── */
  .search-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border-bottom: 1px solid var(--color-border);
    color: var(--color-muted);
    animation: slideDown 0.2s ease;
  }

  .search-input {
    flex: 1;
    background: none;
    border: none;
    color: var(--color-text);
    font-size: 12px;
    font-family: inherit;
    outline: none;
  }

  .search-input::placeholder {
    color: var(--color-muted);
  }

  .search-count {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--color-text-secondary);
    background: var(--color-surface);
    padding: 1px 6px;
    border-radius: var(--radius-full);
  }

  /* ── Messages area ───────────────────────── */
  .transcript {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 12px 10px;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .message {
    animation: fadeIn 0.25s ease both;
  }

  /* ── Chat bubbles ────────────────────────── */
  .bubble {
    max-width: 92%;
    padding: 8px 12px;
    border-radius: var(--radius-lg);
    font-size: 13px;
    line-height: 1.45;
    word-break: break-word;
  }

  .bubble.user {
    align-self: flex-end;
    margin-left: auto;
    background: var(--color-blue);
    color: #fff;
    border-bottom-right-radius: 4px;
  }

  .bubble.agent {
    align-self: flex-start;
    background: var(--color-surface);
    color: var(--color-text);
    border: 1px solid var(--color-border);
    border-bottom-left-radius: 4px;
  }

  .bubble-text {
    display: block;
  }

  /* ── Tool messages ───────────────────────── */
  .tool-message {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 5px 10px;
    border-radius: var(--radius-md);
    background: rgba(74, 158, 255, 0.04);
    border-left: 2px solid rgba(74, 158, 255, 0.2);
  }

  .tool-message.result {
    background: rgba(74, 222, 128, 0.04);
    border-left-color: rgba(74, 222, 128, 0.2);
  }

  .tool-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border-radius: 4px;
    background: rgba(74, 158, 255, 0.1);
    color: var(--color-blue);
    flex-shrink: 0;
    margin-top: 1px;
  }

  .tool-icon.result {
    background: rgba(74, 222, 128, 0.1);
    color: var(--color-green);
  }

  .tool-content {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .tool-name {
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 600;
    color: var(--color-text-secondary);
  }

  .tool-args, .tool-result-text {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-muted);
    word-break: break-all;
    line-height: 1.4;
  }

  /* ── Tool groups ──────────────────────────── */
  .tool-group {
    border-radius: var(--radius-md);
    border: 1px solid rgba(74, 158, 255, 0.08);
    background: rgba(74, 158, 255, 0.02);
    overflow: hidden;
    animation: fadeIn 0.25s ease both;
  }

  .tool-group-header {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 6px 10px;
    background: none;
    border: none;
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: 11px;
    cursor: pointer;
    transition: all var(--transition-fast);
    text-align: left;
  }

  .tool-group-header:hover {
    background: rgba(74, 158, 255, 0.05);
  }

  .tool-group-chevron {
    transition: transform var(--transition-fast);
    flex-shrink: 0;
  }

  .tool-group-chevron.expanded {
    transform: rotate(90deg);
  }

  .tool-group-label {
    font-weight: 600;
    color: var(--color-blue);
  }

  .tool-group-names {
    color: var(--color-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .tool-group-body {
    padding: 0 6px 6px;
    display: flex;
    flex-direction: column;
    gap: 3px;
    animation: slideDown 0.15s ease;
  }

  /* ── Thinking indicator ──────────────────── */
  .thinking-bubble {
    padding: 10px 16px;
  }

  .thinking-dots {
    display: flex;
    gap: 5px;
    align-items: center;
  }

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--color-text-secondary);
    animation: dotPulse 1.4s ease-in-out infinite;
  }

  .dot:nth-child(2) { animation-delay: 0.2s; }
  .dot:nth-child(3) { animation-delay: 0.4s; }

  @keyframes dotPulse {
    0%, 60%, 100% { transform: scale(0.6); opacity: 0.3; }
    30% { transform: scale(1); opacity: 1; }
  }

  /* ── Empty state ─────────────────────────── */
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex: 1;
    gap: 8px;
    padding: 20px;
    animation: fadeIn 0.5s ease;
  }

  .empty-icon {
    color: var(--color-muted);
    opacity: 0.4;
    margin-bottom: 4px;
  }

  .empty-text {
    font-size: 13px;
    color: var(--color-text-secondary);
    font-weight: 500;
  }

  .empty-sub {
    font-size: 11px;
    color: var(--color-muted);
  }

  /* ── Timeline scrubber ────────────────────── */
  .timeline-bar {
    padding: 4px 12px;
    border-top: 1px solid var(--color-border);
    background: var(--color-bg-deep);
  }

  .timeline-track {
    position: relative;
    height: 8px;
    background: var(--color-surface);
    border-radius: var(--radius-full);
    overflow: visible;
  }

  .timeline-marker {
    position: absolute;
    top: 50%;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    transform: translate(-50%, -50%);
    border: none;
    padding: 0;
    cursor: pointer;
    transition: all var(--transition-fast);
    z-index: 1;
    background: var(--color-muted);
  }

  .timeline-marker:hover {
    transform: translate(-50%, -50%) scale(2);
    z-index: 2;
  }

  .timeline-marker.user {
    background: var(--color-blue);
    box-shadow: 0 0 4px var(--color-blue-glow);
  }

  .timeline-marker.agent {
    background: var(--color-green);
    box-shadow: 0 0 4px var(--color-green-glow);
  }

  .timeline-marker.tool {
    background: var(--color-yellow);
    width: 4px;
    height: 4px;
    opacity: 0.6;
  }

  /* ── Input area ──────────────────────────── */
  .input-area {
    padding: 8px 10px;
    border-top: 1px solid var(--color-border);
  }

  .input-row {
    display: flex;
    gap: 6px;
    align-items: center;
  }

  .message-input {
    flex: 1;
    padding: 9px 14px;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-surface);
    color: var(--color-text);
    font-size: 13px;
    font-family: inherit;
    outline: none;
    transition: border-color var(--transition-fast);
  }

  .message-input:focus {
    border-color: var(--color-blue);
    box-shadow: 0 0 0 2px var(--color-blue-glow);
  }

  .message-input::placeholder {
    color: var(--color-muted);
  }

  .message-input:disabled {
    opacity: 0.4;
  }

  .send-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    border: none;
    border-radius: var(--radius-full);
    background: var(--color-blue);
    color: #fff;
    cursor: pointer;
    flex-shrink: 0;
    transition: all var(--transition-fast);
  }

  .send-btn:hover:not(:disabled) {
    background: #5aadff;
    box-shadow: var(--shadow-glow-blue);
  }

  .send-btn:disabled {
    opacity: 0.25;
    cursor: default;
  }
</style>
