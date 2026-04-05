import { Client, Filter, PublicKey, Kind } from "@rust-nostr/nostr-sdk";

import { getConfig } from "./config.js";
import { parseBookmarkATag, parseKind30078 } from "./parse.js";
import {
  setInitialRelayLoadComplete,
  setLoadingFromRelays,
  setNostrError,
  upsertProject,
} from "./state.js";

const DEV_DUMMY =
  typeof import.meta.env !== "undefined" &&
  import.meta.env.VITE_DEV_DUMMY_DATA === "true";

/** @type {Client | null} */
let client = null;
/** @type {import("@rust-nostr/nostr-sdk").AbortHandle | null} */
let notificationsAbort = null;
/** @type {string} */
let listSubscriptionId = "";
/** @type {string} */
let projectsSubscriptionId = "";
/** @type {(() => void) | null} */
let unsubscribeProjects = null;
/** @type {string[] | null} */
let activeProjectDTags = null;
let eoseGraceTimer = 0;

function clearGraceTimer() {
  if (eoseGraceTimer) {
    clearTimeout(eoseGraceTimer);
    eoseGraceTimer = 0;
  }
}

/**
 * @param {import("@rust-nostr/nostr-sdk").Tags} tags
 * @returns {string[][]}
 */
function tagsAsStringArrays(tags) {
  return tags.asVec().map((t) => t.asVec());
}

/**
 * Convert nostr-sdk-js Event to plain JS object for parse.js compatibility.
 * @param {import("@rust-nostr/nostr-sdk").Event} event
 * @returns {{kind: number, tags: string[][], content: string, created_at: number}}
 */
function toPlainEvent(event) {
  return {
    kind: event.kind.asU16(),
    tags: tagsAsStringArrays(event.tags),
    content: event.content,
    created_at: event.createdAt.asSecs(),
  };
}

/**
 * @param {ReturnType<typeof getConfig>} cfg
 */
function scheduleInitialComplete(cfg) {
  clearGraceTimer();
  eoseGraceTimer = window.setTimeout(() => {
    setLoadingFromRelays(false);
    setInitialRelayLoadComplete(true);
    eoseGraceTimer = 0;
  }, cfg.eoseGraceMs);
}

async function tearDownProjectsSubscription() {
  activeProjectDTags = null;
  if (!client || !projectsSubscriptionId) return;
  const id = projectsSubscriptionId;
  projectsSubscriptionId = "";
  try {
    await client.unsubscribe(id);
  } catch (err) {
    console.warn("Failed to unsubscribe projects subscription:", err);
  }
}

/**
 * @param {string[]} dTags
 * @param {string} lurkerPk
 * @param {import("@rust-nostr/nostr-sdk").Client} cl
 * @param {ReturnType<typeof getConfig>} cfg
 */
async function subscribeProjects(dTags, lurkerPk, cl, cfg) {
  unsubscribeProjects = null;
  await tearDownProjectsSubscription();

  if (!dTags.length) {
    scheduleInitialComplete(cfg);
    return;
  }

  const uniqueD = [...new Set(dTags)];

  try {
    const filter = new Filter()
      .author(PublicKey.parse(lurkerPk))
      .kind(new Kind(30078));

    const sub = await cl.subscribe(filter);

    projectsSubscriptionId = sub.id;
    activeProjectDTags = uniqueD;

    unsubscribeProjects = () => {
      void tearDownProjectsSubscription();
    };

    scheduleInitialComplete(cfg);
  } catch (err) {
    console.error("Failed to subscribe to projects:", err);
    setNostrError("Failed to subscribe to project events.");
    scheduleInitialComplete(cfg);
  }
}

/**
 * @param {import("@rust-nostr/nostr-sdk").Event} ev
 * @param {string} lurkerPk
 * @returns {string[]}
 */
function dTagsFromListEvent(ev, lurkerPk) {
  /** @type {string[]} */
  const out = [];
  const rows = tagsAsStringArrays(ev.tags);
  for (const t of rows) {
    if (t[0] === "a" && t[1]) {
      const parsed = parseBookmarkATag(t[1], lurkerPk);
      if (parsed) out.push(parsed.d);
    }
  }
  return out;
}

/**
 * @param {import("@rust-nostr/nostr-sdk").Event} event
 * @param {string} lurkerPk
 * @param {string[]} uniqueD
 */
