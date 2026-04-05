import { describe, expect, it } from "vitest";

import { resolveInitialTheme, THEME_STORAGE_KEY } from "./themeToggle.js";

describe("resolveInitialTheme", () => {
  it("prefers saved theme", () => {
    expect(resolveInitialTheme("dark", false)).toBe("dark");
    expect(resolveInitialTheme("light", true)).toBe("light");
  });

  it("uses system preference when saved invalid", () => {
    expect(resolveInitialTheme("garbage", true)).toBe("dark");
    expect(resolveInitialTheme(null, false)).toBe("light");
  });
});

describe("THEME_STORAGE_KEY", () => {
  it("is stable", () => {
    expect(THEME_STORAGE_KEY).toBe("gitlurker-theme");
  });
});
