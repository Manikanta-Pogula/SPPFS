// vite.config.js (place in project root: C:\student-performance-system\vite.config.js)
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      // forward API, auth and uploads routes to Flask backend
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path
      },
      '/auth': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        secure: false
      },
      '/uploads': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        secure: false
      }
    }
  }
})
