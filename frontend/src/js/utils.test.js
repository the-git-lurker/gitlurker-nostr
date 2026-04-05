import { describe, expect, it } from "vitest";

import { escapeHtml, isValidOwnerRepo, truncate } from "./utils.js";

describe("escapeHtml", () => {
  it("escapes angle brackets", () => {
    expect(escapeHtml("<script>")).toBe("&lt;script&gt;");
  });
});

describe("isValidOwnerRepo", () => {
  it("accepts slug chars", () => {
    expect(isValidOwnerRepo("rust-nostr")).toBe(true);
    expect(isValidOwnerRepo("bad repo")).toBe(false);
  });
});

describe("truncate", () => {
  it("shortens long strings", () => {
    expect(truncate("abcdefgh", 5)).toBe("abcd...");
  });
});
