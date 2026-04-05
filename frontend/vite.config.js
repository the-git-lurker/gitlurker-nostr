import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import dotenv from "dotenv";
import { defineConfig } from "vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** Load repo-root `.env.dev` so Vite sees the same file as the backend (plus VITE_*). */
function loadRootEnvDev() {
  const candidates = [
    path.resolve(__dirname, "../.env.dev"),
    path.resolve(__dirname, "../../.env.dev"),
  ];
  for (const p of candidates) {
    if (!fs.existsSync(p)) continue;
    dotenv.config({ path: p, override: false });
    return p;
  }
  return null;
}

loadRootEnvDev();

/** Base URL for FastAPI during `npm run dev` (Vite proxies `/api` and `/.well-known` here). */
function devApiOrigin() {
  const raw = String(
    process.env.GITLURKER_DEV_API_ORIGIN ||
      process.env.VITE_DEV_API_ORIGIN ||
      "",
  ).trim();
  if (raw) return raw.replace(/\/$/, "");
  return "http://127.0.0.1:8000";
}

/**
 * Derive public key from hex secret key using nostr-sdk-js.
 * Note: This requires WASM to be loaded, so we do it lazily.
 * @param {string} hex64 - 64 character hex secret key
 * @returns {Promise<string>} - Hex public key or empty string on error
 */
async function hexSecretToPubkeyHex(hex64) {
  try {
    const s = hex64.trim().toLowerCase();
    if (!/^[0-9a-f]{64}$/.test(s)) return "";

    // Dynamic import to handle WASM loading
    const { Keys, loadWasmAsync } = await import("@rust-nostr/nostr-sdk");
    await loadWasmAsync();

    // Create secret key from hex and get keys
    const keys = Keys.parse(s);
    return keys.publicKey.toHex().toLowerCase();
  } catch (err) {
    console.warn("Failed to derive pubkey from secret:", err.message);
    return "";
  }
}

// Handle async pubkey derivation
async function setupEnv() {
  const lurkerKey = process.env.LURKER_KEY;
  if (lurkerKey && !String(process.env.VITE_GITLURKER_PUBKEY || "").trim()) {
    const pk = await hexSecretToPubkeyHex(lurkerKey);
    if (pk) process.env.VITE_GITLURKER_PUBKEY = pk;
  }
}

// Copy relay and reviewer settings
const nostrRelays = String(process.env.NOSTR_RELAYS || "").trim();
if (nostrRelays && !String(process.env.VITE_NOSTR_RELAYS || "").trim()) {
  process.env.VITE_NOSTR_RELAYS = nostrRelays;
}

const reviewers = String(process.env.GITLURKER_REVIEWER_PUBKEYS || "").trim();
if (reviewers && !String(process.env.VITE_NOSTR_REVIEWER_PUBKEYS || "").trim()) {
  process.env.VITE_NOSTR_REVIEWER_PUBKEYS = reviewers;
}

// Export config after async setup
export default defineConfig(async () => {
  // Wait for pubkey derivation if needed
  await setupEnv();

  const apiOrigin = devApiOrigin();
  console.info(`[vite] GitLurker API proxy target: ${apiOrigin}`);

  return {
    root: path.resolve(__dirname, "src"),
    publicDir: path.resolve(__dirname, "public"),
    build: {
      outDir: path.resolve(__dirname, "dist"),
      emptyOutDir: true,
    },
    server: {
      proxy: {
        "/api": {
          target: apiOrigin,
          changeOrigin: true,
        },
        "/.well-known": {
          target: apiOrigin,
          changeOrigin: true,
        },
      },
    },
    // nostr-sdk-js is wasm-bindgen output as CommonJS (`module.exports.*`). Excluding it from
    // pre-bundling made Vite serve the raw file to the browser, where `import { Filter }` fails
    // (no ESM named exports). Let esbuild pre-bundle and synthesize ESM interop.
    optimizeDeps: {
      include: ["@rust-nostr/nostr-sdk"],
    },
  };
});
