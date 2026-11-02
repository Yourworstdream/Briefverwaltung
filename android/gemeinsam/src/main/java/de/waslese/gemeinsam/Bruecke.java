package de.waslese.gemeinsam;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.webkit.JavascriptInterface;

/**
 * Die Seite erreicht diese Klasse als window.Bruecke.
 * teilen(): eigene Daten für die Partner-App bereitstellen.
 * lesen(): die Daten der Partner-App holen ("" wenn sie fehlt).
 */
public class Bruecke {

    private final Context context;
    private final String partnerPaket;

    Bruecke(Context context, String partnerPaket) {
        this.context = context.getApplicationContext();
        this.partnerPaket = partnerPaket;
    }

    @JavascriptInterface
    public boolean teilen(String json) {
        try {
            DatenProvider.schreiben(context, json == null ? "" : json);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    @JavascriptInterface
    public String lesen() {
        Uri adresse = Uri.parse("content://" + partnerPaket + ".daten/daten");
        try (Cursor zeilen = context.getContentResolver().query(adresse, null, null, null, null)) {
            if (zeilen != null && zeilen.moveToFirst()) {
                String json = zeilen.getString(0);
                return json == null ? "" : json;
            }
        } catch (Exception e) {
            // Partner-App fehlt, ist anders signiert oder antwortet nicht.
        }
        return "";
    }
}
