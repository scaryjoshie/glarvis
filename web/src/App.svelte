<script>
  import { onMount, onDestroy } from 'svelte';
  import TaskDisplay from './lib/components/TaskDisplay.svelte';
  import Transcript from './lib/components/Transcript.svelte';
  import Board from './lib/components/Board.svelte';
  import AudioOrb from './lib/components/AudioOrb.svelte';
  import StatusBar from './lib/components/StatusBar.svelte';
  import SettingsModal from './lib/components/SettingsModal.svelte';
  import CommandPalette from './lib/components/CommandPalette.svelte';
  import PanelDivider from './lib/components/PanelDivider.svelte';
  import ToastContainer from './lib/components/ToastContainer.svelte';
  import SystemContext from './lib/components/SystemContext.svelte';
  import HelpModal from './lib/components/HelpModal.svelte';
  import { boardStream } from './lib/stores/connection.js';
  import { downloadConversation, saveCurrentSession } from './lib/stores/history.js';

  let commandPaletteVisible = false;
  let systemContextVisible = false;
  let helpVisible = false;

  // Panel widths
  let transcriptWidth = 320;
  let orbHeight = 260;
  const MIN_TRANSCRIPT = 240;
  const MAX_TRANSCRIPT = 500;
  const MIN_ORB = 160;
  const MAX_ORB = 400;

  $: hasBoard = $boardStream.length > 0;

  function handleTranscriptResize(e) {
    const newWidth = transcriptWidth + e.detail.movementX;
    transcriptWidth = Math.max(MIN_TRANSCRIPT, Math.min(MAX_TRANSCRIPT, newWidth));
  }

  function handleOrbResize(e) {
    const newHeight = orbHeight + e.detail.movementY;
    orbHeight = Math.max(MIN_ORB, Math.min(MAX_ORB, newHeight));
  }

  function handleGlobalKeydown(e) {
    // Don't intercept when typing in inputs
    const tag = e.target?.tagName;
    const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || e.target?.isContentEditable;

    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      commandPaletteVisible = !commandPaletteVisible;
    }
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'S') {
      e.preventDefault();
      systemContextVisible = !systemContextVisible;
    }
    // Export conversation: Ctrl+E
    if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
      e.preventDefault();
      downloadConversation();
    }
    // Save session snapshot: Ctrl+Shift+E
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'E') {
      e.preventDefault();
      saveCurrentSession();
      if (window.__minerva_toast) window.__minerva_toast('Session saved', 'success', 2000);
    }
    // Help: ? key (not when typing)
    if (e.key === '?' && !isInput && !e.ctrlKey && !e.metaKey) {
      helpVisible = !helpVisible;
    }
    // Escape: close all overlays
    if (e.key === 'Escape') {
      if (helpVisible) helpVisible = false;
      else if (commandPaletteVisible) commandPaletteVisible = false;
      else if (systemContextVisible) systemContextVisible = false;
    }
  }

  onMount(() => {
    window.addEventListener('keydown', handleGlobalKeydown);
  });

  onDestroy(() => {
    window.removeEventListener('keydown', handleGlobalKeydown);
  });
</script>

<div class="app">
  <div class="ambient-bg"></div>

  <TaskDisplay />

  <div class="main">
    <div class="panel transcript-panel" style="width: {transcriptWidth}px; min-width: {MIN_TRANSCRIPT}px; max-width: {MAX_TRANSCRIPT}px;">
      <Transcript />
    </div>

    <PanelDivider direction="vertical" on:resize={handleTranscriptResize} />

    <div class="right-column">
      {#if hasBoard}
        <div class="orb-section" style="height: {orbHeight}px; min-height: {MIN_ORB}px; max-height: {MAX_ORB}px;">
          <AudioOrb />
        </div>

        <PanelDivider direction="horizontal" on:resize={handleOrbResize} />

        <div class="panel board-panel">
          <Board />
        </div>
      {:else}
        <div class="orb-section full">
          <AudioOrb />
          <div class="orb-watermark">MINERVA</div>
        </div>
      {/if}

      <StatusBar />
    </div>
  </div>

  {#if systemContextVisible}
    <div class="system-context-anchor">
      <SystemContext visible={true} onClose={() => systemContextVisible = false} />
    </div>
  {/if}
</div>

<SettingsModal />
<CommandPalette visible={commandPaletteVisible} onClose={() => commandPaletteVisible = false} />
<HelpModal visible={helpVisible} onClose={() => helpVisible = false} />
<ToastContainer />

<style>
  .app {
    display: flex;
    flex-direction: column;
    height: 100vh;
    background: var(--color-bg);
    color: var(--color-text);
    position: relative;
    overflow: hidden;
  }

  .ambient-bg {
    position: absolute;
    inset: 0;
    background:
      radial-gradient(ellipse 600px 400px at 20% 80%, rgba(74, 158, 255, 0.03), transparent),
      radial-gradient(ellipse 500px 300px at 80% 20%, rgba(167, 139, 250, 0.02), transparent);
    pointer-events: none;
    z-index: 0;
  }

  .main {
    display: flex;
    flex: 1;
    min-height: 0;
    position: relative;
    z-index: 1;
  }

  .panel {
    overflow: hidden;
  }

  .transcript-panel {
    border-right: 1px solid var(--color-border);
    flex-shrink: 0;
  }

  .right-column {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .orb-section {
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    flex-shrink: 0;
    overflow: hidden;
  }

  .orb-section.full {
    flex: 1;
    height: auto !important;
    min-height: 0 !important;
    max-height: none !important;
  }

  .orb-watermark {
    position: absolute;
    bottom: 32px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 8px;
    color: var(--color-muted);
    opacity: 0.15;
    pointer-events: none;
    user-select: none;
  }

  .board-panel {
    flex: 1;
    min-height: 0;
    border-top: 1px solid var(--color-border);
  }

  .system-context-anchor {
    position: fixed;
    top: 52px;
    right: 16px;
    z-index: 5000;
  }
</style>
