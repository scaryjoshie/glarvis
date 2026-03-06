<script>
  import { tasks } from '../stores/connection.js';

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
    return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  }
</script>

{#if $tasks.length > 0}
  <div class="task-display">
    {#each $tasks as task (task.id)}
      <div class="task" title={task.progress || ''}>
        <span class="task-dot" style="background: {statusColor(task.status)}"></span>
        <span class="task-name">{task.name}</span>
        {#if task.progress}
          <span class="task-progress">{task.progress}</span>
        {/if}
        <span class="task-elapsed">{formatElapsed(task.elapsed)}</span>
        <span class="task-status" style="color: {statusColor(task.status)}">{task.status}</span>
      </div>
    {/each}
  </div>
{/if}

<style>
  .task-display {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 8px 16px;
    border-bottom: 1px solid var(--color-border);
    font-size: 13px;
  }

  .task {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 8px;
    border-radius: 4px;
    background: var(--color-surface);
    cursor: default;
    transition: background 0.15s;
  }

  .task:hover {
    background: var(--color-surface-hover);
  }

  .task-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .task-name {
    font-family: var(--font-mono);
    color: var(--color-text);
  }

  .task-progress {
    color: var(--color-muted);
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .task-elapsed {
    color: var(--color-muted);
    font-family: var(--font-mono);
    font-size: 12px;
  }

  .task-status {
    font-size: 12px;
    text-transform: uppercase;
    font-weight: 500;
    min-width: 70px;
    text-align: right;
  }
</style>
