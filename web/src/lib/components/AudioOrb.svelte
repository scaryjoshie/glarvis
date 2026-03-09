<script>
  import { onMount, onDestroy } from 'svelte';
  import { agentState, connectionState, muted, voiceMuted } from '../stores/connection.js';

  let canvas;
  let ctx;
  let animId;
  let time = 0;

  // Reactive state values
  $: state = $agentState;
  $: connected = $connectionState === 'connected';
  $: isMuted = $muted || $voiceMuted;

  // Color configs per state
  const stateColors = {
    idle: { primary: [85, 90, 112], secondary: [74, 158, 255], glow: 0.3 },
    listening: { primary: [74, 222, 128], secondary: [34, 211, 238], glow: 0.7 },
    thinking: { primary: [250, 204, 21], secondary: [167, 139, 250], glow: 0.9 },
    speaking: { primary: [74, 158, 255], secondary: [167, 139, 250], glow: 1.0 },
  };

  let currentColor = { primary: [85, 90, 112], secondary: [74, 158, 255], glow: 0.3 };
  let targetColor = { ...currentColor };

  function lerpColor(a, b, t) {
    return a.map((v, i) => v + (b[i] - v) * t);
  }

  function draw() {
    if (!ctx || !canvas) return;
    const w = canvas.width;
    const h = canvas.height;
    if (w === 0 || h === 0) {
      animId = requestAnimationFrame(draw);
      return;
    }
    const cx = w / 2;
    const cy = h / 2;
    const baseRadius = Math.min(w, h) * 0.28;

    time += 0.016;

    // Smooth color transitions
    const target = connected ? (stateColors[state] || stateColors.idle) : { primary: [40, 42, 55], secondary: [55, 58, 75], glow: 0.15 };
    targetColor = target;
    currentColor.primary = lerpColor(currentColor.primary, targetColor.primary, 0.04);
    currentColor.secondary = lerpColor(currentColor.secondary, targetColor.secondary, 0.04);
    currentColor.glow += (targetColor.glow - currentColor.glow) * 0.04;

    ctx.clearRect(0, 0, w, h);

    // Outer glow
    const glowIntensity = currentColor.glow * (0.7 + 0.3 * Math.sin(time * 1.5));
    const [pr, pg, pb] = currentColor.primary.map(Math.round);
    const [sr, sg, sb] = currentColor.secondary.map(Math.round);

    // Ambient glow rings
    for (let ring = 3; ring >= 1; ring--) {
      const ringRadius = baseRadius + ring * 18;
      const ringAlpha = glowIntensity * 0.06 / ring;
      const grad = ctx.createRadialGradient(cx, cy, ringRadius * 0.8, cx, cy, ringRadius);
      grad.addColorStop(0, `rgba(${pr}, ${pg}, ${pb}, ${ringAlpha})`);
      grad.addColorStop(1, `rgba(${pr}, ${pg}, ${pb}, 0)`);
      ctx.beginPath();
      ctx.arc(cx, cy, ringRadius, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();
    }

    // Main orb body — animated blob
    const segments = 128;
    ctx.beginPath();
    for (let i = 0; i <= segments; i++) {
      const angle = (i / segments) * Math.PI * 2;

      // Multiple noise layers for organic movement
      let noise = 0;
      if (connected) {
        if (state === 'speaking') {
          noise = Math.sin(angle * 3 + time * 4) * 8 +
                  Math.sin(angle * 5 + time * 6) * 5 +
                  Math.sin(angle * 7 + time * 3) * 3 +
                  Math.cos(angle * 2 + time * 8) * 6;
        } else if (state === 'thinking') {
          noise = Math.sin(angle * 4 + time * 3) * 6 +
                  Math.cos(angle * 6 + time * 5) * 4 +
                  Math.sin(angle * 2 + time * 2) * 3;
        } else if (state === 'listening') {
          noise = Math.sin(angle * 3 + time * 2) * 4 +
                  Math.cos(angle * 5 + time * 1.5) * 2;
        } else {
          noise = Math.sin(angle * 2 + time * 0.8) * 2 +
                  Math.cos(angle * 3 + time * 0.5) * 1.5;
        }
      } else {
        noise = Math.sin(angle * 2 + time * 0.3) * 1;
      }

      if (isMuted && connected) {
        noise *= 0.3;
      }

      const r = baseRadius + noise;
      const x = cx + Math.cos(angle) * r;
      const y = cy + Math.sin(angle) * r;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();

    // Gradient fill
    const orbGrad = ctx.createRadialGradient(cx - baseRadius * 0.3, cy - baseRadius * 0.3, 0, cx, cy, baseRadius * 1.2);
    orbGrad.addColorStop(0, `rgba(${sr}, ${sg}, ${sb}, 0.35)`);
    orbGrad.addColorStop(0.5, `rgba(${pr}, ${pg}, ${pb}, 0.2)`);
    orbGrad.addColorStop(1, `rgba(${pr}, ${pg}, ${pb}, 0.05)`);
    ctx.fillStyle = orbGrad;
    ctx.fill();

    // Inner highlight
    const innerGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, baseRadius * 0.6);
    innerGrad.addColorStop(0, `rgba(255, 255, 255, ${0.06 * glowIntensity})`);
    innerGrad.addColorStop(1, `rgba(255, 255, 255, 0)`);
    ctx.beginPath();
    ctx.arc(cx, cy, baseRadius * 0.6, 0, Math.PI * 2);
    ctx.fillStyle = innerGrad;
    ctx.fill();

    // Border glow
    ctx.beginPath();
    for (let i = 0; i <= segments; i++) {
      const angle = (i / segments) * Math.PI * 2;
      let noise = 0;
      if (connected) {
        if (state === 'speaking') {
          noise = Math.sin(angle * 3 + time * 4) * 8 +
                  Math.sin(angle * 5 + time * 6) * 5 +
                  Math.sin(angle * 7 + time * 3) * 3 +
                  Math.cos(angle * 2 + time * 8) * 6;
        } else if (state === 'thinking') {
          noise = Math.sin(angle * 4 + time * 3) * 6 +
                  Math.cos(angle * 6 + time * 5) * 4 +
                  Math.sin(angle * 2 + time * 2) * 3;
        } else if (state === 'listening') {
          noise = Math.sin(angle * 3 + time * 2) * 4 +
                  Math.cos(angle * 5 + time * 1.5) * 2;
        } else {
          noise = Math.sin(angle * 2 + time * 0.8) * 2 +
                  Math.cos(angle * 3 + time * 0.5) * 1.5;
        }
      } else {
        noise = Math.sin(angle * 2 + time * 0.3) * 1;
      }
      if (isMuted && connected) noise *= 0.3;
      const r = baseRadius + noise;
      const x = cx + Math.cos(angle) * r;
      const y = cy + Math.sin(angle) * r;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.strokeStyle = `rgba(${pr}, ${pg}, ${pb}, ${0.4 * glowIntensity})`;
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Orbiting particles
    if (connected && !isMuted) {
      const particleCount = state === 'speaking' ? 8 : state === 'thinking' ? 6 : 3;
      for (let i = 0; i < particleCount; i++) {
        const pAngle = time * (0.8 + i * 0.3) + (i * Math.PI * 2 / particleCount);
        const pDist = baseRadius + 20 + Math.sin(time * 2 + i) * 10;
        const px = cx + Math.cos(pAngle) * pDist;
        const py = cy + Math.sin(pAngle) * pDist;
        const pSize = 2 + Math.sin(time * 3 + i * 1.5) * 1;
        const pAlpha = 0.3 + 0.3 * Math.sin(time * 2 + i);

        ctx.beginPath();
        ctx.arc(px, py, pSize, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${sr}, ${sg}, ${sb}, ${pAlpha})`;
        ctx.fill();
      }
    }

    // State label
    if (connected) {
      const label = state === 'idle' ? '' : state === 'listening' ? 'LISTENING' : state === 'thinking' ? 'THINKING' : 'SPEAKING';
      if (label) {
        ctx.font = `600 10px ${getComputedStyle(canvas).getPropertyValue('--font-mono').trim() || 'monospace'}`;
        ctx.textAlign = 'center';
        ctx.fillStyle = `rgba(${pr}, ${pg}, ${pb}, ${0.6 + 0.3 * Math.sin(time * 2)})`;
        ctx.letterSpacing = '3px';
        ctx.fillText(label, cx, cy + baseRadius + 36);
      }
    }

    animId = requestAnimationFrame(draw);
  }

  function resize() {
    if (!canvas || !ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
  }

  onMount(() => {
    if (!canvas) return;
    ctx = canvas.getContext('2d');
    if (!ctx) return;
    resize();
    draw();
    window.addEventListener('resize', resize);
  });

  onDestroy(() => {
    if (animId) cancelAnimationFrame(animId);
    window.removeEventListener('resize', resize);
  });
</script>

<div class="orb-container">
  <canvas bind:this={canvas} class="orb-canvas"></canvas>
</div>

<style>
  .orb-container {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
  }

  .orb-canvas {
    width: 100%;
    height: 100%;
  }
</style>
