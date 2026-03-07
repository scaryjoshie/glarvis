<script>
  import { boardStream, boardFocused } from '../stores/connection.js';
  import { marked } from 'marked';
  import DOMPurify from 'dompurify';

  marked.setOptions({ breaks: true, gfm: true });

  let hoveredIndex = null;

  $: displayIndex = hoveredIndex !== null ? hoveredIndex : $boardFocused;
  $: focused = displayIndex !== null ? $boardStream[displayIndex] : null;
  $: focusedHtml = focused ? DOMPurify.sanitize(marked.parse(focused.content)) : '';

  function formatTime(ts) {
    return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function focusItem(i) {
    boardFocused.set(i);
  }
</script>

<div class="board-layout">
  <!-- Main area: focused item -->
  <div class="board-main">
    {#if focused}
      <div class="board-header">
        <span class="board-author">{focused.author}</span>
        <span class="board-time">{formatTime(focused.timestamp)}</span>
      </div>
      <div class="board-content">
        {@html focusedHtml}
      </div>
    {:else}
      <div class="empty">
        <div class="empty-label">Board</div>
        <div class="empty-hint">Tool output and content will appear here</div>
      </div>
    {/if}
  </div>

  <!-- Stream sidebar (always visible) -->
  <div class="board-stream">
    <div class="stream-label">Stream</div>
    {#each $boardStream as item, i}
      <button
        class="stream-item"
        class:active={$boardFocused === i}
        class:hovered={hoveredIndex === i && $boardFocused !== i}
        on:click={() => focusItem(i)}
        on:mouseenter={() => hoveredIndex = i}
        on:mouseleave={() => hoveredIndex = null}
      >
        <span class="stream-author">{item.author}</span>
        <span class="stream-time">{formatTime(item.timestamp)}</span>
        <span class="stream-preview">{item.content.slice(0, 60)}</span>
      </button>
    {/each}
    {#if $boardStream.length === 0}
      <div class="stream-empty">No posts yet</div>
    {/if}
  </div>
</div>

<style>
  .board-layout {
    display: flex;
    height: 100%;
  }

  .board-main {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    min-width: 0;
  }

  .board-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--color-border);
  }

  .board-author {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--color-blue);
  }

  .board-time {
    font-size: 11px;
    color: var(--color-muted);
  }

  .board-content {
    color: var(--color-text);
    line-height: 1.6;
    font-size: 14px;
  }

  .board-content :global(pre) {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 12px;
    overflow-x: auto;
    font-family: var(--font-mono);
    font-size: 13px;
  }

  .board-content :global(code) {
    font-family: var(--font-mono);
    font-size: 13px;
  }

  .board-content :global(p code) {
    background: var(--color-surface);
    padding: 2px 6px;
    border-radius: 3px;
  }

  .board-content :global(h1),
  .board-content :global(h2),
  .board-content :global(h3) {
    color: var(--color-text);
    margin-top: 16px;
    margin-bottom: 8px;
  }

  .board-content :global(ul),
  .board-content :global(ol) {
    padding-left: 20px;
  }

  .board-content :global(table) {
    border-collapse: collapse;
    width: 100%;
  }

  .board-content :global(th),
  .board-content :global(td) {
    border: 1px solid var(--color-border);
    padding: 6px 10px;
    text-align: left;
  }

  .board-content :global(th) {
    background: var(--color-surface);
  }

  .board-stream {
    width: 180px;
    min-width: 180px;
    border-left: 1px solid var(--color-border);
    overflow-y: auto;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .stream-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--color-muted);
    padding: 4px 6px;
  }

  .stream-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 6px 8px;
    border: 1px solid transparent;
    border-radius: 4px;
    background: none;
    color: var(--color-text);
    cursor: pointer;
    text-align: left;
    font-family: inherit;
  }

  .stream-item:hover {
    background: var(--color-surface);
  }

  .stream-item.active {
    border-color: var(--color-blue);
    background: var(--color-surface);
  }

  .stream-item.hovered {
    border-color: var(--color-border);
    background: var(--color-surface);
  }

  .stream-author {
    font-size: 11px;
    font-weight: 600;
    color: var(--color-blue);
  }

  .stream-time {
    font-size: 10px;
    color: var(--color-muted);
  }

  .stream-preview {
    font-size: 11px;
    color: var(--color-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 8px;
  }

  .empty-label {
    font-size: 18px;
    color: var(--color-muted);
    font-weight: 500;
  }

  .empty-hint {
    font-size: 13px;
    color: var(--color-muted);
    opacity: 0.6;
  }

  .stream-empty {
    font-size: 11px;
    color: var(--color-muted);
    opacity: 0.5;
    padding: 8px 6px;
    font-style: italic;
  }
</style>
