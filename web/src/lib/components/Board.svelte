<script>
  import { boardContent } from '../stores/connection.js';
  import { marked } from 'marked';

  // Configure marked for code blocks
  marked.setOptions({
    breaks: true,
    gfm: true,
  });

  $: html = $boardContent ? marked.parse($boardContent) : '';
</script>

<div class="board">
  {#if html}
    <div class="board-content">
      {@html html}
    </div>
  {:else}
    <div class="empty">
      <div class="empty-label">Board</div>
      <div class="empty-hint">Tool output and content will appear here</div>
    </div>
  {/if}
</div>

<style>
  .board {
    height: 100%;
    overflow-y: auto;
    padding: 16px;
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
</style>
