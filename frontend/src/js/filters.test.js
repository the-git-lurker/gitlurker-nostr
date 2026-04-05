import { describe, expect, it } from "vitest";

import {
  filterProjectsByCategory,
  filterProjectsBySearch,
} from "./filters.js";

const sample = [
  {
    owner: "alice",
    repo: "zap",
    name: "zap",
    description: "",
    category: "nostr",
    subcategory: "wallet",
    tracking_mode: "release",
    web: "",
    clone: "",
    release_version: null,
    release_date_iso: null,
    tag_name: null,
    tag_date_iso: null,
    commit_sha: null,
    commit_date_iso: null,
    commit_author: null,
    stars: 0,
    forks: 0,
    open_issues: 0,
    stale: false,
    _created_at: 1,
  },
  {
    owner: "bob",
    repo: "bitcoin",
    name: "bitcoin",
    description: "",
    category: "bitcoin",
    subcategory: "node",
    tracking_mode: "tag",
    web: "",
    clone: "",
    release_version: null,
    release_date_iso: null,
    tag_name: null,
    tag_date_iso: null,
    commit_sha: null,
    commit_date_iso: null,
    commit_author: null,
    stars: 0,
    forks: 0,
    open_issues: 0,
    stale: false,
    _created_at: 2,
  },
];

describe("filterProjectsByCategory", () => {
  it("returns all for all", () => {
    expect(filterProjectsByCategory(sample, "all")).toHaveLength(2);
  });

  it("filters by category", () => {
    const out = filterProjectsByCategory(sample, "bitcoin");
    expect(out).toHaveLength(1);
    expect(out[0].repo).toBe("bitcoin");
  });
});

describe("filterProjectsBySearch", () => {
  it("returns all when query empty", () => {
    expect(filterProjectsBySearch(sample, "")).toHaveLength(2);
  });

  it("matches owner, repo, subcategory", () => {
    expect(filterProjectsBySearch(sample, "alice")).toHaveLength(1);
    expect(filterProjectsBySearch(sample, "zap")).toHaveLength(1);
    expect(filterProjectsBySearch(sample, "wallet")).toHaveLength(1);
    expect(filterProjectsBySearch(sample, "nomatch")).toHaveLength(0);
  });
});
