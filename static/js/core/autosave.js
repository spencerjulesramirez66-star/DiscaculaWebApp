// Form draft autosave (GEN-04). Opt in per form: <form data-autosave="some-key">.
// Saves typed values to this browser's localStorage and restores them after a refresh
// or accidental navigation. Cleared when the form is submitted.
// Never saved: passwords, one-time codes, files, hidden fields (incl. CSRF), or any
// field marked data-no-autosave.
(() => {
  const PREFIX = "autosave:";

  const storage = (() => {
    try {
      const probe = "__autosave_probe__";
      window.localStorage.setItem(probe, "1");
      window.localStorage.removeItem(probe);
      return window.localStorage;
    } catch {
      return null; // private mode / blocked: autosave quietly off
    }
  })();
  if (!storage) return;

  const skip = (el) =>
    !el.name ||
    el.disabled ||
    el.dataset.noAutosave !== undefined ||
    ["password", "file", "hidden", "submit", "button"].includes(el.type) ||
    el.autocomplete === "one-time-code" ||
    el.name === "csrfmiddlewaretoken";

  const keyFor = (form) => PREFIX + form.dataset.autosave + ":" + location.pathname;

  function collect(form) {
    const data = {};
    for (const el of form.elements) {
      if (skip(el)) continue;
      if (el.type === "checkbox") data[el.name + "::" + el.value] = el.checked;
      else if (el.type === "radio") { if (el.checked) data[el.name] = el.value; }
      else data[el.name] = el.value;
    }
    return data;
  }

  function restore(form, data) {
    let restored = false;
    for (const el of form.elements) {
      if (skip(el)) continue;
      if (el.type === "checkbox") {
        const k = el.name + "::" + el.value;
        if (k in data && el.checked !== data[k]) { el.checked = data[k]; restored = true; }
      } else if (el.type === "radio") {
        if (el.name in data && el.value === data[el.name] && !el.checked) { el.checked = true; restored = true; }
      } else if (el.name in data && el.value !== data[el.name] && el.value === el.defaultValue) {
        // Only fill fields the server didn't already fill differently (e.g. after an error).
        el.value = data[el.name];
        restored = true;
      }
    }
    return restored;
  }

  for (const form of document.querySelectorAll("form[data-autosave]")) {
    const key = keyFor(form);
    try {
      const saved = JSON.parse(storage.getItem(key) || "null");
      if (saved && restore(form, saved)) {
        const note = document.createElement("p");
        note.className = "autosave-note";
        note.setAttribute("role", "status");
        note.textContent = "We restored what you typed earlier.";
        form.prepend(note);
      }
    } catch {
      storage.removeItem(key);
    }
    let timer;
    const save = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        try { storage.setItem(key, JSON.stringify(collect(form))); } catch { /* full: ignore */ }
      }, 300);
    };
    form.addEventListener("input", save);
    form.addEventListener("change", save);
    form.addEventListener("submit", () => { clearTimeout(timer); storage.removeItem(key); });
  }
})();
