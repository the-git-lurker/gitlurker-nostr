import {
  Client,
  EventBuilder,
  Keys,
  NostrSigner,
  BrowserSigner,
  Kind,
  PublicKey,
  Tag,
} from "@rust-nostr/nostr-sdk";

import { getConfig } from "./config.js";
import { isValidOwnerRepo, truncate } from "./utils.js";

const SESSION_KEY = "gitlurker-session-pubkey";

export function loadSessionPubkey() {
  try {
    const v = sessionStorage.getItem(SESSION_KEY);
    return v ? v.toLowerCase() : null;
  } catch {
    return null;
  }
}

export function saveSessionPubkey(hex) {
  try {
    if (hex) sessionStorage.setItem(SESSION_KEY, hex.toLowerCase());
    else sessionStorage.removeItem(SESSION_KEY);
  } catch {
    /* ignore */
  }
}

export async function authWithNip07() {
  const w = window;
  if (!w.nostr?.getPublicKey) {
    throw new Error("No NIP-07 signer (install Alby, nos2x, etc.).");
  }
  const pk = await w.nostr.getPublicKey();
  return pk.toLowerCase();
}

/**
 * Derive pubkey from pasted nsec. Secret is not persisted.
 * @param {string} nsecInput
 */
export function deriveFromNsec(nsecInput) {
  const trimmed = nsecInput.trim();
  if (!trimmed.startsWith("nsec1")) {
    throw new Error("Expected an nsec1 bech32 key.");
  }

  try {
    // Parse the nsec key using nostr-sdk-js
    const keys = Keys.parse(trimmed);
    const pubkeyHex = keys.publicKey.toHex().toLowerCase();
    const secretKey = keys.secretKey;

    return { pubkeyHex, secretKey, keys };
  } catch (err) {
    throw new Error(`Failed to parse nsec key: ${err.message}`);
  }
}

const CATEGORIES = [
  "bitcoin",
  "layer2",
  "ecash",
  "nostr",
  "ai",
  "other",
];
const SUBCATEGORIES = [
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
];

/**
 * @param {object} fields
 * @param {string} fields.owner
 * @param {string} fields.repo
 * @param {string} fields.category
 * @param {string} fields.subcategory
 * @param {string} fields.reason
 */
export function buildProjectRequestPayload(fields) {
  const owner = truncate(fields.owner, 100);
  const repo = truncate(fields.repo, 100);
  const reason = truncate(fields.reason, 2000);
  const category = String(fields.category || "").toLowerCase();
  const subcategory = String(fields.subcategory || "").toLowerCase();

  if (!isValidOwnerRepo(owner) || !isValidOwnerRepo(repo)) {
    throw new Error("Owner and repo must match [A-Za-z0-9_.-]+");
  }
  if (!CATEGORIES.includes(category)) throw new Error("Invalid category.");
  if (!SUBCATEGORIES.includes(subcategory)) {
    throw new Error("Invalid subcategory.");
  }
  if (!reason.length) throw new Error("Please add a short reason.");

  const body = {
    v: 1,
    type: "project_request",
    owner,
    repo,
    category,
    subcategory,
    reason,
  };
  const text = `GitLurker project request: ${owner}/${repo}\n${reason}\n\n${JSON.stringify(body)}`;
  return { text, body };
}

/**
 * Build Kind 1 event using nostr-sdk-js EventBuilder.
 * @param {object} opts
 * @param {string} opts.content
 * @param {string[][]} opts.tags
 * @param {Keys | null} opts.keys - Keys for signing (null uses NIP-07)
 * @returns {Promise<import("@rust-nostr/nostr-sdk").Event>}
 */
async function buildAndSignKind1(opts) {
  const kind = new Kind(1);
  const builder = new EventBuilder(kind, opts.content);

  // Convert plain tag arrays to Tag objects
  if (opts.tags && opts.tags.length > 0) {
    const tagObjects = opts.tags
      .map((t) => {
        try {
          return Tag.parse(t);
        } catch {
          return null;
        }
      })
      .filter(Boolean);
    builder.tags(tagObjects);
  }

  if (opts.keys) {
    // Sign with keys directly
    return builder.signWithKeys(opts.keys);
  } else {
    // Use NIP-07 via window.nostr
    const w = window;
    if (!w.nostr?.signEvent) {
      throw new Error("NIP-07 signEvent not available.");
    }

    // Build unsigned event (we need to get the unsigned event from builder)
    // Since we can't easily extract the unsigned event, we'll use window.nostr
    // to sign a plain object and then create the Event
    const unsigned = {
      kind: 1,
      created_at: Math.floor(Date.now() / 1000),
      tags: opts.tags,
      content: opts.content,
    };

    const signed = await w.nostr.signEvent(unsigned);

    // Parse the signed event into nostr-sdk-js Event
    // The signed event from NIP-07 has: id, pubkey, created_at, kind, tags, content, sig
    const eventJson = JSON.stringify(signed);
    const { Event } = await import("@rust-nostr/nostr-sdk");
    return Event.fromJson(eventJson);
  }
}

/**
 * @param {object} fields owner, repo, category, subcategory, reason
 * @param {{ keys: Keys | null }} signer null keys uses NIP-07
 */
export async function submitProjectRequest(fields, signer) {
  const cfg = getConfig();
  if (!cfg.lurkerPubkeyHex) {
    throw new Error("VITE_GITLURKER_PUBKEY is required to tag the GitLurker relay key.");
  }

  const { text } = buildProjectRequestPayload(fields);

  /** @type {string[][]} */
  const tags = [["p", cfg.lurkerPubkeyHex]];
  for (const r of cfg.reviewerPubkeys) {
    if (r && r.length === 64) tags.push(["p", r]);
  }

  const signedEvent = await buildAndSignKind1({
    content: text,
    tags,
    keys: signer.keys,
  });

  // Create a temporary client to publish the event
  const client = new Client();

  try {
    // Add all relays
    for (const relayUrl of cfg.relays) {
      try {
        await client.addRelay(relayUrl);
      } catch (err) {
        console.warn(`Failed to add relay ${relayUrl}:`, err);
      }
    }

    // Connect and send event
    await client.connect();
    await client.sendEvent(signedEvent);
  } finally {
    try {
      await client.disconnect();
    } catch {
      /* ignore disconnect errors */
    }
  }

  return signedEvent;
}
