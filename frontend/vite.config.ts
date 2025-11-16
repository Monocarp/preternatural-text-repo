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
          target: 'https://preclinical-scaphoid-felisa.ngrok-free.dev', // Your Ngrok URL
          changeOrigin: true,
          secure: false, // Required for Ngrok's self-signed cert in dev
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