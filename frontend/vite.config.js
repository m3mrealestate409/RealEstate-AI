import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API base URL is injected via VITE_API_URL (defaults to the local backend).
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
  },
});
