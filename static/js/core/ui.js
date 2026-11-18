// Small shared behaviours, attached by data-attributes so templates need no inline JS.
//   <form data-confirm="Are you sure?">  → asks before submitting
//   <button data-print>                  → opens the print dialog
document.addEventListener("submit", (event) => {
  const form = event.target.closest("form[data-confirm]");
  if (form && !window.confirm(form.dataset.confirm)) {
    event.preventDefault();
  }
});

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-print]")) {
    window.print();
  }
});
