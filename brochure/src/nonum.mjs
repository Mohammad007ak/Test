// "No figures" variant of the Bank Tejarat edition (node build.mjs --nonum).
// Strips business metrics (users, points of sale, credit volume, amounts in toman,
// headcounts in examples) from the rendered HTML. Installment structure (1 & 4
// installments, 12–24 month terms) is kept because it defines the products.

const phrase = [
  // stats & network
  ["حدود ۴۰ هزار نقطه فروش آنلاین و حضوری در سراسر کشور", "شبکه گسترده نقاط فروش آنلاین و حضوری در سراسر کشور"],
  ["حدود ۴۰ هزار نقطه فروش آنلاین و حضوری طرف قرارداد دیجی‌پی برای خرید کارکنان", "شبکه گسترده نقاط فروش آنلاین و حضوری طرف قرارداد دیجی‌پی برای خرید کارکنان"],
  ["شبکه ۴۰ هزار نقطه فروش دیجی‌پی", "شبکه گسترده نقاط فروش دیجی‌پی"],
  ["حدود ۴۰ هزار نقطه فروش", "شبکه گسترده نقاط فروش"],
  ["۱۵ میلیون تنوع کالا و خدمت در ۱۲ گروه اصلی", "تنوع گسترده کالا و خدمت در همه گروه‌های اصلی"],
  ["دسترسی به بیش از ۱۲ میلیون کاربر دیجی‌پی", "دسترسی به میلیون‌ها کاربر دیجی‌پی"],
  // product amounts
  ["اعتبار بانکی ۱۲ تا ۲۴ ماهه برای کالای مورد نیاز", "اعتبار بانکی بلندمدت برای کالای مورد نیاز"],
  ["وام خرید کالا با اقساط ۱۲ و ۲۴ ماهه", "وام بلندمدت خرید کالا"],
  ["، تا سقف ۴۰۰ میلیون تومان", ""],
  ["کالاهای بالای ۱۰ میلیون تومان", "کالاهای گران‌قیمت"],
  // headcounts in signals & examples
  ["۲۰ تا ۲۰۰ نفر نیروی ثابت با واریز حقوق از بانک تجارت", "نیروی ثابت با واریز حقوق از بانک تجارت"],
  ["۲۰ تا ۲۰۰ نفر نیروی ثابت", "نیروی ثابت و حقوق‌بگیر"],
  ["بیش از ۱۰۰ نفر کارمند و حساب حقوق نزد بانک تجارت", "تعداد قابل‌توجه کارمند و حساب حقوق نزد بانک تجارت"],
  ["شرکت یا سازمانی با بیش از ۵۰ نفر حساب حقوق در شعبه", "شرکت یا سازمانی با حساب‌های حقوق متعدد در شعبه"],
  ["شرکت تولیدی با ۲٬۰۰۰ کارمند", "شرکت تولیدی بزرگ"],
  ["رستوران زنجیره‌ای با ۶۰ نفر پرسنل", "رستوران زنجیره‌ای"],
  ["شرکت نرم‌افزاری ۸۰ نفره", "شرکت نرم‌افزاری"],
  ["دانشگاه با ۱٬۵۰۰ عضو هیئت‌علمی و کارمند", "دانشگاه بزرگ"],
  ["کارخانه مواد غذایی با ۱۵۰ کارگر", "کارخانه مواد غذایی"],
  ["بیمارستان با ۶۰۰ پرسنل", "بیمارستان بزرگ"],
];

export function stripNumbers(html) {
  for (const [a, b] of phrase) html = html.split(a).join(b);
  // big-number boxes on photos and the network map
  html = html.replace(/<div class="statbox"[^>]*><div class="big">[^<]*<\/div><div class="lbl">[^<]*<\/div><\/div>/g, "");
  // headline stats band -> qualitative claims
  html = html.replace(/<div class="statband"([^>]*)>(?:<div class="s">[\s\S]*?<\/div>)+<\/div>/, (_m, attrs) =>
    `<div class="statband words"${attrs}>${[
      ["نخستین", "فناوری مالی<br>جامع در ایران"],
      ["میلیون‌ها", "کاربر فعال<br>در سراسر کشور"],
      ["یک دهه", "سابقه فعالیت<br>در صنعت پرداخت و اعتبار"],
    ].map(([n, t]) => `<div class="s"><span class="n">${n}</span><span class="t">${t}</span></div>`).join("")}</div>`);
  // "15 million products" block on the glance page
  html = html.replace(/<div style="font-family:Outfit;font-weight:600;font-size:34pt;color:var\(--navy\);line-height:1">15<\/div>\s*<div[^>]*>میلیون تنوع<br>کالا و خدمت<\/div>/,
    `<div style="font-size:10pt;font-weight:700;color:var(--navy);line-height:1.7">تنوع گسترده کالا و خدمت در همه گروه‌های اصلی</div>`);
  // offer cards: money amounts -> product type
  html = html.replace(/تا <b>۳۰۰ میلیون<\/b> تومان/g, "اعتبار <b>چهار قسطه</b>")
    .replace(/تا <b>۳۰ میلیون<\/b> تومان/g, "اعتبار <b>ماهانه</b>")
    .replace(/تا <b>۲۰۰ میلیون<\/b> تومان/g, "وام بانکی <b>کوتاه‌مدت</b>")
    .replace(/تا <b>۴۰۰ میلیون<\/b> تومان/g, "وام بانکی <b>بلندمدت</b>");
  return html;
}
