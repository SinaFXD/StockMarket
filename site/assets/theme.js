// Light / dark switch in the header of every page. The choice is kept in this browser ("ptm.theme"); without one the
// site follows the device setting. A small script in each page's <head> applies the saved choice before the page
// paints, so there is no flash. Charts use CSS colours, so they follow without redrawing.

const KEY = "ptm.theme";
const root = document.documentElement;
const dark = window.matchMedia("(prefers-color-scheme: dark)");

const current = () => root.dataset.theme || (dark.matches ? "dark" : "light");

const ICONS = {
  // shown when the page is light: a moon (switch to dark)
  light: '<path d="M14.5 10.6A6.5 6.5 0 0 1 7.4 3.5a6.5 6.5 0 1 0 7.1 7.1Z" fill="currentColor"/>',
  // shown when the page is dark: a sun (switch to light)
  dark:
    '<circle cx="9" cy="9" r="3.4" fill="currentColor"/><g stroke="currentColor" stroke-width="1.6" stroke-linecap="round">' +
    '<path d="M9 1.5v1.8M9 14.7v1.8M1.5 9h1.8M14.7 9h1.8M3.7 3.7l1.3 1.3M13 13l1.3 1.3M3.7 14.3 5 13M13 5l1.3-1.3"/></g>',
};

function paint(button) {
  const mode = current();
  const next = mode === "dark" ? "light" : "dark";
  button.innerHTML = `<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">${ICONS[mode]}</svg>`;
  button.setAttribute("aria-label", `Switch to the ${next} theme`);
  button.title = `Switch to the ${next} theme`;
}

function mount() {
  const brand = document.querySelector(".site-header .brand");
  if (!brand || document.getElementById("theme-toggle")) return;
  const button = document.createElement("button");
  button.type = "button";
  button.id = "theme-toggle";
  button.className = "theme-toggle";
  button.addEventListener("click", () => {
    const next = current() === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* storage unavailable: the choice lasts for this page only */
    }
    paint(button);
  });
  dark.addEventListener("change", () => paint(button));
  paint(button);
  brand.after(button);
}

mount();
