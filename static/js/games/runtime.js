// Shared game runtime (ADR-0005). Loads static/js/games/<key>/index.js and gives it a
// small `game` API, so every game gets saving, progress, narration and ending for free.
//
// Game module contract:
//   export function mount(root, config, game) { ...; return { destroy() {} } }
//
//   game.submit(questionId, answer, timeMs) → Promise<{correct, tryNumber, done, score, sessionOpen}>
//   game.progress(current, total)            → updates the "Question 2 of 5" text
//   game.speak(text)                         → reads text aloud when narration is on
//   game.finish()                            → goes to the shared result screen
//   game.endedEarly()                        → shows "session ended" after the current question

const config = JSON.parse(document.getElementById("game-config").textContent);
const root = document.getElementById("game-root");
const progressEl = document.querySelector("[data-game-progress]");

function csrfToken() {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

const game = {
  async submit(questionId, answer, timeMs) {
    const response = await fetch(config.urls.attempt, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      credentials: "same-origin",
      body: JSON.stringify({ questionId, answer, timeMs: Math.round(timeMs) }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || `Request failed (${response.status})`);
    }
    return data;
  },

  progress(current, total) {
    if (progressEl) progressEl.textContent = `Question ${current} of ${total}`;
  },

  speak(text) {
    if (!config.a11y?.narration || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
  },

  finish() {
    window.location.assign(config.urls.result);
  },

  endedEarly() {
    root.replaceChildren();
    const panel = document.createElement("div");
    panel.className = "card stack center";
    panel.innerHTML = `<h2>Great job today!</h2>
      <p class="lead">Your teacher's session has ended.</p>
      <a class="btn btn--primary btn--lg" href="${config.urls.finish}">Finish</a>`;
    root.append(panel);
  },
};

if (config.a11y?.reducedMotion) document.body.classList.add("a11y-reduced-motion");

try {
  const module = await import(`./${config.game}/index.js`);
  root.replaceChildren();
  module.mount(root, config, game);
} catch (error) {
  console.error(error);
  root.innerHTML = `<p class="banner banner--warning">Sorry, this game could not load. Please tell your teacher.</p>`;
}
