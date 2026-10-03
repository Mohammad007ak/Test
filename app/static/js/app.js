// رفتارهای رابط: برگه پایین، قالب‌بندی زنده مبلغ، فیلدهای وابسته به نوع، واحد نمایش و نمودار روند.
(function () {
  "use strict";

  var FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
  var AR_DIGITS = "٠١٢٣٤٥٦٧٨٩";
  var faNumber = new Intl.NumberFormat("fa-IR");
  var faShort = new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 2 });

  function toLatin(text) {
    return text.replace(/[۰-۹٠-٩]/g, function (d) {
      var i = FA_DIGITS.indexOf(d);
      return String(i === -1 ? AR_DIGITS.indexOf(d) : i);
    });
  }

  function shortToman(digits) {
    var n = Number(digits);
    var scales = [[1e12, "هزار میلیارد"], [1e9, "میلیارد"], [1e6, "میلیون"], [1e3, "هزار"]];
    for (var i = 0; i < scales.length; i++) {
      if (n >= scales[i][0]) return faShort.format(n / scales[i][0]) + " " + scales[i][1] + " تومان";
    }
    return n ? faNumber.format(n) + " تومان" : "";
  }

  // ---------- برگه پایین ----------
  function sheet() { return document.getElementById("sheet"); }

  function openSheet() {
    var dialog = sheet();
    if (!dialog) return;
    dialog.classList.remove("closing");
    dialog.style.transform = "";
    if (!dialog.open) dialog.showModal();
    dialog.scrollTop = 0;
    var first = dialog.querySelector("input:not([type=radio]):not([type=checkbox]):not([disabled])");
    // روی گوشی فوکوس خودکار صفحه‌کلید را بی‌اجازه باز می‌کند؛ فقط روی دسکتاپ
    if (first && window.matchMedia("(hover: hover)").matches) first.focus({ preventScroll: true });
  }

  function closeSheet() {
    var dialog = sheet();
    if (!dialog || !dialog.open) return;
    dialog.classList.add("closing");
    setTimeout(function () {
      dialog.close();
      dialog.classList.remove("closing");
      dialog.style.transform = "";
      var body = document.getElementById("sheet-body");
      if (body) body.innerHTML = "";
    }, 200);
  }

  document.addEventListener("htmx:afterSwap", function (e) {
    if (e.detail.target && e.detail.target.id === "sheet-body") openSheet();
  });

  document.addEventListener("click", function (e) {
    var dialog = sheet();
    if (!dialog || !dialog.open) return;
    if (e.target === dialog) { closeSheet(); return; } // ضربه روی پس‌زمینه
    var closer = e.target.closest("[data-close]");
    if (closer && dialog.contains(closer)) { e.preventDefault(); closeSheet(); }
  });

  document.addEventListener("cancel", function (e) {
    if (e.target === sheet()) { e.preventDefault(); closeSheet(); }
  }, true);

  // کشیدن دستگیره به پایین برای بستن
  var drag = null;
  document.addEventListener("pointerdown", function (e) {
    var dialog = sheet();
    if (!dialog || !dialog.open || !e.target.closest(".sheet-grip")) return;
    drag = { y: e.clientY, dy: 0 };
    dialog.style.transition = "none";
  });
  document.addEventListener("pointermove", function (e) {
    if (!drag) return;
    drag.dy = Math.max(0, e.clientY - drag.y);
    sheet().style.transform = "translateY(" + drag.dy + "px)";
  });
  document.addEventListener("pointerup", function () {
    if (!drag) return;
    var dialog = sheet();
    dialog.style.transition = "transform .25s cubic-bezier(.2,.8,.2,1)";
    if (drag.dy > 90) closeSheet(); else dialog.style.transform = "";
    drag = null;
  });

  // ---------- مبلغ با جداکننده هزارگان و نمایش «۸۱٫۲ میلیون تومان» ----------
  function formatMoney(input) {
    var digits = toLatin(input.value).replace(/\D/g, "").replace(/^0+(?=\d)/, "");
    input.value = digits ? faNumber.format(BigInt(digits)) : "";
    var words = input.closest(".field");
    words = words && words.querySelector(".money-words");
    if (words) words.textContent = digits ? "≈ " + shortToman(digits) : "";
  }

  document.addEventListener("input", function (e) {
    var input = e.target;
    if (input.matches && input.matches("input[data-money]")) {
      formatMoney(input);
      input.setSelectionRange(input.value.length, input.value.length);
    }
  });

  // ---------- فیلدهای وابسته به «نوع» ----------
  function syncKind(form) {
    var checked = form.querySelector('[name="kind"]:checked') || form.querySelector('select[name="kind"]');
    if (!checked) return;
    form.querySelectorAll("[data-kinds]").forEach(function (el) {
      var show = el.getAttribute("data-kinds").split(" ").indexOf(checked.value) !== -1;
      el.hidden = !show;
      el.querySelectorAll("input, select, textarea").forEach(function (input) { input.disabled = !show; });
    });
  }

  document.addEventListener("change", function (e) {
    if (e.target.name === "kind") {
      var form = e.target.closest("form[data-kind-form]");
      if (form) syncKind(form);
    }
  });

  // ---------- واحد نمایش ثروت (تومان / دلار / طلا) ----------
  function setUnit(box, unit) {
    box.setAttribute("data-unit", unit);
    box.querySelectorAll("[data-set-unit]").forEach(function (b) {
      b.setAttribute("aria-selected", String(b.getAttribute("data-set-unit") === unit));
    });
    try { localStorage.setItem("networth-unit", unit); } catch (err) { /* حالت خصوصی */ }
  }

  document.addEventListener("click", function (e) {
    var button = e.target.closest("[data-set-unit]");
    if (!button || button.disabled) return;
    setUnit(button.closest("[data-unit-switch]"), button.getAttribute("data-set-unit"));
  });

  // ---------- نمودار روند ----------
  function drawTrend(canvas) {
    if (!window.Chart || canvas.dataset.drawn) return;
    canvas.dataset.drawn = "1";
    var data = JSON.parse(canvas.getAttribute("data-trend"));
    var css = getComputedStyle(document.documentElement);
    var accent = css.getPropertyValue("--accent").trim();
    var muted = css.getPropertyValue("--muted").trim();
    var grid = css.getPropertyValue("--border").trim();
    var compact = new Intl.NumberFormat("fa-IR", { notation: "compact", maximumFractionDigits: 1 });
    var ctx = canvas.getContext("2d");
    var fill = ctx.createLinearGradient(0, 0, 0, canvas.clientHeight || 200);
    fill.addColorStop(0, accent + "40");
    fill.addColorStop(1, accent + "00");
    Chart.defaults.font.family = "Vazirmatn";
    Chart.defaults.color = muted;
    new Chart(canvas, {
      type: "line",
      data: {
        labels: data.labels,
        datasets: [{ data: data.values, borderColor: accent, backgroundColor: fill, fill: true,
          borderWidth: 2, tension: .3, pointRadius: 0, pointHoverRadius: 5, pointHitRadius: 20 }]
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: { rtl: true, displayColors: false, callbacks: {
            label: function (c) { return shortToman(String(Math.round(c.raw))) || "۰"; } } }
        },
        scales: {
          x: { reverse: true, grid: { display: false }, ticks: { maxTicksLimit: 4, maxRotation: 0 } },
          y: { position: "right", grid: { color: grid }, border: { display: false },
            ticks: { maxTicksLimit: 4, callback: function (v) { return compact.format(v); } } }
        }
      }
    });
  }

  // ---------- راه‌اندازی هر محتوای تازه (بار اول و پس از هر جابه‌جایی htmx) ----------
  function all(root, selector) {
    var found = Array.prototype.slice.call(root.querySelectorAll(selector));
    if (root.matches && root.matches(selector)) found.unshift(root);
    return found;
  }

  function init(root) {
    all(root, "form[data-kind-form]").forEach(syncKind);
    all(root, "input[data-money]").forEach(function (input) { if (input.value) formatMoney(input); });
    all(root, "[data-unit-switch]").forEach(function (box) {
      var saved = null;
      try { saved = localStorage.getItem("networth-unit"); } catch (err) { /* حالت خصوصی */ }
      var button = saved && box.querySelector('[data-set-unit="' + saved + '"]:not([disabled])');
      if (button) setUnit(box, saved);
    });
    all(root, "canvas[data-trend]").forEach(drawTrend);
  }

  function start() {
    if (window.htmx) htmx.onLoad(init); else init(document);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
