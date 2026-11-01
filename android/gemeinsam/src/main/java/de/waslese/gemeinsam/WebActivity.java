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

/**
 * Zeigt die Seite der App aus assets/ an. Über window.Bruecke tauscht sie im Hintergrund
 * Daten mit der Partner-App aus; sichtbar verbunden sind die beiden Apps nicht.
 */
public abstract class WebActivity extends Activity {

    private static final String ASSETS = "file:///android_asset/";

    protected WebView web;

    /** Die Seite dieser App, z. B. "index.html". */
    protected abstract String startPage();

    /** Paketname der Partner-App. */
    protected abstract String partnerPaket();

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
                // Fremde Webseiten im Browser öffnen, alles andere ignorieren.
                String scheme = ziel.getScheme();
                if ("http".equals(scheme) || "https".equals(scheme)) {
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, ziel));
                    } catch (ActivityNotFoundException ignoriert) {
                        // Kein Browser installiert.
                    }
                }
                return true;
            }
        });

        setContentView(web);

        if (zustand == null || web.restoreState(zustand) == null) {
            web.loadUrl(ASSETS + startPage());
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
