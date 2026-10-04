package ir.getvazir.app;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.provider.Telephony;
import android.telephony.SmsMessage;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * پیامک تازه: فقط اگر اپ به حساب وصل باشد و پیامک بانکی (نه شخصی، نه رمز و کد) باشد،
 * نسخه پوشانده‌شده‌اش فرستاده می‌شود. متن خام هیچ‌جا ذخیره یا ارسال نمی‌شود.
 */
public class SmsReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (!Telephony.Sms.Intents.SMS_RECEIVED_ACTION.equals(intent.getAction())) {
            return;
        }
        final String token = SmsUploader.token(context);
        if (token == null) {
            return;
        }
        SmsMessage[] parts = Telephony.Sms.Intents.getMessagesFromIntent(intent);
        if (parts == null || parts.length == 0) {
            return;
        }
        // پیامک‌های چندتکه یک فرستنده به هم چسبانده می‌شوند
        Map<String, StringBuilder> bodies = new LinkedHashMap<>();
        Map<String, Long> times = new LinkedHashMap<>();
        for (SmsMessage part : parts) {
            String from = part.getDisplayOriginatingAddress();
            if (from == null) {
                continue;
            }
            StringBuilder body = bodies.get(from);
            if (body == null) {
                body = new StringBuilder();
                bodies.put(from, body);
                times.put(from, part.getTimestampMillis());
            }
            body.append(part.getDisplayMessageBody());
        }
        final List<JSONObject> fresh = new ArrayList<>();
        for (Map.Entry<String, StringBuilder> entry : bodies.entrySet()) {
            String body = entry.getValue().toString();
            if (!SmsText.isBankMessage(entry.getKey(), body)) {
                continue;
            }
            try {
                JSONObject item = new JSONObject();
                item.put("text", SmsText.prepare(body));
                item.put("received_at", SmsUploader.isoUtc(times.get(entry.getKey())));
                fresh.add(item);
            } catch (JSONException ignored) {
                // پیامک نامعتبر نادیده گرفته می‌شود
            }
        }
        if (fresh.isEmpty()) {
            return;
        }
        final Context app = context.getApplicationContext();
        final PendingResult pending = goAsync();
        new Thread(() -> {
            try {
                SmsUploader.enqueueAndFlush(app, token, fresh);
            } finally {
                pending.finish();
            }
        }).start();
    }
}
