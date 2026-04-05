/**
 * Bitcoin Design outline icons — SVG strings from `btcOutlineSvgs.generated.js`
 * (sourced from @bitcoin-design/bitcoin-icons-svg, MIT). Regenerate: `node scripts/extract-btc-icons.mjs`.
 */
import { SVG_SNOOZE, SVG_TOMBSTONE } from "./customIcons.js";
import { BTC_OUTLINE_SVGS } from "./btcOutlineSvgs.generated.js";
import { escapeHtml } from "./utils.js";

/** @typedef {{ name: string, svg: string }} BtcIcon */

/** @param {string} key @returns {BtcIcon} */
function entry(key) {
  const svg = BTC_OUTLINE_SVGS[key];
  if (!svg) {
    throw new Error(`Missing BTC outline SVG: ${key}`);
  }
  return { name: key, svg };
}

/** @param {BtcIcon} ic @param {string} className @param {string} title */
function wrapSvg(ic, className, title) {
  const t = title ? ` title="${title.replace(/"/g, "&quot;")}"` : "";
  return `<span class="${className}" aria-hidden="true"${t}>${ic.svg}</span>`;
}

/** @param {string} rawSvg full <svg>…</svg> string @param {string} className @param {string} title */
function wrapRawSvg(rawSvg, className, title) {
  const t = title ? ` title="${title.replace(/"/g, "&quot;")}"` : "";
  return `<span class="${className}" aria-hidden="true"${t}>${rawSvg}</span>`;
}

/** @param {string} title */
export function iconStars(title = "Stars") {
  return wrapSvg(entry("StarIcon"), "bc-icon bc-icon--inline", title);
}

/** @param {string} title */
export function iconForks(title = "Forks") {
  return wrapSvg(entry("ShareIcon"), "bc-icon bc-icon--inline", title);
}

/** @param {string} title */
export function iconIssues(title = "Open issues") {
  return wrapSvg(entry("MessageIcon"), "bc-icon bc-icon--inline", title);
}

/** @type {Record<string, string>} maps subcategory → BTC_OUTLINE_SVGS key */
const SUB_KEYS = {
  client: "DevicesIcon",
  development: "LinuxTerminalIcon",
  exchange: "ExchangeIcon",
  interface: "LinkIcon",
  node: "NodeIcon",
  wallet: "WalletIcon",
  server: "ProxyIcon",
  payments: "CreditCardIcon",
  protocol: "FileIcon",
  relay: "RelayIcon",
  signer: "KeyIcon",
  agent: "MagicWandIcon",
  model: "GraphIcon",
  mcp: "GearIcon",
  skills: "CodeIcon",
  other: "QuestionCircleIcon",
};

/**
 * @param {string} subcategory lower-case key
 * @param {string} title attribute
 */
export function iconSubcategory(subcategory, title) {
  const key = SUB_KEYS[subcategory] || SUB_KEYS.other;
  return wrapSvg(entry(key), "bc-icon bc-icon--sub", title);
}

/** @type {Record<string, string>} */
const CAT_KEYS = {
  bitcoin: "BitcoinIcon",
  layer2: "LightningIcon",
  ecash: "NoDollarsIcon",
  nostr: "MessageIcon",
  ai: "MagicWandIcon",
  other: "QuestionIcon",
};

/**
 * @param {string} category lower-case
 * @param {string} title
 */
export function iconCategory(category, title) {
  const key = CAT_KEYS[category] || CAT_KEYS.other;
  return wrapSvg(entry(key), "bc-icon bc-icon--cat", title);
}

/**
 * Category filter tab: All uses globe; others use category glyph.
 * @param {string} tabId e.g. `all`, `bitcoin`, `layer2`
 * @param {string} title
 */
export function iconCategoryTab(tabId, title) {
  const key = tabId === "all" ? "GlobeIcon" : CAT_KEYS[tabId] || CAT_KEYS.other;
  return wrapSvg(entry(key), "bc-icon bc-icon--tab", title);
}

/** @param {'recent'|'two-week'|'old'} kind */
export function iconRecencyMark(kind, title) {
  if (kind === "old") {
    return wrapRawSvg(
      SVG_SNOOZE,
      "bc-icon bc-icon--recency bc-icon--recency-old",
      title,
    );
  }
  const keys = { recent: "SunIcon", "two-week": "MoonIcon" };
  const k = keys[kind];
  return wrapSvg(
    entry(k),
    `bc-icon bc-icon--recency bc-icon--recency-${kind}`,
    title,
  );
}

/** Stale / unavailable repository (activity column). */
export function iconStaleTombstone(title = "Stale or moved repository") {
  return wrapRawSvg(
    SVG_TOMBSTONE,
    "bc-icon bc-icon--recency bc-icon--recency-stale",
    title,
  );
}

/**
 * Type column when “All” is selected: category icon / subcategory icon.
 * @param {string} category lower-case
 * @param {string} subcategory lower-case
 */
export function iconTypePair(category, subcategory) {
  const cat = (category || "other").toLowerCase();
  const sub = (subcategory || "other").toLowerCase();
  const subLabel = subcategoryTitle(sub);
  const label = `${cat} / ${subLabel}`;
  return `<span class="type-icons" role="img" aria-label="${escapeHtml(label)}">${iconCategory(cat, cat)}<span class="type-icons-sep" aria-hidden="true">/</span>${iconSubcategory(sub, subLabel)}</span>`;
}

/** Placeholder when row has no recency band (matches last column width). */
export function iconRecencyMarkEmpty() {
  return '<span class="recency-cell-empty" aria-hidden="true">—</span>';
}

export function iconLegendRecent() {
  return iconRecencyMark("recent", "≤ 7 days");
}
export function iconLegendTwoWeeks() {
  return iconRecencyMark("two-week", "≤ 14 days");
}
export function iconLegendOld() {
  return iconRecencyMark("old", "> 365 days");
}
export function iconLegendInfo() {
  return wrapSvg(
    entry("InfoCircleIcon"),
    "bc-icon bc-icon--legend bc-icon--legend-info",
    "Latest activity (UTC)",
  );
}

/** @type {Array<{ sub: string, label: string }>} */
export const SUB_LEGEND_ROWS = [
  { sub: "client", label: "Client" },
  { sub: "development", label: "Development" },
  { sub: "exchange", label: "Exchange" },
  { sub: "interface", label: "Interface" },
  { sub: "node", label: "Node" },
  { sub: "wallet", label: "Wallet" },
  { sub: "server", label: "Server" },
  { sub: "payments", label: "Payments" },
  { sub: "protocol", label: "Protocol" },
  { sub: "relay", label: "Relay" },
  { sub: "signer", label: "Signer" },
  { sub: "agent", label: "Agent" },
  { sub: "model", label: "Model" },
  { sub: "mcp", label: "MCP Tools" },
  { sub: "skills", label: "Skills" },
  { sub: "other", label: "Other" },
];

/** Human-readable subcategory label (for UI / a11y). */
export function subcategoryTitle(key) {
  const k = (key || "other").toLowerCase();
  const row = SUB_LEGEND_ROWS.find((r) => r.sub === k);
  return row ? row.label : k;
}
