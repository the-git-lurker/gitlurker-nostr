import {
  SUB_LEGEND_ROWS,
  iconLegendInfo,
  iconLegendOld,
  iconLegendRecent,
  iconLegendTwoWeeks,
  iconSubcategory,
} from "../icons.js";

/** @param {HTMLElement} container */
export function mountHomeLegends(container) {
  const wrap = document.createElement("div");
  wrap.className = "home-legends";

  const rec = document.createElement("div");
  rec.className = "legend-row legend-row--recency";
  rec.setAttribute("aria-label", "Activity recency legend");
  rec.innerHTML = `
    <span class="legend-recency-title">${iconLegendInfo()} <span class="legend-label">Latest activity (UTC)</span></span>
    <div class="legend-recency-icons" role="group" aria-label="Recency indicators">
      <span class="legend-item legend-recency legend-recency--recent">${iconLegendRecent()} <span class="legend-label">≤ 7 days</span></span>
      <span class="legend-item legend-recency legend-recency--two-week">${iconLegendTwoWeeks()} <span class="legend-label">≤ 14 days</span></span>
      <span class="legend-item legend-recency legend-recency--old">${iconLegendOld()} <span class="legend-label">&gt; 365 days</span></span>
    </div>
  `;

  const sub = document.createElement("div");
  sub.className = "legend-row legend-row--sub";
  sub.setAttribute("aria-label", "Subcategory legend");
  const parts = SUB_LEGEND_ROWS.map(
    ({ sub: sid, label }) =>
      `<span class="legend-item legend-sub legend-sub--${escapeLegendClass(sid)}">${iconSubcategory(sid, label)} <span class="legend-label">${label}</span></span>`,
  );
  sub.innerHTML = parts.join("");

  wrap.append(rec, sub);
  container.appendChild(wrap);
}

/** @param {string} sid */
function escapeLegendClass(sid) {
  return sid.replace(/[^a-z0-9_-]/gi, "-");
}
