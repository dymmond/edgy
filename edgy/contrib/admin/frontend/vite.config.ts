import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../static', // or 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173
  }
})
