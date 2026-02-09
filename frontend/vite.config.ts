import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import path from 'path';
import { viteSourceLocator } from '@metagptx/vite-plugin-source-locator';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [
    viteSourceLocator({
      prefix: 'mgx',
    }),
    react(),
  ],
  server: {
    watch: { usePolling: true, interval: 800 /* 300~1500 */ },
    proxy: {
      '/api': {
        target: 'https://apis.data.go.kr',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        secure: false,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
}));