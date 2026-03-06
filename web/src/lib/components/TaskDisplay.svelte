<script>
  import { tasks, boardFocused } from '../stores/connection.js';

  function statusColor(status) {
    switch (status) {
      case 'running': return 'var(--color-blue)';
      case 'completed': return 'var(--color-green)';
      case 'failed':
      case 'expired': return 'var(--color-red)';
      default: return 'var(--color-muted)';
    }
  }

  function formatElapsed(seconds) {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    return `${Math.floor(seconds / 60)}m${Math.round(seconds % 60)}s`;
  }

  function handleChipClick(task) {
    if (task.board_post_index !== null && task.board_post_index !== undefined) {
      boardFocused.set(task.board_post_index);
    }
  }

  function clearCompleted() {
    tasks.update(t => t.filter(task => task.status === 'running'));
  }

  $: hasCompleted = $tasks.some(t => t.status !== 'running');
</script>

<div class="task-bar" class:empty={$tasks.length === 0}>
  {#if $tasks.length > 0}
    <div class="task-chips">
      {#each $tasks as task (task.id)}
        <button
          class="task-chip"
          class:clickable={task.board_post_index !== null && task.board_post_index !== undefined}
          on:click={() => handleChipClick(task)}
          title="{task.name}: {task.progress || task.status} ({formatElapsed(task.elapsed)})"
        >
          <span class="chip-dot" style="background: {statusColor(task.status)}">
            {#if task.status === 'running'}
              <span class="chip-spin"></span>
            {/if}
          </span>
          <span class="chip-name">{task.name}</span>
          <span class="chip-time">{formatElapsed(task.elapsed)}</span>
        </button>
      {/each}
    </div>
    {#if hasCompleted}
      <button class="clear-btn" on:click={clearCompleted} title="Clear completed tasks">Clear</button>
    {/if}
  {:else}
    <span class="no-tasks">No active tasks</span>
  {/if}
</div>

<style>
  .task-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    min-height: 40px;
    border-bottom: 1px solid var(--color-border);
  }

  .task-bar.empty {
    justify-content: center;
  }

  .no-tasks {
    font-size: 11px;
    color: var(--color-muted);
    opacity: 0.5;
  }

  .task-chips {
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 1;
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-width: none;
  }

  .task-chips::-webkit-scrollbar {
    display: none;
  }

  .task-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    border-radius: 999px;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    font-size: 12px;
    cursor: default;
    flex-shrink: 0;
    transition: background 0.15s;
    color: inherit;
    font-family: inherit;
  }

  .task-chip:hover {
    background: var(--color-surface-hover);
  }

  .task-chip.clickable {
    cursor: pointer;
  }

  .task-chip.clickable:hover {
    border-color: var(--color-blue);
  }

  .chip-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
    position: relative;
  }

  .chip-spin {
    position: absolute;
    inset: -3px;
    border: 2px solid transparent;
    border-top-color: var(--color-blue);
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .chip-name {
    font-family: var(--font-mono);
    color: var(--color-text);
  }

  .chip-time {
    color: var(--color-muted);
    font-family: var(--font-mono);
    font-size: 11px;
  }

  .clear-btn {
    padding: 3px 10px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: none;
    color: var(--color-muted);
    font-size: 11px;
    cursor: pointer;
    flex-shrink: 0;
    font-family: inherit;
  }

  .clear-btn:hover {
    color: var(--color-text);
    border-color: var(--color-muted);
  }
</style>
