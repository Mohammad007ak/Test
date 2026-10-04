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

  // ---------- خطای درخواست: به‌جای اینکه هیچ اتفاقی نیفتد، پیام کوتاه ----------
  function showToast(message) {
    var old = document.querySelector(".toast");
    if (old) old.remove();
    var toast = document.createElement("div");
    toast.className = "toast";
    toast.setAttribute("role", "status");
    toast.textContent = message;
    (document.querySelector(".screen") || document.body).appendChild(toast);
    setTimeout(function () { toast.remove(); }, 3000);
  }

  function requestFailed(e) {
    if (e.detail.elt && e.detail.elt.id === "live") return; // تازه‌سازی پس‌زمینه بی‌صدا
    showToast(document.body.getAttribute("data-error-message"));
  }
  document.addEventListener("htmx:responseError", requestFailed);
  document.addEventListener("htmx:sendError", requestFailed);

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
          x: { reverse: false, grid: { display: false }, ticks: { maxTicksLimit: 4, maxRotation: 0 } },
          y: { position: "right", grid: { color: grid }, border: { display: false },
            ticks: { maxTicksLimit: 4, callback: function (v) { return compact.format(v); } } }
        }
      }
    });
  }

  // ---------- شمارش عدد درشت از صفر تا مقدار (فقط بار اول، نه تازه‌سازی خودکار) ----------
  function countUp(el) {
    var number = el.querySelector(".amt") ? el.querySelector(".amt").firstChild : null;
    if (!number || number.nodeType !== 3) return;
    var text = number.textContent.trim();
    var latin = toLatin(text).replace(/[٬,]/g, "").replace("٫", ".");
    var target = Number(latin);
    if (!isFinite(target) || target === 0) return;
    var places = (latin.split(".")[1] || "").length;
    var fmt = new Intl.NumberFormat("fa-IR", { minimumFractionDigits: places, maximumFractionDigits: places });
    var start = null;
    var duration = 1100;
    function frame(now) {
      if (start === null) start = now;
      var p = Math.min((now - start) / duration, 1);
      var eased = 1 - Math.pow(2, -10 * p);
      number.textContent = p < 1 ? fmt.format(target * eased) : text;
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  // تازه‌سازی خودکار داشبورد: بدون انیمیشن ورود دوباره
  document.addEventListener("htmx:beforeSwap", function (e) {
    if (e.detail.target && e.detail.target.id === "live" && e.detail.serverResponse) {
      e.detail.serverResponse = e.detail.serverResponse.replace('class="live"', 'class="live refreshed"');
    }
  });

  // ---------- ظاهر: خودکار (طبق سیستم)، روشن یا تیره ----------
  var systemLight = window.matchMedia("(prefers-color-scheme: light)");

  function themeChoice() {
    try { return localStorage.getItem("theme") || "system"; } catch (err) { return "system"; }
  }

  function applyTheme() {
    var choice = themeChoice();
    var dark = choice === "dark" || (choice === "system" && !systemLight.matches);
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", getComputedStyle(document.documentElement).getPropertyValue("--bg").trim());
    document.querySelectorAll("[data-set-theme]").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-set-theme") === choice));
    });
  }

  systemLight.addEventListener("change", applyTheme);
  document.addEventListener("click", function (e) {
    var button = e.target.closest("[data-set-theme]");
    if (!button) return;
    try { localStorage.setItem("theme", button.getAttribute("data-set-theme")); } catch (err) { /* حالت خصوصی */ }
    applyTheme();
  });

  // ---------- چت «از وزیر بپرس»: پرسش فوری روی صفحه، نقطه‌های «در حال نوشتن»، اسکرول خودکار ----------
  function initChat(app) {
    if (app.dataset.ready) return;
    app.dataset.ready = "1";
    var scroll = app.querySelector("#chat-scroll");
    var log = app.querySelector("#chat-log");
    var form = app.querySelector("#chat-form");
    if (!form) return;  // هنوز رضایت نداده
    var box = form.querySelector("textarea");
    var send = form.querySelector(".chat-send");
    var busy = false;
    var image = null;  // عکس کوچک‌شده آماده ارسال (Blob)
    var fileInput = form.querySelector("[data-image-input]");
    var preview = app.querySelector("[data-preview]");

    function toBottom(smooth) {
      scroll.scrollTo({ top: scroll.scrollHeight, behavior: smooth ? "smooth" : "auto" });
    }
    function grow() {
      box.style.height = "auto";
      box.style.height = Math.min(box.scrollHeight, 140) + "px";
      send.disabled = busy || (!box.value.trim() && !image);
    }
    // عکس در مرورگر کوچک و دوباره JPEG می‌شود: حجم کم‌تر و حذف EXIF (مثل مکان عکس)
    function shrink(file, done) {
      var url = URL.createObjectURL(file);
      var img = new Image();
      img.onload = function () {
        var scale = Math.min(1, 1600 / Math.max(img.width, img.height));
        var c = document.createElement("canvas");
        c.width = Math.round(img.width * scale); c.height = Math.round(img.height * scale);
        c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
        URL.revokeObjectURL(url);
        c.toBlob(function (blob) { done(blob); }, "image/jpeg", 0.85);
      };
      img.onerror = function () { URL.revokeObjectURL(url); done(null); };
      img.src = url;
    }
    function setImage(blob) {
      image = blob;
      if (preview) {
        preview.hidden = !blob;
        var thumb = preview.querySelector("img");
        if (thumb.src) URL.revokeObjectURL(thumb.src);
        thumb.src = blob ? URL.createObjectURL(blob) : "";
      }
      if (!blob && fileInput) fileInput.value = "";
      grow();
    }
    if (fileInput) fileInput.addEventListener("change", function () {
      var file = fileInput.files && fileInput.files[0];
      if (file) shrink(file, setImage);
    });
    if (preview) preview.querySelector("[data-remove-image]").addEventListener("click", function () { setImage(null); });
    function row(who, child) {
      var r = document.createElement("div");
      r.className = "chat-row " + who;
      r.appendChild(child);
      log.appendChild(r);
      return r;
    }
    function message(who, text) {
      var m = document.createElement("div");
      m.className = "chat-msg " + who;
      m.textContent = text;
      return row(who, m);
    }
    function ask(text) {
      if ((!text && !image) || busy) return;
      busy = true;
      var sending = image;
      var hello = log.querySelector(".chat-hello");
      if (hello) hello.remove();
      log.querySelectorAll(".chat-chips, .quick-link").forEach(function (el) { el.remove(); });
      var mine = message("me", text);
      if (sending) {
        var pic = document.createElement("img");
        pic.className = "chat-photo";
        pic.alt = "";
        pic.src = URL.createObjectURL(sending);
        mine.querySelector(".chat-msg").prepend(pic);
        setImage(null);
      }
      var dots = document.createElement("div");
      dots.className = "chat-msg vazir typing";
      dots.innerHTML = "<i></i><i></i><i></i>";
      var typing = row("vazir", dots);
      box.value = "";
      grow();
      toBottom(true);
      var data = new FormData();
      data.append("question", text);
      if (sending) data.append("image", sending, "photo.jpg");
      fetch(form.action, { method: "POST", body: data, credentials: "same-origin",
                           headers: { "HX-Request": "true" } })
        .then(function (r) {
          if (r.redirected) { window.location.href = r.url; return null; }
          return r.text();
        })
        .catch(function () { return ""; })
        .then(function (html) {
          if (html === null) return;
          typing.remove();
          if (html && html.trim()) log.insertAdjacentHTML("beforeend", html);
          else message("vazir error", app.getAttribute("data-error"));
          busy = false;
          grow();
          toBottom(true);
        });
    }

    form.addEventListener("submit", function (e) { e.preventDefault(); ask(box.value.trim()); });
    box.addEventListener("input", grow);
    box.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing && window.matchMedia("(hover: hover)").matches) {
        e.preventDefault();
        ask(box.value.trim());
      }
    });
    app.addEventListener("click", function (e) {
      var starter = e.target.closest("[data-ask]");
      if (starter) ask(starter.getAttribute("data-ask"));
      var all = e.target.closest("[data-confirm-all]");
      if (all) {
        all.disabled = true;
        var ids = all.getAttribute("data-confirm-all").split(",");
        var body = new FormData();
        body.append("ids", ids.join(","));
        fetch("/assistant/actions-all", { method: "POST", body: body, credentials: "same-origin",
                                          headers: { "HX-Request": "true" } })
          .then(function (r) { return r.ok ? r.text() : ""; })
          .catch(function () { return ""; })
          .then(function (html) {
            if (!html) { all.disabled = false; return; }
            ids.forEach(function (id) {
              var card = log.querySelector('[data-action="' + id + '"]');
              if (card) card.closest(".chat-row").remove();
            });
            all.outerHTML = html;
          });
        return;
      }
      var button = e.target.closest("[data-action-do]");
      if (!button) return;
      var card = button.closest("[data-action]");
      card.querySelectorAll("button").forEach(function (b) { b.disabled = true; });
      fetch("/assistant/actions/" + card.getAttribute("data-action") + "/" +
            button.getAttribute("data-action-do"),
            { method: "POST", credentials: "same-origin", headers: { "HX-Request": "true" } })
        .then(function (r) { return r.ok || r.status === 400 ? r.text() : ""; })
        .catch(function () { return ""; })
        .then(function (html) {
          if (html) card.outerHTML = html;
          else card.querySelectorAll("button").forEach(function (b) { b.disabled = false; });
        });
    });
    grow();
    toBottom(false);
  }

  // ---------- راه‌اندازی هر محتوای تازه (بار اول و پس از هر جابه‌جایی htmx) ----------
  // مصاحبه پرسونا: سؤال‌ها یکی‌یکی، مثل گفتگو با وزیر؛ بدون جاوااسکریپت همه با هم دیده می‌شوند
  function initInterview(app) {
    if (app.dataset.ready) return;
    app.dataset.ready = "1";
    app.classList.add("js");
    var scroll = app.querySelector(".chat-scroll");
    var steps = Array.prototype.slice.call(app.querySelectorAll(".q"));
    var bar = app.querySelector(".interview-progress span");
    var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function checked(step) { return Array.prototype.slice.call(step.querySelectorAll("input:checked")); }
    function toBottom() { scroll.scrollTo({ top: scroll.scrollHeight, behavior: reduced ? "auto" : "smooth" }); }
    function progress() {
      var done = steps.filter(function (s) { return s.classList.contains("answered"); }).length;
      if (bar) bar.style.setProperty("--p", Math.round(done / (steps.length - 1) * 100) + "%");
    }
    function answer(step) {
      var labels = checked(step).map(function (input) { return input.nextElementSibling.textContent; });
      step.querySelector(".q-answer .chat-msg").textContent = labels.join("، ") || app.dataset.none;
      step.classList.add("answered");
      progress();
    }
    function reveal(index) {
      var step = steps[index];
      if (!step || step.classList.contains("shown")) return;
      if (reduced) { step.classList.add("shown"); toBottom(); return; }
      var typing = document.createElement("div");
      typing.className = "chat-row vazir";
      typing.innerHTML = '<div class="chat-msg vazir typing"><i></i><i></i><i></i></div>';
      step.parentNode.insertBefore(typing, step);
      toBottom();
      setTimeout(function () { typing.remove(); step.classList.add("shown"); toBottom(); }, 550);
    }

    // پاسخ‌های قبلی (دوباره جواب دادن) همه باز می‌مانند تا هر کدام با یک ضربه عوض شود
    for (var i = 0; i < steps.length; i++) {
      var step = steps[i];
      step.classList.add("shown");
      if (step.hasAttribute("data-final")) break;
      if (!checked(step).length) break;
      answer(step);
    }
    progress();

    app.addEventListener("change", function (e) {
      var step = e.target.closest(".q");
      if (!step || e.target.type !== "radio") return;
      answer(step);
      setTimeout(function () { reveal(steps.indexOf(step) + 1); }, reduced ? 0 : 180);
    });
    app.addEventListener("click", function (e) {
      var next = e.target.closest("[data-next]");
      if (next) {
        var step = next.closest(".q");
        answer(step);
        reveal(steps.indexOf(step) + 1);
        return;
      }
      var edit = e.target.closest("[data-edit]");
      if (edit) edit.closest(".q").classList.remove("answered");
    });
  }

  // کارت شخصیت با حرکت انگشت یا موشواره کمی می‌چرخد و فویلش برق می‌زند
  document.addEventListener("pointermove", function (e) {
    var card = e.target.closest && e.target.closest("[data-tilt]");
    if (!card || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    var box = card.getBoundingClientRect();
    var x = (e.clientX - box.left) / box.width, y = (e.clientY - box.top) / box.height;
    card.classList.add("tilting");
    card.style.setProperty("--ry", ((x - .5) * 14).toFixed(2) + "deg");
    card.style.setProperty("--rx", ((.5 - y) * 12).toFixed(2) + "deg");
    card.style.setProperty("--mx", (x * 100).toFixed(1) + "%");
    card.style.setProperty("--my", (y * 100).toFixed(1) + "%");
  });
  ["pointerleave", "pointerup", "pointercancel"].forEach(function (type) {
    document.addEventListener(type, function (e) {
      var card = e.target.closest && e.target.closest("[data-tilt]");
      if (!card) return;
      card.classList.remove("tilting");
      card.style.setProperty("--rx", "0deg");
      card.style.setProperty("--ry", "0deg");
    }, true);
  });

  // ---------- نمودار قیمت با بازه‌های هفته تا پنج سال ----------
  function drawPriceChart(box) {
    if (!window.Chart || box.dataset.drawn) return;
    var canvas = box.querySelector("canvas");
    if (!canvas) return;
    box.dataset.drawn = "1";
    var raw = JSON.parse(box.getAttribute("data-price-chart"));
    var days = raw.d.map(function (d) { return new Date(d + "T12:00:00"); });
    var css = getComputedStyle(document.documentElement);
    var good = css.getPropertyValue("--good").trim(), bad = css.getPropertyValue("--bad").trim();
    var muted = css.getPropertyValue("--muted").trim(), grid = css.getPropertyValue("--border").trim();
    var compact = new Intl.NumberFormat("fa-IR", { notation: "compact", maximumFractionDigits: 2 });
    // بازه کوتاه: روز و ماه؛ بازه بلند: ماه و سال (برچسب‌ها روی هم نیفتند)
    var dayFmt = new Intl.DateTimeFormat("fa-IR", { month: "short", day: "numeric" });
    var monthFmt = new Intl.DateTimeFormat("fa-IR", { month: "short", year: "2-digit" });
    var pct = new Intl.NumberFormat("fa-IR", { style: "percent", maximumFractionDigits: 1, signDisplay: "exceptZero" });
    var label = box.querySelector("[data-range-change]");
    Chart.defaults.font.family = "Vazirmatn";
    Chart.defaults.color = muted;
    var chart = new Chart(canvas, {
      type: "line",
      data: { labels: [], datasets: [{ data: [], borderWidth: 2, tension: .25, pointRadius: 0,
        pointHoverRadius: 4, pointHitRadius: 16, fill: true }] },
      options: {
        maintainAspectRatio: false, animation: { duration: 350 },
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { display: false }, tooltip: { rtl: true, displayColors: false, callbacks: {
          label: function (c) { return compact.format(c.raw) + " تومان"; } } } },
        scales: {
          x: { reverse: false, grid: { display: false }, ticks: { maxTicksLimit: 4, maxRotation: 0 } },
          y: { position: "right", grid: { color: grid }, border: { display: false },
            ticks: { maxTicksLimit: 4, callback: function (v) { return compact.format(v); } } }
        }
      }
    });
    function show(range) {
      var last = days[days.length - 1];
      var from = new Date(last.getTime() - range * 86400000);
      var start = days.findIndex(function (d) { return d >= from; });
      if (start < 0) start = 0;
      var fmt = range > 91 ? monthFmt : dayFmt;
      var values = raw.v.slice(start), labels = days.slice(start).map(function (d) { return fmt.format(d); });
      var up = values[values.length - 1] >= values[0];
      var color = up ? good : bad;
      var ctx = canvas.getContext("2d");
      var fill = ctx.createLinearGradient(0, 0, 0, canvas.clientHeight || 220);
      fill.addColorStop(0, color + "40"); fill.addColorStop(1, color + "00");
      var ds = chart.data.datasets[0];
      ds.data = values; ds.borderColor = color; ds.backgroundColor = fill;
      chart.data.labels = labels;
      chart.update();
      if (label && values.length > 1) {
        label.textContent = pct.format((values[values.length - 1] - values[0]) / values[0]);
        label.className = up ? "up" : "down";
      }
      box.querySelectorAll("[data-range]").forEach(function (b) {
        b.setAttribute("aria-selected", b.getAttribute("data-range") === String(range) ? "true" : "false");
      });
    }
    var span = (days[days.length - 1] - days[0]) / 86400000;
    box.querySelectorAll("[data-range]").forEach(function (b) {
      var range = Number(b.getAttribute("data-range"));
      // بازه‌ای که داده‌اش نیست (مثلاً ۵ سال برای رمزارز) غیرفعال می‌شود، مگر کوچک‌ترین بازه
      if (range > 7 && span < range * 0.6) b.disabled = true;
      b.addEventListener("click", function () { show(range); });
    });
    var initial = span >= 30 * 0.6 ? 30 : 7;
    show(initial);
  }

  // ---------- صفحه معرفی: ظاهر شدن با اسکرول، متن تایپی، گفتگوی نمایشی، نور روی کارت‌ها ----------
  function initLanding(root) {
    if (root.dataset.ready) return;
    root.dataset.ready = "1";
    var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    root.classList.add("js");
    var items = root.querySelectorAll("[data-reveal]");
    if ("IntersectionObserver" in window && !reduced) {
      var seen = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          var el = entry.target;
          var siblings = Array.prototype.indexOf.call(el.parentNode.children, el);
          setTimeout(function () { el.classList.add("in"); }, Math.min(siblings, 6) * 90);
          seen.unobserve(el);
        });
      }, { threshold: 0.15 });
      items.forEach(function (el) { seen.observe(el); });
    } else {
      items.forEach(function (el) { el.classList.add("in"); });
    }

    root.addEventListener("pointermove", function (e) {
      var card = e.target.closest && e.target.closest("[data-spot]");
      if (!card) return;
      var box = card.getBoundingClientRect();
      card.style.setProperty("--mx", (e.clientX - box.left) + "px");
      card.style.setProperty("--my", (e.clientY - box.top) + "px");
    });

    var typed = root.querySelector("[data-typed]");
    if (typed && !reduced) {
      var phrases = JSON.parse(typed.getAttribute("data-typed"));
      // عبارت اول کامل دیده می‌شود، بعد پاک و عبارت بعدی تایپ می‌شود
      var p = 0, c = phrases[0].length, deleting = true;
      var tick = function () {
        var text = phrases[p];
        if (deleting) {
          c -= 1;
          typed.textContent = "«" + text.slice(0, c);
          if (c <= 0) { deleting = false; p = (p + 1) % phrases.length; setTimeout(tick, 300); return; }
          setTimeout(tick, 25);
          return;
        }
        c += 1;
        var done = c >= text.length;
        typed.textContent = "«" + text.slice(0, c) + (done ? "»" : "");
        if (done) { deleting = true; setTimeout(tick, 2400); return; }
        setTimeout(tick, 55);
      };
      setTimeout(tick, 2400);
    }

    var chat = root.querySelector("[data-demo]");
    if (chat) playDemo(chat, JSON.parse(chat.getAttribute("data-demo")), reduced);
  }

  function playDemo(chat, steps, reduced) {
    function bubble(step) {
      var m = document.createElement("div");
      m.className = "lx-msg " + step.who;
      m.textContent = step.text;
      if (step.bars) {
        var bars = document.createElement("div");
        bars.className = "lx-bars";
        step.bars.forEach(function (b) {
          var row = document.createElement("div");
          var name = document.createElement("span");
          name.textContent = b[0];
          var bar = document.createElement("i");
          row.appendChild(name); row.appendChild(bar); bars.appendChild(row);
          setTimeout(function () { bar.style.width = b[1] + "%"; }, 60);
        });
        m.appendChild(bars);
      }
      if (step.card) {
        var card = document.createElement("div");
        card.className = "lx-msg-card";
        card.textContent = step.card;
        m.appendChild(card);
      }
      return m;
    }
    function trim() { while (chat.children.length > 5) chat.removeChild(chat.firstChild); }
    if (reduced) { steps.slice(-3).forEach(function (s) { chat.appendChild(bubble(s)); }); return; }
    var i = 0;
    (function next() {
      if (i >= steps.length) {
        setTimeout(function () { chat.innerHTML = ""; i = 0; next(); }, 3500);
        return;
      }
      var step = steps[i++];
      if (step.who === "vazir") {
        var dots = document.createElement("div");
        dots.className = "lx-msg vazir typing";
        dots.innerHTML = "<i></i><i></i><i></i>";
        chat.appendChild(dots); trim();
        setTimeout(function () { dots.replaceWith(bubble(step)); setTimeout(next, 2200); }, 1300);
      } else {
        chat.appendChild(bubble(step)); trim();
        setTimeout(next, 900);
      }
    })();
  }

  // ---------- نسخه نصبی (PWA): Service Worker، پاک کردن کش بعد از خروج، صفحه نصب ----------
  var installEvent = null;
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    installEvent = e;
    document.querySelectorAll("[data-install-button]").forEach(function (b) { b.hidden = false; });
  });
  function setupPwa() {
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(function () { /* اپ بدون SW هم کار می‌کند */ });
    // صفحه ورود یا معرفی یعنی کاربر وارد نیست؛ صفحه‌های کش‌شده حساب قبلی پاک شوند
    if (document.querySelector(".auth, #landing") && window.caches) caches.delete("vazir-pages");
  }
  function initInstall(root) {
    var ua = navigator.userAgent;
    var platform = /iPhone|iPad|iPod/.test(ua) ? "ios" : /Android/.test(ua) ? "android" : "desktop";
    var standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone;
    root.querySelectorAll("[data-platform]").forEach(function (card) {
      if (card.getAttribute("data-platform") === platform) card.parentNode.insertBefore(card, root.querySelector("[data-platform]"));
      card.classList.toggle("mine", card.getAttribute("data-platform") === platform);
    });
    if (standalone) root.querySelector("[data-installed]").hidden = false;
    if (installEvent) root.querySelectorAll("[data-install-button]").forEach(function (b) { b.hidden = false; });
    root.addEventListener("click", function (e) {
      if (!e.target.closest("[data-install-button]") || !installEvent) return;
      installEvent.prompt();
      installEvent.userChoice.then(function () { installEvent = null; });
    });
  }

  // ---------- ورود با چهره / اثر انگشت (WebAuthn) ----------
  function b64u(buf) {
    var s = "", bytes = new Uint8Array(buf);
    for (var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
    return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }
  function unb64u(text) {
    var s = atob(text.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((text.length + 3) % 4));
    var out = new Uint8Array(s.length);
    for (var i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
    return out.buffer;
  }
  function creationOptions(o) {
    o.challenge = unb64u(o.challenge);
    o.user.id = unb64u(o.user.id);
    (o.excludeCredentials || []).forEach(function (c) { c.id = unb64u(c.id); });
    return o;
  }
  function requestOptions(o) {
    o.challenge = unb64u(o.challenge);
    (o.allowCredentials || []).forEach(function (c) { c.id = unb64u(c.id); });
    return o;
  }
  function credentialJSON(cred) {
    var r = cred.response, response = { clientDataJSON: b64u(r.clientDataJSON) };
    if (r.attestationObject) {
      response.attestationObject = b64u(r.attestationObject);
      if (r.getTransports) response.transports = r.getTransports();
    } else {
      response.authenticatorData = b64u(r.authenticatorData);
      response.signature = b64u(r.signature);
      if (r.userHandle) response.userHandle = b64u(r.userHandle);
    }
    return { id: cred.id, rawId: b64u(cred.rawId), type: cred.type, response: response,
             clientExtensionResults: {}, authenticatorAttachment: cred.authenticatorAttachment || null };
  }
  function postJSON(url, body) {
    return fetch(url, { method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : "{}" })
      .then(function (r) { return r.json().then(function (j) { j.status = r.status; return j; }); });
  }
  function showError(box, message) {
    var el = box.querySelector("[data-passkey-error]");
    if (el) { el.textContent = message; el.hidden = !message; }
  }
  function initPasskeys(root) {
    var supported = !!window.PublicKeyCredential;
    all(root, "[data-passkey-login-box]").forEach(function (box) {
      if (!supported) return;
      box.hidden = false;
      box.querySelector("[data-passkey-login]").addEventListener("click", function () {
        showError(box, "");
        postJSON("/passkeys/login/options").then(function (o) {
          return navigator.credentials.get({ publicKey: requestOptions(o) });
        }).then(function (cred) {
          return postJSON("/passkeys/login/verify", credentialJSON(cred));
        }).then(function (res) {
          if (res.ok) window.location.href = res.next || "/";
          else showError(box, res.error || box.getAttribute("data-error"));
        }).catch(function () { showError(box, box.getAttribute("data-error")); });
      });
    });
    all(root, "#passkeys").forEach(function (box) {
      var button = box.querySelector("[data-passkey-register]");
      if (!supported) { button.disabled = true; showError(box, box.getAttribute("data-unsupported")); return; }
      button.addEventListener("click", function () {
        showError(box, "");
        button.disabled = true;
        postJSON("/passkeys/register/options").then(function (o) {
          return navigator.credentials.create({ publicKey: creationOptions(o) });
        }).then(function (cred) {
          return postJSON("/passkeys/register/verify", credentialJSON(cred));
        }).then(function (res) {
          if (res.ok) window.location.reload();
          else { showError(box, res.error || box.getAttribute("data-error")); button.disabled = false; }
        }).catch(function () { showError(box, box.getAttribute("data-error")); button.disabled = false; });
      });
    });
  }

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
    applyTheme();
    all(root, "canvas[data-trend]").forEach(drawTrend);
    all(root, "[data-price-chart]").forEach(drawPriceChart);
    all(root, "#chat-app").forEach(initChat);
    all(root, "#interview").forEach(initInterview);
    all(root, "#landing").forEach(initLanding);
    all(root, "#install").forEach(initInstall);
    initPasskeys(root);
    var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!reduced && !(root.id === "live")) all(root, "[data-countup]").forEach(countUp);
  }

  function start() {
    setupPwa();
    if (window.htmx) htmx.onLoad(init); else init(document);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
