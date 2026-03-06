<script>
  import TaskDisplay from './lib/components/TaskDisplay.svelte';
  import Transcript from './lib/components/Transcript.svelte';
  import Board from './lib/components/Board.svelte';
  import StatusBar from './lib/components/StatusBar.svelte';
  import { pendingPopupStore, openPendingPopup } from './lib/stores/connection.js';
</script>

<div class="app">
  <TaskDisplay />
  {#if $pendingPopupStore}
    <button class="popup-blocked" on:click={openPendingPopup}>
      Popup blocked — click here to open
    </button>
  {/if}
  <div class="main">
    <div class="panel transcript-panel">
      <Transcript />
    </div>
    <div class="right-column">
      <div class="panel board-panel">
        <Board />
      </div>
      <StatusBar />
    </div>
  </div>
</div>

<style>
  .app {
    display: flex;
    flex-direction: column;
    height: 100vh;
    background: var(--color-bg);
    color: var(--color-text);
  }

  .main {
    display: flex;
    flex: 1;
    min-height: 0;
  }

  .panel {
    overflow: hidden;
  }

  .transcript-panel {
    width: 300px;
    min-width: 240px;
    border-right: 1px solid var(--color-border);
  }

  .right-column {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .board-panel {
    flex: 1;
    min-height: 0;
  }

  .popup-blocked {
    display: block;
    width: 100%;
    padding: 8px;
    background: rgba(168, 85, 247, 0.15);
    border: none;
    border-bottom: 1px solid var(--color-border);
    color: var(--color-purple, #a855f7);
    font-size: 12px;
    cursor: pointer;
    font-family: inherit;
    text-align: center;
  }

  .popup-blocked:hover {
    background: rgba(168, 85, 247, 0.25);
  }
</style>
