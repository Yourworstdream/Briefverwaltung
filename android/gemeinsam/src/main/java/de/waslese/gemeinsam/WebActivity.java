package de.waslese.gemeinsam;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

/**
 * Zeigt die Seite der App aus assets/ an und verbindet sie über window.Bruecke mit der Partner-App.
 * Links wie lesetagebuch://buch/s3 öffnen die Partner-App direkt beim richtigen Buch.
 */
public abstract class WebActivity extends Activity {

    private static final String ASSETS = "file:///android_asset/";

    protected WebView web;

    /** Die Seite dieser App, z. B. "index.html". */
    protected abstract String startPage();

    /** Paketname der Partner-App. */
    protected abstract String partnerPaket();

    /** Name der Partner-App für Hinweise. */
    protected abstract String partnerName();

    @SuppressLint({"SetJavaScriptEnabled", "JavascriptInterface"})
    @Override
    protected void onCreate(Bundle zustand) {
        super.onCreate(zustand);

        web = new WebView(this);
        web.setBackgroundColor(getResources().getColor(R.color.paper, getTheme()));

        WebSettings einstellungen = web.getSettings();
        einstellungen.setJavaScriptEnabled(true);
        einstellungen.setDomStorageEnabled(true);

        web.addJavascriptInterface(new Bruecke(this, partnerPaket()), "Bruecke");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView ansicht, WebResourceRequest anfrage) {
                Uri ziel = anfrage.getUrl();
                if ("file".equals(ziel.getScheme())) {
                    return false;
                }
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, ziel));
                } catch (ActivityNotFoundException e) {
                    String scheme = ziel.getScheme();
                    boolean partner = scheme != null && !scheme.startsWith("http");
                    Toast.makeText(WebActivity.this,
                            partner ? "Installiere zuerst die App „" + partnerName() + "“." : "Kein Browser gefunden.",
                            Toast.LENGTH_LONG).show();
                }
                return true;
            }
        });

        setContentView(web);

        if (zustand == null || web.restoreState(zustand) == null) {
            web.loadUrl(adresse(getIntent()));
        }
    }

    /** lesetagebuch://buch/<id> bzw. wasleseichheute://buch/<id> springt direkt zum Buch. */
    private String adresse(Intent intent) {
        String url = ASSETS + startPage();
        Uri daten = intent != null ? intent.getData() : null;
        if (daten != null && "buch".equals(daten.getHost())) {
            String id = daten.getLastPathSegment();
            if (id != null && !id.isEmpty()) {
                url += "#buch-" + Uri.encode(id);
            }
        }
        return url;
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (intent.getData() != null) {
            web.loadUrl(adresse(intent));
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();
        // Die Seite holt sich neu, was die Partner-App inzwischen gespeichert hat.
        web.evaluateJavascript("window.dispatchEvent(new Event('appresume'))", null);
    }

    @Override
    protected void onPause() {
        web.onPause();
        super.onPause();
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        if (web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle ausgabe) {
        super.onSaveInstanceState(ausgabe);
        web.saveState(ausgabe);
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.destroy();
        }
        super.onDestroy();
    }
}
