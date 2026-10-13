import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@neoavlod/ui/admin-guide": fileURLToPath(new URL("./packages/ui/src/guide/AdminGuideView.tsx", import.meta.url)),
      "@neoavlod/ui/teacher-guide": fileURLToPath(new URL("./packages/ui/src/guide/TeacherGuideView.tsx", import.meta.url)),
      "@neoavlod/ui": fileURLToPath(new URL("./packages/ui/src/index.ts", import.meta.url)),
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
  },
});
