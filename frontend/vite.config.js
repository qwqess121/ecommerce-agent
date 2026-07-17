import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 部署在 FastAPI 的 /ui 路由下，故 base 设为 /ui/
export default defineConfig({
  base: '/ui/',
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
