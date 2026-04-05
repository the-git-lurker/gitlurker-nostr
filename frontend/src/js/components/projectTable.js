import {
  iconRecencyMark,
  iconRecencyMarkEmpty,
  iconStaleTombstone,
  iconSubcategory,
  iconTypePair,
  subcategoryTitle,
} from "../icons.js";
import { escapeHtml } from "../utils.js";

/**
 * @param {import('../parse.js').ParsedProject} p
 */
function activityLabel(p) {
  if (p.tracking_mode === "release") {
    if (p.release_version) return p.release_version;
    return "Latest commit";
  }
  if (p.tracking_mode === "tag") {
    if (p.tag_name) return p.tag_name;
    return "Latest commit";
  }
  const sha = p.commit_sha || "";
  if (sha.length > 7) return sha.slice(0, 7);
  if (sha) return sha;
  return "Latest commit";
}

/**
 * @param {import('../parse.js').ParsedProject} p
 */
function activityDateIso(p) {
  if (p.tracking_mode === "release") {
    if (p.release_date_iso) return p.release_date_iso;
    return p.commit_date_iso || "";
  }
  if (p.tracking_mode === "tag") {
    if (p.tag_date_iso) return p.tag_date_iso;
    return p.commit_date_iso || "";
  }
  return p.commit_date_iso || "";
}

/**
 * Row recency: ≤7d, ≤14d, >365d (ignored when row is stale).
 * @param {import('../parse.js').ParsedProject} p
 */
function recencyHint(p) {
  const iso = activityDateIso(p);
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const days = (Date.now() - t) / (86400 * 1000);
  if (days <= 7) return "recent";
  if (days <= 14) return "two-week";
  if (days > 365) return "old";
  return "";
}

const RECENCY_TITLES = {
  recent: "≤ 7 days since activity",
  "two-week": "≤ 14 days since activity",
  old: "> 365 days since activity (inactive)",
};

/**
 * @param {import('../parse.js').ParsedProject[]} projects
 * @param {(path: string) => void} navigate
 * @param {string} categoryFilter from category tabs (`all`, `bitcoin`, …)
 */
export function renderProjectTable(container, projects, navigate, categoryFilter = "all") {
  const sorted = [...projects].sort((a, b) => {
    const da = activityDateIso(a);
    const db = activityDateIso(b);
    return db.localeCompare(da);
  });

  container.innerHTML = "";
  const table = document.createElement("table");
  table.className = "project-table";
  const thead = document.createElement("thead");
  thead.innerHTML =
    "<tr><th>Type</th><th>REPOSITORY</th><th>Owner</th><th>Version</th><th>Updated</th><th class=\"recency-col-head\"><span class=\"sr-only\">Activity</span></th></tr>";
  table.appendChild(thead);
  const tbody = document.createElement("tbody");

  const showFullType = categoryFilter === "all";

  for (const p of sorted) {
    const tr = document.createElement("tr");
    if (p.stale) tr.classList.add("is-stale");

    const sub = (p.subcategory || "other").toLowerCase();
    const cat = (p.category || "other").toLowerCase();

    const typeCell = document.createElement("td");
    typeCell.className = "type-cell";
    const typeInner = document.createElement("div");
    typeInner.className = "type-cell-inner";
    if (showFullType) {
      typeInner.innerHTML = iconTypePair(cat, sub);
    } else {
      const subLabel = subcategoryTitle(sub);
      typeInner.innerHTML = `<span class="type-icons">${iconSubcategory(sub, subLabel)}<span class="sr-only">${escapeHtml(subLabel)}</span></span>`;
    }
    typeCell.appendChild(typeInner);

    const repoCell = document.createElement("td");
    if (p.stale) {
      const sR = document.createElement("span");
      sR.className = "cell-text-plain";
      sR.textContent = p.repo;
      repoCell.appendChild(sR);
    } else {
      const aR = document.createElement("a");
      aR.href = `/${encodeURIComponent(p.owner)}/${encodeURIComponent(p.repo)}`;
      aR.dataset.spa = "1";
      aR.textContent = p.repo;
      repoCell.appendChild(aR);
    }

    const ownerCell = document.createElement("td");
    if (p.stale) {
      const sO = document.createElement("span");
      sO.className = "cell-text-plain";
      sO.textContent = p.owner;
      ownerCell.appendChild(sO);
    } else {
      const aO = document.createElement("a");
      aO.href = `/${encodeURIComponent(p.owner)}`;
      aO.dataset.spa = "1";
      aO.textContent = p.owner;
      ownerCell.appendChild(aO);
    }

    const verCell = document.createElement("td");
    if (p.stale) {
      const sV = document.createElement("span");
      sV.className = "cell-text-plain";
      sV.textContent = activityLabel(p);
      verCell.appendChild(sV);
    } else {
      const aV = document.createElement("a");
      aV.href = `/${encodeURIComponent(p.owner)}/${encodeURIComponent(p.repo)}/release`;
      aV.dataset.spa = "1";
      aV.textContent = activityLabel(p);
      verCell.appendChild(aV);
    }

    const dateCell = document.createElement("td");
    dateCell.textContent = activityDateIso(p) || "—";

    const recCell = document.createElement("td");
    if (p.stale) {
      recCell.className = "recency-cell recency-cell--stale";
      recCell.innerHTML = iconStaleTombstone();
    } else {
      const hint = recencyHint(p);
      recCell.className = hint
        ? `recency-cell recency-cell--${hint}`
        : "recency-cell recency-cell--none";
      recCell.innerHTML = hint
        ? iconRecencyMark(
            /** @type {'recent'|'two-week'|'old'} */ (hint),
            RECENCY_TITLES[/** @type {'recent'|'two-week'|'old'} */ (hint)],
          )
        : iconRecencyMarkEmpty();
    }

    tr.append(typeCell, repoCell, ownerCell, verCell, dateCell, recCell);
    tbody.appendChild(tr);
  }

  table.appendChild(tbody);
  container.appendChild(table);

  container.querySelectorAll("a[data-spa]").forEach((el) => {
    el.addEventListener("click", (ev) => {
      ev.preventDefault();
      const href = el.getAttribute("href");
      if (href) navigate(href);
    });
  });
}
