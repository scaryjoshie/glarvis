<script>
  import { emit, listen } from '@tauri-apps/api/event';
  import { getCurrentWindow, LogicalSize, LogicalPosition } from '@tauri-apps/api/window';
  import { onMount, onDestroy } from 'svelte';
  import { diffWords } from 'diff';

  export let text = '';
  export let mode = 'minimized';
  export let paused = false;
  export let toolName = '';
  export let edit_prompt = 'clean up grammar and formatting';
  export let show_diff = true;
  export let snap_to_bottom = true;

  let currentText = text || '';
  let expanded = mode === 'maximized';
  let recording = !paused;
  let snapToBottom = snap_to_bottom;
  let scrollContainer;
  let rightScrollContainer;
  let unlistens = [];

  // Edit/diff state
  let editedText = '';
  let editPrompt = edit_prompt || 'clean up grammar and formatting';
  let isEditing = false;  // LLM edit in progress
  let showDiff = show_diff;
  let originalForDiff = '';

  // Track how expanded was opened
  let openedVia = null; // 'direct' | 'edit'

  // Contenteditable refs
  let leftEditable;
  let rightEditable;

  $: words = currentText ? currentText.split(/\s+/).filter(Boolean) : [];
  $: visibleWords = words.slice(-8);
  $: diffResult = showDiff && originalForDiff && editedText ? diffWords(originalForDiff, editedText) : [];
  $: leftDiff = showDiff ? diffResult.filter(d => !d.added) : [];
  $: rightDiff = showDiff ? diffResult.filter(d => !d.removed) : [];

  onMount(async () => {
    unlistens.push(await listen('transcriber-update', (event) => {
      currentText = event.payload.text || '';
      if (leftEditable && document.activeElement !== leftEditable && !showDiff) {
        leftEditable.innerText = currentText;
      }
      if (expanded && scrollContainer && !isEditing) {
        requestAnimationFrame(() => {
          scrollContainer.scrollTop = scrollContainer.scrollHeight;
        });
      }
    }));
    unlistens.push(await listen('transcriber-state', (event) => {
      recording = !event.payload.paused;
    }));
    unlistens.push(await listen('transcriber-editing', (event) => {
      isEditing = event.payload.editing;
      // Auto-expand on edit if minimized
      if (event.payload.editing && !expanded) {
        openedVia = 'edit';
        doExpand();
      }
    }));
    unlistens.push(await listen('transcriber-edit-result', (event) => {
      originalForDiff = event.payload.original;
      editedText = event.payload.edited;
      currentText = event.payload.original;
      showDiff = true;
      isEditing = false;
    }));
    unlistens.push(await listen('transcriber-sent', () => {
      afterSendOrSubmit();
    }));

    // Snap to bottom: keep vertical position locked, allow horizontal movement.
    // If dragged far enough vertically (>100px from bottom), let it stay.
    let snapTimer = null;
    let snapping = false;
    const win = getCurrentWindow();
    unlistens.push(await win.onMoved(({ payload }) => {
      if (!snapToBottom || expanded || snapping) return;
      clearTimeout(snapTimer);
      snapTimer = setTimeout(async () => {
        const bottomY = (screen.availTop || 0) + screen.availHeight - 56 - 10;
        const currentY = payload.y;
        // If close enough vertically, snap Y but keep X
        if (Math.abs(currentY - bottomY) < 100) {
          snapping = true;
          try { await win.setPosition(new LogicalPosition(payload.x, bottomY)); } catch {}
          setTimeout(() => { snapping = false; }, 100);
        }
      }, 300);
    }));
  });

  onDestroy(() => {
    unlistens.forEach(u => u());
  });

  async function action(name, data = {}) {
    await emit('popup-action', { tool_name: toolName, action: name, data });
  }

  function doSend() {
    action('transcriber_send');
    afterSendOrSubmit();
  }
  function doCopy() { action('transcriber_copy'); }
  function doClear() {
    action('transcriber_clear');
    editedText = '';
    showDiff = false;
    originalForDiff = '';
  }
  function doStop() {
    action('transcriber_stop');
    try { getCurrentWindow().close(); } catch {}
  }
  function doSubmit() {
    action('transcriber_submit');
    afterSendOrSubmit();
  }

  function afterSendOrSubmit() {
    editedText = '';
    showDiff = false;
    originalForDiff = '';
    if (openedVia === 'edit') {
      // Collapse back to pill
      doCollapse();
    }
    // If openedVia === 'direct', stay expanded — text is cleared by backend
  }

  function doEdit() {
    const instruction = editPrompt.trim() || 'clean up grammar and formatting';
    action('transcriber_edit', { instruction });
    // Don't clear editPrompt — keep it for reuse
  }

  function doUpdateText(newText) {
    action('transcriber_update_text', { text: newText });
  }

  function toggleRecording() {
    if (recording) {
      action('transcriber_pause');
      recording = false;
    } else {
      action('transcriber_resume');
      recording = true;
    }
  }

  function toggleDiff() {
    showDiff = !showDiff;
    action('transcriber_set_show_diff', { show_diff: showDiff });
  }

  function getBottomPosition(w = 520, h = 56) {
    const x = Math.round(screen.availWidth / 2 - w / 2 + (screen.availLeft || 0));
    const y = (screen.availTop || 0) + screen.availHeight - h - 10;
    return { x, y };
  }

  // Contenteditable input handlers
  function onLeftInput(e) {
    const newText = e.target.innerText;
    currentText = newText;
    doUpdateText(newText);
    // Auto-pause on edit
    if (recording) {
      action('transcriber_pause');
      recording = false;
    }
  }

  function onRightInput(e) {
    editedText = e.target.innerText;
    // Auto-pause on edit
    if (recording) {
      action('transcriber_pause');
      recording = false;
    }
  }

  // Save prompt on blur
  function onPromptBlur() {
    const trimmed = editPrompt.trim();
    if (trimmed) {
      action('transcriber_set_prompt', { prompt: trimmed });
    }
  }

  async function doExpand() {
    expanded = true;
    try {
      const win = getCurrentWindow();
      const w = 760, h = 440;
      await win.setSize(new LogicalSize(w, h));
      const x = Math.round(screen.width / 2 - w / 2);
      const y = Math.round(screen.height / 2 - h / 2);
      await win.setPosition(new LogicalPosition(x, y));
    } catch (e) {
      console.warn('[Transcriber] Resize failed:', e);
    }
  }

  async function doCollapse() {
    expanded = false;
    openedVia = null;
    showDiff = false;
    try {
      const win = getCurrentWindow();
      const w = 520, h = 56;
      await win.setSize(new LogicalSize(w, h));
      if (snapToBottom) {
        const pos = getBottomPosition(w, h);
        await win.setPosition(new LogicalPosition(pos.x, pos.y));
      }
    } catch (e) {
      console.warn('[Transcriber] Resize failed:', e);
    }
  }

  async function toggleExpand() {
    if (expanded) {
      doCollapse();
    } else {
      openedVia = 'direct';
      doExpand();
    }
  }

  function onKeydown(e) {
    if (e.key === 'Escape') doStop();
    if (e.key === 'Enter' && !e.shiftKey && editPrompt.trim() && document.activeElement?.classList?.contains('prompt-input')) {
      e.preventDefault();
      doEdit();
    }
    // Space toggles pause/resume (unless typing in an input)
    if (e.key === ' ' && !isInputFocused()) {
      e.preventDefault();
      toggleRecording();
    }
  }

  function isInputFocused() {
    const el = document.activeElement;
    if (!el) return false;
    const tag = el.tagName;
    return tag === 'INPUT' || tag === 'TEXTAREA' || el.isContentEditable;
  }
