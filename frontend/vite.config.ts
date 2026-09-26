import { defineConfig } from 'vite';
export default defineConfig({
  server: {
    port: 5173,
    proxy: { '/api': { target: process.env.API_TARGET || 'http://127.0.0.1:8010', changeOrigin: true, rewrite: path => path.replace(/^\/api/, '') } },
  },
});
