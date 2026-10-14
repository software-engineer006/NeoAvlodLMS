import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@neoavlod/ui/teacher-guide": fileURLToPath(new URL("../../packages/ui/src/guide/TeacherGuideView.tsx", import.meta.url)),
      "@neoavlod/ui": fileURLToPath(new URL("../../packages/ui/src/index.ts", import.meta.url)),
    },
  },
  server: {
    allowedHosts: ["teacher"],
    port: 3001,
    host: "0.0.0.0",
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
