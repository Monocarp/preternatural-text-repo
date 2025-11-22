// frontend/vite.config.ts
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  // Load all environment variables (including NEXT_PUBLIC_ prefixed ones)
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: '0.0.0.0',
      allowedHosts: [
        'app.local',
        'localhost'
      ],
      proxy: {
        '/api': {
          target: 'http://localhost:8000', // Local backend for development
          changeOrigin: true,
          secure: false,
        }
      }
    },
    base: '/',
    define: {
      // Polyfill process.env to fix "process is not defined" in @stackframe/react
      'process.env': JSON.stringify(env)
    }
  }
})