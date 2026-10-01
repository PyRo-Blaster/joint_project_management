// Applies the saved or system theme before first paint, so there is no flash of the
// wrong theme. A file rather than an inline script so the CSP can stay script-src 'self'.
/* global localStorage, matchMedia, document */
(function () {
  try {
    var t = localStorage.getItem("cmc-theme");
    var dark = t === "dark" || (!t && matchMedia("(prefers-color-scheme: dark)").matches);
    if (dark) document.documentElement.classList.add("dark");
  } catch {
    // Storage blocked (private mode, policy): keep the default light theme.
  }
})();
