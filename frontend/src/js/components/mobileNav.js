import { mountThemeToggle } from "./themeToggle.js";

const DRAWER_ID = "mobile-nav-drawer";
const BTN_ID = "nav-menu-btn";

/** Sync open state on the menu button and drawer. */
function setDrawerOpen(open) {
  const btn = document.getElementById(BTN_ID);
  const drawer = document.getElementById(DRAWER_ID);
  if (!btn || !drawer) return;
  btn.setAttribute("aria-expanded", open ? "true" : "false");
  btn.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  drawer.classList.toggle("is-open", open);
  drawer.hidden = !open;
  document.body.classList.toggle("mobile-nav-open", open);
}

/** Close drawer (no-op if elements missing). */
export function closeMobileNav() {
  setDrawerOpen(false);
}

/** Wire hamburger, drawer links, backdrop, and Escape. */
export function mountMobileNav() {
  const btn = document.getElementById(BTN_ID);
  const drawer = document.getElementById(DRAWER_ID);
  const backdrop = drawer?.querySelector(".mobile-nav-backdrop");
  const themeSlot = document.getElementById("theme-slot-drawer");
  if (!btn || !drawer) return;

  if (themeSlot) mountThemeToggle(themeSlot);

  btn.addEventListener("click", () => {
    const open = btn.getAttribute("aria-expanded") !== "true";
    setDrawerOpen(open);
  });

  backdrop?.addEventListener("click", () => closeMobileNav());

  drawer.querySelectorAll("a[data-spa]").forEach((el) => {
    el.addEventListener("click", () => closeMobileNav());
  });

  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && drawer.classList.contains("is-open")) {
      closeMobileNav();
      btn.focus();
    }
  });
}
