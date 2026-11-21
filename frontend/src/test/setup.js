import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
  // Saved checks live in browser storage, so each test starts with none.
  window.localStorage.clear();
});
