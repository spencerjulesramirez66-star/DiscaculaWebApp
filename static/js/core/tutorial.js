// Tutorial gate (GAM-09): the "ready" button unlocks when the video ends.
// If the video can't play (missing file, unsupported format), unlock right away so a child
// is never stuck.
(() => {
  const video = document.querySelector("[data-tutorial-video]");
  const done = document.querySelector("[data-tutorial-done]");
  const hint = document.querySelector("[data-tutorial-hint]");
  if (!video || !done) return;

  const unlock = () => {
    done.disabled = false;
    if (hint) hint.hidden = true;
  };
  video.addEventListener("ended", unlock);
  video.addEventListener("error", unlock, true);
  video.querySelector("source")?.addEventListener("error", unlock);
})();
