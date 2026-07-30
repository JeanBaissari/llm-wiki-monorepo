import { describe, it, expect } from "vitest";

describe("graph-bridge", () => {
  it("exports are importable", async () => {
    const mod = await import("./index.js");
    expect(mod).toBeDefined();
  });
});
