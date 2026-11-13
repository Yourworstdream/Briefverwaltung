package de.waslese.gemeinsam;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

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
            // Kein java.nio.file: das gibt es erst ab Android 8 (API 26), die App läuft ab Android 7.
            try (FileInputStream ein = new FileInputStream(datei);
                 ByteArrayOutputStream puffer = new ByteArrayOutputStream()) {
                byte[] block = new byte[8192];
                int n;
                while ((n = ein.read(block)) > 0) {
                    puffer.write(block, 0, n);
                }
                return new String(puffer.toByteArray(), StandardCharsets.UTF_8);
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

    /**
     * Gibt die Datei selbst heraus. Anders als query() hat das keine Größengrenze
     * (ein Cursor-Fenster fasst nur etwa 2 MB je Zeile).
     */
    @Override
    public ParcelFileDescriptor openFile(Uri uri, String modus) throws FileNotFoundException {
        if (!"r".equals(modus)) {
            throw new SecurityException("Nur lesen");
        }
        synchronized (SPERRE) {
            File datei = new File(getContext().getFilesDir(), DATEI);
            if (!datei.exists()) {
                throw new FileNotFoundException("Noch nichts geteilt");
            }
            return ParcelFileDescriptor.open(datei, ParcelFileDescriptor.MODE_READ_ONLY);
        }
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
