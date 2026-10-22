// Header menu of every page: the "Macro" and "Stocks" drop-downs and, on narrow screens, the menu button that shows
// the whole menu as a panel. Menus open on click or tap (and on hover with a mouse); Escape, a click outside or
// tabbing away closes them. Without this script the header still shows the direct links.

const header = document.querySelector(".site-header");
const toggle = header && header.querySelector(".nav-toggle");
const groups = header ? [...header.querySelectorAll(".nav-group")] : [];
const hoverable = window.matchMedia("(hover: hover) and (pointer: fine) and (min-width: 881px)");
const state = new Map(); // trigger -> "hover" while opened by the mouse only

function setOpen(trigger, open, how = "click") {
  trigger.setAttribute("aria-expanded", String(open));
  if (open) state.set(trigger, how);
  else state.delete(trigger);
}

function closeAll(except = null) {
  for (const g of groups) {
    const t = g.querySelector(".nav-trigger");
    if (t !== except && t.getAttribute("aria-expanded") === "true") setOpen(t, false);
  }
}

function setPanel(open) {
  if (!toggle) return;
  header.classList.toggle("is-open", open);
  toggle.setAttribute("aria-expanded", String(open));
  toggle.setAttribute("aria-label", open ? "Close the menu" : "Open the menu");
}

for (const group of groups) {
  const trigger = group.querySelector(".nav-trigger");
  let timer = null;
  trigger.addEventListener("click", () => {
    const open = trigger.getAttribute("aria-expanded") === "true";
    // a menu the mouse already opened stays open on click instead of closing under the pointer
    if (open && state.get(trigger) === "hover") return state.set(trigger, "click");
    closeAll(trigger);
    setOpen(trigger, !open);
  });
  group.addEventListener("pointerenter", () => {
    if (!hoverable.matches) return;
    clearTimeout(timer);
    if (trigger.getAttribute("aria-expanded") !== "true") {
      closeAll(trigger);
      setOpen(trigger, true, "hover");
    }
  });
  group.addEventListener("pointerleave", () => {
    if (!hoverable.matches || state.get(trigger) !== "hover") return;
    timer = setTimeout(() => setOpen(trigger, false), 180);
  });
  group.addEventListener("focusout", (ev) => {
    if (!group.contains(ev.relatedTarget) && ev.relatedTarget) setOpen(trigger, false);
  });
}

if (toggle) {
  toggle.addEventListener("click", () => setPanel(!header.classList.contains("is-open")));
  window.matchMedia("(min-width: 881px)").addEventListener("change", (ev) => ev.matches && setPanel(false));
}

document.addEventListener("click", (ev) => {
  if (!header || header.contains(ev.target)) return;
  closeAll();
  setPanel(false);
});

document.addEventListener("keydown", (ev) => {
  if (ev.key !== "Escape" || !header) return;
  const open = groups
    .map((g) => g.querySelector(".nav-trigger"))
    .find((t) => t.getAttribute("aria-expanded") === "true");
  if (open) {
    setOpen(open, false);
    open.focus();
  } else if (header.classList.contains("is-open")) {
    setPanel(false);
    toggle.focus();
  }
});
