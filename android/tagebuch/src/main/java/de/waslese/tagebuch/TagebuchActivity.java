package de.waslese.tagebuch;

import de.waslese.gemeinsam.WebActivity;

/** „Lesetagebuch“: Gedanken, Zusammenfassung und gelesene Seiten zu jedem Buch. */
public class TagebuchActivity extends WebActivity {
    @Override
    protected String startPage() {
        return "tagebuch.html";
    }

    @Override
    protected String partnerPaket() {
        return "de.waslese.heute";
    }

    @Override
    protected String partnerName() {
        return "Was lese ich heute?";
    }
}
