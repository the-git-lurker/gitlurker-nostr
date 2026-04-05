# Development environment (GitLurker)

All application code under this `gitlurker/` directory. Repo-root `.env.dev` holds local secrets (gitignored).

## Secrets mapping (`.env.dev`)

| Variable in `.env.dev` | Purpose | In code (`gitlurker.config.Settings`) |
|------------------------|---------|--------------------------------------|
| `AUTH_TOKEN` | GitHub PAT | Field `github_token`; alias `GITHUB_TOKEN` also accepted |
| `LURKER_KEY` | Nostr secret key, **hex** (64 chars) | Field `lurker_secret_hex`; alias `GITLURKER_NSEC_HEX` also accepted |

All keys are documented in **`../.env.example`** (single file for backend and browser). Server-side code ignores `VITE_*` keys. At startup, call **`load_gitlurker_dotenv()`** so dotenv files are applied to `os.environ` before **`get_settings()`**. For the SPA, copy the `VITE_*` section from that file into **`frontend/.env.local`**.

Never commit `.env.dev`. If it was ever exposed, **rotate** the GitHub token and consider rotating the Nostr key.

## Nostr: local-first while building

**Goal:** avoid publishing or depending on the public network during day-to-day dev and CI.

1. **Run a local relay** (developer machine only; not shipped with production):

   Example using [strfry](https://github.com/hoytech/strfry) (image/name may vary — adjust to your install):

   ```bash
   # Example only — verify upstream docs for current image and ports
   docker run --rm -p 7777:7777 ghcr.io/hoytech/strfry:latest
   ```

   Point the app at `ws://127.0.0.1:7777` (or whatever port your relay uses).

2. **Guardrails in config:**

   - `NOSTR_PUBLISH_ENABLED=false` — backend must not `EVENT` to relays when false.
   - `RELAYS` / `NOSTR_RELAYS` — in dev, only `ws://127.0.0.1:…` entries.

3. **Public relay smoke tests** — optional, manual or tagged tests:

   Set relays to:

   - `wss://relay.damus.io`
   - `wss://relay.primal.net`
   - `wss://nostr.mom`

   Enable only when you intentionally test connectivity (separate env file or flag such as `NOSTR_USE_PUBLIC_RELAYS=true`). Still keep `NOSTR_PUBLISH_ENABLED=false` until you explicitly allow publishing.

## EOSE grace timeout (faster UI)

For multi-relay subscriptions:

1. Track `EOSE` per relay per subscription id.
2. When **any** relay sends `EOSE` for that subscription, start a **grace timer** (recommended **500–1500 ms**).
3. When the timer fires:
   - Mark the initial load complete for UX (e.g. clear “loading”, resolve `waitForInitialResults`).
4. **Do not** tear down the subscription unless product requires it — late relays may still send events; merge into state.

This avoids waiting for the slowest relay on first paint while keeping correctness for stragglers.

## GitHub API

- Uses `AUTH_TOKEN` from `.env.dev` as the Bearer token.
- Respect rate limits (pre design requirements).
