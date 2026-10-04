package ir.getvazir.app;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.widget.Toast;

/**
 * اتصال پیامک بانکی به حساب وزیر، فقط با تأیید کاربر:
 * سایت لینک intent://pair?token=…&account=… را باز می‌کند؛ این صفحه حساب را نشان می‌دهد،
 * اجازه دریافت پیامک را می‌گیرد و توکن را نگه می‌دارد. intent://unpair اتصال را قطع می‌کند.
 * مقصد ارسال همیشه دامنه خود اپ است، نه چیزی از لینک.
 */
public class PairActivity extends Activity {
    private static final int REQUEST_SMS = 7;
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
        token = data.getQueryParameter("token");
        if (!"pair".equals(data.getHost()) || token == null || !SmsUploader.TOKEN.matcher(token).matches()) {
            finish();
            return;
        }
        String account = data.getQueryParameter("account");
        new AlertDialog.Builder(this, android.R.style.Theme_DeviceDefault_Light_Dialog_Alert)
                .setTitle(R.string.sms_pair_title)
                .setMessage(getString(R.string.sms_pair_message, account == null ? "" : account))
                .setPositiveButton(R.string.sms_pair_allow, (d, w) -> askPermission())
                .setNegativeButton(R.string.sms_pair_cancel, (d, w) -> finish())
                .setOnCancelListener(d -> finish())
                .show();
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
