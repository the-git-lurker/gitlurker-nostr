import {
  authWithNip07,
  deriveFromNsec,
  loadSessionPubkey,
  saveSessionPubkey,
  submitProjectRequest,
} from "../auth.js";
import { getConfig } from "../config.js";
import { SUB_LEGEND_ROWS } from "../icons.js";
import { updatePageMeta } from "../meta.js";

const CATEGORIES = [
  ["bitcoin", "Bitcoin"],
  ["layer2", "Layer 2"],
  ["ecash", "e-Cash"],
  ["nostr", "Nostr"],
  ["ai", "AI"],
  ["other", "Other"],
];

/** @param {HTMLElement} mainEl */
export function renderAbout(mainEl) {
  updatePageMeta({
    title: "About",
    description: "About GitLurker",
    path: "/about",
  });

  mainEl.innerHTML = `
    <article class="detail-page about-page">
      <h1>About GitLurker</h1>
      <p>GitLurker passively watches open-source GitHub activity and publishes a project index on <strong>Nostr</strong> (Kind 30078 + 10003). This site reads relays directly; the API adds GitHub detail for owner and repository pages.</p>
      <p class="muted">No endorsement of third-party trademarks. Data may be incomplete or delayed.</p>

      <h2>Contact</h2>
      <p>Operators coordinate via configured Nostr identities. For user-facing requests, use the form below once signed in.</p>

      <section class="donation-placeholder card" aria-labelledby="don-h">
        <h2 id="don-h">Support (coming soon)</h2>
        <p>Lightning, Cashu, and on-chain options will be added here later. There are no payment widgets yet; this section is a placeholder only.</p>
      </section>

      <section class="card auth-section" id="auth-section">
        <h2>Sign in (Nostr)</h2>
        <p class="muted">Your pubkey is kept in <code>sessionStorage</code> only. Nsec is never stored; paste it only for this session.</p>
        <p id="auth-status" class="auth-status"></p>
        <div class="auth-actions">
          <button type="button" class="btn" id="btn-nip07">Use browser extension (NIP-07)</button>
        </div>
        <div class="nsec-row">
          <label for="nsec-in">Or paste nsec (session only)</label>
          <input type="password" id="nsec-in" class="search-input" autocomplete="off" placeholder="nsec1..." />
          <button type="button" class="btn" id="btn-nsec">Derive pubkey</button>
        </div>
        <button type="button" class="btn btn-ghost hidden" id="btn-signout">Sign out</button>
      </section>

      <section class="card request-section hidden" id="request-section">
        <h2>Request a project</h2>
        <p class="muted">Publishes a Kind 1 note tagging the GitLurker key and configured reviewer pubkeys. Reviewers act on their own workflow.</p>
        <form id="req-form" class="stack-form">
          <label>Owner <input name="owner" required class="search-input" pattern="[A-Za-z0-9_.-]+" /></label>
          <label>Repo <input name="repo" required class="search-input" pattern="[A-Za-z0-9_.-]+" /></label>
          <label>Category <select name="category" id="req-cat" required></select></label>
          <label>Subcategory <select name="subcategory" id="req-sub" required></select></label>
          <label>Reason <textarea name="reason" required rows="4" class="search-input"></textarea></label>
          <button type="submit" class="btn">Submit request</button>
        </form>
        <p id="req-msg" class="banner hidden" role="status"></p>
      </section>
    </article>`;

  const catSel = mainEl.querySelector("#req-cat");
  const subSel = mainEl.querySelector("#req-sub");
  if (catSel) {
    for (const [v, label] of CATEGORIES) {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = label;
      catSel.appendChild(o);
    }
  }
  if (subSel) {
    for (const { sub, label } of SUB_LEGEND_ROWS) {
      const o = document.createElement("option");
      o.value = sub;
      o.textContent = label;
      subSel.appendChild(o);
    }
  }

  const statusEl = mainEl.querySelector("#auth-status");
  const reqSection = mainEl.querySelector("#request-section");
  const btnSignout = mainEl.querySelector("#btn-signout");

  function syncAuthUi() {
    const pk = loadSessionPubkey();
    if (statusEl) {
      statusEl.textContent = pk
        ? `Signed in: ${pk.slice(0, 12)}...${pk.slice(-8)}`
        : "Not signed in.";
    }
    if (reqSection) reqSection.classList.toggle("hidden", !pk);
    if (btnSignout) btnSignout.classList.toggle("hidden", !pk);
  }

  syncAuthUi();

  mainEl.querySelector("#btn-nip07")?.addEventListener("click", async () => {
    try {
      const pk = await authWithNip07();
      saveSessionPubkey(pk);
      syncAuthUi();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  });

  /** @type {Uint8Array | null} */
  let sessionSecret = null;

  mainEl.querySelector("#btn-nsec")?.addEventListener("click", () => {
    const raw = mainEl.querySelector("#nsec-in")?.value || "";
    try {
      const { pubkeyHex, secretKey } = deriveFromNsec(raw);
      sessionSecret = secretKey;
      saveSessionPubkey(pubkeyHex);
      syncAuthUi();
      (mainEl.querySelector("#nsec-in")).value = "";
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  });

  mainEl.querySelector("#btn-signout")?.addEventListener("click", () => {
    sessionSecret = null;
    saveSessionPubkey("");
    syncAuthUi();
  });

  const cfg = getConfig();
  if (!cfg.lurkerPubkeyHex) {
    const warn = document.createElement("p");
    warn.className = "banner banner-error";
    warn.textContent =
      "VITE_GITLURKER_PUBKEY is not set; project requests cannot tag the app key.";
    mainEl.querySelector("#request-section")?.prepend(warn);
  }

  mainEl.querySelector("#req-form")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    if (!(form instanceof HTMLFormElement)) return;
    const fd = new FormData(form);
    const msg = mainEl.querySelector("#req-msg");
    if (msg) {
      msg.classList.add("hidden");
      msg.textContent = "";
    }
    const fields = {
      owner: String(fd.get("owner") || ""),
      repo: String(fd.get("repo") || ""),
      category: String(fd.get("category") || ""),
      subcategory: String(fd.get("subcategory") || ""),
      reason: String(fd.get("reason") || ""),
    };
    try {
      const hasNip07 = typeof window !== "undefined" && window.nostr?.signEvent;
      const sk = sessionSecret;
      if (!sk && !hasNip07) {
        throw new Error("Use NIP-07 or derive from nsec first.");
      }
      await submitProjectRequest(fields, { secretKey: sk });
      if (msg) {
        msg.textContent = "Request published to relays.";
        msg.className = "banner banner-ok";
        msg.classList.remove("hidden");
      }
      form.reset();
    } catch (e) {
      if (msg) {
        msg.textContent = e instanceof Error ? e.message : String(e);
        msg.className = "banner banner-error";
        msg.classList.remove("hidden");
      }
    }
  });
}
