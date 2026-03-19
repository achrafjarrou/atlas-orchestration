import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    // Proxy API calls to avoid CORS in development
    proxy: {
      "/api":  "http://localhost:8000",
      "/a2a":  "http://localhost:8000",
      "/.well-known": "http://localhost:8000",
    },
  },
});