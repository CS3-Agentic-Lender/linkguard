import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    // Component tests run in a browser-like DOM, so they can check labels,
    // focus and the live region the way a user and a screen reader meet them.
    environment: "jsdom",
    setupFiles: ["./src/test/setup.js"],
  },
});
