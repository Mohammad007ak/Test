// نمایش فیلدهای وابسته به «نوع» (مثلاً عیار فقط برای طلا).
(function () {
  function sync(form) {
    var kind = form.querySelector('[name="kind"]');
    if (!kind) return;
    form.querySelectorAll("[data-kinds]").forEach(function (el) {
      var kinds = el.getAttribute("data-kinds").split(" ");
      var show = kinds.indexOf(kind.value) !== -1;
      el.hidden = !show;
      el.querySelectorAll("input, select, textarea").forEach(function (input) {
        input.disabled = !show;
      });
    });
  }
  document.querySelectorAll("form[data-kind-form]").forEach(function (form) {
    sync(form);
    form.addEventListener("change", function (e) {
      if (e.target.name === "kind") sync(form);
    });
  });
})();
