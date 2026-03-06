<script>
  import TaskDisplay from './lib/components/TaskDisplay.svelte';
  import Transcript from './lib/components/Transcript.svelte';
  import Board from './lib/components/Board.svelte';
</script>

<div class="app">
  <TaskDisplay />
  <div class="main">
    <div class="panel transcript-panel">
      <Transcript />
    </div>
    <div class="panel board-panel">
      <Board />
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

  .board-panel {
    flex: 1;
  }
</style>
