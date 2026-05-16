import { describe, expect, it, vi } from "vitest";

import { renderProjectTable } from "./projectTable.js";

/** @returns {import('../parse.js').ParsedProject} */
function project(overrides = {}) {
  return {
    owner: "acme",
    repo: "demo",
    name: "demo",
    description: "",
    category: "bitcoin",
    subcategory: "wallet",
    tracking_mode: "release",
    web: "https://github.com/acme/demo",
    clone: "https://github.com/acme/demo.git",
    release_version: "v1",
    release_date_iso: "2024-06-01T12:00:00Z",
    tag_name: null,
    tag_date_iso: null,
    commit_sha: null,
    commit_date_iso: null,
    commit_author: null,
    stars: 1,
    forks: 0,
    open_issues: 0,
    stale: false,
    _created_at: 0,
    ...overrides,
  };
}

describe("renderProjectTable", () => {
  it("orders REPOSITORY before Owner and shows category/subcategory when All", () => {
    const host = document.createElement("div");
    const nav = vi.fn();
    renderProjectTable(host, [project()], nav, "all");
    const ths = host.querySelectorAll("thead th");
    expect(ths[1].textContent).toContain("REPOSITORY");
    expect(ths[2].textContent).toContain("Owner");
    const row = host.querySelector("tbody tr");
    expect(row).not.toBeNull();
    const cells = row.querySelectorAll("td");
    const typePair = cells[0].querySelector(".type-cell-inner .type-icons");
    expect(typePair?.getAttribute("aria-label")).toBe("bitcoin / Wallet");
    expect(cells[0].querySelectorAll(".bc-icon").length).toBe(2);
    expect(cells[1].textContent.trim()).toBe("demo");
    expect(cells[2].textContent.trim()).toBe("acme");
    expect(host.innerHTML).toContain("bc-icon");
    const verA = cells[3].querySelector("a");
    expect(verA?.getAttribute("data-spa")).toBe("1");
    expect(verA?.getAttribute("href")).toBe("/acme/demo/release");
  });

  it("shows only subcategory icon when a category tab is selected", () => {
    const host = document.createElement("div");
    renderProjectTable(host, [project()], vi.fn(), "bitcoin");
    const sr = host.querySelector(".type-icons .sr-only");
    expect(sr?.textContent).toBe("Wallet");
    expect(host.querySelectorAll(".type-icons .bc-icon").length).toBe(1);
  });

  it("shows tombstone in activity column when stale", () => {
    const host = document.createElement("div");
    renderProjectTable(host, [project({ stale: true })], vi.fn(), "all");
    const rec = host.querySelector(".recency-cell--stale");
    expect(rec).not.toBeNull();
    expect(rec?.innerHTML).toContain("bc-icon--recency-stale");
  });

  it("stale rows have no SPA links in repo, owner, or version cells", () => {
    const host = document.createElement("div");
    renderProjectTable(host, [project({ stale: true })], vi.fn(), "all");
    const row = host.querySelector("tbody tr");
    expect(row?.querySelectorAll("a[data-spa]").length).toBe(0);
  });

  it("release mode without release_version shows Latest commit and commit_date_iso in table", () => {
    const host = document.createElement("div");
    renderProjectTable(
      host,
      [
        project({
          release_version: null,
          release_date_iso: null,
          commit_date_iso: "2025-08-01T10:00:00Z",
          commit_sha: "abcd123",
        }),
      ],
      vi.fn(),
      "all",
    );
    const row = host.querySelector("tbody tr");
    const cells = row?.querySelectorAll("td");
    expect(cells?.[3].textContent.trim()).toBe("Latest commit");
    expect(cells?.[4].textContent.trim()).toContain("2025-08-01");
    const verLink = cells?.[3].querySelector("a");
    expect(verLink?.getAttribute("data-spa")).toBeNull();
    expect(verLink?.getAttribute("target")).toBe("_blank");
    expect(verLink?.getAttribute("href")).toBe("https://github.com/acme/demo/commits");
  });
});
