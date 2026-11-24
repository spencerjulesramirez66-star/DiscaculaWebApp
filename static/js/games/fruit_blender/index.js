// Visual → Fruit Blender (GAM-02). DOM + SVG + Pointer Events (ADR-0003).
//
// Count the parts, then the whole (a common way to teach early addition/subtraction):
//   Adding  3 + 2:  put 3 apples in → "How many apples?" → add 2 bananas → "How many bananas?"
//                   → Blend! → "How many fruits altogether?"   (only this last answer is scored)
//   Taking away 5 − 2: "How many apples are in the blender?" → take 2 out → "How many did you
//                   take out?" → Blend! → "How many are left?"  (scored)
// Counting steps are practice: hints and retries, nothing is sent to the server.
//
// Every fruit is a real <button>: drag it, tap it, or press Enter/Space to move it.
// That makes it work with mouse, touch, keyboard and screen readers.

const DRAG_THRESHOLD = 6; // px a pointer must move before a press counts as a drag
const MOVE_PHASES = new Set(["addA", "addB", "takeOut"]);

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

  const label = (kind) => fruits[kind].label.toLowerCase();
  const plural = (kind, n) => (n === 1 ? label(kind) : `${label(kind)}s`);
  const makeItems = (kind, count, where) =>
    Array.from({ length: count }, () => ({ id: nextId++, kind, where, locked: false }));
  const countIn = (where, kind) =>
    items.filter((i) => i.where === where && (!kind || i.kind === kind)).length;

  function startQuestion() {
    q = questions[index];
    nextId = 0;
    startedAt = performance.now();
    el.feedback.textContent = "";
    el.blenderImg.src = config.assets.blender.empty;
    el.blenderZone.classList.remove("is-blending", "is-blended", "is-cheer");
    game.progress(index + 1, questions.length);
    el.sum.textContent = `${q.a} ${q.op === "+" ? "+" : "−"} ${q.b}`;

    if (q.op === "+") {
      phase = "addA";
      items = makeItems(q.fruitA, q.a + 2, "tray");
    } else {
      phase = "countStart";
      items = makeItems(q.fruitA, q.a, "blender");
    }
    render();
    game.speak(`${el.sum.textContent}. ${el.prompt.textContent}`);
  }

  // What the child is asked at each step. Counting steps also name the right answer.
  function step() {
    const A = q.fruitA;
    const B = q.fruitB;
    switch (phase) {
      case "addA": return { prompt: `Put ${q.a} ${plural(A, q.a)} in the blender.` };
      case "countA": return { prompt: `How many ${plural(A, 2)} are in the blender?`, count: q.a, then: "addB" };
      case "addB": return { prompt: `Now add ${q.b} ${plural(B, q.b)}.` };
      case "countB": return { prompt: `How many ${plural(B, 2)} did you add?`, count: q.b, then: "ready" };
      case "countStart": return { prompt: `How many ${plural(A, 2)} are in the blender?`, count: q.a, then: "takeOut" };
      case "takeOut": return { prompt: `Take ${q.b} ${plural(A, q.b)} out of the blender.` };
      case "countOut": return { prompt: `How many ${plural(A, 2)} did you take out?`, count: q.b, then: "ready" };
      case "ready": return { prompt: "Great counting! Now press Blend!" };
      case "answer": return {
        prompt: q.op === "+" ? "How many fruits are in the blender altogether?" : "How many fruits are left in the blender?",
      };
      default: return { prompt: "" };
    }
  }

  // ---- rendering ----------------------------------------------------------
  function fruitButton(item) {
    const f = fruits[item.kind];
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "fb__fruit";
    btn.dataset.id = item.id;
    btn.disabled = item.locked || !MOVE_PHASES.has(phase);
    const action = item.where === "tray" ? "put in the blender" : "take out";
    btn.setAttribute("aria-label", btn.disabled ? f.label : `${f.label}, ${action}`);
    btn.innerHTML = `<img src="${f.src}" alt="" draggable="false">`;
    return btn;
  }

  function render() {
    el.prompt.textContent = step().prompt;
    el.tray.replaceChildren(...items.filter((i) => i.where === "tray").map(fruitButton));
    el.blender.replaceChildren(...items.filter((i) => i.where === "blender").map(fruitButton));
    el.trayZone.hidden = phase === "answer" || phase === "done";
    renderActions();
  }

  function actionButton(text, onClick, primary = true) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `btn btn--lg ${primary ? "btn--primary" : "btn--secondary"}`;
    btn.textContent = text;
    btn.addEventListener("click", onClick);
    return btn;
  }

  function choiceGroup(numbers, onPick, label) {
    const group = document.createElement("div");
    group.className = "fb__choices";
    group.setAttribute("role", "group");
    group.setAttribute("aria-label", label);
    for (const n of numbers) {
      const btn = actionButton(String(n), () => onPick(n, btn), false);
      btn.classList.add("fb__choice");
      group.append(btn);
    }
    return group;
  }

  // The right number plus two neighbours (never below zero), shuffled.
  function countChoices(n) {
    const set = new Set([n, n + 1]);
    set.add(n - 1 >= 0 ? n - 1 : n + 2);
    const list = [...set];
    for (let i = list.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [list[i], list[j]] = [list[j], list[i]];
    }
    return list;
  }

  function renderActions() {
    el.actions.replaceChildren();
    const s = step();
    if (MOVE_PHASES.has(phase)) {
      el.actions.append(actionButton("Done", checkMove));
    } else if (s.count !== undefined) {
      const group = choiceGroup(countChoices(s.count), countPick, "How many?");
      el.actions.append(group);
      group.querySelector("button")?.focus();
    } else if (phase === "ready") {
      const btn = actionButton("Blend!", blend);
      el.actions.append(btn);
      btn.focus();
    } else if (phase === "answer") {
      const group = choiceGroup(q.choices, answer, "Answers");
      el.actions.append(group);
      group.querySelector("button")?.focus();
    }
  }

  function goTo(next) {
    phase = next;
    if (phase === "addB") {
      items.forEach((i) => { i.locked = true; });          // the apples stay in
      items = items.filter((i) => i.where === "blender");
      items.push(...makeItems(q.fruitB, q.b + 2, "tray"));
    }
    render();
    game.speak(el.prompt.textContent);
  }

  // ---- moving fruit -------------------------------------------------------
  function move(id) {
    const item = items.find((i) => i.id === Number(id));
    if (!item || item.locked || !MOVE_PHASES.has(phase)) return;
    item.where = item.where === "tray" ? "blender" : "tray";
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
    if (drag.ghost) {
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
  function say(text) {
    el.feedback.textContent = text;
    game.speak(text);
  }

  // "Done" after moving fruit: is the right number in the right place?
  function checkMove() {
    if (phase === "addA" && countIn("blender", q.fruitA) !== q.a) {
      return say(`Let's check. We need ${q.a} ${plural(q.fruitA, q.a)} in the blender.`);
    }
    if (phase === "addB" && countIn("blender", q.fruitB) !== q.b) {
      return say(`Let's check. Add ${q.b} ${plural(q.fruitB, q.b)}.`);
    }
    if (phase === "takeOut" && countIn("tray") !== q.b) {
      return say(`Let's check. Take ${q.b} ${plural(q.fruitA, q.b)} out.`);
    }
    el.feedback.textContent = "";
    goTo({ addA: "countA", addB: "countB", takeOut: "countOut" }[phase]);
  }

  // Practice counting step: never sent to the server.
  function countPick(n, btn) {
    const s = step();
    if (n !== s.count) {
      btn.classList.add("is-wrong");
      btn.disabled = true;
      return say("Not quite. Point to each one and count them slowly.");
    }
    btn.classList.add("is-right");
    el.actions.querySelectorAll("button").forEach((b) => { b.disabled = true; });
    say(`Yes, ${n}!`);
    setTimeout(() => { el.feedback.textContent = ""; goTo(s.then); }, config.a11y?.reducedMotion ? 300 : 700);
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
      goTo("answer");
    }, wait);
  }

  // ---- the scored answer --------------------------------------------------
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
      return say("Something went wrong. Please try again.");
    }
    busy = false;

    if (!result.correct) {
      btn.classList.add("is-wrong");
      el.actions.querySelectorAll("button:not(.is-wrong)").forEach((b) => { b.disabled = false; });
      return say(q.op === "+"
        ? "Not quite. Count all the fruits in the blender, then try again."
        : "Not quite. Count the fruits still in the blender, then try again.");
    }

    btn.classList.add("is-right");
    phase = "done";
    const sign = q.op === "+" ? "+" : "−";
    say(`Yes! ${q.a} ${sign} ${q.b} = ${choice}`);
    el.blenderZone.classList.add("is-cheer");

    if (result.done) {
      el.actions.replaceChildren(actionButton("See my score", () => game.finish()));
    } else if (result.sessionOpen === false) {
      el.actions.replaceChildren(actionButton("Finish", () => game.endedEarly()));
    } else {
      el.actions.replaceChildren(actionButton("Next question", () => { index += 1; startQuestion(); }));
    }
    el.actions.querySelector("button")?.focus();
  }

  startQuestion();
  return { destroy() { root.replaceChildren(); } };
}
