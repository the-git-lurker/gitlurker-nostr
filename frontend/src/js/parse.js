/**
 * Parse Kind 30078 GitLurker project events (tags mirror backend `nostr.py`).
 * @typedef {object} ParsedProject
 * @property {string} owner
 * @property {string} repo
 * @property {string} name
 * @property {string} description
 * @property {string} category
 * @property {string} subcategory
 * @property {'release'|'tag'|'commit'} tracking_mode
 * @property {string} web
 * @property {string} clone
 * @property {string | null} release_version
 * @property {string | null} release_date_iso
 * @property {string | null} tag_name
 * @property {string | null} tag_date_iso
 * @property {string | null} commit_sha
 * @property {string | null} commit_date_iso
 * @property {string | null} commit_author
 * @property {number} stars
 * @property {number} forks
 * @property {number} open_issues
 * @property {boolean} stale
 * @property {number} _created_at
 */

const CATEGORIES = new Set([
  "bitcoin",
  "layer2",
  "ecash",
  "nostr",
  "ai",
  "other",
]);
const SUBCATEGORIES = new Set([
  "client",
  "development",
  "exchange",
  "interface",
  "node",
  "wallet",
  "server",
  "payments",
  "protocol",
  "relay",
  "signer",
  "agent",
  "model",
  "mcp",
  "skills",
  "other",
]);

function indexTags(tags) {
  /** @type {Map<string, string[]>} */
  const m = new Map();
  for (const t of tags || []) {
    if (!t || !t.length) continue;
    const k = t[0];
    if (!m.has(k)) m.set(k, []);
    m.get(k).push(...t.slice(1));
  }
  return m;
}

function one(m, key) {
  const xs = m.get(key);
  return xs && xs.length ? xs[0] : "";
}

/**
 * @param {import('nostr-tools').Event} event
 * @returns {ParsedProject | null}
 */
export function parseKind30078(event) {
  if (event.kind !== 30078) return null;
  const tags = indexTags(event.tags);

  let owner = one(tags, "owner");
  let repo = "";
  const dvals = tags.get("d");
  if (dvals && dvals[0] && dvals[0].includes("/")) {
    const i = dvals[0].indexOf("/");
    owner = owner || dvals[0].slice(0, i).trim();
    repo = dvals[0].slice(i + 1).trim();
  }

  let meta = {};
  try {
    meta = JSON.parse(event.content || "{}");
  } catch {
    meta = {};
  }
  if (meta && typeof meta === "object") {
    owner = owner || String(meta.owner || "").trim();
    repo = repo || String(meta.repo || "").trim();
  }

  if (!owner || !repo) return null;

  let subcategory = (tags.get("t") && tags.get("t")[0]) || "other";
  subcategory = String(subcategory).toLowerCase();
  if (!SUBCATEGORIES.has(subcategory)) subcategory = "other";

  let category = one(tags, "category").toLowerCase() || "other";
  if (!CATEGORIES.has(category)) category = "other";

  let mode = one(tags, "mode").toLowerCase() || "release";
  if (!["release", "tag", "commit"].includes(mode)) mode = "release";

  const name = one(tags, "name") || repo;
  const descVals = tags.get("description");
  const description = descVals && descVals.length ? descVals[0] : "";

  const web =
    one(tags, "web") || `https://github.com/${owner}/${repo}`;
  const clone =
    one(tags, "clone") || `https://github.com/${owner}/${repo}.git`;

  const stars = parseInt(one(tags, "stars") || "0", 10) || 0;
  const forks = parseInt(one(tags, "forks") || "0", 10) || 0;
  const open_issues = parseInt(one(tags, "open_issues") || "0", 10) || 0;

  const staleRaw = tags.get("stale");
  const stale =
    !!staleRaw &&
    staleRaw.length > 0 &&
    ["1", "true", "yes"].includes(String(staleRaw[0]).toLowerCase());

  const release_version = one(tags, "release") || null;
  const rd = tags.get("release_date");
  const release_date_iso = rd && rd[0] ? rd[0] : null;

  const tag_name = one(tags, "tag") || null;
  const tgd = tags.get("tag_date");
  const tag_date_iso = tgd && tgd[0] ? tgd[0] : null;

  const commit_sha = one(tags, "commit") || null;
  const cdd = tags.get("commit_date");
  const commit_date_iso = cdd && cdd[0] ? cdd[0] : null;
  const commit_author = one(tags, "commit_author") || null;

  return {
    owner,
    repo,
    name,
    description,
    category,
    subcategory,
    tracking_mode: /** @type {'release'|'tag'|'commit'} */ (mode),
    web,
    clone,
    release_version,
    release_date_iso,
    tag_name,
    tag_date_iso,
    commit_sha,
    commit_date_iso,
    commit_author,
    stars,
    forks,
    open_issues,
    stale,
    _created_at: event.created_at,
  };
}

/**
 * @param {string} aValue `a` tag value: kind:hexpubkey:d-identifier
 * @param {string} expectedAuthorHex
 * @returns {{ d: string } | null}
 */
export function parseBookmarkATag(aValue, expectedAuthorHex) {
  const m = /^(\d+):([0-9a-f]{64}):(.*)$/i.exec(aValue.trim());
  if (!m) return null;
  const kind = Number(m[1], 10);
  const pk = m[2].toLowerCase();
  const d = m[3];
  if (kind !== 30078 || pk !== expectedAuthorHex.toLowerCase()) return null;
  if (!d || !d.includes("/")) return null;
  return { d: d.toLowerCase() };
}
