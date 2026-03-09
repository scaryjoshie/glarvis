<script>
  import { onMount } from 'svelte';
  import { writable } from 'svelte/store';
  import { getCurrentWindow } from '@tauri-apps/api/window';
  // In popup mode, stores aren't connected — we use local state + REST
  import { settingsOpen as _settingsOpen, settingsData as _settingsData, saveSettings as _saveSettings, reloadSettings as _reloadSettings, sfxVolume, voiceVolume } from '../stores/connection.js';

  export let popupMode = false;

  // In popup mode, create local stores so the rest of the component works unchanged
  const localOpen = writable(true);
  const localData = writable({});
  const settingsOpen = popupMode ? localOpen : _settingsOpen;
  const settingsData = popupMode ? localData : _settingsData;

  let reloading = false;
  async function reload() {
    reloading = true;
    if (popupMode) {
      try {
        const res = await fetch('/api/settings?reload=true');
        if (res.ok) localData.set(await res.json());
      } catch {}
    } else {
      await _reloadSettings();
    }
    reloading = false;
  }

  onMount(async () => {
    if (popupMode) {
      try {
        const res = await fetch('/api/settings');
        if (res.ok) {
          const data = await res.json();
          localData.set(data);
          initFromData(data);
        }
      } catch {}
    }
  });

  // ── Selection state (synced from store on open, once) ─────────────────────

  let llmProvider = '';
  let llmModel = '';
  let ttsProvider = '';
  let ttsVoice = '';
  let sttProvider = '';
  let sttModel = '';
  let transcriberProvider = '';
  let transcriberModel = '';
  let transcriberEditPrompt = 'clean up grammar and formatting';
  let transcriberShowDiff = true;
  let transcriberSnapToBottom = true;
  let transcriberAutoEdit = false;
  let settingsInitialized = false;

  function initFromData(d) {
    llmProvider = d.llm?.provider || 'anthropic';
    llmModel = d.llm?.model || '';
    ttsProvider = d.tts?.provider || 'cartesia';
    ttsVoice = d.tts?.voice_id || '';
    sttProvider = d.stt?.provider || 'deepgram';
    sttModel = d.stt?.model || '';
    transcriberProvider = d.transcriber?.provider || 'anthropic';
    transcriberModel = d.transcriber?.model || 'claude-haiku-4-5-20251001';
    transcriberEditPrompt = d.transcriber?.edit_prompt || 'clean up grammar and formatting';
    transcriberShowDiff = d.transcriber?.show_diff !== false;
    transcriberSnapToBottom = d.transcriber?.snap_to_bottom !== false;
    transcriberAutoEdit = d.transcriber?.auto_edit || false;
    llmHasOverride = d.llm?.has_override || false;
    ttsHasOverride = d.tts?.has_override || false;
    sttHasOverride = d.stt?.has_override || false;
    transcriberHasOverride = d.transcriber?.has_override || false;
    // Init speed from the current TTS provider
    const ttsProv = (d.services?.tts || []).find(p => p.id === (d.tts?.provider || 'cartesia'));
    speedEnabled = ttsProv?.speed != null;
    speedValue = ttsProv?.speed ?? (ttsProv?.speed_config?.default ?? 1.0);
    settingsInitialized = true;
  }

  $: if ($settingsOpen && !settingsInitialized && $settingsData?.services && Object.keys($settingsData.services).length > 0) {
    initFromData($settingsData);
  }

  // ── Derived data ──────────────────────────────────────────────────────────

  $: services = $settingsData.services || {};
  $: llmProviders = services.llm || [];
  $: ttsProviders = services.tts || [];
  $: sttProviders = services.stt || [];

  let activeTab = 'general';
  $: showProviderPanel = ['llm', 'tts', 'stt'].includes(activeTab);

  // Transcriber: derived from LLM providers
  $: transcriberProviderData = llmProviders.find(p => p.id === transcriberProvider);
  $: transcriberModels = transcriberProviderData?.models || [];

  $: currentProviders = activeTab === 'llm' ? llmProviders
                       : activeTab === 'tts' ? ttsProviders
                       : activeTab === 'stt' ? sttProviders
                       : [];

  $: selectedProviderId = activeTab === 'llm' ? llmProvider
                        : activeTab === 'tts' ? ttsProvider
                        : activeTab === 'stt' ? sttProvider
                        : '';

  $: currentProvider = currentProviders.find(p => p.id === selectedProviderId);

  $: currentItems = activeTab === 'tts'
    ? (currentProvider?.voices || []).map(v => ({ id: v.id, label: v.name, sublabel: v.id }))
    : (activeTab === 'llm' ? currentProvider?.models : currentProvider?.models)
        ?.map(m => ({ id: m, label: m })) || [];

  $: selectedItemId = activeTab === 'llm' ? llmModel
                    : activeTab === 'tts' ? ttsVoice
                    : activeTab === 'stt' ? sttModel
                    : '';

  $: tabTitle = { general: 'General', llm: 'Language Model', tts: 'Text to Speech', stt: 'Speech to Text', transcriber: 'Transcriber' }[activeTab] || '';
  $: detailTitle = currentProvider ? currentProvider.name : tabTitle;

  // ── API key state ─────────────────────────────────────────────────────────

  let llmHasOverride = false;
  let ttsHasOverride = false;
  let sttHasOverride = false;
  let transcriberHasOverride = false;
  let editingKeyFor = null; // null | 'llm' | 'tts' | 'stt' | 'transcriber'
  let keyConfirmed = false;
  let newKeyValue = '';

  $: currentHasOverride = activeTab === 'llm' ? llmHasOverride
                         : activeTab === 'tts' ? ttsHasOverride
                         : activeTab === 'stt' ? sttHasOverride
                         : false;

  function startEditKey() {
    editingKeyFor = activeTab;
    keyConfirmed = false;
    newKeyValue = '';
  }

  function confirmEditKey() {
    keyConfirmed = true;
  }

  function cancelEditKey() {
    editingKeyFor = null;
    keyConfirmed = false;
    newKeyValue = '';
  }

  function clearKeyOverride() {
    // Send empty string to clear the override
    pendingKeyClears[activeTab] = true;
    if (activeTab === 'llm') llmHasOverride = false;
    else if (activeTab === 'tts') ttsHasOverride = false;
    else if (activeTab === 'stt') sttHasOverride = false;
    editingKeyFor = null;
  }

  // Track pending key changes to include in save
  let pendingKeyValues = {}; // { llm: 'sk-...', tts: 'sk-...' }
  let pendingKeyClears = {}; // { llm: true }

  function applyKey() {
    if (!newKeyValue.trim()) return;
    pendingKeyValues[editingKeyFor] = newKeyValue.trim();
    if (editingKeyFor === 'llm') llmHasOverride = true;
    else if (editingKeyFor === 'tts') ttsHasOverride = true;
    else if (editingKeyFor === 'stt') sttHasOverride = true;
    else if (editingKeyFor === 'transcriber') transcriberHasOverride = true;
    editingKeyFor = null;
    keyConfirmed = false;
    newKeyValue = '';
  }

  // ── Provider / item selection ─────────────────────────────────────────────

  function selectProvider(id) {
    const p = currentProviders.find(x => x.id === id);
    if (activeTab === 'llm') {
      llmProvider = id;
      if (p) llmModel = p.default_model || '';
    } else if (activeTab === 'tts') {
      ttsProvider = id;
      if (p) ttsVoice = p.default_voice || '';
      // Update speed state for the new provider
      speedEnabled = p?.speed != null;
      speedValue = p?.speed ?? (p?.speed_config?.default ?? 1.0);
    } else if (activeTab === 'stt') {
      sttProvider = id;
      if (p) sttModel = p.default_model || '';
    }
    // Reset key editing when switching providers
    editingKeyFor = null;
  }

  function selectItem(id) {
    if (activeTab === 'llm') llmModel = id;
    else if (activeTab === 'tts') ttsVoice = id;
    else if (activeTab === 'stt') sttModel = id;
  }

  // ── Speed slider ──────────────────────────────────────────────────────────

  let speedEnabled = false;
  let speedValue = 1.0;
  let speedDebounce = null;

  async function toggleSpeed() {
    speedEnabled = !speedEnabled;
    if (speedEnabled) {
      const dflt = currentProvider?.speed_config?.default ?? 1.0;
      speedValue = dflt;
      await saveSpeed(dflt);
    } else {
      await clearSpeed();
    }
  }

  async function onSpeedChange() {
    clearTimeout(speedDebounce);
    speedDebounce = setTimeout(() => saveSpeed(speedValue), 300);
  }

  async function saveSpeed(val) {
    try {
      const res = await fetch('/api/services/speed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: ttsProvider, speed: val }),
      });
      const data = await res.json();
      if (data.ok) updateServices(data.services);
    } catch {}
  }

  async function clearSpeed() {
    try {
      const res = await fetch('/api/services/speed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: ttsProvider, speed: null }),
      });
      const data = await res.json();
      if (data.ok) updateServices(data.services);
    } catch {}
  }

  // ── Add / Edit / Remove items ─────────────────────────────────────────────

  let adding = false;
  let addName = '';
  let addId = '';

  let editingVoiceId = null;
  let editName = '';
  let editId = '';

  function startAdd() {
    adding = true;
    addName = '';
    addId = '';
  }

  function cancelAdd() {
    adding = false;
    addName = '';
    addId = '';
  }

  async function submitAdd() {
    const serviceType = activeTab;
    let item;
    if (serviceType === 'tts') {
      if (!addName.trim() || !addId.trim()) return;
      item = { id: addId.trim(), name: addName.trim() };
    } else {
      if (!addName.trim()) return;
      item = addName.trim();
    }
    try {
      const res = await fetch('/api/services/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service_type: serviceType, provider: selectedProviderId, item }),
      });
      const data = await res.json();
      if (data.ok) updateServices(data.services);
    } catch {}
    cancelAdd();
  }

  async function removeItem(itemId) {
    try {
      const res = await fetch('/api/services/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service_type: activeTab, provider: selectedProviderId, item_id: itemId }),
      });
      const data = await res.json();
      if (data.ok) {
        updateServices(data.services);
        // If removed the selected item, pick the first remaining
        if (itemId === selectedItemId) {
          const remaining = activeTab === 'tts'
            ? (data.services.tts?.find(p => p.id === selectedProviderId)?.voices?.[0]?.id || '')
            : (data.services[activeTab]?.find(p => p.id === selectedProviderId)?.models?.[0] || '');
          selectItem(remaining);
        }
      }
    } catch {}
  }

  function startEditVoice(voice) {
    editingVoiceId = voice.id;
    editName = voice.label;
    editId = voice.sublabel;
  }

  function cancelEditVoice() {
    editingVoiceId = null;
    editName = '';
    editId = '';
  }

  async function submitEditVoice() {
    if (!editName.trim() || !editId.trim()) return;
    try {
      const res = await fetch('/api/services/edit-voice', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: selectedProviderId,
          voice_id: editingVoiceId,
          updates: { name: editName.trim(), id: editId.trim() },
        }),
      });
      const data = await res.json();
      if (data.ok) {
        updateServices(data.services);
        // If edited the selected voice and ID changed, update selection
        if (editingVoiceId === ttsVoice && editId.trim() !== editingVoiceId) {
          ttsVoice = editId.trim();
        }
      }
    } catch {}
    cancelEditVoice();
  }

  function updateServices(newServices) {
    settingsData.update(sd => ({ ...sd, services: newServices }));
  }

  // ── Save / Close ──────────────────────────────────────────────────────────

  function save() {
    const payload = {
      llm: { provider: llmProvider, model: llmModel },
      tts: { provider: ttsProvider, voice_id: ttsVoice },
      stt: { provider: sttProvider, model: sttModel },
      transcriber: { provider: transcriberProvider, model: transcriberModel, edit_prompt: transcriberEditPrompt, show_diff: transcriberShowDiff, snap_to_bottom: transcriberSnapToBottom, auto_edit: transcriberAutoEdit },
    };
    // Include api_key only if changed
    if (pendingKeyValues.llm) payload.llm.api_key = pendingKeyValues.llm;
    else if (pendingKeyClears.llm) payload.llm.api_key = '';
    if (pendingKeyValues.tts) payload.tts.api_key = pendingKeyValues.tts;
    else if (pendingKeyClears.tts) payload.tts.api_key = '';
    if (pendingKeyValues.stt) payload.stt.api_key = pendingKeyValues.stt;
    else if (pendingKeyClears.stt) payload.stt.api_key = '';
    if (pendingKeyValues.transcriber) payload.transcriber.api_key = pendingKeyValues.transcriber;
    else if (pendingKeyClears.transcriber) payload.transcriber.api_key = '';

    if (popupMode) {
      fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }).catch(() => {});
      try { getCurrentWindow().close(); } catch {}
    } else {
      _saveSettings(payload);
      settingsData.update(sd => ({
        ...sd,
        llm: { ...sd.llm, provider: llmProvider, model: llmModel, has_override: llmHasOverride },
        tts: { ...sd.tts, provider: ttsProvider, voice_id: ttsVoice, has_override: ttsHasOverride },
        stt: { ...sd.stt, provider: sttProvider, model: sttModel, has_override: sttHasOverride },
        transcriber: { ...sd.transcriber, provider: transcriberProvider, model: transcriberModel, has_override: transcriberHasOverride, edit_prompt: transcriberEditPrompt, show_diff: transcriberShowDiff, snap_to_bottom: transcriberSnapToBottom, auto_edit: transcriberAutoEdit },
      }));
      settingsOpen.set(false);
    }
    cleanup();
  }

  function close() {
    if (popupMode) {
      try { getCurrentWindow().close(); } catch {}
    } else {
      settingsOpen.set(false);
    }
    cleanup();
  }

  function cleanup() {
    adding = false;
    editingVoiceId = null;
    editingKeyFor = null;
    pendingKeyValues = {};
    pendingKeyClears = {};
    settingsInitialized = false;
  }

  function onKeydown(e) {
    if (e.key === 'Escape') close();
  }

  function onBackdropClick(e) {
    if (e.target === e.currentTarget) close();
  }

  // Tabs
  const tabs = [
    { id: 'general', label: 'General' },
    { id: 'llm', label: 'LLM' },
    { id: 'tts', label: 'TTS' },
    { id: 'stt', label: 'STT' },
    { id: 'transcriber', label: 'Transcriber' },
  ];
