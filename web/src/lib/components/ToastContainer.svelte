<script>
  import { writable } from 'svelte/store';

  // Toast store — exported so other components can push toasts
  export const toasts = writable([]);
  let nextId = 0;

  export function addToast(message, type = 'info', duration = 3000) {
    const id = nextId++;
    toasts.update(t => [...t, { id, message, type, leaving: false }]);
    if (duration > 0) {
      setTimeout(() => removeToast(id), duration);
    }
    return id;
  }

  export function removeToast(id) {
    toasts.update(t => t.map(toast =>
      toast.id === id ? { ...toast, leaving: true } : toast
    ));
    setTimeout(() => {
      toasts.update(t => t.filter(toast => toast.id !== id));
    }, 300);
  }

  // Make addToast available globally
  if (typeof window !== 'undefined') {
    window.__minerva_toast = addToast;
  }
</script>

<div class="toast-container">
  {#each $toasts as toast (toast.id)}
    <button
      class="toast toast-{toast.type}"
      class:leaving={toast.leaving}
      on:click={() => removeToast(toast.id)}
    >
      <div class="toast-icon">
        {#if toast.type === 'success'}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        {:else if toast.type === 'error'}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
        {:else if toast.type === 'warning'}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
        {:else}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
          </svg>
        {/if}
      </div>
      <span class="toast-message">{toast.message}</span>
    </button>
  {/each}
</div>

<style>
  .toast-container {
    position: fixed;
    bottom: 48px;
    right: 16px;
    z-index: 9999;
    display: flex;
    flex-direction: column-reverse;
    gap: 8px;
    pointer-events: none;
  }

  .toast {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 16px;
    border-radius: var(--radius-md);
    background: var(--color-surface-solid);
    border: 1px solid var(--color-border-strong);
    box-shadow: var(--shadow-lg);
    font-size: 13px;
    color: var(--color-text);
    pointer-events: auto;
    cursor: pointer;
    animation: toastIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) both;
    max-width: 360px;
  }

  .toast.leaving {
    animation: toastOut 0.3s ease both;
  }

  .toast-info .toast-icon { color: var(--color-blue); }
  .toast-success .toast-icon { color: var(--color-green); }
  .toast-error .toast-icon { color: var(--color-red); }
  .toast-warning .toast-icon { color: var(--color-yellow); }

  .toast-info { border-left: 3px solid var(--color-blue); }
  .toast-success { border-left: 3px solid var(--color-green); }
  .toast-error { border-left: 3px solid var(--color-red); }
  .toast-warning { border-left: 3px solid var(--color-yellow); }

  .toast-icon {
    flex-shrink: 0;
  }

  .toast-message {
    line-height: 1.3;
  }

  @keyframes toastIn {
    from {
      opacity: 0;
      transform: translateX(40px) scale(0.9);
    }
    to {
      opacity: 1;
      transform: translateX(0) scale(1);
    }
  }

  @keyframes toastOut {
    to {
      opacity: 0;
      transform: translateX(40px) scale(0.9);
    }
  }
</style>
