<script>
  import { connectionState, agentState } from '../stores/connection.js';

  $: stateLabel = {
    idle: 'Idle',
    listening: 'Listening',
    thinking: 'Thinking...',
    speaking: 'Speaking',
  }[$agentState] || $agentState;

  $: stateColor = {
    idle: 'var(--color-muted)',
    listening: 'var(--color-green)',
    thinking: 'var(--color-yellow)',
    speaking: 'var(--color-blue)',
  }[$agentState] || 'var(--color-muted)';
</script>

<div class="status-bar">
  <div class="left">
    {#if $connectionState === 'connected'}
      <span class="indicator" style="background: {stateColor}"></span>
      <span class="state-label">{stateLabel}</span>
    {:else if $connectionState === 'connecting'}
      <span class="indicator connecting"></span>
      <span class="state-label">Connecting...</span>
    {:else}
      <span class="indicator" style="background: var(--color-muted)"></span>
      <span class="state-label">Disconnected</span>
    {/if}
  </div>

  <div class="right">
    <span class="model-label">Claude Haiku 4.5</span>
  </div>
</div>

<style>
  .status-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    border-top: 1px solid var(--color-border);
    font-size: 12px;
    min-height: 32px;
    background: var(--color-bg);
  }

  .left, .right {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .indicator {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .connecting {
    background: var(--color-yellow);
    animation: pulse 1s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }

  .state-label {
    color: var(--color-muted);
  }

  .model-label {
    color: var(--color-muted);
    font-family: var(--font-mono);
    font-size: 11px;
  }
</style>
