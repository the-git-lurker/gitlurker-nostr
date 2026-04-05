import { escapeHtml } from "../utils.js";
import { updatePageMeta } from "../meta.js";

/** @param {string} iso */
function formatPushedAt(iso) {
  if (!iso || !String(iso).trim()) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  return new Date(t).toISOString().slice(0, 10);
}

/** @param {HTMLElement} mainEl @param {string} owner @param {(path: string) => void} navigate */
export async function renderOwner(mainEl, owner, navigate) {
  mainEl.innerHTML = "<p class=\"muted\">Loading...</p>";
  updatePageMeta({ title: owner, description: `Repositories for ${owner}`, path: `/${owner}` });

  let data;
  try {
    const r = await fetch(`/api/v1/owner/${encodeURIComponent(owner)}`);
    if (!r.ok) {
      mainEl.innerHTML = `<p class="banner banner-error">Could not load owner (${r.status}).</p>`;
      return;
    }
    data = await r.json();
  } catch {
    mainEl.innerHTML = `<p class="banner banner-error">Network error.</p>`;
    return;
  }

  const gh = escapeHtml(data.github_url || `https://github.com/${owner}`);
  const escOwner = escapeHtml(owner);

  const reposSorted = [...(data.repos || [])].sort((a, b) => {
    const da = a.pushed_at_iso || "";
    const db = b.pushed_at_iso || "";
    return db.localeCompare(da);
  });

  const repoRows = reposSorted
    .map((rep) => {
      const href = `/${encodeURIComponent(owner)}/${encodeURIComponent(rep.name)}`;
      const descRaw = rep.description;
      const desc =
        descRaw && String(descRaw).trim()
          ? escapeHtml(String(descRaw))
          : "<span class=\"muted\">No description</span>";
      const pushed = formatPushedAt(rep.pushed_at_iso || "");
      return `<tr>
        <td><a data-spa href="${href}">${escapeHtml(rep.full_name || rep.name)}</a></td>
        <td>${desc}</td>
        <td>${escapeHtml(pushed)}</td>
      </tr>`;
    })
    .join("");

  const members = (data.members || [])
    .map((m) => {
      const av = (m.avatar_url || "").trim();
      const img = av
        ? `<img class="contributor-avatar" src="${escapeHtml(av)}" alt="" width="48" height="48" loading="lazy" />`
        : `<div class="contributor-avatar contributor-avatar--placeholder" aria-hidden="true"></div>`;
      return `<li class="contributor-card">
        <a class="contributor-link" href="${escapeHtml(m.html_url)}" target="_blank" rel="noopener" title="${escapeHtml(m.login)}">
          ${img}
          <span class="contributor-login">${escapeHtml(m.login)}</span>
          <span class="contributor-count">Member</span>
        </a>
      </li>`;
    })
    .join("");

  const teams = (data.teams || [])
    .map((t) => {
      const desc = t.description && String(t.description).trim();
      const subtitle = desc ? escapeHtml(String(desc)) : "Team";
      const name = escapeHtml(t.name || t.slug || "Team");
      const url = escapeHtml(t.html_url || "#");
      return `<li class="contributor-card">
        <a class="contributor-link" href="${url}" target="_blank" rel="noopener">
          <div class="contributor-avatar contributor-avatar--placeholder" aria-hidden="true"></div>
          <span class="contributor-login">${name}</span>
          <span class="contributor-count">${subtitle}</span>
        </a>
      </li>`;
    })
    .join("");

  mainEl.innerHTML = `
    <article class="detail-page">
      <header class="detail-page__header">
        <h1>${escOwner}</h1>
        <a data-spa class="btn btn-ghost" href="/">Back to list</a>
      </header>
      <p class="detail-actions"><a class="btn btn-github" href="${gh}" target="_blank" rel="noopener">View on GitHub</a></p>
      <h2>Repositories</h2>
      <div class="table-host">
        <table class="project-table owner-repos-table">
          <thead><tr><th>Name</th><th>Description</th><th>Last updated</th></tr></thead>
          <tbody>${repoRows || "<tr><td colspan=\"3\" class=\"muted\">None returned.</td></tr>"}</tbody>
        </table>
      </div>
      <h2>Teams</h2>
      <ul class="contributor-grid">${teams || "<li class=\"muted\">No teams (user account or insufficient API access).</li>"}</ul>
      <h2>Public members</h2>
      <ul class="contributor-grid">${members || "<li class=\"muted\">None (user account or private).</li>"}</ul>
    </article>`;

  mainEl.querySelectorAll("a[data-spa]").forEach((el) => {
    el.addEventListener("click", (ev) => {
      ev.preventDefault();
      const href = el.getAttribute("href");
      if (href) navigate(href);
    });
  });
}
