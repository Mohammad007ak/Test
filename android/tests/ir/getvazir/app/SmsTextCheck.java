package ir.getvazir.app;

/**
 * بررسی SmsText بدون اندروید و بدون وابستگی (در CI با javac اجرا می‌شود).
 * خروجی‌های mask همان خروجی mask_numbers سرور (app/sms/text.py) برای همین ورودی‌هاست.
 */
public final class SmsTextCheck {
    private static int failures = 0;

    private static void mask(String in, String want) {
        String got = SmsText.prepare(in);
        if (!got.equals(want)) {
            failures++;
            System.out.println("MASK FAIL: " + in + "\n  got:  " + got + "\n  want: " + want);
        }
    }

    private static void bank(String from, String body, boolean want) {
        if (SmsText.isBankMessage(from, body) != want) {
            failures++;
            System.out.println("FILTER FAIL: " + from + " / " + body);
        }
    }

    public static void main(String[] args) {
        mask("کارت 6037-9918-1234-5678 برداشت 1,250,000 ریال مانده 4,500,000",
             "کارت ************5678 برداشت 1,250,000 ریال مانده 4,500,000");
        mask("حساب ۰۱۰۲۳۴۵۶۷۸۹۰۰۱ واریز ۲٬۰۰۰٬۰۰۰",
             "حساب 010*******9001 واریز 2٬000٬000");
        mask("شبا IR120170000000123456789012 انتقال",
             "شبا IR********************9012 انتقال");
        mask("حساب 123.456.7890123 برداشت",
             "حساب 123******0123 برداشت");
        mask("حساب‏ ‎0212345678‎ مانده",
             "حساب 021***5678 مانده");
        mask("مبلغ 50000 تاریخ 1405/07/13 ساعت 12:30",
             "مبلغ 50000 تاریخ 1405/07/13 ساعت 12:30");
        mask("کارت 6219861034567890",
             "کارت ************7890");
        mask("حساب 1234-5678-90 خرید",
             "حساب 1234**7890 خرید");
        bank("Bank Mellat", "برداشت 500,000 مانده 1,000,000", true);
        bank("9830003000", "خرید از کارت ۱۲۳۴ مبلغ ۲۰۰٬۰۰۰ ریال", true);
        bank("Saman", "واریز 1,000,000 به حساب", true);
        bank("Ayandeh", "انتقال ۵۰۰٬۰۰۰ ریال از حساب ۰۱۲۳ کد پیگیری ۸۸۹۹۰۰", true);
        bank("+989121234567", "حساب کن 200 تومن بهم بدهکاری", false);
        bank("09121234567", "واریز کردم 500", false);
        bank("۰۹۱۲۱۲۳۴۵۶۷", "واریز کردم ۵۰۰", false);
        bank("Digikala", "کد تخفیف شما", false);
        bank("Mellat", "رمز پویا کارت ۱۲۳۴: ۵۶۷۸۹۰ مبلغ خرید ۲۰۰٬۰۰۰", false);
        bank("Tejarat", "کد تایید انتقال وجه: 482913", false);
        bank("Melli", "Your OTP for card 1234 is 556677", false);
        bank("Sepah", "کد ورود به همراه بانک: 112233", false);
        if (failures > 0) {
            System.exit(1);
        }
        System.out.println("SmsText: all checks passed");
    }
}