function handleProjectEvent(event, lurkerPk, uniqueD) {
  const tags = tagsAsStringArrays(event.tags);
  const dTag = tags.find((t) => t[0] === "d");
  if (!dTag || !dTag[1]) return;

  const dValue = dTag[1].toLowerCase();
  if (!uniqueD.includes(dValue)) return;

  const plainEvent = toPlainEvent(event);
  const p = parseKind30078(plainEvent);
  if (p) upsertProject(p);
}

export async function startNostrClient() {
  const cfg = getConfig();
  setNostrError("");
  setLoadingFromRelays(true);
  setInitialRelayLoadComplete(false);
  clearGraceTimer();

  if (DEV_DUMMY) {
    const { getDevDummyProjects } = await import("./devDummyProjects.js");
    for (const p of getDevDummyProjects()) {
      upsertProject(p);
    }
    setNostrError("");
    setLoadingFromRelays(false);
    setInitialRelayLoadComplete(true);
    return;
  }

  if (!cfg.lurkerPubkeyHex || cfg.lurkerPubkeyHex.length !== 64) {
    setNostrError(
      "Set VITE_GITLURKER_PUBKEY (64-char hex) in your Vite env to load projects.",
    );
    setLoadingFromRelays(false);
    setInitialRelayLoadComplete(true);
    return;
  }

  if (!cfg.relays.length) {
    setNostrError(
      "No relays configured. Set VITE_NOSTR_RELAYS or VITE_NOSTR_USE_PUBLIC_RELAYS=true.",
    );
    setLoadingFromRelays(false);
    setInitialRelayLoadComplete(true);
    return;
  }

  await stopNostrClient();

  try {
    client = new Client();

    for (const relayUrl of cfg.relays) {
      try {
        await client.addRelay(relayUrl);
      } catch (err) {
        console.warn(`Failed to add relay ${relayUrl}:`, err);
      }
    }

    await client.connect();

    const lurkerPk = cfg.lurkerPubkeyHex;

    listSubscriptionId = "";
    projectsSubscriptionId = "";
    activeProjectDTags = null;

    notificationsAbort = client.handleNotifications({
      handleEvent: async (relayUrl, subscriptionId, event) => {
        try {
          if (subscriptionId === listSubscriptionId) {
            if (event.kind.asU16() === 10003) {
              const dTags = dTagsFromListEvent(event, lurkerPk);
              if (dTags.length > 0 && client) {
                await subscribeProjects(dTags, lurkerPk, client, getConfig());
              }
            }
            return false;
          }

          if (subscriptionId === projectsSubscriptionId) {
            if (event.kind.asU16() === 30078 && activeProjectDTags) {
              handleProjectEvent(event, lurkerPk, activeProjectDTags);
            }
            return false;
          }
        } catch (err) {
          console.error("Nostr notification handler error:", err);
        }
        return false;
      },
      handleMsg: async () => false,
    });

    const listFilter = new Filter()
      .author(PublicKey.parse(lurkerPk))
      .kind(new Kind(10003));

    const listOut = await client.subscribe(listFilter);
    listSubscriptionId = listOut.id;

    scheduleInitialComplete(cfg);
  } catch (err) {
    console.error("Failed to start Nostr client:", err);
    setNostrError("Failed to connect to Nostr relays.");
    setLoadingFromRelays(false);
    setInitialRelayLoadComplete(true);
  }
}

export async function stopNostrClient() {
  clearGraceTimer();
  if (notificationsAbort) {
    try {
      notificationsAbort.abort();
    } catch (err) {
      console.warn("Error aborting notifications:", err);
    }
    notificationsAbort = null;
  }
  if (unsubscribeProjects) {
    unsubscribeProjects();
    unsubscribeProjects = null;
  }
  await tearDownProjectsSubscription();
  if (client && listSubscriptionId) {
    try {
      await client.unsubscribe(listSubscriptionId);
    } catch (err) {
      console.warn("Error unsubscribing list:", err);
    }
    listSubscriptionId = "";
  }
  if (client) {
    try {
      await client.disconnect();
    } catch (err) {
      console.warn("Error disconnecting client:", err);
    }
    client = null;
  }
}

export async function initNostr() {
  await startNostrClient();
}
