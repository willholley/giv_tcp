import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    host: '0.0.0.0',
    fs: {
      // 
      allow: ['/config/GivTCP/allsettings.json'],
    },
  },
  plugins: [
    vue(),
  ],
//  base: '/api/hassio_ingress/Sh0KGb4ov2KVn9o-o9PskOkIO_4HtHc3p63Y1aWJOGg',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    }
  }
})
