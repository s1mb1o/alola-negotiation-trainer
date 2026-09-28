import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const uiPort = Number(env.VITE_DEV_PORT ?? '8171')
  const apiTarget = env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:8172'

  return {
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      port: uiPort,
      strictPort: true,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
    preview: {
      host: '127.0.0.1',
      port: uiPort,
      strictPort: true,
    },
  }
})
