/** @param {HTMLElement} container @param {number} rows */
export function showTableSkeleton(container, rows = 8) {
  container.innerHTML = "";
  const table = document.createElement("table");
  table.className = "project-table skeleton-table";
  table.dataset.testid = "loading-skeleton";
  const thead = document.createElement("thead");
  thead.innerHTML =
    "<tr><th>Type</th><th>REPOSITORY</th><th>Owner</th><th>Version</th><th>Updated</th><th><span class=\"sr-only\">Activity</span></th></tr>";
  table.appendChild(thead);
  const tbody = document.createElement("tbody");
  for (let i = 0; i < rows; i++) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td><span class="sk sk-icon"></span><span class="sk sk-text"></span></td><td><span class="sk sk-text sk-wide"></span></td><td><span class="sk sk-text"></span></td><td><span class="sk sk-text"></span></td><td><span class="sk sk-text"></span></td><td><span class="sk sk-icon"></span></td>`;
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  container.appendChild(table);
}
