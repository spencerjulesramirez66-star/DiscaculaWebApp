// Loading splash (GEN-01): once per browser visit, at most ~1.2 s, never with reduced motion.
// Loaded in <head> without defer so the splash shows before the page paints.
(() => {
  const root = document.documentElement;
  const SHOW_MS = 1200;
  let seen = true;
  try {
    seen = sessionStorage.getItem("splashSeen") === "1";
    sessionStorage.setItem("splashSeen", "1");
  } catch {
    // Storage blocked (private mode etc.): just skip the splash.
  }
  const reduced =
    window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
    root.dataset.reducedMotion === "true";
  if (seen || reduced) return;

  root.classList.add("show-splash");
  const hide = () => {
    root.classList.add("splash-leaving");
    setTimeout(() => root.classList.remove("show-splash", "splash-leaving"), 250);
  };
  setTimeout(hide, SHOW_MS);
  document.addEventListener("click", hide, { once: true });
  document.addEventListener("keydown", hide, { once: true });
})();
