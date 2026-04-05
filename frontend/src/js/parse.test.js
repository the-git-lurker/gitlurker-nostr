import { describe, expect, it } from "vitest";

import { parseBookmarkATag, parseKind30078 } from "./parse.js";

describe("parseKind30078", () => {
  it("parses tags and content", () => {
    const p = parseKind30078({
      kind: 30078,
      tags: [
        ["d", "foo/bar"],
        ["owner", "foo"],
        ["category", "nostr"],
        ["t", "protocol"],
        ["mode", "release"],
        ["stars", "3"],
      ],
      content: '{"owner":"foo","repo":"bar"}',
      created_at: 1700000000,
    });
    expect(p).not.toBeNull();
    expect(p.owner).toBe("foo");
    expect(p.repo).toBe("bar");
    expect(p.category).toBe("nostr");
    expect(p.subcategory).toBe("protocol");
    expect(p.tracking_mode).toBe("release");
    expect(p.stars).toBe(3);
  });

  it("returns null for wrong kind", () => {
    expect(
      parseKind30078({
        kind: 1,
        tags: [],
        content: "",
        created_at: 1,
      }),
    ).toBeNull();
  });
});

describe("parseBookmarkATag", () => {
  it("parses 30078 coordinate for matching author", () => {
    const pk = "a".repeat(64);
    const tag = "30078:" + pk + ":own/r";
    const d = parseBookmarkATag(tag, pk);
    expect(d).toEqual({ d: "own/r" });
  });

  it("rejects wrong kind or author", () => {
    const pk = "a".repeat(64);
    const other = "b".repeat(64);
    expect(parseBookmarkATag("30078:" + other + ":o/r", pk)).toBeNull();
    expect(parseBookmarkATag("1:" + pk + ":x", pk)).toBeNull();
  });
});
