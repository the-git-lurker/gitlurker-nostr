import { mountCategoryTabs } from "../components/categoryTabs.js";
import { mountHomeLegends } from "../components/homeLegends.js";
import { showTableSkeleton } from "../components/loadingSkeleton.js";
import { renderProjectTable } from "../components/projectTable.js";
import { mountSearchBar } from "../components/searchBar.js";
import {
  filterProjectsByCategory,
  filterProjectsBySearch,
} from "../filters.js";
import { resetMetaHome } from "../meta.js";
import {
  categoryFilter,
  getProjects,
  initialRelayLoadComplete,
  loadingFromRelays,
  nostrError,
  searchQuery,
  subscribe,
} from "../state.js";

/** @param {(path: string) => void} navigate */
export function renderHome(mainEl, navigate) {
  resetMetaHome();
  mainEl.innerHTML = "";
  const err = document.createElement("p");
  err.className = "banner banner-error hidden";
  mainEl.appendChild(err);

  const controls = document.createElement("div");
  controls.className = "home-controls";
  mountCategoryTabs(controls);
  mountSearchBar(controls);
  mainEl.appendChild(controls);

  const legendHost = document.createElement("div");
  mountHomeLegends(legendHost);
  mainEl.appendChild(legendHost);

  const tableHost = document.createElement("div");
  tableHost.className = "table-host";
  mainEl.appendChild(tableHost);

  function paint() {
    err.textContent = nostrError;
    err.classList.toggle("hidden", !nostrError);

    if (loadingFromRelays && !initialRelayLoadComplete) {
      showTableSkeleton(tableHost, 10);
      return;
    }

    const all = filterProjectsBySearch(
      filterProjectsByCategory(getProjects(), categoryFilter),
      searchQuery,
    );
    if (!all.length) {
      tableHost.innerHTML = "";
      const p = document.createElement("p");
      p.className = "muted empty-hint";
      p.textContent = nostrError
        ? nostrError
        : "No projects match your filters, or nothing has loaded from relays yet.";
      tableHost.appendChild(p);
      return;
    }
    renderProjectTable(tableHost, all, navigate, categoryFilter);
  }

  subscribe(paint);
  paint();
}

