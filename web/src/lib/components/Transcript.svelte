<script>
  import { transcript } from '../stores/connection.js';
  import { afterUpdate } from 'svelte';

  let container;

  afterUpdate(() => {
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  });
</script>

<div class="transcript" bind:this={container}>
  {#each $transcript as entry (entry.id)}
    <div class="entry entry-{entry.role}">
      <span class="entry-role">{entry.role === 'user' ? 'You' : 'Agent'}</span>
      {#if entry.type === 'tool_call'}
        <span class="entry-tool">[{entry.tool}]</span>
      {:else}
        <span class="entry-text">{entry.text}</span>
      {/if}
    </div>
  {/each}

  {#if $transcript.length === 0}
    <div class="empty">Waiting for conversation...</div>
  {/if}
</div>

<style>
  .transcript {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px;
    overflow-y: auto;
    height: 100%;
    font-size: 14px;
  }

  .entry {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .entry-role {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .entry-user .entry-role {
    color: var(--color-blue);
  }

  .entry-assistant .entry-role {
    color: var(--color-green);
  }

  .entry-text {
    color: var(--color-text);
    line-height: 1.4;
  }

  .entry-tool {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--color-muted);
    padding: 2px 6px;
    background: var(--color-surface);
    border-radius: 3px;
    width: fit-content;
  }

  .empty {
    color: var(--color-muted);
    font-style: italic;
    text-align: center;
    margin-top: 24px;
  }
</style>
