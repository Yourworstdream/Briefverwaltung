"""Reiter „Übersicht“: Kennzahlen, Fristen, Wiedervorlagen, offene Briefe je Absender."""
from __future__ import annotations

import datetime as dt
import tkinter as tk
from tkinter import ttk

from .. import hilfen
from . import stil
from .tab_aktivitaeten import zeile_text
from .widgets import Karte, ScrollRahmen, Tooltip, liste, liste_leeren

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


class UebersichtTab(ScrollRahmen):
    def __init__(self, eltern, app):
        super().__init__(eltern, polster=(18, 14, 18, 24))
        self.app = app
        self.veraltet = True
        f = self.innen
        for spalte in range(2):
            f.columnconfigure(spalte, weight=1, uniform="spalten")

        kopf = ttk.Frame(f)
        kopf.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.titel = ttk.Label(kopf, text="Übersicht", style="Titel.TLabel")
        self.titel.pack(side="left")
        self.hinweis = ttk.Label(kopf, text="", style="Klein.TLabel")
        self.hinweis.pack(side="right")

        karten = ttk.Frame(f)
        karten.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 18))
        self.karten = {}
        definition = [
            ("neu", "Neu – noch nicht bearbeitet", stil.AKZENT, "neu", "Frisch importiert: Absender, Frist usw. eintragen"),
            ("offen", "Offene Briefe", stil.HELLGRAU, "offen", "Alles, was noch nicht erledigt ist"),
            ("dringend", "Dringend", stil.ORANGE, "dringend", "Dringlichkeit „hoch“ oder „sehr dringend“"),
            ("ueberfaellig", "Frist überschritten", stil.ROT, "ueberfaellig", "Frist liegt in der Vergangenheit"),
            ("fristen", "Frist in 7 Tagen", stil.ORANGE, "fristen", "Frist heute oder in den nächsten 7 Tagen"),
            ("offener_betrag", "Noch zu zahlen", stil.HELLGRAU, "offen", "Beträge offener Briefe minus Zahlungen"),
        ]
        for nr, (schluessel, text, farbe, filter_, tipp) in enumerate(definition):
            karte = Karte(karten, text, farbe, tipp, befehl=lambda s=filter_: self.app.briefe_filter(s))
            karte.grid(row=0, column=nr, sticky="nsew", padx=(0 if nr == 0 else 10, 0))
            karten.columnconfigure(nr, weight=1, uniform="karten")
            self.karten[schluessel] = karte

        self.fristen = self._liste(f, 2, 0, "Fristen in den nächsten 30 Tagen", [
            ("frist", "Frist", 95, "w"), ("wann", "", 140, "w"), ("betreff", "Betreff", 200, "w"),
            ("absender", "Absender", 150, "w")])
        self.fristen.bind("<Double-1>", lambda e: self._brief_oeffnen(self.fristen))
        self.wiedervorlagen = self._liste(f, 2, 1, "Wiedervorlagen", [
            ("datum", "Datum", 95, "w"), ("art", "Art", 100, "w"), ("text", "Worum", 200, "w"),
            ("mit", "Mit wem", 150, "w")])
        self.wiedervorlagen.bind("<Double-1>", lambda e: self._aktivitaet_oeffnen(self.wiedervorlagen))

        rahmen = ttk.Frame(f)
        rahmen.grid(row=4, column=0, sticky="nsew", padx=(0, 10), pady=(18, 0))
        ttk.Label(rahmen, text="Offene Briefe je Absender", style="Untertitel.TLabel").pack(anchor="w", pady=(0, 6))
        self.diagramm = tk.Canvas(rahmen, height=240, background=stil.FLAECHE, highlightthickness=1,
                                  highlightbackground=stil.RAND)
        self.diagramm.pack(fill="x")
        self.diagramm.bind("<Configure>", lambda e: self._diagramm_zeichnen())
        Tooltip(self.diagramm, "Anklicken zeigt die offenen Briefe dieses Absenders")
        self._diagramm_daten = []

        self.letzte = self._liste(f, 4, 1, "Zuletzt dokumentiert", [
            ("wann", "Wann", 120, "w"), ("art", "Art", 100, "w"), ("text", "Worum", 200, "w"),
            ("mit", "Mit wem", 150, "w")], hoehe=5)
        self.letzte.bind("<Double-1>", lambda e: self._aktivitaet_oeffnen(self.letzte))
        self.importe = ttk.Label(f, text="", style="Klein.TLabel", justify="left")
        self.importe.grid(row=6, column=0, columnspan=2, sticky="w", pady=(16, 0))

    def _liste(self, f, zeile, spalte, titel, spalten, hoehe=7):
        rahmen = ttk.Frame(f)
        rahmen.grid(row=zeile, column=spalte, sticky="nsew", padx=(0, 10) if spalte == 0 else (10, 0),
                    pady=(18, 0) if zeile > 2 else 0)
        ttk.Label(rahmen, text=titel, style="Untertitel.TLabel").pack(anchor="w", pady=(0, 6))
        tabelle, tv = liste(rahmen, spalten, hoehe=hoehe)
        tabelle.pack(fill="both", expand=True)
        return tv

    def neu_laden(self) -> None:
        self.veraltet = False
        db = self.app.db
        heute = dt.date.today()
        self.titel.configure(text=f"Übersicht – {WOCHENTAGE[heute.weekday()]}, {hilfen.datum_text(heute)}")
        werte = db.kennzahlen()
        for schluessel, karte in self.karten.items():
            wert = werte.get(schluessel, 0)
            karte.setzen(hilfen.betrag_text(wert) if schluessel == "offener_betrag" else wert)

        liste_leeren(self.fristen)
        for b in db.naechste_fristen(30):
            tags = ["rot"] if b["frist"] < heute else []
            tags.append(f"d{b['dringlichkeit']}")
            self.fristen.insert("", "end", iid=str(b["id"]), tags=tuple(tags), values=(
                hilfen.datum_text(b["frist"]), hilfen.frist_text(b["frist"]), b["betreff"] or "(ohne Betreff)",
                b["absender"] or ""))
        if not self.fristen.get_children():
            self.fristen.insert("", "end", values=("", "Keine Fristen in den nächsten 30 Tagen", "", ""),
                                tags=("grau",))

        liste_leeren(self.wiedervorlagen)
        for a in db.wiedervorlagen(14):
            self.wiedervorlagen.insert("", "end", iid=str(a["id"]), tags=("rot",) if a["wiedervorlage"] < heute else (),
                                       values=(hilfen.datum_text(a["wiedervorlage"]),
                                               f"{hilfen.aktivitaet_zeichen(a['art'])} {a['art']}", zeile_text(a),
                                               a["ansprechpartner"] or a["absender"] or ""))
        if not self.wiedervorlagen.get_children():
            self.wiedervorlagen.insert("", "end", values=("", "", "Keine Wiedervorlagen fällig", ""), tags=("grau",))

        liste_leeren(self.letzte)
        for a in db.aktivitaeten(grenze=8):
            self.letzte.insert("", "end", iid=str(a["id"]), values=(
                hilfen.datum_text(a["zeitpunkt"]), f"{hilfen.aktivitaet_zeichen(a['art'])} {a['art']}",
                zeile_text(a), a["ansprechpartner"] or a["absender"] or ""))

        self._diagramm_daten = [d for d in db.briefe_je_absender(10) if int(d["offen"] or 0) > 0]
        self._diagramm_daten.sort(key=lambda d: (-int(d["offen"]), d["name"].lower()))
        self._diagramm_zeichnen()

        importe = db.letzte_importe(3)
        if importe:
            zeilen = [f"{hilfen.datum_text(i['zeitpunkt'])}  {i['quelle']}:  "
                      f"{hilfen.anzahl(i['neue_briefe'], 'neuer Brief', 'neue Briefe')}, "
                      f"{hilfen.anzahl(i['neue_fotos'], 'Foto', 'Fotos')}, {i['doppelt']} schon vorhanden"
                      + (f", {i['fehler']} Fehler" if i["fehler"] else "") for i in importe]
            self.importe.configure(text="Letzte Importe\n" + "\n".join(zeilen))
        else:
            self.importe.configure(text="Noch nichts importiert. Stecke einen USB-Stick mit dem Ordner "
                                        f"„{self.app.konfig['usb']['ordnername']}“ ein.")
        self.hinweis.configure(text=self.app.usb_text())

    def _diagramm_zeichnen(self):
        """Waagerechte Balken, eine Farbe, Werte direkt am Balken. Klick öffnet die Briefe des Absenders."""
        c = self.diagramm
        c.delete("all")
        daten = self._diagramm_daten
        breite = max(c.winfo_width(), 200)
        if not daten:
            c.configure(height=60)
            c.create_text(16, 30, anchor="w", text="Keine offenen Briefe – alles erledigt.", fill=stil.GRAU)
            return
        zeile, oben = 26, 12
        c.configure(height=oben * 2 + zeile * len(daten))
        label_breite = min(220, int(breite * 0.38))
        platz = breite - label_breite - 60
        maximum = max(int(d["offen"]) for d in daten)
        schrift = stil.schrift("normal")
        for nr, d in enumerate(daten):
            y = oben + nr * zeile + zeile / 2
            name = d["name"]
            while schrift.measure(name) > label_breite - 16 and len(name) > 4:
                name = name[:-2] + "…"
            tag = f"z{nr}"
            c.create_text(label_breite - 10, y, anchor="e", text=name, fill=stil.TEXT, tags=(tag,))
            laenge = max(4, platz * int(d["offen"]) / maximum)
            c.create_rectangle(label_breite, y - 7, label_breite + laenge, y + 7, fill=stil.AKZENT, outline="",
                               tags=(tag,))
            c.create_text(label_breite + laenge + 8, y, anchor="w", text=str(d["offen"]), fill=stil.TEXT,
                          tags=(tag,))
            # unsichtbare, größere Klickfläche über die ganze Zeile
            c.create_rectangle(0, y - zeile / 2, breite, y + zeile / 2, outline="", fill="", tags=(tag, "flaeche"))
            c.tag_bind(tag, "<Button-1>", lambda e, n=d["name"]: self._absender_briefe(n))
            c.tag_bind(tag, "<Enter>", lambda e: c.configure(cursor="hand2"))
            c.tag_bind(tag, "<Leave>", lambda e: c.configure(cursor=""))

    def _absender_briefe(self, name):
        self.app.briefe_filter("offen", "" if name.startswith("(") else name)

    def _brief_oeffnen(self, tv):
        auswahl = tv.selection()
        if auswahl and auswahl[0].isdigit():
            self.app.brief_zeigen(int(auswahl[0]))

    def _aktivitaet_oeffnen(self, tv):
        auswahl = tv.selection()
        if not (auswahl and auswahl[0].isdigit()):
            return
        from .dialoge import AktivitaetDialog
        daten = self.app.db.aktivitaet_holen(int(auswahl[0]))
        if daten and AktivitaetDialog(self, self.app.db, daten=daten).zeigen():
            self.app.geaendert()
