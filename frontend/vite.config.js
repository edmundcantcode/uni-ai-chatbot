import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [
    {
      name: 'react',
      // Simplified React plugin
    }
  ],
  server: {
    host: '0.0.0.0',
    port: 3000
  }
})