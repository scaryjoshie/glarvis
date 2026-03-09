<script>
  import { tasks, boardFocused } from '../stores/connection.js';
  import { sendContextToggle } from '../stores/connection.js';

  function statusColor(task) {
    if (task.context_active) return 'var(--color-purple)';
    switch (task.status) {
      case 'running': return 'var(--color-blue)';
      case 'completed': return 'var(--color-green)';
      case 'failed':
      case 'expired': return 'var(--color-red)';
      default: return 'var(--color-muted)';
    }
  }

  function statusGlow(task) {
    if (task.context_active) return 'var(--color-purple-glow)';
    switch (task.status) {
      case 'running': return 'var(--color-blue-glow)';
      case 'completed': return 'var(--color-green-glow)';
      case 'failed':
      case 'expired': return 'var(--color-red-glow)';
      default: return 'transparent';
    }
  }

  function formatElapsed(seconds) {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    return `${Math.floor(seconds / 60)}m${Math.round(seconds % 60)}s`;
  }

  function handleChipClick(task) {
    if (task.is_session) {
      sendContextToggle(task.id);
    } else if (task.board_post_index !== null && task.board_post_index !== undefined) {
      boardFocused.set(task.board_post_index);
    }
  }

  function clearCompleted() {
    tasks.update(t => t.filter(task => task.status === 'running'));
  }

  $: hasCompleted = $tasks.some(t => t.status !== 'running');
  $: runningCount = $tasks.filter(t => t.status === 'running').length;
</script>

<div class="task-bar" class:empty={$tasks.length === 0}>
  {#if $tasks.length > 0}
    <div class="task-chips">
      {#each $tasks as task (task.id)}
        <button
          class="task-chip"
          class:clickable={task.is_session || (task.board_post_index !== null && task.board_post_index !== undefined)}
          class:context-active={task.context_active}
          class:running={task.status === 'running'}
          class:completed={task.status === 'completed'}
          class:failed={task.status === 'failed' || task.status === 'expired'}
          on:click={() => handleChipClick(task)}
          title="{task.name}: {task.progress || task.status} ({formatElapsed(task.elapsed)}){task.context_active ? ' [context active]' : ''}"
          style="--chip-color: {statusColor(task)}; --chip-glow: {statusGlow(task)}"
        >
          <span class="chip-indicator">
            {#if task.status === 'running'}
              <span class="chip-ring"></span>
            {:else if task.status === 'completed'}
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            {:else if task.status === 'failed' || task.status === 'expired'}
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            {/if}
          </span>
          <span class="chip-name">{task.name}</span>
          <span class="chip-time">{formatElapsed(task.elapsed)}</span>
        </button>
      {/each}
    </div>
    {#if hasCompleted}
      <button class="clear-btn" on:click={clearCompleted} title="Clear completed">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    {/if}
  {:else}
    <div class="empty-bar">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2v4m0 12v4m-6-10H2m20 0h-4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8"/>
      </svg>
      <span>No active tasks</span>
    </div>
  {/if}
</div>

<style>
  .task-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    min-height: 38px;
    border-bottom: 1px solid var(--color-border);
    background: var(--color-bg);
  }

  .task-bar.empty {
    justify-content: center;
  }

  .empty-bar {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: var(--color-muted);
    opacity: 0.4;
  }

  .task-chips {
    display: flex;
    align-items: center;
    gap: 5px;
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
    padding: 4px 12px 4px 8px;
    border-radius: var(--radius-full);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    font-size: 11px;
    cursor: default;
    flex-shrink: 0;
    transition: all var(--transition-fast);
    color: inherit;
    font-family: inherit;
    animation: fadeInScale 0.3s ease both;
  }

  .task-chip:hover {
    background: var(--color-surface-hover);
    border-color: var(--chip-color);
  }

  .task-chip.clickable {
    cursor: pointer;
  }

  .task-chip.running {
    border-color: rgba(74, 158, 255, 0.15);
  }

  .task-chip.context-active {
    border-color: var(--color-purple);
    background: var(--color-purple-glow);
  }

  .chip-indicator {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    color: var(--chip-color);
    position: relative;
  }

  .chip-ring {
    width: 10px;
    height: 10px;
    border: 2px solid transparent;
    border-top-color: var(--chip-color);
    border-right-color: var(--chip-color);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  .chip-name {
    font-family: var(--font-mono);
    color: var(--color-text);
    font-size: 11px;
  }

  .chip-time {
    color: var(--color-muted);
    font-family: var(--font-mono);
    font-size: 10px;
  }

  .clear-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-full);
    background: none;
    color: var(--color-muted);
    cursor: pointer;
    flex-shrink: 0;
    transition: all var(--transition-fast);
  }

  .clear-btn:hover {
    color: var(--color-red);
    border-color: var(--color-red);
    background: var(--color-red-glow);
  }
</style>
