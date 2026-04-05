"""FastAPI application: API, NIP-05, optional static SPA, lifespan (Nostr + scheduler)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.staticfiles import StaticFiles

from gitlurker.api.routes import build_api_v1_router, build_limiter, well_known
from gitlurker.config import Settings, get_settings, load_gitlurker_dotenv
from gitlurker.services.github import GitHubService
from gitlurker.services.nostr import NostrService
from gitlurker.services.scheduler import RefreshScheduler, SchedulerBudget

logger = logging.getLogger(__name__)

# backend/src/gitlurker/main.py → parents[3] = gitlurker/ (implementation root)
_FRONTEND_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"


def create_app(
    *,
    enable_background: bool = True,
    settings: Settings | None = None,
    github_api: GitHubService | None = None,
    nostr_service: NostrService | None = None,
) -> FastAPI:
    load_gitlurker_dotenv()
    s = settings or get_settings()
    limiter = build_limiter()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = s
        gh_api = github_api or GitHubService(s.github_token)
        app.state.github = gh_api
        nostr = nostr_service or NostrService(s)
        app.state.nostr = nostr
        await nostr.start()
        if nostr.public_key is not None:
            app.state.lurker_pubkey_hex = nostr.public_key.to_hex()
        else:
            app.state.lurker_pubkey_hex = None

        sched_task: asyncio.Task[None] | None = None
        gh_sched: GitHubService | None = None
        if enable_background and s.github_token.strip() and nostr.public_key is not None:
            budget = SchedulerBudget(s.github_scheduler_budget_per_hour)
            gh_sched = GitHubService(s.github_token, on_request=budget.record_request)
            scheduler = RefreshScheduler(s, gh_sched, nostr, budget)
            sched_task = asyncio.create_task(scheduler.run_forever())
            logger.info("Background refresh scheduler started")
        elif enable_background and not s.github_token.strip():
            logger.warning("Scheduler disabled: no GitHub token")
        elif enable_background and nostr.public_key is None:
            logger.warning("Scheduler disabled: Nostr client has no public key")

        yield

        if sched_task is not None:
            sched_task.cancel()
            try:
                await sched_task
            except asyncio.CancelledError:
                pass
        await nostr.stop()
        await gh_api.aclose()
        if gh_sched is not None:
            await gh_sched.aclose()

    app = FastAPI(title="GitLurker", lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    api_v1 = build_api_v1_router(s, limiter)
    app.include_router(api_v1)
    app.include_router(well_known)

    if s.app_environment == "production" and _FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="spa")
    else:

        @app.get("/", response_class=PlainTextResponse)
        async def root() -> str:
            return "GitLurker"

    return app


app = create_app()

__all__ = ["app", "create_app"]
