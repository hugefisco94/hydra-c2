import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/hydra-c2/',
  server: {
    proxy: {
      '/api': {
        target: 'http://134.199.207.172:8080',
        changeOrigin: true,
      },
    },
  },
  define: {
    __API_BASE_URL__: JSON.stringify(
      process.env.VITE_API_BASE_URL ?? 'http://134.199.207.172:8080'
    ),
  },
})
