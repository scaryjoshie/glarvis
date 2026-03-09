<script>
  import { connectionState, agentState, modelDisplay, openSettings } from '../stores/connection.js';

  $: stateLabel = {
    idle: 'Idle',
    listening: 'Listening',
    thinking: 'Processing',
    speaking: 'Speaking',
  }[$agentState] || $agentState;

  $: stateColor = {
    idle: 'var(--color-muted)',
    listening: 'var(--color-green)',
    thinking: 'var(--color-yellow)',
    speaking: 'var(--color-blue)',
  }[$agentState] || 'var(--color-muted)';

  $: stateGlow = {
    idle: 'transparent',
    listening: 'var(--color-green-glow)',
    thinking: 'var(--color-yellow-glow)',
    speaking: 'var(--color-blue-glow)',
  }[$agentState] || 'transparent';

  $: isActive = $agentState !== 'idle' && $connectionState === 'connected';
</script>

<div class="status-bar">
  <div class="left">
    {#if $connectionState === 'connected'}
      <div class="state-badge" class:active={isActive} style="--state-color: {stateColor}; --state-glow: {stateGlow}">
        <span class="state-dot" style="background: {stateColor}; box-shadow: 0 0 6px {stateGlow}"></span>
        <span class="state-label">{stateLabel}</span>
      </div>
    {:else if $connectionState === 'connecting'}
      <div class="state-badge">
        <span class="state-dot connecting"></span>
        <span class="state-label">Connecting</span>
      </div>
    {:else}
      <div class="state-badge">
        <span class="state-dot"></span>
        <span class="state-label">Offline</span>
      </div>
    {/if}
  </div>

  <div class="right">
    <span class="shortcut-hint">Ctrl+K</span>
    <button class="model-btn" on:click={openSettings}>
      {$modelDisplay || 'model'}
    </button>
  </div>
</div>

<style>
  .status-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 16px;
    border-top: 1px solid var(--color-border);
    font-size: 11px;
    min-height: 30px;
    background: var(--color-bg);
  }

  .left, .right {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .state-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 2px 10px 2px 6px;
    border-radius: var(--radius-full);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    transition: all var(--transition-normal);
  }

  .state-badge.active {
    border-color: var(--state-color);
    background: var(--state-glow);
  }

  .state-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--color-muted);
    flex-shrink: 0;
    transition: all var(--transition-normal);
  }

  .state-dot.connecting {
    background: var(--color-yellow);
    animation: pulse 1s infinite;
  }

  .state-label {
    color: var(--color-text-secondary);
    font-weight: 500;
    font-size: 11px;
  }

  .shortcut-hint {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--color-muted);
    padding: 1px 6px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    opacity: 0.5;
  }

  .model-btn {
    background: none;
    border: none;
    color: var(--color-muted);
    font-family: var(--font-mono);
    font-size: 10px;
    cursor: pointer;
    padding: 2px 8px;
    border-radius: var(--radius-sm);
    transition: all var(--transition-fast);
  }

  .model-btn:hover {
    background: var(--color-surface);
    color: var(--color-text);
  }
</style>
