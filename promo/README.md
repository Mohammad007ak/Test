# تیزر تبلیغاتی دیجی قرض

یک موشن‌گرافی ۶۰ ثانیه‌ای عمودی (۱۰۸۰×۱۹۲۰) با همان آدمک‌های سکه‌ای اپ.
همه‌ی حرکت‌ها انیمیشن CSS روی یک خط زمانی‌اند؛ صفحه فریم‌به‌فریم گرفته و با
ffmpeg به MP4 تبدیل می‌شود. موسیقی و افکت‌ها با `music.py` از صفر ساخته
می‌شوند (بدون نمونه‌ی صوتی یا موسیقی دارای حق نشر).

```sh
node promo/build.mjs          # promo.html  (متن زیرنویس‌ها و صحنه‌ها این‌جاست)
python3 promo/music.py        # music.wav   (نیاز به numpy)
FFMPEG=/path/to/ffmpeg node promo/render.mjs   # digigharz-promo.mp4 (نیاز به playwright)
```