</script>

<svelte:window on:keydown={onKeydown} />

{#if expanded}
  <div class="popup expanded">
    <div class="header" data-tauri-drag-region>
      <button
        class="rec-btn"
        class:recording
        class:paused={!recording}
        on:click={toggleRecording}
        title={recording ? 'Pause' : 'Resume'}
      >
        {#if recording}
          <div class="rec-dot"></div>
        {:else}
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="6,4 20,12 6,20"/>
          </svg>
        {/if}
      </button>
      <span class="title" data-tauri-drag-region>
        {#if isEditing}
          Editing...
        {:else}
          {recording ? 'Transcribing' : 'Paused'}
        {/if}
      </span>
      <div class="header-actions">
        {#if originalForDiff && editedText}
          <button
            class="icon-btn"
            class:active={showDiff}
            on:click={toggleDiff}
            title={showDiff ? 'Hide diff' : 'Show diff'}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              {#if showDiff}
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
              {:else}
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                <line x1="1" y1="1" x2="23" y2="23"/>
              {/if}
            </svg>
          </button>
        {/if}
        <button class="icon-btn" on:click={toggleExpand} title="Minimize">&#x2013;</button>
        <button class="icon-btn close" on:click={doStop} title="Close">&times;</button>
      </div>
    </div>

    <!-- Split panes -->
    <div class="split-panes">
      <div class="pane left">
        <div class="pane-label">Original</div>
        <div class="pane-body" bind:this={scrollContainer}>
          {#if showDiff && diffResult.length}
            <div class="diff-view" on:click={() => showDiff = false} role="button" tabindex="-1">
              {#each leftDiff as part}
                <span class:diff-removed={part.removed}>{part.value}</span>
              {/each}
            </div>
          {:else if currentText}
            <div
              class="editable-pane"
              contenteditable="true"
              bind:this={leftEditable}
              on:input={onLeftInput}
              role="textbox"
              tabindex="0"
            >{currentText}</div>
          {:else}
            <p class="placeholder-text">
              {recording ? 'Speak to start...' : 'Paused'}
            </p>
          {/if}
        </div>
      </div>

      <div class="pane-divider">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
      </div>

      <div class="pane right">
        <div class="pane-label">Edited</div>
        <div class="pane-body" bind:this={rightScrollContainer}>
          {#if isEditing}
            <div class="spinner-container">
              <div class="spinner"></div>
              <span class="spinner-text">Editing...</span>
            </div>
          {:else if showDiff && diffResult.length}
            <div class="diff-view" on:click={() => showDiff = false} role="button" tabindex="-1">
              {#each rightDiff as part}
                <span class:diff-added={part.added}>{part.value}</span>
              {/each}
            </div>
          {:else if editedText}
            <div
              class="editable-pane"
              contenteditable="true"
              bind:this={rightEditable}
              on:input={onRightInput}
              role="textbox"
              tabindex="0"
            >{editedText}</div>
          {:else}
            <p class="placeholder-text">Use Edit to rewrite</p>
          {/if}
        </div>
      </div>
    </div>

    <!-- Prompt bar -->
    <div class="prompt-bar">
      <textarea
        class="prompt-input"
        rows="1"
        bind:value={editPrompt}
        on:blur={onPromptBlur}
        placeholder="Edit instruction (e.g. 'make it formal')..."
        disabled={isEditing || !currentText}
      ></textarea>
      <button
        class="prompt-btn"
        on:click={doEdit}
        disabled={isEditing || !currentText}
      >
        {isEditing ? '...' : 'Edit'}
      </button>
    </div>

    <!-- Action bar -->
    <div class="action-bar">
      <button class="action-btn primary" on:click={doSubmit} disabled={!currentText && !editedText}>
        Submit
      </button>
      <button class="action-btn primary" on:click={doSend} disabled={!currentText && !editedText}>
        Send
      </button>
      <button class="action-btn" on:click={doCopy} disabled={!currentText && !editedText}>
        Copy
      </button>
      <button class="action-btn" on:click={doClear} disabled={!currentText && !editedText}>
        Clear
      </button>
      <div class="spacer"></div>
      <button class="action-btn stop" on:click={doStop}>
        Close
      </button>
    </div>
  </div>
{:else}
  <!-- Minimized pill -->
  <div class="popup minimized" data-tauri-drag-region>
    <div class="mini-left" data-tauri-drag-region>
      <button
        class="rec-btn mini"
        class:recording
        class:paused={!recording}
        on:click={toggleRecording}
        title={recording ? 'Pause' : 'Resume'}
      >
        {#if recording}
          <div class="rec-dot"></div>
        {:else}
          <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="6,4 20,12 6,20"/>
          </svg>
        {/if}
      </button>
      <div class="ticker" data-tauri-drag-region>
        {#each visibleWords as word, i}
          <span
            class="ticker-word"
            style="opacity: {0.3 + 0.7 * ((i + 1) / visibleWords.length)}"
          >{word}</span>
        {/each}
        {#if !visibleWords.length}
          <span class="ticker-placeholder">
            {recording ? 'Listening...' : 'Paused'}
          </span>
        {/if}
      </div>
    </div>
    <div class="mini-actions">
      <!-- Send -->
      <button class="mini-btn" on:click={doSend} disabled={!currentText} title="Send">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 2L11 13M22 2L15 22L11 13L2 9L22 2Z"/>
        </svg>
      </button>
      <!-- Copy -->
      <button class="mini-btn" on:click={doCopy} disabled={!currentText} title="Copy">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
          <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
        </svg>
      </button>
      <!-- Clear -->
      <button class="mini-btn" on:click={doClear} disabled={!currentText} title="Clear">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"/>
          <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
        </svg>
      </button>
      <!-- Expand -->
      <button class="mini-btn" on:click={toggleExpand} title="Expand">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="15 3 21 3 21 9"/>
          <polyline points="9 21 3 21 3 15"/>
          <line x1="21" y1="3" x2="14" y2="10"/>
          <line x1="3" y1="21" x2="10" y2="14"/>
        </svg>
      </button>
      <!-- Close -->
      <button class="mini-btn close" on:click={doStop} title="Close">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>
  </div>
{/if}

<style>
  :global(html), :global(body) {
    background: transparent !important;
    margin: 0;
    padding: 0;
    height: 100%;
    overflow: hidden;
  }

  :global(#popup) {
    height: 100%;
  }

  .popup {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    color: #e4e4e7;
    box-sizing: border-box;
    height: 100%;
  }

  /* ── Record button ──────────────────────────────────────────────── */

  .rec-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 50%;
    cursor: pointer;
    padding: 0;
    flex-shrink: 0;
    transition: background 0.15s;
  }

  .rec-btn.mini {
    width: 26px;
    height: 26px;
  }

  .rec-btn.recording {
    background: rgba(239, 68, 68, 0.15);
  }

  .rec-btn.recording:hover {
    background: rgba(239, 68, 68, 0.25);
  }

  .rec-btn.paused {
    background: rgba(255, 255, 255, 0.08);
    color: #a1a1aa;
  }

  .rec-btn.paused:hover {
    background: rgba(255, 255, 255, 0.14);
    color: #e4e4e7;
  }

  .rec-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #ef4444;
    animation: pulse 1.5s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }

  /* ── Minimized mode ─────────────────────────────────────────────── */

  .minimized {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 10px;
    background: rgba(10, 10, 12, 0.95);
    border-radius: 28px;
    height: 100%;
    gap: 8px;
    cursor: grab;
  }

  .mini-left {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;
    cursor: grab;
  }

  .ticker {
    display: flex;
    gap: 5px;
    overflow: hidden;
    white-space: nowrap;
    flex: 1;
    min-width: 0;
    padding-right: 8px;
    mask-image: linear-gradient(to right, black 85%, transparent);
    -webkit-mask-image: linear-gradient(to right, black 85%, transparent);
    cursor: grab;
  }

  .ticker-word {
    font-size: 13px;
    color: #a1a1aa;
    transition: opacity 0.3s ease;
    flex-shrink: 0;
  }

  .ticker-placeholder {
    font-size: 13px;
    color: #52525b;
    font-style: italic;
  }

  .mini-actions {
    display: flex;
    gap: 3px;
    flex-shrink: 0;
  }

  .mini-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border: none;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.06);
    color: #a1a1aa;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
    padding: 0;
  }

  .mini-btn:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.12);
    color: #e4e4e7;
  }

  .mini-btn:disabled {
    opacity: 0.3;
    cursor: default;
  }

  .mini-btn.close {
    color: #71717a;
  }

  .mini-btn.close:hover {
    color: #ef4444;
    background: rgba(239, 68, 68, 0.12);
  }

  /* ── Expanded mode ──────────────────────────────────────────────── */

  .expanded {
    display: flex;
    flex-direction: column;
    background: #0a0a0c;
    border-radius: 12px;
    overflow: hidden;
  }

  .header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
    flex-shrink: 0;
    cursor: grab;
  }

  .title {
    font-size: 13px;
    font-weight: 600;
    color: #a1a1aa;
    flex: 1;
    cursor: grab;
  }

  .header-actions {
    display: flex;
    gap: 4px;
  }

  .icon-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: #71717a;
    font-size: 18px;
    cursor: pointer;
    font-family: inherit;
    line-height: 1;
    padding: 0;
    transition: background 0.15s, color 0.15s;
  }

  .icon-btn:hover {
    background: rgba(255, 255, 255, 0.08);
    color: #a1a1aa;
  }

  .icon-btn.close:hover {
    color: #ef4444;
  }

  .icon-btn.active {
    color: #818cf8;
  }

  /* ── Split panes ────────────────────────────────────────────────── */

  .split-panes {
    display: flex;
    flex: 1;
    min-height: 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  }

  .pane {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .pane-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #52525b;
    padding: 6px 12px 2px;
    flex-shrink: 0;
  }

  .pane-body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 4px 12px 12px;
  }

  .pane-divider {
    width: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    color: #3f3f46;
  }

  .placeholder-text {
    margin: 0;
    font-size: 13px;
    color: #52525b;
    font-style: italic;
  }

  .editable-pane {
    font-size: 13px;
    line-height: 1.7;
    color: #d4d4d8;
    white-space: pre-wrap;
    word-break: break-word;
    outline: none;
    min-height: 100%;
    border-radius: 6px;
    padding: 4px;
    transition: background 0.15s;
  }

  .editable-pane:focus {
    background: rgba(255, 255, 255, 0.03);
  }

  /* ── Diff view ──────────────────────────────────────────────────── */

  .diff-view {
    font-size: 13px;
    line-height: 1.7;
    white-space: pre-wrap;
    word-break: break-word;
    cursor: pointer;
  }

  .diff-removed {
    background: rgba(239, 68, 68, 0.2);
    color: #fca5a5;
    text-decoration: line-through;
    border-radius: 2px;
    padding: 0 1px;
  }

  .diff-added {
    background: rgba(34, 197, 94, 0.2);
    color: #86efac;
    border-radius: 2px;
    padding: 0 1px;
  }

  /* ── Spinner ────────────────────────────────────────────────────── */

  .spinner-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 10px;
  }

  .spinner {
    width: 24px;
    height: 24px;
    border: 2px solid rgba(255, 255, 255, 0.1);
    border-top-color: #818cf8;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .spinner-text {
    font-size: 12px;
    color: #71717a;
  }

  /* ── Prompt bar ─────────────────────────────────────────────────── */

  .prompt-bar {
    display: flex;
    gap: 8px;
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
    flex-shrink: 0;
  }

  .prompt-input {
    flex: 1;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    color: #d4d4d8;
    font-size: 12px;
    padding: 6px 10px;
    outline: none;
    font-family: inherit;
    resize: none;
    field-sizing: content;
    min-height: 28px;
    max-height: 80px;
  }

  .prompt-input:focus {
    border-color: rgba(99, 102, 241, 0.4);
  }

  .prompt-input::placeholder {
    color: #52525b;
  }

  .prompt-input:disabled {
    opacity: 0.4;
  }

  .prompt-btn {
    padding: 6px 14px;
    border: none;
    border-radius: 6px;
    background: rgba(99, 102, 241, 0.2);
    color: #818cf8;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
    transition: background 0.15s;
    flex-shrink: 0;
    align-self: flex-end;
  }

  .prompt-btn:hover:not(:disabled) {
    background: rgba(99, 102, 241, 0.3);
  }

  .prompt-btn:disabled {
    opacity: 0.35;
    cursor: default;
  }

  /* ── Action bar ─────────────────────────────────────────────────── */

  .action-bar {
    display: flex;
    gap: 8px;
    padding: 10px 12px;
    flex-shrink: 0;
  }

  .spacer {
    flex: 1;
  }

  .action-btn {
    padding: 7px 14px;
    border: none;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.06);
    color: #a1a1aa;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
    transition: background 0.15s, color 0.15s;
  }

  .action-btn:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    color: #e4e4e7;
  }

  .action-btn:disabled {
    opacity: 0.35;
    cursor: default;
  }

  .action-btn.primary {
    background: rgba(99, 102, 241, 0.2);
    color: #818cf8;
  }

  .action-btn.primary:hover:not(:disabled) {
    background: rgba(99, 102, 241, 0.3);
  }

  .action-btn.stop {
    color: #ef4444;
  }

  .action-btn.stop:hover {
    background: rgba(239, 68, 68, 0.12);
  }
</style>
