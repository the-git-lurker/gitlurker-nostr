/** In-memory app state + pub/sub for views. */

const listeners = new Set();

/** @type {Map<string, import('./parse.js').ParsedProject>} */
const projects = new Map();

export let categoryFilter = "all";
export let searchQuery = "";
export let loadingFromRelays = true;
export let initialRelayLoadComplete = false;
/** @type {string | null} */
export let authPubkeyHex = null;
export let nostrError = "";

function projectKey(owner, repo) {
  return `${owner.trim().toLowerCase()}/${repo.trim().toLowerCase()}`;
}

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function notify() {
  listeners.forEach((fn) => {
    try {
      fn();
    } catch (e) {
      console.error(e);
    }
  });
}

/**
 * @param {import('./parse.js').ParsedProject} p
 */
export function upsertProject(p) {
  const key = projectKey(p.owner, p.repo);
  const prev = projects.get(key);
  if (prev && prev._created_at > p._created_at) return;
  projects.set(key, p);
  notify();
}

export function getProjects() {
  return Array.from(projects.values());
}

export function setCategoryFilter(cat) {
  categoryFilter = cat;
  notify();
}

export function setSearchQuery(q) {
  searchQuery = q;
  notify();
}

export function setLoadingFromRelays(v) {
  loadingFromRelays = v;
  notify();
}

export function setInitialRelayLoadComplete(v) {
  initialRelayLoadComplete = v;
  notify();
}

export function setNostrError(msg) {
  nostrError = msg;
  notify();
}

export function setAuthPubkey(hex) {
  const next = hex ? hex.toLowerCase() : null;
  if (next === authPubkeyHex) return;
  authPubkeyHex = next;
  notify();
}
