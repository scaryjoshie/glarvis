<script>
  import { boardStream, boardFocused } from '../stores/connection.js';
  import { marked } from 'marked';
  import DOMPurify from 'dompurify';

  marked.setOptions({ breaks: true, gfm: true });

  let hoveredIndex = null;
  let pinnedIndices = new Set();
  let streamCollapsed = false;

  $: displayIndex = hoveredIndex !== null ? hoveredIndex : $boardFocused;
  $: focused = displayIndex !== null ? $boardStream[displayIndex] : null;
  $: focusedHtml = focused ? DOMPurify.sanitize(marked.parse(focused.content)) : '';
  $: sortedStream = $boardStream.map((item, i) => ({ ...item, _index: i }));

  function formatTime(ts) {
    return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function formatDate(ts) {
    const d = new Date(ts * 1000);
    const now = new Date();
    if (d.toDateString() === now.toDateString()) return 'Today';
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  }

  function focusItem(i) {
    boardFocused.set(i);
  }

  function togglePin(i, e) {
    e.stopPropagation();
    if (pinnedIndices.has(i)) {
      pinnedIndices.delete(i);
    } else {
      pinnedIndices.add(i);
    }
    pinnedIndices = pinnedIndices; // trigger reactivity
  }

  function copyContent() {
    if (focused) {
      navigator.clipboard.writeText(focused.content).catch(() => {});
    }
  }
</script>

<div class="board-layout">
  <!-- Main area: focused item -->
  <div class="board-main">
    {#if focused}
      <div class="board-header">
        <div class="header-left">
          <div class="author-badge">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="3"/><path d="M12 1v2m0 18v2m-9-11h2m18 0h2m-3.5-6.5-1.4 1.4M6.9 17.1 5.5 18.5m0-13 1.4 1.4m10.2 10.2 1.4 1.4"/>
            </svg>
          </div>
          <div class="header-info">
            <span class="board-author">{focused.author}</span>
            <span class="board-time">{formatDate(focused.timestamp)} at {formatTime(focused.timestamp)}</span>
          </div>
        </div>
        <div class="header-actions">
          <button class="action-btn" on:click={(e) => togglePin(displayIndex, e)} class:pinned={pinnedIndices.has(displayIndex)} title="Pin">
            <svg width="13" height="13" viewBox="0 0 24 24" fill={pinnedIndices.has(displayIndex) ? 'currentColor' : 'none'} stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 17v5m-7-5h14l-1.6-7.2a2 2 0 0 0-2-1.5l-1.3-.2a4.8 4.8 0 0 1-2.2-1l-1-1a2 2 0 0 0-2.8 0l-1 1a4.8 4.8 0 0 1-2.2 1l-1.3.2a2 2 0 0 0-2 1.5z"/>
            </svg>
          </button>
          <button class="action-btn" on:click={copyContent} title="Copy content">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
          </button>
        </div>
      </div>
      <div class="board-content">
        {@html focusedHtml}
      </div>
    {:else}
      <div class="empty">
        <div class="empty-orb">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
            <line x1="3" y1="9" x2="21" y2="9"/>
            <line x1="9" y1="21" x2="9" y2="9"/>
          </svg>
        </div>
        <div class="empty-label">Board</div>
        <div class="empty-hint">Tool output and content will appear here</div>
      </div>
    {/if}
  </div>

  <!-- Stream sidebar -->
  <div class="board-stream" class:collapsed={streamCollapsed}>
    <div class="stream-header">
      <span class="stream-label">Stream</span>
      <button class="stream-toggle" on:click={() => streamCollapsed = !streamCollapsed} title={streamCollapsed ? 'Expand' : 'Collapse'}>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          {#if streamCollapsed}
            <polyline points="15 18 9 12 15 6"/>
          {:else}
            <polyline points="9 18 15 12 9 6"/>
          {/if}
        </svg>
      </button>
    </div>

    {#if !streamCollapsed}
      <div class="stream-items">
        <!-- Pinned items first -->
        {#each sortedStream.filter(s => pinnedIndices.has(s._index)) as item (item._index)}
          <button
            class="stream-item pinned"
            class:active={$boardFocused === item._index}
            class:hovered={hoveredIndex === item._index && $boardFocused !== item._index}
            on:click={() => focusItem(item._index)}
            on:mouseenter={() => hoveredIndex = item._index}
            on:mouseleave={() => hoveredIndex = null}
          >
            <div class="stream-item-header">
              <svg class="pin-icon" width="9" height="9" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/></svg>
              <span class="stream-author">{item.author}</span>
              <span class="stream-time">{formatTime(item.timestamp)}</span>
            </div>
            <span class="stream-preview">{item.content.replace(/[#*`]/g, '').slice(0, 50)}</span>
          </button>
        {/each}

        <!-- Rest of items -->
        {#each sortedStream.filter(s => !pinnedIndices.has(s._index)) as item (item._index)}
          <button
            class="stream-item"
            class:active={$boardFocused === item._index}
            class:hovered={hoveredIndex === item._index && $boardFocused !== item._index}
            on:click={() => focusItem(item._index)}
            on:mouseenter={() => hoveredIndex = item._index}
            on:mouseleave={() => hoveredIndex = null}
          >
            <div class="stream-item-header">
              <span class="stream-author">{item.author}</span>
              <span class="stream-time">{formatTime(item.timestamp)}</span>
            </div>
            <span class="stream-preview">{item.content.replace(/[#*`]/g, '').slice(0, 50)}</span>
          </button>
        {/each}

        {#if $boardStream.length === 0}
          <div class="stream-empty">No posts yet</div>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .board-layout {
    display: flex;
    height: 100%;
  }

  /* ── Main content ────────────────────────── */
  .board-main {
    flex: 1;
    overflow-y: auto;
    padding: 20px 24px;
    min-width: 0;
  }

  .board-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--color-border);
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .author-badge {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: var(--radius-md);
    background: var(--color-blue-glow);
    color: var(--color-blue);
  }

  .header-info {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .board-author {
    font-size: 12px;
    font-weight: 600;
    color: var(--color-text);
  }

  .board-time {
    font-size: 10px;
    color: var(--color-muted);
  }

  .header-actions {
    display: flex;
    gap: 4px;
  }

  .action-btn {
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

  .action-btn:hover {
    background: var(--color-surface);
    color: var(--color-text);
  }

  .action-btn.pinned {
    color: var(--color-yellow);
  }

  /* ── Board content (markdown) ────────────── */
  .board-content {
    color: var(--color-text);
    line-height: 1.7;
    font-size: 14px;
    animation: fadeIn 0.3s ease;
  }

  .board-content :global(pre) {
    background: var(--color-surface-solid);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: 14px 16px;
    overflow-x: auto;
    font-family: var(--font-mono);
    font-size: 13px;
    margin: 12px 0;
  }

  .board-content :global(code) {
    font-family: var(--font-mono);
    font-size: 13px;
  }

  .board-content :global(p code) {
    background: var(--color-surface);
    padding: 2px 7px;
    border-radius: 4px;
    border: 1px solid var(--color-border);
  }

  .board-content :global(h1),
  .board-content :global(h2),
  .board-content :global(h3) {
    color: var(--color-text);
    margin-top: 20px;
    margin-bottom: 8px;
    font-weight: 600;
  }

  .board-content :global(h1) { font-size: 20px; }
  .board-content :global(h2) { font-size: 17px; }
  .board-content :global(h3) { font-size: 15px; }

  .board-content :global(ul),
  .board-content :global(ol) {
    padding-left: 24px;
    margin: 8px 0;
  }

  .board-content :global(li) {
    margin: 4px 0;
  }

  .board-content :global(table) {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    font-size: 13px;
  }

  .board-content :global(th),
  .board-content :global(td) {
    border: 1px solid var(--color-border);
    padding: 8px 12px;
    text-align: left;
  }

  .board-content :global(th) {
    background: var(--color-surface);
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .board-content :global(blockquote) {
    border-left: 3px solid var(--color-blue);
    padding-left: 16px;
    margin: 12px 0;
    color: var(--color-text-secondary);
  }

  .board-content :global(a) {
    color: var(--color-blue);
    text-decoration: none;
  }

  .board-content :global(a:hover) {
    text-decoration: underline;
  }

  .board-content :global(hr) {
    border: none;
    border-top: 1px solid var(--color-border);
    margin: 16px 0;
  }

  /* ── Stream sidebar ──────────────────────── */
  .board-stream {
    width: 200px;
    min-width: 200px;
    border-left: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    transition: width var(--transition-normal), min-width var(--transition-normal);
    background: var(--color-bg-deep);
  }

  .board-stream.collapsed {
    width: 36px;
    min-width: 36px;
  }

  .stream-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 10px;
    border-bottom: 1px solid var(--color-border);
    min-height: 42px;
  }

  .stream-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--color-muted);
  }

  .collapsed .stream-label {
    display: none;
  }

  .stream-toggle {
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
    transition: all var(--transition-fast);
  }

  .stream-toggle:hover {
    background: var(--color-surface);
    color: var(--color-text);
  }

  .stream-items {
    overflow-y: auto;
    padding: 6px;
    display: flex;
    flex-direction: column;
    gap: 3px;
    flex: 1;
  }

  .stream-item {
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding: 7px 9px;
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    background: none;
    color: var(--color-text);
    cursor: pointer;
    text-align: left;
    font-family: inherit;
    transition: all var(--transition-fast);
  }

  .stream-item:hover {
    background: var(--color-surface);
  }

  .stream-item.active {
    border-color: var(--color-blue);
    background: var(--color-blue-glow);
  }

  .stream-item.hovered {
    border-color: var(--color-border-strong);
    background: var(--color-surface);
  }

  .stream-item.pinned {
    border-color: rgba(250, 204, 21, 0.15);
    background: rgba(250, 204, 21, 0.03);
  }

  .stream-item-header {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .pin-icon {
    color: var(--color-yellow);
  }

  .stream-author {
    font-size: 10px;
    font-weight: 600;
    color: var(--color-blue);
  }

  .stream-time {
    font-size: 9px;
    color: var(--color-muted);
    margin-left: auto;
  }

  .stream-preview {
    font-size: 11px;
    color: var(--color-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.3;
  }

  /* ── Empty states ────────────────────────── */
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 10px;
    animation: fadeIn 0.5s ease;
  }

  .empty-orb {
    color: var(--color-muted);
    opacity: 0.3;
    animation: breathe 4s ease-in-out infinite;
  }

  .empty-label {
    font-size: 16px;
    color: var(--color-text-secondary);
    font-weight: 500;
  }

  .empty-hint {
    font-size: 12px;
    color: var(--color-muted);
  }

  .stream-empty {
    font-size: 11px;
    color: var(--color-muted);
    opacity: 0.5;
    padding: 12px 8px;
    text-align: center;
  }
</style>
