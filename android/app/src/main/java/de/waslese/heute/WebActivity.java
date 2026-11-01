package de.waslese.heute;

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
 * Zeigt eine Seite aus assets/ an. Beide Apps laufen im selben Paket, ihre Seiten
 * teilen sich deshalb denselben Speicher (localStorage) – so „reden“ sie miteinander.
 */
public abstract class WebActivity extends Activity {

    private static final String ASSETS = "file:///android_asset/";

    protected WebView web;

    /** Die Seite, mit der diese App startet, z. B. "index.html". */
    protected abstract String startPage();

    @Override
    protected void onCreate(Bundle zustand) {
        super.onCreate(zustand);

        web = new WebView(this);
        web.setBackgroundColor(getResources().getColor(R.color.paper, getTheme()));

        WebSettings einstellungen = web.getSettings();
        einstellungen.setJavaScriptEnabled(true);
        einstellungen.setDomStorageEnabled(true);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView ansicht, WebResourceRequest anfrage) {
                Uri ziel = anfrage.getUrl();
                if ("file".equals(ziel.getScheme())) {
                    return false; // Links zwischen den beiden Apps bleiben in dieser Ansicht.
                }
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, ziel));
                } catch (ActivityNotFoundException ignoriert) {
                    // Kein Browser installiert: Link nicht öffnen.
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
        // Die Seite liest neu, was die andere App inzwischen gespeichert hat.
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
