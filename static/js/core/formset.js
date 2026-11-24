// Add/remove rows in a Django formset without saving first (question editor).
//   <form data-formset> … <ol data-formset-rows> rows with [data-formset-row] …
//   <template data-formset-empty> one blank row using the __prefix__ placeholder
//   <button data-formset-add>, and in each row <button data-formset-remove>
// Existing rows are only *marked* for removal (their DELETE box is ticked, the row greys out,
// and ✕ turns into "Undo"), so nothing is lost until the teacher presses Save.
(() => {
  for (const form of document.querySelectorAll("form[data-formset]")) {
    const rows = form.querySelector("[data-formset-rows]");
    const template = form.querySelector("template[data-formset-empty]");
    const total = form.querySelector('input[name$="-TOTAL_FORMS"]');
    const max = Number(form.querySelector('input[name$="-MAX_NUM_FORMS"]')?.value || 1000);
    const addBtn = form.querySelector("[data-formset-add]");

    const renumber = () => {
      let n = 0;
      for (const row of rows.querySelectorAll("[data-formset-row]")) {
        const num = row.querySelector(".q-row__num");
        if (row.classList.contains("is-removed")) { if (num) num.textContent = ""; continue; }
        n += 1;
        if (num) num.textContent = `${n}.`;
      }
      addBtn.disabled = Number(total.value) >= max;
    };

    addBtn.addEventListener("click", () => {
      const index = Number(total.value);
      if (index >= max) return;
      const html = template.innerHTML.replaceAll("__prefix__", String(index));
      rows.insertAdjacentHTML("beforeend", html);
      total.value = String(index + 1);
      renumber();
      rows.lastElementChild.querySelector("input:not([type=hidden])")?.focus();
    });

    rows.addEventListener("click", (event) => {
      const btn = event.target.closest("[data-formset-remove]");
      if (!btn) return;
      const row = btn.closest("[data-formset-row]");
      const del = row.querySelector('input[name$="-DELETE"]');
      if (del) {
        // Saved question: toggle "remove when I save".
        del.checked = !del.checked;
        row.classList.toggle("is-removed", del.checked);
        btn.setAttribute("aria-label", del.checked ? "Keep this question" : "Remove this question");
        btn.innerHTML = del.checked ? "Undo" : btn.dataset.icon || btn.innerHTML;
      } else {
        // New, unsaved row: just clear it. Django ignores rows left blank.
        row.querySelectorAll("input:not([type=hidden])").forEach((i) => { i.value = ""; });
        row.hidden = true;
        row.classList.add("is-removed");
      }
      renumber();
    });

    for (const btn of rows.querySelectorAll("[data-formset-remove]")) btn.dataset.icon = btn.innerHTML;
    renumber();
  }
})();
