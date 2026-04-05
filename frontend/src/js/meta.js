import { getConfig } from "./config.js";

const OG_IDS = {
  title: "meta-og-title",
  desc: "meta-og-desc",
  url: "meta-og-url",
  twTitle: "meta-tw-title",
  twDesc: "meta-tw-desc",
};

function setMetaByName(name, content) {
  const el = document.querySelector(`meta[name="${name}"]`);
  if (el) el.setAttribute("content", content);
}

function setMetaByProperty(prop, content) {
  const el = document.querySelector(`meta[property="${prop}"]`);
  if (el) el.setAttribute("content", content);
}

/**
 * @param {{ title?: string, description?: string, path?: string }} p
 */
export function updatePageMeta(p) {
  const cfg = getConfig();
  const title = p.title
    ? `${p.title} - ${cfg.siteTitle}`
    : cfg.siteTitle;
  const description = p.description || cfg.siteDescription;
  const path = p.path ?? window.location.pathname;
  const url = `${cfg.siteUrl || window.location.origin}${path}`;

  document.title = title;

  setMetaByName("description", description);
  setMetaByProperty("og:title", title);
  setMetaByProperty("og:description", description);
  setMetaByProperty("og:url", url);
  setMetaByName("twitter:title", title);
  setMetaByName("twitter:description", description);

  const ogImg = `${cfg.siteUrl || window.location.origin}/og-image.png`;
  setMetaByProperty("og:image", ogImg);
  setMetaByName("twitter:image", ogImg);

  const t = document.getElementById(OG_IDS.title);
  if (t) t.setAttribute("content", title);
  const d = document.getElementById(OG_IDS.desc);
  if (d) d.setAttribute("content", description);
  const u = document.getElementById(OG_IDS.url);
  if (u) u.setAttribute("content", url);
  const tt = document.getElementById(OG_IDS.twTitle);
  if (tt) tt.setAttribute("content", title);
  const td = document.getElementById(OG_IDS.twDesc);
  if (td) td.setAttribute("content", description);

  const ld = document.getElementById("jsonld-placeholder");
  if (ld) {
    ld.textContent = JSON.stringify({
      "@context": "https://schema.org",
      "@type": "WebSite",
      name: cfg.siteTitle,
      description,
      url: cfg.siteUrl || window.location.origin,
    });
  }
}

export function resetMetaHome() {
  updatePageMeta({});
}
