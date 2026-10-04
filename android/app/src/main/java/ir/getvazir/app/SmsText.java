package ir.getvazir.app;

import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * متن پیامک بانک روی خود گوشی: تشخیص پیامک بانکی و پوشاندن شماره‌ها پیش از ارسال.
 * همان قاعده سرور (app/sms/text.py): کارت و شبا فقط ۴ رقم آخر؛ حساب ابتدای شماره + ۴ رقم آخر.
 * بدون وابستگی به اندروید تا جدا تست شود.
 */
final class SmsText {
    static final int MIN_MASKED_DIGITS = 10;
    static final int CARD_DIGITS = 16;
    static final int PREFIX_MAX = 4;
    private static final Pattern NUMBER_RUN = Pattern.compile("\\d(?:\\d|[-. ](?=\\d))*\\d");
    private static final Pattern SEPARATOR = Pattern.compile("[-. ]");
    private static final String BIDI = "‎‏‪‫‬‭‮⁦⁧⁨⁩﻿";
    /** واژه‌هایی که پیامک تراکنش بانکی تقریباً همیشه دارد. */
    private static final String[] KEYWORDS = {
        "مانده", "برداشت", "واریز", "انتقال", "خرید", "حساب", "کارت", "بانک", "ریال", "موجودی"
    };

    /** پیامک رمز و کد (رمز پویا، کد تأیید) هرگز از گوشی بیرون نمی‌رود، حتی از طرف بانک. */
    private static final String[] SECRETS = {
        "رمز", "پویا", "کد تایید", "کد تأیید", "کد ورود", "کد امنیتی", "کد یکبار", "کد یک‌بار",
        "کد فعال", "otp", "password", "verification", "cvv"
    };

    private SmsText() {}

    /** ارقام فارسی و عربی به لاتین، حذف نویسه‌های نامرئی جهت متن. */
    static String normalize(String raw) {
        StringBuilder out = new StringBuilder(raw.length());
        for (int i = 0; i < raw.length(); i++) {
            char c = raw.charAt(i);
            if (c >= '۰' && c <= '۹') {
                out.append((char) ('0' + (c - '۰')));
            } else if (c >= '٠' && c <= '٩') {
                out.append((char) ('0' + (c - '٠')));
            } else if (BIDI.indexOf(c) < 0) {
                out.append(c);
            }
        }
        return out.toString();
    }

    static String accountPrefix(String raw) {
        String first = SEPARATOR.split(raw, 2)[0];
        if (first.length() <= PREFIX_MAX && !first.equals(raw)) {
            return first;
        }
        String digits = raw.replaceAll("\\D", "");
        return digits.substring(0, Math.min(3, digits.length()));
    }

    static String maskNumbers(String text) {
        Matcher m = NUMBER_RUN.matcher(text);
        StringBuilder out = new StringBuilder();
        while (m.find()) {
            String raw = m.group();
            String digits = raw.replaceAll("\\D", "");
            String replacement = raw;
            if (digits.length() >= MIN_MASKED_DIGITS) {
                String prefix = digits.length() >= CARD_DIGITS ? "" : accountPrefix(raw);
                int stars = digits.length() - prefix.length() - 4;
                replacement = prefix + "*".repeat(Math.max(stars, 0)) + digits.substring(digits.length() - 4);
            }
            m.appendReplacement(out, Matcher.quoteReplacement(replacement));
        }
        m.appendTail(out);
        return out.toString();
    }

    /** متنی که از گوشی بیرون می‌رود: فقط نسخه پوشانده‌شده. */
    static String prepare(String raw) {
        return maskNumbers(normalize(raw)).trim();
    }

    /**
     * پیامک بانکی است؟ فرستنده شماره موبایل شخصی نباشد و متن واژه بانکی و عدد داشته باشد.
     * پیامک شخصی هرگز ارسال نمی‌شود.
     */
    static boolean isBankMessage(String sender, String body) {
        if (sender == null || body == null) {
            return false;
        }
        String from = normalize(sender).replace(" ", "").toLowerCase(Locale.ROOT);
        if (from.matches("^(\\+98|0098|98|0)?9[0-39]\\d{8}$")) {
            return false;
        }
        String text = normalize(body);
        if (!text.matches("(?s).*\\d.*")) {
            return false;
        }
        String lower = text.toLowerCase(Locale.ROOT);
        for (String secret : SECRETS) {
            if (lower.contains(secret)) {
                return false;
            }
        }
        for (String word : KEYWORDS) {
            if (text.contains(word)) {
                return true;
            }
        }
        return false;
    }
}
