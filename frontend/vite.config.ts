import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/hydra-c2/',
  server: {
    proxy: {
      '/api': {
        target: 'https://134-199-207-172.sslip.io',
        changeOrigin: true,
        secure: true,
      },
    },
  },
})
