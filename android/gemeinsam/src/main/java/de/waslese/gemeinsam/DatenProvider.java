package de.waslese.gemeinsam;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

/**
 * Gibt die Daten dieser App für die Partner-App frei: eine Zeile, eine Spalte "json".
 * „Was lese ich heute?“ teilt Bücher und Tagesbuch, das Lesetagebuch teilt seine Einträge.
 * Lesen dürfen nur Apps mit der Berechtigung de.waslese.DATEN (gleiche Unterschrift).
 */
public class DatenProvider extends ContentProvider {

    private static final String DATEI = "geteilt.json";
    private static final Object SPERRE = new Object();

    /** Speichert, was die Seite teilen will. Wird von der Brücke aufgerufen. */
    static void schreiben(Context context, String json) throws IOException {
        synchronized (SPERRE) {
            File ziel = new File(context.getFilesDir(), DATEI);
            File neu = new File(context.getFilesDir(), DATEI + ".neu");
            try (FileOutputStream aus = new FileOutputStream(neu)) {
                aus.write(json.getBytes(StandardCharsets.UTF_8));
                aus.getFD().sync();
            }
            if (!neu.renameTo(ziel)) {
                throw new IOException("Datei konnte nicht ersetzt werden");
            }
        }
    }

    static String lesen(Context context) {
        synchronized (SPERRE) {
            File datei = new File(context.getFilesDir(), DATEI);
            if (!datei.exists()) {
                return "";
            }
            try {
                return new String(Files.readAllBytes(datei.toPath()), StandardCharsets.UTF_8);
            } catch (IOException e) {
                return "";
            }
        }
    }

    @Override
    public boolean onCreate() {
        return true;
    }

    @Override
    public Cursor query(Uri uri, String[] spalten, String auswahl, String[] argumente, String sortierung) {
        MatrixCursor ergebnis = new MatrixCursor(new String[] {"json"});
        ergebnis.addRow(new Object[] {lesen(getContext())});
        return ergebnis;
    }

    @Override
    public String getType(Uri uri) {
        return "application/json";
    }

    @Override
    public Uri insert(Uri uri, ContentValues werte) {
        throw new UnsupportedOperationException("Nur lesen");
    }

    @Override
    public int delete(Uri uri, String auswahl, String[] argumente) {
        throw new UnsupportedOperationException("Nur lesen");
    }

    @Override
    public int update(Uri uri, ContentValues werte, String auswahl, String[] argumente) {
        throw new UnsupportedOperationException("Nur lesen");
    }
}
