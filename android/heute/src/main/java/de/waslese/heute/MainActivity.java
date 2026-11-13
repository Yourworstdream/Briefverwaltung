package de.waslese.heute;

import de.waslese.gemeinsam.WebActivity;

/** „Was lese ich heute?“: Regal, Verzeichnis und das Buch des Tages. */
public class MainActivity extends WebActivity {
    @Override
    protected String startPage() {
        return "index.html";
    }

    @Override
    protected String partnerPaket() {
        return "de.waslese.tagebuch";
    }
}
