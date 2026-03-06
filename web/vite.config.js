import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  plugins: [svelte()],
  server: {
    proxy: {
      '/webrtc': 'http://localhost:8011',
      '/ws': {
        target: 'ws://localhost:8011',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})
