<script>
  import { createEventDispatcher } from 'svelte';

  export let direction = 'vertical'; // vertical = drag left/right, horizontal = drag up/down

  const dispatch = createEventDispatcher();
  let dragging = false;

  function onPointerDown(e) {
    dragging = true;
    document.body.style.cursor = direction === 'vertical' ? 'col-resize' : 'row-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
  }

  function onPointerMove(e) {
    if (!dragging) return;
    dispatch('resize', {
      clientX: e.clientX,
      clientY: e.clientY,
      movementX: e.movementX,
      movementY: e.movementY,
    });
  }

  function onPointerUp() {
    dragging = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
  }
</script>

<div
  class="divider"
  class:vertical={direction === 'vertical'}
  class:horizontal={direction === 'horizontal'}
  class:dragging
  on:pointerdown={onPointerDown}
  role="separator"
>
  <div class="divider-handle"></div>
</div>

<style>
  .divider {
    position: relative;
    z-index: 10;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .divider.vertical {
    width: 5px;
    cursor: col-resize;
    margin: 0 -2px;
  }

  .divider.horizontal {
    height: 5px;
    cursor: row-resize;
    margin: -2px 0;
  }

  .divider-handle {
    border-radius: 999px;
    background: var(--color-border);
    transition: background var(--transition-fast), transform var(--transition-fast);
    opacity: 0;
  }

  .divider.vertical .divider-handle {
    width: 3px;
    height: 32px;
  }

  .divider.horizontal .divider-handle {
    width: 32px;
    height: 3px;
  }

  .divider:hover .divider-handle,
  .divider.dragging .divider-handle {
    background: var(--color-blue);
    opacity: 1;
    box-shadow: 0 0 8px var(--color-blue-glow);
  }

  .divider.dragging .divider-handle {
    transform: scaleY(1.5);
  }
</style>
