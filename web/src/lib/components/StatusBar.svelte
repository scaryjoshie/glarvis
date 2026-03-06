<script>
  import { connectionState, agentState } from '../stores/connection.js';
  import { connectWebSocket, connectWebRTC, disconnect } from '../stores/connection.js';

  function handleConnect() {
    connectWebSocket();
    connectWebRTC();
  }

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
      <button class="connect-btn" on:click={handleConnect}>Connect</button>
    {/if}
  </div>

  <div class="right">
    <span class="model-label">Claude Haiku 4.5</span>
    {#if $connectionState === 'connected'}
      <button class="disconnect-btn" on:click={disconnect}>Disconnect</button>
    {/if}
  </div>
</div>

<style>
  .status-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    border-top: 1px solid var(--color-border);
    font-size: 13px;
    background: var(--color-bg);
  }

  .left, .right {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .indicator {
    width: 8px;
    height: 8px;
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
    color: var(--color-text);
  }

  .model-label {
    color: var(--color-muted);
    font-family: var(--font-mono);
    font-size: 12px;
  }

  .connect-btn {
    background: var(--color-blue);
    color: white;
    border: none;
    padding: 4px 16px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
  }

  .connect-btn:hover {
    opacity: 0.9;
  }

  .disconnect-btn {
    background: none;
    border: 1px solid var(--color-border);
    color: var(--color-muted);
    padding: 2px 10px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
  }

  .disconnect-btn:hover {
    border-color: var(--color-red);
    color: var(--color-red);
  }
</style>
