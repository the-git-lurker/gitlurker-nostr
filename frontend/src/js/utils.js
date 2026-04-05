/** @param {string} s */
export function escapeHtml(s) {
  if (s == null) return "";
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

/** @param {string} s */
export function sanitizeSlug(s) {
  return String(s || "")
    .trim()
    .slice(0, 200)
    .replace(/[^\w./-]/g, "");
}

const OWNER_REPO_RE = /^[A-Za-z0-9_.-]+$/;

export function isValidOwnerRepo(s) {
  return OWNER_REPO_RE.test(s);
}

/** @param {string} s @param {number} max */
export function truncate(s, max) {
  const t = String(s || "").trim();
  return t.length <= max ? t : `${t.slice(0, max - 1)}...`;
}
