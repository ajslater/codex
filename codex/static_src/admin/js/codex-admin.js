/* Dirty hack for django admin's refusal to display non-editable fields */
const disable = function (el) {
  el.setAttribute("readonly", true);
  // el.setAttribute("disabled", true);
};

document.addEventListener("DOMContentLoaded", function () {
  let els = document.querySelectorAll(
    ".field-last_poll .vDateField, .field-last_poll .vTimeField"
  );
  Array.from(els).forEach((el) => {
    disable(el);
  });
});
