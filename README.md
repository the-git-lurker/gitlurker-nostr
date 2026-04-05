# GitLurker

**Author:** [RydalWater](https://github.com/RydalWater)

GitLurker indexes open-source Bitcoin, Lightning, e-cash, Nostr, and related repositories, refreshes metadata from GitHub, and publishes a curated list on [Nostr](https://nostr.com/) (Kind **30078** per project, Kind **10003** bookmark list). This repo is the FastAPI backend plus a Vite/React SPA.

## Disclaimer

**GitLurker does not endorse any repository or project** that appears in the seed data, on the site, or in relay events. Listings are for discovery only. **Review source code, licenses, and trust assumptions yourself** before installing or running third-party software. The maintainers are not responsible for downstream use of linked projects.

## Requirements

- Python 3.12+, [uv](https://docs.astral.sh/uv/)
- Node.js (LTS) for the frontend
- A GitHub personal access token for live API data (optional in some dev modes)

## Quick start

1. Copy **`.env.example`** to **`.env.dev`** at the repo root (`gitlurker/.env.dev` from this folder’s parent layout — see [`docs/DEV_ENVIRONMENT.md`](docs/DEV_ENVIRONMENT.md)).
2. Set **`AUTH_TOKEN`** (GitHub) and, for publishing, **`LURKER_KEY`** and **`NOSTR_RELAYS`**. Keep **`NOSTR_PUBLISH_ENABLED=false`** until you intend to write to relays.

**Backend** (from `gitlurker/backend`):

```bash
uv sync
uv run uvicorn gitlurker.main:app --reload --host 127.0.0.1 --port 8080
```

**Frontend** (from `gitlurker/frontend`):

```bash
npm install
npm run dev
```

If the API is not on port 8000, set **`GITLURKER_DEV_API_ORIGIN`** (e.g. `http://127.0.0.1:8080`).

## Tests and lint

From **`gitlurker/backend`**:

```bash
uv run pytest
uv run ruff check --fix .
uv run ruff format .
```

From **`gitlurker/frontend`**:

```bash
npm run test
```

## Seed script

Canonical list: **`backend/fixtures/seed_projects.json`** (Django-style `git_lurker.project` rows). From `gitlurker/backend`:

```bash
uv run python -m gitlurker.scripts.seed
uv run python -m gitlurker.scripts.seed --no-github
uv run python -m gitlurker.scripts.seed --publish
```

Default is **dry-run** (no relay I/O). With **`--publish`**, you need **`NOSTR_PUBLISH_ENABLED=true`**, **`LURKER_KEY`**, and relays configured.

If any project is **stale** (e.g. missing on GitHub) and you do **not** pass **`--include-stale`**, the script writes **`backend/fixtures/stale_seed.json`** containing only those rows (same JSON shape as the seed file) so you can review or merge changes back into **`seed_projects.json`**. See the module docstring in [`backend/src/gitlurker/scripts/seed.py`](backend/src/gitlurker/scripts/seed.py).

## Example Nostr event shapes

Values are illustrative; real events are signed and use your pubkey and timestamps.

**Kind 30078** (project metadata) — `content` is compact JSON; tags carry the same fields for clients that scan tags:

```json
{
  "kind": 30078,
  "content": "{\"owner\":\"bitcoin\",\"repo\":\"bitcoin\",\"name\":\"bitcoin\",\"category\":\"bitcoin\",\"subcategory\":\"node\",\"tracking_mode\":\"release\"}",
  "tags": [
    ["d", "bitcoin/bitcoin"],
    ["name", "bitcoin"],
    ["description", "Bitcoin Core integration/staging tree"],
    ["owner", "bitcoin"],
    ["category", "bitcoin"],
    ["t", "node"],
    ["stars", "40000"],
    ["forks", "20000"],
    ["open_issues", "500"],
    ["web", "https://github.com/bitcoin/bitcoin"],
    ["clone", "https://github.com/bitcoin/bitcoin.git"],
    ["release", "v28.0"],
    ["release_date", "2024-10-01"],
    ["mode", "release"]
  ]
}
```

**Kind 10003** (bookmark list) — `a` tags reference each Kind 30078 replaceable coordinate (`<kind>:<pubkey>:<d-tag>`):

```json
{
  "kind": 10003,
  "content": "",
  "tags": [
    ["a", "30078:<hex_pubkey>:bitcoin/bitcoin", "wss://relay.example.com"],
    ["a", "30078:<hex_pubkey>:cashubtc/cashu", "wss://relay.example.com"]
  ]
}
```

Tag naming matches [`backend/src/gitlurker/services/nostr.py`](backend/src/gitlurker/services/nostr.py) (`build_kind30078_builder`, `build_kind10003_builder`).

## Environment reference

Single template: **`.env.example`** (backend + optional **`VITE_*`** keys for the SPA). Details: [`docs/DEV_ENVIRONMENT.md`](docs/DEV_ENVIRONMENT.md).
