import { describe, expect, it } from "vitest";

import { mountHomeLegends } from "./homeLegends.js";
import { setSubcategoryFilter, subcategoryFilter } from "../state.js";

describe("mountHomeLegends", () => {
  it("subcategory legend buttons filter by subcategory", () => {
    const host = document.createElement("div");
    mountHomeLegends(host);
    setSubcategoryFilter("all");

    const nodeBtn = host.querySelector('.subcategory-accordion button[data-sub="node"]');
    expect(nodeBtn).not.toBeNull();
    nodeBtn?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(subcategoryFilter).toBe("node");
    expect(nodeBtn?.classList.contains("is-active")).toBe(true);

    const allBtn = host.querySelector('.subcategory-accordion button[data-sub="all"]');
    allBtn?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(subcategoryFilter).toBe("all");
    expect(allBtn?.classList.contains("is-active")).toBe(true);
  });
});
