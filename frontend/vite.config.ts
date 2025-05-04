import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir:  "edgy/contrib/admin/backend/static",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    strictPort: true,
    open: true,
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
