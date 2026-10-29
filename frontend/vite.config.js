import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // In development the page and the backend run on different ports. The dev
    // server passes /scan on to the backend, so the page only ever calls its own origin.
    // BACKEND_URL points it elsewhere if the backend isn't on its default port.
    proxy: {
      "/scan": process.env.BACKEND_URL ?? "http://127.0.0.1:8000",
    },
  },
  test: {
    // Component tests run in a browser-like DOM, so they can check labels,
    // focus and the live region the way a user and a screen reader meet them.
    environment: "jsdom",
    setupFiles: ["./src/test/setup.js"],
  },
});
