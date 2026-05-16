import {
  SUB_LEGEND_ROWS,
  iconCategoryTab,
  iconLegendRecent,
  iconLegendOld,
  iconLegendTwoWeeks,
  iconSubcategory,
  subcategoryTitle,
} from "../icons.js";
import { escapeHtml } from "../utils.js";
import { setSubcategoryFilter, subcategoryFilter, subscribe } from "../state.js";

const MOBILE_MQ = "(max-width: 639px)";

/**
 * @param {string} id
 * @param {string} label
 * @param {string} iconHtml
 */
function createSubcategoryFilterButton(id, label, iconHtml) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "legend-filter-btn legend-sub";
  btn.dataset.sub = id;
  btn.setAttribute("aria-label", label);
  btn.innerHTML = `${iconHtml} <span class="legend-label">${escapeHtml(label)}</span>`;
  btn.addEventListener("click", () => setSubcategoryFilter(id));
  return btn;
}

/** @param {string} filterId */
function subcategorySummaryLabel(filterId) {
  if (filterId === "all") return "All";
  return subcategoryTitle(filterId);
}

/** @param {HTMLDetailsElement} details */
function syncAccordionLayout(details) {
  details.open = !window.matchMedia(MOBILE_MQ).matches;
}

/** @param {HTMLElement} container */
export function mountHomeLegends(container) {
  const wrap = document.createElement("div");
  wrap.className = "home-legends";

  const rec = document.createElement("div");
  rec.className = "legend-row legend-row--recency";
  rec.setAttribute("aria-label", "Activity recency legend");
  rec.innerHTML = `
    <span class="legend-recency-title legend-recency-title--desktop">
      <span class="legend-label">Latest activity (UTC)</span>
    </span>
    <div class="legend-recency-icons" role="group" aria-label="Recency indicators">
      <span class="legend-item legend-recency legend-recency--recent">
        ${iconLegendRecent()}
        <span class="legend-label legend-label--desktop">≤ 7 days</span>
        <span class="legend-label legend-label--mobile">≤7d</span>
      </span>
      <span class="legend-item legend-recency legend-recency--two-week">
        ${iconLegendTwoWeeks()}
        <span class="legend-label legend-label--desktop">≤ 14 days</span>
        <span class="legend-label legend-label--mobile">≤14d</span>
      </span>
      <span class="legend-item legend-recency legend-recency--old">
        ${iconLegendOld()}
        <span class="legend-label legend-label--desktop">&gt; 365 days</span>
        <span class="legend-label legend-label--mobile">&gt;365d</span>
      </span>
    </div>
  `;

  const details = document.createElement("details");
  details.className = "subcategory-accordion";

  const summary = document.createElement("summary");
  summary.className = "subcategory-accordion__summary";
  const summaryPrefix = document.createElement("span");
  summaryPrefix.className = "subcategory-accordion__prefix";
  summaryPrefix.textContent = "Subcategory: ";
  const summaryValue = document.createElement("span");
  summaryValue.className = "subcategory-accordion__value";
  summary.append(summaryPrefix, summaryValue);

  const subInner = document.createElement("div");
  subInner.className = "legend-row legend-row--sub legend-row--sub-filters";
  subInner.setAttribute("role", "group");
  subInner.setAttribute("aria-label", "Subcategory filter");
  subInner.appendChild(
    createSubcategoryFilterButton("all", "All", iconCategoryTab("all", "All")),
  );
  for (const { sub: sid, label } of SUB_LEGEND_ROWS) {
    subInner.appendChild(createSubcategoryFilterButton(sid, label, iconSubcategory(sid, label)));
  }

  details.append(summary, subInner);

  function syncSubcategoryActive() {
    for (const btn of subInner.querySelectorAll("button[data-sub]")) {
      const id = btn.getAttribute("data-sub");
      const active = id === subcategoryFilter;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    }
    summaryValue.textContent = subcategorySummaryLabel(subcategoryFilter);
  }

  const mq = window.matchMedia(MOBILE_MQ);
  mq.addEventListener("change", () => syncAccordionLayout(details));

  wrap.append(rec, details);
  container.appendChild(wrap);
  syncAccordionLayout(details);
  subscribe(syncSubcategoryActive);
  syncSubcategoryActive();
}
