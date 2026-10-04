package ir.getvazir.app;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;
import java.util.regex.Pattern;

/**
 * توکن اتصال و صف ارسال پیامک‌های بانکی (فقط متن پوشانده‌شده) به سرور وزیر.
 * اگر اینترنت نبود، تا ۵۰ پیامک در صف می‌ماند و با پیامک بعدی دوباره فرستاده می‌شود.
 */
final class SmsUploader {
    private static final String PREFS = "vazir_sms";
    private static final String KEY_TOKEN = "token";
    private static final String KEY_QUEUE = "queue";
    private static final int MAX_QUEUE = 50;
    private static final int TIMEOUT_MS = 15000;
    static final Pattern TOKEN = Pattern.compile("^[A-Za-z0-9_-]{16,64}$");

    private SmsUploader() {}

    private static SharedPreferences prefs(Context ctx) {
        return ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    static String token(Context ctx) {
        return prefs(ctx).getString(KEY_TOKEN, null);
    }

    static void saveToken(Context ctx, String token) {
        prefs(ctx).edit().putString(KEY_TOKEN, token).remove(KEY_QUEUE).apply();
    }

    static void clear(Context ctx) {
        prefs(ctx).edit().clear().apply();
    }

    static String isoUtc(long millis) {
        SimpleDateFormat f = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.ROOT);
        f.setTimeZone(TimeZone.getTimeZone("UTC"));
        return f.format(new Date(millis));
    }

    /** پیامک‌های تازه را به صف اضافه و کل صف را ارسال می‌کند (در رشته پس‌زمینه صدا زده شود). */
    static synchronized void enqueueAndFlush(Context ctx, String token, List<JSONObject> fresh) {
        JSONArray queue = loadQueue(ctx);
        for (JSONObject item : fresh) {
            queue.put(item);
        }
        while (queue.length() > MAX_QUEUE) {
            queue.remove(0);
        }
        String endpoint = "https://" + ctx.getString(R.string.host_name) + "/api/sms";
        JSONArray left = new JSONArray();
        boolean stop = false;
        for (int i = 0; i < queue.length(); i++) {
            JSONObject item = queue.optJSONObject(i);
            if (item == null) {
                continue;
            }
            if (stop) {
                left.put(item);
                continue;
            }
            int status = post(endpoint, token, item);
            if (status == 401) {  // توکن در سایت عوض شده یا حساب حذف شده: اتصال قطع
                clear(ctx);
                return;
            }
            if (status == 429 || status < 0 || status >= 500) {  // بعداً دوباره
                left.put(item);
                stop = true;
            }
        }
        prefs(ctx).edit().putString(KEY_QUEUE, left.toString()).apply();
    }

    private static JSONArray loadQueue(Context ctx) {
        try {
            return new JSONArray(prefs(ctx).getString(KEY_QUEUE, "[]"));
        } catch (JSONException e) {
            return new JSONArray();
        }
    }

    private static int post(String endpoint, String token, JSONObject item) {
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(endpoint).openConnection();
            conn.setRequestMethod("POST");
            conn.setConnectTimeout(TIMEOUT_MS);
            conn.setReadTimeout(TIMEOUT_MS);
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            conn.setRequestProperty("X-Ingest-Token", token);
            byte[] body = item.toString().getBytes(StandardCharsets.UTF_8);
            try (OutputStream out = conn.getOutputStream()) {
                out.write(body);
            }
            return conn.getResponseCode();
        } catch (Exception e) {
            return -1;
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }
}
