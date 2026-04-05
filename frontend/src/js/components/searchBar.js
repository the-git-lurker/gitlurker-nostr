import { searchQuery, setSearchQuery, subscribe } from "../state.js";

/** @param {HTMLElement} container */
export function mountSearchBar(container) {
  const wrap = document.createElement("div");
  wrap.className = "search-bar";

  const input = document.createElement("input");
  input.type = "search";
  input.className = "search-input";
  input.placeholder = "Search owner, repo, subcategory";
  input.setAttribute("aria-label", "Filter projects");
  input.value = searchQuery;

  input.addEventListener("input", () => {
    setSearchQuery(input.value);
  });

  subscribe(() => {
    if (input.value !== searchQuery) input.value = searchQuery;
  });

  wrap.appendChild(input);
  container.appendChild(wrap);
}
