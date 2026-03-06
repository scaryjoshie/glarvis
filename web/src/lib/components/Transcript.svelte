<script>
  import { transcript, sendText } from '../stores/connection.js';
  import { afterUpdate } from 'svelte';
  import VoiceControls from './VoiceControls.svelte';

  let container;
  let inputText = '';

  afterUpdate(() => {
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  });

  function handleSubmit() {
    const text = inputText.trim();
    if (!text) return;
    sendText(text);
    inputText = '';
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }
</script>

<div class="transcript-wrapper">
  <div class="transcript" bind:this={container}>
    {#each $transcript as entry (entry.id)}
      <div class="entry entry-{entry.role}">
        <span class="entry-role">{entry.role === 'user' ? 'You' : 'Agent'}</span>
        {#if entry.type === 'tool_call'}
          <span class="entry-tool">[{entry.tool}]</span>
          {#if entry.tool_args && Object.keys(entry.tool_args).length > 0}
            <span class="entry-tool-detail">{JSON.stringify(entry.tool_args)}</span>
          {/if}
        {:else if entry.type === 'tool_result'}
          <span class="entry-tool result">[{entry.tool} result]</span>
          {#if entry.tool_result}
            <span class="entry-tool-detail">{entry.tool_result}</span>
          {/if}
        {:else}
          <span class="entry-text">{entry.text}</span>
        {/if}
      </div>
    {/each}

    {#if $transcript.length === 0}
      <div class="empty">Waiting for conversation...</div>
    {/if}
  </div>

  <form class="input-bar" on:submit|preventDefault={handleSubmit}>
    <input
      type="text"
      bind:value={inputText}
      on:keydown={handleKeydown}
      placeholder="Type a message..."
    />
    <button type="submit" disabled={!inputText.trim()}>Send</button>
  </form>

  <VoiceControls />
</div>

<style>
  .transcript-wrapper {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .transcript {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
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

  .entry-tool.result {
    color: var(--color-green);
    opacity: 0.7;
  }

  .entry-tool-detail {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-muted);
    opacity: 0.6;
    word-break: break-all;
    line-height: 1.3;
  }

  .empty {
    color: var(--color-muted);
    font-style: italic;
    text-align: center;
    margin-top: 24px;
  }

  .input-bar {
    display: flex;
    gap: 6px;
    padding: 8px 12px;
    border-top: 1px solid var(--color-border);
    background: var(--color-bg);
  }

  .input-bar input {
    flex: 1;
    padding: 6px 10px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: var(--color-surface);
    color: var(--color-text);
    font-size: 13px;
    font-family: inherit;
    outline: none;
  }

  .input-bar input:focus {
    border-color: var(--color-blue);
  }

  .input-bar input::placeholder {
    color: var(--color-muted);
  }

  .input-bar button {
    padding: 6px 12px;
    border: none;
    border-radius: 4px;
    background: var(--color-blue);
    color: white;
    font-size: 13px;
    cursor: pointer;
  }

  .input-bar button:disabled {
    opacity: 0.4;
    cursor: default;
  }
</style>
