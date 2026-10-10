package ir.getvazir.app;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.text.InputFilter;
import android.text.InputType;
import android.view.Gravity;
import android.widget.EditText;
import android.widget.Toast;

/**
 * اتصال پیامک بانکی به حساب وزیر، فقط با تأیید کاربر:
 * سایت لینک intent://pair?token=…&account=… را باز می‌کند (فقط در Chrome کار می‌کند)، یا
 * کاربر از میان‌بر «اتصال پیامک» (نگه داشتن آیکن، vazir://code) کد ۶ رقمی صفحه پیامک را وارد
 * می‌کند و اپ توکن را از سرور می‌گیرد؛ این راه به مرورگر بستگی ندارد. سپس حساب نشان داده
 * می‌شود، اجازه دریافت پیامک گرفته و توکن نگه داشته می‌شود. intent://unpair اتصال را قطع می‌کند.
 * مقصد ارسال همیشه دامنه خود اپ است، نه چیزی از لینک.
 */
public class PairActivity extends Activity {
    private static final int REQUEST_SMS = 7;
    private static final int CODE_LENGTH = 6;
    private static final int THEME = android.R.style.Theme_DeviceDefault_Light_Dialog_Alert;
    private String token;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Uri data = getIntent().getData();
        if (data == null) {
            finish();
            return;
        }
        if ("unpair".equals(data.getHost())) {
            SmsUploader.clear(this);
            Toast.makeText(this, R.string.sms_unpaired, Toast.LENGTH_LONG).show();
            finish();
            return;
        }
        if ("code".equals(data.getHost())) {
            askCode();
            return;
        }
        token = data.getQueryParameter("token");
        if (!"pair".equals(data.getHost()) || token == null || !SmsUploader.TOKEN.matcher(token).matches()) {
            finish();
            return;
        }
        confirm(data.getQueryParameter("account"));
    }

    /** نشان دادن حساب و گرفتن تأیید کاربر پیش از اجازه دریافت پیامک. */
    private void confirm(String account) {
        new AlertDialog.Builder(this, THEME)
                .setTitle(R.string.sms_pair_title)
                .setMessage(getString(R.string.sms_pair_message, account == null ? "" : account))
                .setPositiveButton(R.string.sms_pair_allow, (d, w) -> askPermission())
                .setNegativeButton(R.string.sms_pair_cancel, (d, w) -> finish())
                .setOnCancelListener(d -> finish())
                .show();
    }

    private void askCode() {
        final EditText input = new EditText(this);
        input.setInputType(InputType.TYPE_CLASS_NUMBER);
        input.setFilters(new InputFilter[] {new InputFilter.LengthFilter(CODE_LENGTH)});
        input.setGravity(Gravity.CENTER);
        input.setHint(R.string.sms_code_hint);
        new AlertDialog.Builder(this, THEME)
                .setTitle(R.string.sms_code_title)
                .setMessage(R.string.sms_code_message)
                .setView(input)
                .setPositiveButton(R.string.sms_code_connect, (d, w) -> redeem(input.getText().toString()))
                .setNegativeButton(R.string.sms_pair_cancel, (d, w) -> finish())
                .setOnCancelListener(d -> finish())
                .show();
    }

    /** کد را در رشته پس‌زمینه با توکن عوض می‌کند. */
    private void redeem(final String code) {
        new Thread(() -> {
            final String[] answer = SmsUploader.redeemPairCode(this, code.trim());
            runOnUiThread(() -> {
                if (isFinishing()) {
                    return;
                }
                if (answer == null) {
                    Toast.makeText(this, R.string.sms_code_failed, Toast.LENGTH_LONG).show();
                    finish();
                    return;
                }
                token = answer[0];
                confirm(answer[1]);
            });
        }).start();
    }

    private void askPermission() {
        if (Build.VERSION.SDK_INT >= 23
                && checkSelfPermission(Manifest.permission.RECEIVE_SMS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[] {Manifest.permission.RECEIVE_SMS}, REQUEST_SMS);
        } else {
            done();
        }
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(code, permissions, results);
        if (code == REQUEST_SMS && results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) {
            done();
        } else {
            Toast.makeText(this, R.string.sms_pair_denied, Toast.LENGTH_LONG).show();
            finish();
        }
    }

    private void done() {
        SmsUploader.saveToken(this, token);
        Toast.makeText(this, R.string.sms_paired, Toast.LENGTH_LONG).show();
        finish();
    }
}