</script>

<svelte:window on:keydown={onKeydown} />

{#if popupMode || $settingsOpen}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <div class={popupMode ? 'popup-fill' : 'backdrop'} on:click={popupMode ? null : onBackdropClick}>
    <div class="modal" class:popup-mode={popupMode}>

      <!-- Nav sidebar -->
      <div class="sidebar">
        <h2>Settings</h2>
        <nav>
          {#each tabs as tab}
            <button
              class="nav-item"
              class:active={activeTab === tab.id}
              on:click={() => { activeTab = tab.id; adding = false; editingVoiceId = null; editingKeyFor = null; }}
            >
              {tab.label}
            </button>
          {/each}
        </nav>
      </div>

      <!-- Provider panel (LLM / TTS / STT tabs) -->
      {#if showProviderPanel}
        <div class="provider-panel">
          <div class="panel-label">Providers</div>
          <div class="provider-items">
            {#each currentProviders as p}
              <button
                class="prov-row"
                class:selected={selectedProviderId === p.id}
                on:click={() => selectProvider(p.id)}
              >
                <span class="status-dot" class:has-key={p.has_key}></span>
                <span class="prov-name">{p.name}</span>
                <span class="prov-count">
                  {activeTab === 'tts' ? (p.voices?.length || 0) : (p.models?.length || 0)}
                </span>
              </button>
            {/each}
            {#if currentProviders.length === 0}
              <p class="empty">Start the backend to load providers.</p>
            {/if}
          </div>
        </div>
      {/if}

      <!-- Detail panel -->
      <div class="detail">
        <div class="detail-header">
          <h3>{showProviderPanel ? detailTitle : tabTitle}</h3>
          <div class="header-actions">
            <button class="hdr-btn" on:click={reload} disabled={reloading} title="Reload services.yaml">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class:spinning={reloading}>
                <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
              </svg>
            </button>
            <button class="hdr-btn" on:click={close} title="Close">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>

        <div class="detail-body">

          <!-- GENERAL TAB -->
          {#if activeTab === 'general'}
            <div class="volume-section">
              <div class="section-label">Voice Volume</div>
              <div class="vol-row">
                <svg class="vol-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>{#if $voiceVolume > 0}<path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>{/if}{#if $voiceVolume > 0.5}<path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>{/if}</svg>
                <input
                  type="range"
                  class="vol-slider"
                  min="0"
                  max="1"
                  step="0.01"
                  bind:value={$voiceVolume}
                />
                <span class="vol-val">{Math.round($voiceVolume * 100)}%</span>
              </div>
            </div>

            <div class="volume-section">
              <div class="section-label">Sound Effects</div>
              <div class="vol-row">
                <svg class="vol-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 1 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
                <input
                  type="range"
                  class="vol-slider"
                  min="0"
                  max="1"
                  step="0.01"
                  bind:value={$sfxVolume}
                />
                <span class="vol-val">{Math.round($sfxVolume * 100)}%</span>
              </div>
            </div>

          <!-- TRANSCRIBER TAB -->
          {:else if activeTab === 'transcriber'}
            <div class="section-label">LLM for Transcript Editing</div>
            <p class="transcriber-hint">Choose which language model to use when editing transcribed text.</p>

            <div class="transcriber-field">
              <label class="field-label">Provider</label>
              <select class="field-select" bind:value={transcriberProvider} on:change={() => {
                const p = llmProviders.find(x => x.id === transcriberProvider);
                if (p) transcriberModel = p.default_model || (p.models?.[0] || '');
              }}>
                {#each llmProviders as p}
                  <option value={p.id}>{p.name}</option>
                {/each}
              </select>
            </div>

            <div class="transcriber-field">
              <label class="field-label">Model</label>
              <select class="field-select" bind:value={transcriberModel}>
                {#each transcriberModels as m}
                  <option value={m}>{m}</option>
                {/each}
              </select>
            </div>

            <div class="transcriber-field">
              <label class="field-label">Edit Prompt</label>
              <textarea
                class="field-textarea"
                rows="2"
                bind:value={transcriberEditPrompt}
                placeholder="Instruction for LLM when editing transcripts..."
              ></textarea>
            </div>

            <div class="transcriber-field toggle-row">
              <label class="field-label">Show Diff After Edit</label>
              <button
                class="toggle-btn"
                class:on={transcriberShowDiff}
                on:click={() => transcriberShowDiff = !transcriberShowDiff}
              >
                {transcriberShowDiff ? 'ON' : 'OFF'}
              </button>
            </div>

            <div class="transcriber-field toggle-row">
              <label class="field-label">Snap to Bottom</label>
              <button
                class="toggle-btn"
                class:on={transcriberSnapToBottom}
                on:click={() => transcriberSnapToBottom = !transcriberSnapToBottom}
              >
                {transcriberSnapToBottom ? 'ON' : 'OFF'}
              </button>
            </div>

            <div class="transcriber-field toggle-row">
              <label class="field-label">Auto-Edit Before Send/Copy</label>
              <button
                class="toggle-btn"
                class:on={transcriberAutoEdit}
                on:click={() => transcriberAutoEdit = !transcriberAutoEdit}
              >
                {transcriberAutoEdit ? 'ON' : 'OFF'}
              </button>
            </div>

            <!-- API Key override for transcriber -->
            <div class="key-section">
              <div class="section-label">API Key Override</div>
              {#if editingKeyFor === 'transcriber'}
                {#if !keyConfirmed}
                  <div class="key-warning">
                    <p>This will set an API key override for the transcriber. Are you sure?</p>
                    <div class="edit-actions">
                      <button class="sm-btn" on:click={confirmEditKey}>Yes, override</button>
                      <button class="sm-btn muted" on:click={cancelEditKey}>Cancel</button>
                    </div>
                  </div>
                {:else}
                  <div class="key-paste">
                    <input
                      type="password"
                      class="edit-input mono"
                      bind:value={newKeyValue}
                      placeholder="Paste API key"
                      on:keydown={e => e.key === 'Enter' && applyKey()}
                      autofocus
                    />
                    <div class="edit-actions">
                      <button class="sm-btn" on:click={applyKey} disabled={!newKeyValue.trim()}>Apply</button>
                      <button class="sm-btn muted" on:click={cancelEditKey}>Cancel</button>
                    </div>
                  </div>
                {/if}
              {:else}
                <div class="key-display">
                  <div class="key-info">
                    {#if transcriberHasOverride}
                      <span class="key-val">{'\u2022'.repeat(12)}</span>
                      <span class="key-source">override</span>
                    {:else}
                      <span class="key-none">Uses LLM provider key from .env</span>
                    {/if}
                  </div>
                  <div class="key-actions">
                    <button class="sm-btn" on:click={() => { editingKeyFor = 'transcriber'; keyConfirmed = false; newKeyValue = ''; }}>
                      {transcriberHasOverride ? 'Edit' : 'Add'}
                    </button>
                    {#if transcriberHasOverride}
                      <button class="sm-btn muted" on:click={() => { pendingKeyClears.transcriber = true; transcriberHasOverride = false; editingKeyFor = null; }}>Clear override</button>
                    {/if}
                  </div>
                </div>
              {/if}
            </div>

          <!-- LLM / TTS / STT TABS -->
          {:else if currentProvider}
            <!-- Items list (models or voices) -->
            <div class="section-label">{activeTab === 'tts' ? 'Voices' : 'Models'}</div>
            <div class="item-list">
              {#each currentItems as item (item.id)}
                {#if editingVoiceId === item.id}
                  <!-- Inline edit form for voice -->
                  <div class="item-edit-form">
                    <input class="edit-input" bind:value={editName} placeholder="Name" />
                    <input class="edit-input mono" bind:value={editId} placeholder="Voice ID" />
                    <div class="edit-actions">
                      <button class="sm-btn" on:click={submitEditVoice}>Save</button>
                      <button class="sm-btn muted" on:click={cancelEditVoice}>Cancel</button>
                    </div>
                  </div>
                {:else}
                  <!-- svelte-ignore a11y-click-events-have-key-events -->
                  <div
                    class="item-row"
                    class:active={selectedItemId === item.id}
                    role="button"
                    tabindex="0"
                    on:click={() => selectItem(item.id)}
                  >
                    <span class="item-radio" class:checked={selectedItemId === item.id}></span>
                    <span class="item-label">{item.label}</span>
                    {#if item.sublabel}
                      <span class="item-sub">{item.sublabel.length > 20 ? item.sublabel.slice(0, 8) + '...' + item.sublabel.slice(-8) : item.sublabel}</span>
                    {/if}
                    <span class="item-actions">
                      {#if activeTab === 'tts'}
                        <button class="act-btn" on:click|stopPropagation={() => startEditVoice(item)} title="Edit">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                        </button>
                      {/if}
                      <button class="act-btn danger" on:click|stopPropagation={() => removeItem(item.id)} title="Remove">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                      </button>
                    </span>
                  </div>
                {/if}
              {/each}

              <!-- Add form / button -->
              {#if adding}
                <div class="item-add-form">
                  {#if activeTab === 'tts'}
                    <input class="edit-input" bind:value={addName} placeholder="Voice name" on:keydown={e => e.key === 'Enter' && submitAdd()} autofocus />
                    <input class="edit-input mono" bind:value={addId} placeholder="Voice ID" on:keydown={e => e.key === 'Enter' && submitAdd()} />
                  {:else}
                    <input class="edit-input mono" bind:value={addName} placeholder="Model name" on:keydown={e => e.key === 'Enter' && submitAdd()} autofocus />
                  {/if}
                  <div class="edit-actions">
                    <button class="sm-btn" on:click={submitAdd}>Add</button>
                    <button class="sm-btn muted" on:click={cancelAdd}>Cancel</button>
                  </div>
                </div>
              {:else}
                <button class="add-row" on:click={startAdd}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                  Add {activeTab === 'tts' ? 'voice' : 'model'}
                </button>
              {/if}
            </div>

            {#if currentItems.length === 0 && activeTab !== 'tts'}
              <p class="no-models-hint">No models configured. This service may not require a model selection.</p>
            {/if}

            <!-- Speed (TTS only, for providers that support it) -->
            {#if activeTab === 'tts' && currentProvider?.supports_speed}
              <div class="speed-section">
                <div class="speed-header">
                  <label class="speed-toggle">
                    <input type="checkbox" checked={speedEnabled} on:change={toggleSpeed} />
                    <span class="section-label">Speed</span>
                  </label>
                  {#if speedEnabled}
                    <span class="speed-val">{speedValue.toFixed(2)}x</span>
                  {/if}
                </div>
                {#if speedEnabled}
                  {@const cfg = currentProvider.speed_config || { min: 0.5, max: 2.0 }}
                  <input
                    type="range"
                    class="speed-slider"
                    min={cfg.min}
                    max={cfg.max}
                    step="0.05"
                    bind:value={speedValue}
                    on:input={onSpeedChange}
                  />
                {/if}
              </div>
            {/if}

            <!-- API Key -->
            <div class="key-section">
              <div class="section-label">API Key</div>
              {#if editingKeyFor === activeTab}
                {#if !keyConfirmed}
                  <div class="key-warning">
                    <p>This will override your existing API key{currentProvider.has_key ? ' from .env' : ''}. Are you sure?</p>
                    <div class="edit-actions">
                      <button class="sm-btn" on:click={confirmEditKey}>Yes, override</button>
                      <button class="sm-btn muted" on:click={cancelEditKey}>Cancel</button>
                    </div>
                  </div>
                {:else}
                  <div class="key-paste">
                    <input
                      type="password"
                      class="edit-input mono"
                      bind:value={newKeyValue}
                      placeholder="Paste API key"
                      on:keydown={e => e.key === 'Enter' && applyKey()}
                      autofocus
                    />
                    <div class="edit-actions">
                      <button class="sm-btn" on:click={applyKey} disabled={!newKeyValue.trim()}>Apply</button>
                      <button class="sm-btn muted" on:click={cancelEditKey}>Cancel</button>
                    </div>
                  </div>
                {/if}
              {:else}
                <div class="key-display">
                  <div class="key-info">
                    {#if currentHasOverride}
                      <span class="key-val">{'\u2022'.repeat(12)}</span>
                      <span class="key-source">override</span>
                    {:else if currentProvider.has_key}
                      <span class="key-val">{currentProvider.key_hint || '\u2022'.repeat(12)}</span>
                      <span class="key-source">from .env</span>
                    {:else}
                      <span class="key-none">No key configured</span>
                    {/if}
                  </div>
                  <div class="key-actions">
                    <button class="sm-btn" on:click={startEditKey}>
                      {currentProvider.has_key || currentHasOverride ? 'Edit' : 'Add'}
                    </button>
                    {#if currentHasOverride}
                      <button class="sm-btn muted" on:click={clearKeyOverride}>Clear override</button>
                    {/if}
                  </div>
                </div>
              {/if}
            </div>

          {:else if showProviderPanel}
            <p class="empty">Select a provider.</p>
          {/if}
        </div>

        <!-- Footer -->
        <div class="detail-footer">
          <p class="hint">Changes apply on next connection.</p>
          <div class="footer-actions">
            <button class="cancel-btn" on:click={close}>Cancel</button>
            <button class="save-btn" on:click={save}>Save</button>
          </div>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .popup-fill {
    width: 100%;
    height: 100vh;
    display: flex;
  }

  .modal {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 12px;
    width: 860px;
    max-width: 94vw;
    height: 85vh;
    max-height: 85vh;
    display: flex;
    overflow: hidden;
    box-shadow: 0 24px 48px rgba(0, 0, 0, 0.4);
  }

  .modal.popup-mode {
    width: 100%;
    max-width: 100%;
    height: 100vh;
    max-height: 100vh;
    border-radius: 0;
    border: none;
    box-shadow: none;
  }

  /* ── Nav sidebar ────────────────────────────── */

  .sidebar {
    width: 150px;
    flex-shrink: 0;
    background: var(--color-bg);
    border-right: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    padding: 20px 0;
  }

  .sidebar h2 {
    font-size: 14px;
    font-weight: 600;
    color: var(--color-text);
    padding: 0 16px 16px;
  }

  .sidebar nav {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 0 8px;
  }

  .nav-item {
    background: none;
    border: none;
    text-align: left;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 13px;
    font-family: inherit;
    color: var(--color-muted);
    cursor: pointer;
    transition: background 0.1s, color 0.1s;
  }

  .nav-item:hover { background: rgba(255,255,255,0.04); color: var(--color-text); }
  .nav-item.active { background: rgba(255,255,255,0.08); color: var(--color-text); font-weight: 500; }

  /* ── Provider panel ─────────────────────────── */

  .provider-panel {
    width: 180px;
    flex-shrink: 0;
    border-right: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .panel-label {
    font-size: 10px;
    font-weight: 600;
    color: var(--color-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 16px 14px 8px;
  }

  .provider-items {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }

  .prov-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border: none;
    background: none;
    color: var(--color-text);
    font-size: 13px;
    font-family: inherit;
    cursor: pointer;
    text-align: left;
    border-left: 2px solid transparent;
    transition: background 0.1s, border-color 0.15s;
  }

  .prov-row:hover { background: rgba(255,255,255,0.04); }
  .prov-row.selected { background: rgba(74,158,255,0.06); border-left-color: var(--color-blue); }

  .prov-name { flex: 1; font-weight: 500; }
  .prov-count { font-size: 10px; color: var(--color-muted); }

  /* ── Status dot ─────────────────────────────── */

  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--color-red);
    flex-shrink: 0;
  }

  .status-dot.has-key { background: var(--color-green); }

  /* ── Detail panel ───────────────────────────── */

  .detail {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .detail-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--color-border);
    flex-shrink: 0;
  }

  .detail-header h3 { font-size: 15px; font-weight: 600; color: var(--color-text); }

  .header-actions { display: flex; gap: 4px; }

  .hdr-btn {
    background: none;
    border: none;
    color: var(--color-muted);
    cursor: pointer;
    padding: 6px;
    border-radius: 4px;
    display: flex;
    transition: color 0.1s, background 0.1s;
  }

  .hdr-btn:hover:not(:disabled) { color: var(--color-text); background: rgba(255,255,255,0.06); }
  .hdr-btn:disabled { opacity: 0.4; cursor: default; }

  .spinning { animation: spin 0.8s linear infinite; }
  @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

  .detail-body {
    flex: 1;
    overflow-y: auto;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    min-height: 0;
  }

  /* ── Section label ──────────────────────────── */

  .section-label {
    font-size: 10px;
    font-weight: 600;
    color: var(--color-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: -8px;
  }

  /* ── Volume sliders ──────────────────────────── */

  .volume-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .vol-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .vol-icon {
    flex-shrink: 0;
    color: var(--color-muted);
  }

  .vol-slider {
    flex: 1;
    height: 4px;
    -webkit-appearance: none;
    appearance: none;
    background: rgba(255,255,255,0.1);
    border-radius: 2px;
    outline: none;
  }

  .vol-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--color-blue);
    cursor: pointer;
    transition: transform 0.1s;
  }

  .vol-slider::-webkit-slider-thumb:hover {
    transform: scale(1.15);
  }

  .vol-val {
    font-size: 12px;
    font-family: var(--font-mono);
    color: var(--color-muted);
    min-width: 38px;
    text-align: right;
  }

  /* ── Item list (models / voices) ────────────── */

  .item-list {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    overflow: hidden;
  }

  .item-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border: none;
    background: none;
    color: var(--color-text);
    font-size: 13px;
    font-family: inherit;
    cursor: pointer;
    text-align: left;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    transition: background 0.1s;
  }

  .item-row:last-child { border-bottom: none; }
  .item-row:hover { background: rgba(255,255,255,0.04); }
  .item-row.active { background: rgba(74,158,255,0.06); }

  .item-radio {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    border: 2px solid var(--color-muted);
    flex-shrink: 0;
    transition: border-color 0.1s, background 0.1s;
  }

  .item-radio.checked {
    border-color: var(--color-blue);
    background: var(--color-blue);
    box-shadow: inset 0 0 0 3px var(--color-surface);
  }

  .item-label { flex: 1; }

  .item-sub {
    font-size: 10px;
    color: var(--color-muted);
    font-family: var(--font-mono);
  }

  .item-actions {
    display: flex;
    gap: 2px;
    opacity: 0;
    transition: opacity 0.15s;
  }

  .item-row:hover .item-actions { opacity: 1; }

  .act-btn {
    background: none;
    border: none;
    color: var(--color-muted);
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    display: flex;
    transition: color 0.1s, background 0.1s;
  }

  .act-btn:hover { color: var(--color-text); background: rgba(255,255,255,0.08); }
  .act-btn.danger:hover { color: var(--color-red); }

  /* ── Add row ────────────────────────────────── */

  .add-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border: none;
    background: none;
    color: var(--color-muted);
    font-size: 12px;
    font-family: inherit;
    cursor: pointer;
    transition: color 0.1s, background 0.1s;
    border-top: 1px solid rgba(255,255,255,0.05);
  }

  .add-row:hover { color: var(--color-text); background: rgba(255,255,255,0.04); }

  /* ── Inline forms ───────────────────────────── */

  .item-add-form, .item-edit-form {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 10px 14px;
    background: var(--color-bg);
    border-top: 1px solid rgba(255,255,255,0.05);
  }

  .edit-input {
    width: 100%;
    padding: 6px 10px;
    border: 1px solid var(--color-border);
    border-radius: 5px;
    background: var(--color-surface);
    color: var(--color-text);
    font-size: 12px;
    font-family: inherit;
    outline: none;
    transition: border-color 0.15s;
    box-sizing: border-box;
  }

  .edit-input.mono { font-family: var(--font-mono); font-size: 11px; }
  .edit-input:focus { border-color: var(--color-blue); }
  .edit-input::placeholder { color: #444; }

  .edit-actions {
    display: flex;
    gap: 6px;
  }

  .sm-btn {
    padding: 5px 12px;
    border: none;
    border-radius: 5px;
    font-size: 11px;
    font-family: inherit;
    font-weight: 500;
    cursor: pointer;
    background: var(--color-blue);
    color: #0f0f0f;
    transition: opacity 0.1s;
  }

  .sm-btn:hover:not(:disabled) { opacity: 0.85; }
  .sm-btn:disabled { opacity: 0.4; cursor: default; }
  .sm-btn.muted { background: rgba(255,255,255,0.06); color: var(--color-muted); }
  .sm-btn.muted:hover { color: var(--color-text); }

  /* ── Speed section ──────────────────────────── */

  .speed-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .speed-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .speed-toggle {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
  }

  .speed-toggle input[type="checkbox"] {
    width: 14px;
    height: 14px;
    accent-color: var(--color-blue);
    cursor: pointer;
  }

  .speed-slider {
    flex: 1;
    height: 4px;
    -webkit-appearance: none;
    appearance: none;
    background: rgba(255,255,255,0.1);
    border-radius: 2px;
    outline: none;
  }

  .speed-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--color-blue);
    cursor: pointer;
  }

  .speed-val {
    font-size: 12px;
    font-family: var(--font-mono);
    color: var(--color-muted);
    min-width: 42px;
    text-align: right;
  }

  /* ── API Key section ────────────────────────── */

  .key-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .key-display {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 14px;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-bg);
  }

  .key-info { display: flex; align-items: center; gap: 8px; }

  .key-val {
    font-size: 12px;
    font-family: var(--font-mono);
    color: var(--color-text);
    letter-spacing: 0.05em;
  }

  .key-source {
    font-size: 10px;
    color: var(--color-muted);
    padding: 1px 5px;
    border-radius: 3px;
    background: rgba(255,255,255,0.04);
  }

  .key-none { font-size: 12px; color: var(--color-muted); }

  .key-actions { display: flex; gap: 6px; }

  .key-warning {
    padding: 12px 14px;
    border: 1px solid rgba(248,113,113,0.2);
    border-radius: 8px;
    background: rgba(248,113,113,0.05);
  }

  .key-warning p {
    font-size: 12px;
    color: var(--color-text);
    margin: 0 0 10px;
  }

  .key-paste {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  /* ── Footer ─────────────────────────────────── */

  .detail-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 20px;
    border-top: 1px solid var(--color-border);
    flex-shrink: 0;
  }

  .hint { font-size: 11px; color: var(--color-muted); }

  .footer-actions { display: flex; gap: 8px; }

  .cancel-btn, .save-btn {
    padding: 8px 18px;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-family: inherit;
    cursor: pointer;
  }

  .cancel-btn { background: none; color: var(--color-muted); }
  .cancel-btn:hover { color: var(--color-text); }

  .save-btn {
    background: var(--color-blue);
    color: #0f0f0f;
    font-weight: 600;
  }

  .save-btn:hover { opacity: 0.9; }

  /* ── Shared ─────────────────────────────────── */

  .empty {
    font-size: 12px;
    color: var(--color-muted);
    padding: 16px;
  }

  .no-models-hint {
    font-size: 11px;
    color: var(--color-muted);
    font-style: italic;
    padding: 4px 2px 0;
  }

  /* ── Transcriber tab ─────────────────────────── */

  .transcriber-hint {
    font-size: 12px;
    color: var(--color-muted);
    margin: -8px 0 4px;
  }

  .transcriber-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .field-label {
    font-size: 11px;
    font-weight: 500;
    color: var(--color-muted);
  }

  .field-select {
    width: 100%;
    padding: 8px 12px;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: var(--color-bg);
    color: var(--color-text);
    font-size: 13px;
    font-family: var(--font-mono);
    outline: none;
    cursor: pointer;
    transition: border-color 0.15s;
    -webkit-appearance: none;
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg width='10' height='6' viewBox='0 0 10 6' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1L5 5L9 1' stroke='%23666' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 12px center;
    padding-right: 32px;
  }

  .field-select:focus {
    border-color: var(--color-blue);
  }

  .field-select option {
    background: var(--color-surface);
    color: var(--color-text);
  }

  .field-textarea {
    width: 100%;
    padding: 8px 12px;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-surface);
    color: var(--color-text);
    font-family: inherit;
    font-size: 13px;
    resize: vertical;
    outline: none;
    box-sizing: border-box;
    min-height: 48px;
  }

  .field-textarea:focus {
    border-color: var(--color-blue);
  }

  .field-textarea::placeholder {
    color: var(--color-muted);
  }

  .toggle-row {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }

  .toggle-btn {
    padding: 4px 12px;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: var(--color-surface);
    color: var(--color-muted);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
    transition: background 0.15s, color 0.15s, border-color 0.15s;
  }

  .toggle-btn.on {
    background: rgba(99, 102, 241, 0.15);
    color: #818cf8;
    border-color: rgba(99, 102, 241, 0.3);
  }
</style>
