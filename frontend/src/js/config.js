/** Vite env-driven client config (no secrets).
 * Set VITE_DEV_DUMMY_DATA=true to load fixture projects (see devDummyProjects.js) without relays.
 */

const PUBLIC_RELAYS = [
  "wss://relay.damus.io",
  "wss://relay.primal.net",
  "wss://nostr.mom",
];

function parseCommaList(raw) {
  if (!raw || !String(raw).trim()) return [];
  return String(raw)
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function getConfig() {
  const relaysRaw = import.meta.env.VITE_NOSTR_RELAYS || "";
  let relays = parseCommaList(relaysRaw);
  const usePublic = import.meta.env.VITE_NOSTR_USE_PUBLIC_RELAYS === "true";
  if (relays.length === 0 && usePublic) relays = [...PUBLIC_RELAYS];

  const lurkerPubkeyHex = (import.meta.env.VITE_GITLURKER_PUBKEY || "")
    .trim()
    .toLowerCase();
  const reviewerPubkeys = parseCommaList(
    import.meta.env.VITE_NOSTR_REVIEWER_PUBKEYS || "",
  ).map((p) => p.toLowerCase());

  const graceMs = Number(import.meta.env.VITE_NOSTR_EOSE_GRACE_MS || 800);

  return {
    lurkerPubkeyHex,
    relays,
    reviewerPubkeys,
    eoseGraceMs: Number.isFinite(graceMs) ? graceMs : 800,
    siteTitle: "GitLurker",
    siteDescription:
      "Passive index of open-source GitHub activity published on Nostr.",
    siteUrl: typeof window !== "undefined" ? window.location.origin : "",
  };
}
