// Visual → Fruit Blender (GAM-02). DOM + SVG + Pointer Events (ADR-0003).
//
// Addition a + b:  put a fruits in, then b more, Blend, pick the total.
// Subtraction a − b: blender starts with a fruits, take b out, Blend, pick what's left.
//
// Every fruit is a real <button>: drag it, tap it, or press Enter/Space to move it.
// That makes it work with mouse, touch, keyboard and screen readers.

const DRAG_THRESHOLD = 6; // px a pointer must move before a press counts as a drag

export function mount(root, config, game) {
  const fruits = Object.fromEntries(config.assets.fruits.map((f) => [f.id, f]));
  const questions = config.questions;
  let index = 0;

  root.innerHTML = `
    <div class="fb">
      <header class="fb__question">
        <p class="fb__sum" data-sum></p>
        <p class="fb__prompt" data-prompt aria-live="polite"></p>
      </header>
      <div class="fb__stage">
        <section class="fb__zone fb__tray" data-zone="tray" aria-label="Fruit basket">
          <div class="fb__items" data-items="tray"></div>
        </section>
        <section class="fb__zone fb__blender" data-zone="blender" aria-label="Blender">
          <img class="fb__blender-img" alt="" data-blender-img src="${config.assets.blender.empty}">
          <div class="fb__items" data-items="blender"></div>
        </section>
      </div>
      <div class="fb__actions" data-actions></div>
      <p class="fb__feedback" data-feedback role="status" aria-live="assertive"></p>
    </div>`;

  const el = {
    sum: root.querySelector("[data-sum]"),
    prompt: root.querySelector("[data-prompt]"),
    tray: root.querySelector('[data-items="tray"]'),
    blender: root.querySelector('[data-items="blender"]'),
    blenderZone: root.querySelector('[data-zone="blender"]'),
    trayZone: root.querySelector('[data-zone="tray"]'),
    blenderImg: root.querySelector("[data-blender-img]"),
    actions: root.querySelector("[data-actions]"),
    feedback: root.querySelector("[data-feedback]"),
  };

  // ---- per-question state -------------------------------------------------
  let q, items, phase, startedAt, nextId;

  function plural(label, n) {
    return n === 1 ? label.toLowerCase() : `${label.toLowerCase()}s`;
  }

  function makeItems(kind, count, where, locked = false) {
    return Array.from({ length: count }, () => ({ id: nextId++, kind, where, locked }));
  }

  function startQuestion() {
    q = questions[index];
    nextId = 0;
    startedAt = performance.now();
    el.feedback.textContent = "";
    el.blenderImg.src = config.assets.blender.empty;
    el.blenderZone.classList.remove("is-blending", "is-blended");
    game.progress(index + 1, questions.length);
    el.sum.textContent = `${q.a} ${q.op === "+" ? "+" : "−"} ${q.b}`;

    if (q.op === "+") {
      phase = "addA";
      items = makeItems(q.fruitA, q.a + 2, "tray");
    } else {
      phase = "takeOut";
      items = [...makeItems(q.fruitA, q.a, "blender"), ...makeItems(q.fruitA, 0, "tray")];
    }
    render();
    game.speak(`${el.sum.textContent}. ${el.prompt.textContent}`);
  }

  function inBlender(kind, includeLocked = true) {
    return items.filter((i) => i.where === "blender" && i.kind === kind && (includeLocked || !i.locked)).length;
  }

  function promptText() {
    const A = fruits[q.fruitA].label;
    const B = fruits[q.fruitB].label;
    switch (phase) {
      case "addA": return `Put ${q.a} ${plural(A, q.a)} in the blender.`;
      case "addB": return `Now add ${q.b} ${plural(B, q.b)}.`;
      case "takeOut": return `Take ${q.b} ${plural(A, q.b)} out of the blender.`;
      case "answer": return q.op === "+"
        ? "How many fruits are in the blender?"
        : "How many fruits are left in the blender?";
      default: return "";
    }
  }

  // ---- rendering ----------------------------------------------------------
  function fruitButton(item) {
    const f = fruits[item.kind];
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "fb__fruit";
    btn.dataset.id = item.id;
    btn.disabled = item.locked || phase === "answer" || phase === "done";
    const action = item.where === "tray" ? "put in the blender" : "take out";
    btn.setAttribute("aria-label", `${f.label}, ${action}`);
    btn.innerHTML = `<img src="${f.src}" alt="" draggable="false">`;
    return btn;
  }

  function render() {
    el.prompt.textContent = promptText();
    el.tray.replaceChildren(...items.filter((i) => i.where === "tray").map(fruitButton));
    el.blender.replaceChildren(...items.filter((i) => i.where === "blender").map(fruitButton));
    el.trayZone.hidden = phase === "answer" || phase === "done";
    renderActions();
  }

  function actionButton(label, onClick, primary = true) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `btn btn--lg ${primary ? "btn--primary" : "btn--secondary"}`;
    btn.textContent = label;
    btn.addEventListener("click", onClick);
    return btn;
  }

  function renderActions() {
    el.actions.replaceChildren();
    if (phase === "addA") el.actions.append(actionButton("Next fruit", checkAddA));
    if (phase === "addB") el.actions.append(actionButton("Blend!", checkAddB));
    if (phase === "takeOut") el.actions.append(actionButton("Blend!", checkTakeOut));
    if (phase === "answer") {
      const group = document.createElement("div");
      group.className = "fb__choices";
      group.setAttribute("role", "group");
      group.setAttribute("aria-label", "Answers");
      for (const choice of q.choices) {
        const btn = actionButton(String(choice), () => answer(choice, btn), false);
        btn.classList.add("fb__choice");
        group.append(btn);
      }
      el.actions.append(group);
      group.querySelector("button")?.focus();
    }
  }

  // ---- moving fruit -------------------------------------------------------
  function move(id) {
    const item = items.find((i) => i.id === Number(id));
    if (!item || item.locked) return;
    if (phase === "takeOut") {
      item.where = item.where === "blender" ? "tray" : "blender";
    } else if (phase === "addA" || phase === "addB") {
      item.where = item.where === "tray" ? "blender" : "tray";
    }
    el.feedback.textContent = "";
    render();
  }

  let drag = null;
  let suppressClick = false;

  root.addEventListener("click", (event) => {
    const btn = event.target.closest(".fb__fruit");
    if (!btn || btn.disabled) return;
    if (suppressClick) { suppressClick = false; return; }
    move(btn.dataset.id);
  });

  root.addEventListener("pointerdown", (event) => {
    const btn = event.target.closest(".fb__fruit");
    if (!btn || btn.disabled || event.button > 0) return;
    drag = { btn, id: btn.dataset.id, x: event.clientX, y: event.clientY, ghost: null };
    btn.setPointerCapture(event.pointerId);
  });

  root.addEventListener("pointermove", (event) => {
    if (!drag) return;
    const dx = event.clientX - drag.x;
    const dy = event.clientY - drag.y;
    if (!drag.ghost && Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
    if (!drag.ghost) {
      drag.ghost = drag.btn.cloneNode(true);
      drag.ghost.classList.add("fb__ghost");
      document.body.append(drag.ghost);
      drag.btn.classList.add("is-dragging");
    }
    drag.ghost.style.left = `${event.clientX}px`;
    drag.ghost.style.top = `${event.clientY}px`;
    const over = zoneAt(event.clientX, event.clientY);
    el.blenderZone.classList.toggle("is-over", over === "blender");
    el.trayZone.classList.toggle("is-over", over === "tray");
  });

  function endDrag(event) {
    if (!drag) return;
    const wasDrag = Boolean(drag.ghost);
    if (wasDrag) {
      const over = zoneAt(event.clientX, event.clientY);
      const item = items.find((i) => i.id === Number(drag.id));
      drag.ghost.remove();
      // Some browsers fire a click after a drag, some don't. Ignore only a click that
      // arrives in this same task; otherwise the child's NEXT tap would be swallowed.
      suppressClick = true;
      setTimeout(() => { suppressClick = false; }, 0);
      if (item && over && over !== item.where) move(drag.id);
      else render();
    }
    el.blenderZone.classList.remove("is-over");
    el.trayZone.classList.remove("is-over");
    drag = null;
  }
  root.addEventListener("pointerup", endDrag);
  root.addEventListener("pointercancel", endDrag);

  function zoneAt(x, y) {
    for (const [name, zone] of [["blender", el.blenderZone], ["tray", el.trayZone]]) {
      const r = zone.getBoundingClientRect();
      if (!zone.hidden && x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) return name;
    }
    return null;
  }

  // ---- checks -------------------------------------------------------------
  function tryAgain(text) {
    el.feedback.textContent = text;
    game.speak(text);
  }

  function checkAddA() {
    const n = inBlender(q.fruitA);
    if (n !== q.a) return tryAgain(`Count again. We need ${q.a} ${plural(fruits[q.fruitA].label, q.a)} in the blender.`);
    items.forEach((i) => { if (i.where === "blender") i.locked = true; });
    items = items.filter((i) => i.where === "blender");
    items.push(...makeItems(q.fruitB, q.b + 2, "tray"));
    phase = "addB";
    render();
    game.speak(el.prompt.textContent);
  }

  function checkAddB() {
    const n = inBlender(q.fruitB, false);
    if (n !== q.b) return tryAgain(`Count again. Add ${q.b} ${plural(fruits[q.fruitB].label, q.b)}.`);
    blend();
  }

  function checkTakeOut() {
    const out = items.filter((i) => i.where === "tray").length;
    if (out !== q.b) return tryAgain(`Count again. Take ${q.b} ${plural(fruits[q.fruitA].label, q.b)} out.`);
    blend();
  }

  function blend() {
    items = items.filter((i) => i.where === "blender");
    items.forEach((i) => { i.locked = true; });
    phase = "blending";
    el.actions.replaceChildren();
    el.blenderZone.classList.add("is-blending");
    const wait = config.a11y?.reducedMotion ? 0 : 900;
    setTimeout(() => {
      el.blenderZone.classList.remove("is-blending");
      el.blenderZone.classList.add("is-blended");
      el.blenderImg.src = config.assets.blender.full;
      phase = "answer";
      render();
      game.speak(el.prompt.textContent);
    }, wait);
  }

  // ---- answering ----------------------------------------------------------
  let busy = false;

  async function answer(choice, btn) {
    if (busy) return;
    busy = true;
    el.actions.querySelectorAll("button").forEach((b) => { b.disabled = true; });
    let result;
    try {
      result = await game.submit(q.id, choice, performance.now() - startedAt);
    } catch (error) {
      busy = false;
      el.actions.querySelectorAll("button:not(.is-wrong)").forEach((b) => { b.disabled = false; });
      return tryAgain("Something went wrong. Please try again.");
    }
    busy = false;

    if (!result.correct) {
      btn.classList.add("is-wrong");
      el.actions.querySelectorAll("button:not(.is-wrong)").forEach((b) => { b.disabled = false; });
      const hint = q.op === "+"
        ? "Not quite. Count all the fruits in the blender, then try again."
        : "Not quite. Count the fruits still in the blender, then try again.";
      return tryAgain(hint);
    }

    btn.classList.add("is-right");
    phase = "done";
    const sign = q.op === "+" ? "+" : "−";
    const cheer = `Yes! ${q.a} ${sign} ${q.b} = ${choice}`;
    el.feedback.textContent = cheer;
    game.speak(cheer);
    el.blenderZone.classList.add("is-cheer");

    if (result.done) {
      el.actions.replaceChildren(actionButton("See my score", () => game.finish()));
    } else if (result.sessionOpen === false) {
      el.actions.replaceChildren(actionButton("Finish", () => game.endedEarly()));
    } else {
      el.actions.replaceChildren(actionButton("Next question", () => {
        el.blenderZone.classList.remove("is-cheer");
        index += 1;
        startQuestion();
      }));
    }
    el.actions.querySelector("button")?.focus();
  }

  startQuestion();
  return { destroy() { root.replaceChildren(); } };
}
