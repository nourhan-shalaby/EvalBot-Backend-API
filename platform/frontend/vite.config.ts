import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { "/api": "http://127.0.0.1:7870", "/demo": "http://127.0.0.1:7870" } },
  build: { outDir: "dist", chunkSizeWarningLimit: 1200 },
});
