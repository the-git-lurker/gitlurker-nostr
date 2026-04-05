import { describe, expect, it } from "vitest";

import { showTableSkeleton } from "./loadingSkeleton.js";

describe("showTableSkeleton", () => {
  it("marks the table for e2e / a11y hooks", () => {
    const host = document.createElement("div");
    showTableSkeleton(host, 2);
    const table = host.querySelector("[data-testid='loading-skeleton']");
    expect(table).not.toBeNull();
    expect(table?.classList.contains("skeleton-table")).toBe(true);
    expect(host.textContent).toContain("REPOSITORY");
  });
});
