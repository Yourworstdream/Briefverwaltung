package de.waslese.heute;

/** „Lesetagebuch“: Gedanken, Zusammenfassung und gelesene Seiten zu jedem Buch. */
public class TagebuchActivity extends WebActivity {
    @Override
    protected String startPage() {
        return "tagebuch.html";
    }
}
