package de.waslese.gemeinsam;

import android.annotation.SuppressLint;
import android.annotation.TargetApi;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.ViewGroup;
import android.webkit.RenderProcessGoneDetail;
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
        // Assets (file:///android_asset/) bleiben auch ohne Dateizugriff erreichbar.
        einstellungen.setAllowFileAccess(false);
        einstellungen.setAllowContentAccess(false);
        einstellungen.setAllowFileAccessFromFileURLs(false);
        einstellungen.setAllowUniversalAccessFromFileURLs(false);
        einstellungen.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);

        web.addJavascriptInterface(new Bruecke(this, partnerPaket()), "Bruecke");

        web.setWebViewClient(Build.VERSION.SDK_INT >= Build.VERSION_CODES.O ? new KlientAb26() : new Klient());

        setContentView(web);

        if (zustand == null || web.restoreState(zustand) == null) {
            web.loadUrl(ASSETS + startPage());
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (web == null) {
            return;
        }
        web.onResume();
        // Die Seite holt sich neu, was die Partner-App inzwischen gespeichert hat.
        web.evaluateJavascript("window.dispatchEvent(new Event('appresume'))", null);
    }

    @Override
    protected void onPause() {
        if (web != null) {
            web.onPause();
        }
        super.onPause();
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        if (web != null && web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle ausgabe) {
        super.onSaveInstanceState(ausgabe);
        if (web != null) {
            web.saveState(ausgabe);
        }
    }

    @Override
    protected void onDestroy() {
        webAbbauen();
        super.onDestroy();
    }

    /** Nimmt die WebView aus dem Layout und gibt sie frei. */
    private void webAbbauen() {
        if (web == null) {
            return;
        }
        if (web.getParent() instanceof ViewGroup) {
            ((ViewGroup) web.getParent()).removeView(web);
        }
        web.destroy();
        web = null;
    }

    private class Klient extends WebViewClient {
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
    }

    /**
     * RenderProcessGoneDetail gibt es erst ab Android 8; eine eigene Klasse, die nur dort
     * angelegt wird, hält ältere Geräte aus dem Spiel.
     */
    @TargetApi(Build.VERSION_CODES.O)
    private class KlientAb26 extends Klient {
        @Override
        public boolean onRenderProcessGone(WebView ansicht, RenderProcessGoneDetail detail) {
            // Ohne diese Methode beendet das System die ganze App, wenn die Darstellung abstürzt.
            if (ansicht == web) {
                webAbbauen();
                recreate();
            }
            return true;
        }
    }
}
