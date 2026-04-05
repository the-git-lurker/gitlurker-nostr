import { loadWasmAsync } from "@rust-nostr/nostr-sdk";

import { mountThemeToggle, initTheme } from "./components/themeToggle.js";
import { updatePageMeta } from "./meta.js";
import { initNostr } from "./nostr.js";
import { renderAbout } from "./views/about.js";
import { renderHome } from "./views/home.js";
import { renderOwner } from "./views/owner.js";
import { renderRepo } from "./views/repo.js";
import { renderRelease } from "./views/release.js";

/**
 * @param {string} pathname
 */
function parsePath(pathname) {
  const raw = pathname.endsWith("/") && pathname.length > 1 ? pathname.slice(0, -1) : pathname;
  const p = raw || "/";
  if (p === "/") return { name: "home" };
  if (p === "/about") return { name: "about" };
  const parts = p.split("/").filter(Boolean);
  if (parts.length === 1) {
    return { name: "owner", owner: decodeURIComponent(parts[0]) };
  }
  if (parts.length === 2) {
    return {
      name: "repo",
      owner: decodeURIComponent(parts[0]),
      repo: decodeURIComponent(parts[1]),
    };
  }
  if (parts.length === 3 && parts[2] === "release") {
    return {
      name: "release",
      owner: decodeURIComponent(parts[0]),
      repo: decodeURIComponent(parts[1]),
    };
  }
  return { name: "404" };
}

/** @param {string} path */
export function navigate(path) {
  let next = path;
  if (!next.startsWith("/")) next = `/${next}`;
  const url = new URL(next, window.location.origin);
  if (url.origin !== window.location.origin) {
    window.location.href = path;
    return;
  }
  window.history.pushState({}, "", url.pathname);
  handleRoute();
}

function handleRoute() {
  const mainEl = document.getElementById("main-outlet");
  if (!mainEl) return;

  const route = parsePath(window.location.pathname);

  if (route.name === "home") {
    renderHome(mainEl, navigate);
    return;
  }
  if (route.name === "about") {
    renderAbout(mainEl);
    return;
  }
  if (route.name === "owner") {
    void renderOwner(mainEl, route.owner, navigate);
    return;
  }
  if (route.name === "repo") {
    void renderRepo(mainEl, route.owner, route.repo, navigate);
    return;
  }
  if (route.name === "release") {
    void renderRelease(mainEl, route.owner, route.repo, navigate);
    return;
  }

  mainEl.innerHTML =
    "<article class=\"detail-page\"><h1>Not found</h1><p><a data-spa href=\"/\">Home</a></p></article>";
  updatePageMeta({ title: "Not found", path: window.location.pathname });
  mainEl.querySelector("a[data-spa]")?.addEventListener("click", (ev) => {
    ev.preventDefault();
    navigate("/");
  });
}

function bindGlobalNav() {
  document.body.addEventListener("click", (ev) => {
    const t = ev.target;
    if (!(t instanceof Element)) return;
    const a = t.closest("a[data-spa]");
    if (!a || !(a instanceof HTMLAnchorElement)) return;
    const href = a.getAttribute("href");
    if (!href || href.startsWith("http")) return;
    ev.preventDefault();
    navigate(href);
  });
}

/**
 * Initialize the application after WASM loads
 */
async function main() {
  try {
    // Load WASM before any nostr-sdk-js operations
    await loadWasmAsync();
  } catch (err) {
    console.error("Failed to load WebAssembly module:", err);
    const mainEl = document.getElementById("main-outlet");
    if (mainEl) {
      mainEl.innerHTML = `
        <article class="detail-page">
          <h1>Browser Not Supported</h1>
          <p>GitLurker requires WebAssembly support. Please use a modern browser.</p>
          <p><a data-spa href="/">Try again</a></p>
        </article>
      `;
    }
    return;
  }

  initTheme();
  const themeSlot = document.getElementById("theme-slot");
  if (themeSlot) mountThemeToggle(themeSlot);

  bindGlobalNav();
  window.addEventListener("popstate", handleRoute);

  // Render the current route before Nostr init so the home view can show loading
  // UI (skeleton) using default relay state. If initNostr runs first, the no-pubkey
  // and similar fast paths can set initialRelayLoadComplete before the first paint.
  handleRoute();
  if (typeof window !== "undefined") {
    window.__GITLURKER_APP_BOOTSTRAPPED__ = true;
  }
  // Defer past the next frame so the skeleton row is painted before sync nostr fast paths run.
  requestAnimationFrame(() => {
    void initNostr();
  });
}

main();
