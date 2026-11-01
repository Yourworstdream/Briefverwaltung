package de.waslese.heute;

/** „Was lese ich heute?“: Regal, Verzeichnis und das Buch des Tages. */
public class MainActivity extends WebActivity {
    @Override
    protected String startPage() {
        return "index.html";
    }
}
