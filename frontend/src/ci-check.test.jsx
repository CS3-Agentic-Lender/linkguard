import { describe, expect, it } from "vitest";

// Deliberately failing, to show the frontend job goes red and names this test.
// Removed again before review.
describe("frontend job check", () => {
  it("fails on purpose", () => {
    expect(1 + 1).toBe(3);
  });
});
