import { iconForks, iconIssues, iconStars } from "../icons.js";
import { updatePageMeta } from "../meta.js";
import { escapeHtml } from "../utils.js";

/** @param {HTMLElement} mainEl @param {string} owner @param {string} repo @param {(path: string) => void} navigate */
export async function renderRepo(mainEl, owner, repo, navigate) {
  mainEl.innerHTML = "<p class=\"muted\">Loading...</p>";
  const path = `/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`;
  updatePageMeta({
    title: `${owner}/${repo}`,
    description: `Repository ${owner}/${repo} on GitLurker`,
    path,
  });

  let data;
  try {
    const r = await fetch(
      `/api/v1/repo/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`,
    );
    if (!r.ok) {
      mainEl.innerHTML = `<p class="banner banner-error">Could not load repo (${r.status}).</p>`;
      return;
    }
    data = await r.json();
  } catch {
    mainEl.innerHTML = `<p class="banner banner-error">Network error.</p>`;
    return;
  }

  const desc = data.description
    ? `<p>${escapeHtml(data.description)}</p>`
    : "<p class=\"muted\">No description.</p>";

  const contribs = (data.contributors || [])
    .map((c) => {
      const av = (c.avatar_url || "").trim();
      const img = av
        ? `<img class="contributor-avatar" src="${escapeHtml(av)}" alt="" width="48" height="48" loading="lazy" />`
        : `<div class="contributor-avatar contributor-avatar--placeholder" aria-hidden="true"></div>`;
      return `<li class="contributor-card">
        <a class="contributor-link" href="${escapeHtml(c.html_url)}" target="_blank" rel="noopener" title="${escapeHtml(c.login)}">
          ${img}
          <span class="contributor-login">${escapeHtml(c.login)}</span>
          <span class="contributor-count">${c.contributions} commits</span>
        </a>
      </li>`;
    })
    .join("");

  const gh = escapeHtml(data.github_url || `https://github.com/${owner}/${repo}`);

  mainEl.innerHTML = `
    <article class="detail-page">
      <header class="detail-page__header">
        <h1>${escapeHtml(owner)}/${escapeHtml(repo)}</h1>
        <a data-spa class="btn btn-ghost" href="/">Back to list</a>
      </header>
      <ul class="repo-stats" aria-label="Repository statistics">
        <li>${iconStars()} <strong>${data.stars}</strong> <span class="muted">stars</span></li>
        <li>${iconForks()} <strong>${data.forks}</strong> <span class="muted">forks</span></li>
        <li>${iconIssues()} <strong>${data.issues}</strong> <span class="muted">open issues</span></li>
      </ul>
      <p class="detail-actions">
        <a data-spa class="btn btn-ghost" href="/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/release">Release / activity</a>
        <a class="btn btn-github" href="${gh}" target="_blank" rel="noopener">Open on GitHub</a>
      </p>
      ${desc}
      <h2>Contributors</h2>
      <p class="muted contributors-note">Only the top 50 contributors are listed when a project has more.</p>
      <ul class="contributor-grid">${contribs || "<li class=\"muted\">No contributor data returned.</li>"}</ul>
    </article>`;

  mainEl.querySelectorAll("a[data-spa]").forEach((el) => {
    el.addEventListener("click", (ev) => {
      ev.preventDefault();
      const href = el.getAttribute("href");
      if (href) navigate(href);
    });
  });
}
