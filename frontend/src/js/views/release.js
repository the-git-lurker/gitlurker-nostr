import DOMPurify from "dompurify";

import { updatePageMeta } from "../meta.js";
import { escapeHtml } from "../utils.js";

/** @param {HTMLElement} mainEl @param {string} owner @param {string} repo @param {(path: string) => void} navigate */
export async function renderRelease(mainEl, owner, repo, navigate) {
  mainEl.innerHTML = "<p class=\"muted\">Loading...</p>";
  const path = `/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/release`;
  updatePageMeta({
    title: `${owner}/${repo} release`,
    description: `Release notes for ${owner}/${repo}`,
    path,
  });

  let data;
  try {
    const r = await fetch(
      `/api/v1/release/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`,
    );
    if (!r.ok) {
      mainEl.innerHTML = `<p class="banner banner-error">Could not load release (${r.status}).</p>`;
      return;
    }
    data = await r.json();
  } catch {
    mainEl.innerHTML = `<p class="banner banner-error">Network error.</p>`;
    return;
  }

  const notes = data.notes_html
    ? `<div class="release-notes">${DOMPurify.sanitize(data.notes_html)}</div>`
    : "<p class=\"muted\">No release notes or README available.</p>";

  const gh = escapeHtml(data.github_url || `https://github.com/${owner}/${repo}`);
  const shaShort = data.commit_sha_short ? String(data.commit_sha_short).trim() : "";
  const metaParts = [data.date ? escapeHtml(data.date) : ""];
  if (shaShort) metaParts.push(escapeHtml(shaShort));
  if (data.publisher) metaParts.push(escapeHtml(data.publisher));
  const metaLine = metaParts.filter(Boolean).join(" · ");

  mainEl.innerHTML = `
    <article class="detail-page">
      <header class="detail-page__header">
        <div>
          <nav class="crumb"><a data-spa href="/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}">${escapeHtml(owner)}/${escapeHtml(repo)}</a> / release</nav>
          <h1>${escapeHtml(data.version || "—")}</h1>
        </div>
        <a data-spa class="btn btn-ghost" href="/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}">Back to repository</a>
      </header>
      <p class="muted">${metaLine}</p>
      <p class="detail-actions"><a class="btn btn-github" href="${gh}" target="_blank" rel="noopener">Open on GitHub</a></p>
      ${notes}
    </article>`;

  mainEl.querySelectorAll("a[data-spa]").forEach((el) => {
    el.addEventListener("click", (ev) => {
      ev.preventDefault();
      const href = el.getAttribute("href");
      if (href) navigate(href);
    });
  });
}
