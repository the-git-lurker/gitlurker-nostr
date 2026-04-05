import { iconCategoryTab } from "../icons.js";
import { escapeHtml } from "../utils.js";
import { categoryFilter, setCategoryFilter, subscribe } from "../state.js";

const TABS = [
  { id: "all", label: "All" },
  { id: "bitcoin", label: "Bitcoin" },
  { id: "layer2", label: "Layer 2" },
  { id: "ecash", label: "e-Cash" },
  { id: "nostr", label: "Nostr" },
  { id: "ai", label: "AI" },
  { id: "other", label: "Other" },
];

/** @param {HTMLElement} container */
export function mountCategoryTabs(container) {
  const nav = document.createElement("nav");
  nav.className = "category-tabs";
  nav.setAttribute("aria-label", "Category filter");

  function syncActive() {
    for (const btn of nav.querySelectorAll("button[data-cat]")) {
      const id = btn.getAttribute("data-cat");
      btn.classList.toggle("is-active", id === categoryFilter);
    }
  }

  for (const t of TABS) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tab";
    btn.dataset.cat = t.id;
    btn.innerHTML = `${escapeHtml(t.label)} ${iconCategoryTab(t.id, t.label)}`;
    btn.addEventListener("click", () => setCategoryFilter(t.id));
    nav.appendChild(btn);
  }

  container.appendChild(nav);
  subscribe(syncActive);
  syncActive();
}
