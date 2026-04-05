export const THEME_STORAGE_KEY = "gitlurker-theme";

/**
 * @param {string | null} saved
 * @param {boolean} prefersDark
 */
export function resolveInitialTheme(saved, prefersDark) {
  if (saved === "dark" || saved === "light") return saved;
  return prefersDark ? "dark" : "light";
}

export function initTheme() {
  let saved = null;
  try {
    saved = localStorage.getItem(THEME_STORAGE_KEY);
  } catch {
    saved = null;
  }
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const initial = resolveInitialTheme(saved, prefersDark);
  document.documentElement.setAttribute("data-theme", initial);
  return initial;
}

/** @param {HTMLElement} container */
export function mountThemeToggle(container) {
  initTheme();
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "btn theme-toggle";
  btn.setAttribute("aria-label", "Toggle color theme");

  function label() {
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    btn.textContent = dark ? "Light" : "Dark";
  }

  label();
  btn.addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme");
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
    label();
  });

  container.appendChild(btn);
}
