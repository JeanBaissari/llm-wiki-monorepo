import { describe, it, expect } from "vitest";
import { loadJsonSchema } from "./schema_validator.js";

describe("Schema Validator", () => {
  it("loads page schema", () => {
    const schema = loadJsonSchema("page");
    expect(schema).toBeDefined();
  });

  it("loads audit schema", () => {
    const schema = loadJsonSchema("audit");
    expect(schema).toBeDefined();
  });
});
