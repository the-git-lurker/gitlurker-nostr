/**
 * Pure project list filters (used by home view and unit tests).
 * @param {import('./parse.js').ParsedProject[]} projects
 */
export function filterProjectsByCategory(projects, categoryFilter) {
  if (categoryFilter === "all") return projects;
  return projects.filter(
    (p) => p.category.toLowerCase() === categoryFilter,
  );
}

/**
 * @param {import('./parse.js').ParsedProject[]} projects
 */
export function filterProjectsBySubcategory(projects, subcategoryFilter) {
  if (subcategoryFilter === "all") return projects;
  return projects.filter(
    (p) => (p.subcategory || "other").toLowerCase() === subcategoryFilter,
  );
}

/**
 * @param {import('./parse.js').ParsedProject[]} projects
 */
export function filterProjectsBySearch(projects, searchQuery) {
  const q = searchQuery.trim().toLowerCase();
  if (!q) return projects;
  return projects.filter((p) => {
    const sub = (p.subcategory || "").toLowerCase();
    return (
      p.owner.toLowerCase().includes(q) ||
      p.repo.toLowerCase().includes(q) ||
      sub.includes(q)
    );
  });
}
