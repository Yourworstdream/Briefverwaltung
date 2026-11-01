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

/** Zeigt die Bücher-App (assets/index.html) an. Die Bücher speichert die Seite im Gerätespeicher der WebView. */
public class MainActivity extends Activity {

    private WebView web;

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
                    return false;
                }
                // Fremde Links im Browser öffnen statt in der App.
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, ziel));
                } catch (ActivityNotFoundException ignoriert) {
                    // Kein Browser installiert: Link einfach nicht öffnen.
                }
                return true;
            }
        });

        setContentView(web);

        if (zustand == null || web.restoreState(zustand) == null) {
            web.loadUrl("file:///android_asset/index.html");
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
