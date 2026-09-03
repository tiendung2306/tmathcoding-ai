import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Trong Docker, frontend chạy trong container riêng -> backend nằm tại http://backend:8000.
// Khi chạy dev trên máy (npm run dev), backend nằm tại http://localhost:8000.
// Dùng biến môi trường VITE_PROXY_TARGET (do docker-compose inject) để không trỏ sai.
const PROXY_TARGET = process.env.VITE_PROXY_TARGET || 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: PROXY_TARGET,
        changeOrigin: true,
      },
    },
  },
});
