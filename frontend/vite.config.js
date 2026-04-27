import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 250,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/react/") || id.includes("node_modules/react-dom/")) {
            return "react-core";
          }
          if (id.includes("node_modules/react-router") || id.includes("node_modules/react-router-dom")) {
            return "router";
          }
          if (id.includes("node_modules/jwt-decode")) {
            return "auth";
          }
          if (id.includes("node_modules/leaflet") || id.includes("node_modules/react-leaflet")) {
            return "maps";
          }
          if (id.includes("node_modules/firebase")) {
            return "firebase";
          }
          if (id.includes("node_modules")) {
            return "vendor";
          }
          return undefined;
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/setupTests.js",
  },
});
