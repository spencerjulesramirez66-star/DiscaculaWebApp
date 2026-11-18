// Shared helper for fetch() calls (games will post attempts with this).
// HTMX requests already get the token via hx-headers on <body>.
window.csrfToken = function csrfToken() {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
};
