"""Telefonate, Treffen, Zahlungen & Co.: kleine Liste (in Brief/Absender/Anlass) und eigener Reiter."""
from __future__ import annotations

import datetime as dt
import tkinter as tk
from decimal import Decimal
from tkinter import ttk

from .. import hilfen
from .dialoge import AktivitaetDialog
from .widgets import knopf, liste, liste_leeren

SCHNELL = (("Telefonat", "☎ Telefonat"), ("Treffen", "● Treffen"), ("Zahlung", "€ Zahlung"), ("Notiz", "✎ Notiz"))


def zeile_text(a: dict) -> str:
    teile = [a["betreff"] or hilfen.kurz(a["notizen"], 50) or ""]
    if a["art"] == "Telefonat" and a.get("dauer_min"):
        teile.append(f"({a['dauer_min']} Min.)")
    if a["art"] == "Treffen" and a.get("ort"):
        teile.append(f"in {a['ort']}")
    return " ".join(t for t in teile if t)


def betrag_mit_richtung(a: dict) -> str:
    if a.get("betrag") is None:
        return ""
    zeichen = "−" if a.get("richtung") == "ausgehend" and a["art"] == "Zahlung" else ""
    return zeichen + hilfen.betrag_text(a["betrag"])


class AktivitaetenListe(ttk.Frame):
    """Aktivitäten zu einem Brief, Absender oder Anlass – mit Knöpfen zum schnellen Eintragen.

    kontext() liefert z. B. {"brief_id": 4} oder None, wenn gerade nichts ausgewählt ist.
    """

    def __init__(self, eltern, app, kontext, bei_aenderung=None, hoehe: int = 5, stilname: str = "TFrame",
                 kompakt: bool = False):
        super().__init__(eltern, style=stilname)
        self.app, self.kontext, self.bei_aenderung = app, kontext, bei_aenderung
        self.kompakt = kompakt
        leiste = ttk.Frame(self, style=stilname)
        leiste.pack(fill="x", pady=(0, 4))
        self.knoepfe = []
        for art, text in SCHNELL:
            k = knopf(leiste, text, lambda a=art: self.neu(a), f"{art} dokumentieren",
                      style="Kompakt.TButton" if kompakt else "TButton")
            k.pack(side="left", padx=(0, 4))
            self.knoepfe.append(k)
        rahmen, self.tv = liste(self, [("wann", "Wann", 88 if kompakt else 120, "w"), ("art", "Art", 100, "w"),
                                       ("text", "Worum ging es", 200, "w"), ("betrag", "Betrag", 85, "e")],
                                hoehe=hoehe)
        self.tv.column("wann", stretch=False)
        self.tv.column("art", stretch=False)
        rahmen.pack(fill="both", expand=True)
        self.tv.bind("<Double-1>", lambda e: self.bearbeiten())
        self.tv.bind("<Return>", lambda e: self.bearbeiten())
        self.tv.bind("<Delete>", lambda e: self.loeschen())

    def laden(self) -> None:
        liste_leeren(self.tv)
        filter_ = self.kontext()
        zustand = ["!disabled"] if filter_ is not None else ["disabled"]
        for k in self.knoepfe:
            k.state(zustand)
        if not filter_:
            return
        for a in self.app.db.aktivitaeten(**filter_):
            wann = hilfen.datum_text(a["zeitpunkt"].date() if self.kompakt else a["zeitpunkt"])
            self.tv.insert("", "end", iid=str(a["id"]), values=(
                wann, f"{hilfen.aktivitaet_zeichen(a['art'])} {a['art']}", zeile_text(a), betrag_mit_richtung(a)))

    def neu(self, art: str) -> None:
        filter_ = self.kontext()
        if filter_ is None:
            return
        vorgaben = {"art": art, **filter_}
        ergebnis = AktivitaetDialog(self, self.app.db, vorgaben=vorgaben).zeigen()
        if ergebnis:
            self._geaendert(art)

    def bearbeiten(self) -> None:
        auswahl = self.tv.selection()
        if not auswahl:
            return
        daten = self.app.db.aktivitaet_holen(int(auswahl[0]))
        if daten and AktivitaetDialog(self, self.app.db, daten=daten).zeigen():
            self._geaendert(daten["art"])

    def loeschen(self) -> None:
        auswahl = self.tv.selection()
        if auswahl and self.app.fragen("Ausgewählten Eintrag löschen?"):
            self.app.db.aktivitaet_loeschen(int(auswahl[0]))
            self._geaendert(None)

    def _geaendert(self, art):
        self.laden()
        self.app.geaendert()
        if self.bei_aenderung:
            self.bei_aenderung(art)


class AktivitaetenTab(ttk.Frame):
    """Alle Telefonate, Treffen, Zahlungen … auf einen Blick."""

    def __init__(self, eltern, app):
        super().__init__(eltern, padding=(12, 10))
        self.app = app
        self.veraltet = True
        oben = ttk.Frame(self)
        oben.pack(fill="x", pady=(0, 8))
        for art, text in SCHNELL:
            knopf(oben, text, lambda a=art: self.neu(a), f"Neues {art} dokumentieren").pack(side="left", padx=(0, 4))
        knopf(oben, "＋ Weitere …", lambda: self.neu("E-Mail"), "E-Mail, Brief verschickt, Sonstiges").pack(side="left")
        self.suche = tk.StringVar()
        ttk.Entry(oben, textvariable=self.suche, width=24).pack(side="right")
        ttk.Label(oben, text="Suche").pack(side="right", padx=(12, 6))
        self.art = ttk.Combobox(oben, state="readonly", width=16, values=["Alle"] + list(hilfen.AKTIVITAET_ARTEN))
        self.art.current(0)
        self.art.pack(side="right")
        ttk.Label(oben, text="Art").pack(side="right", padx=(12, 6))
        self.art.bind("<<ComboboxSelected>>", lambda e: self.neu_laden())
        self._timer = None
        self.suche.trace_add("write", lambda *a: self._spaeter())

        rahmen, self.tv = liste(self, [
            ("wann", "Wann", 130, "w"), ("art", "Art", 120, "w"), ("text", "Worum ging es", 260, "w"),
            ("mitwem", "Mit wem", 220, "w"), ("brief", "Brief / Anlass", 200, "w"), ("betrag", "Betrag", 100, "e"),
            ("wv", "Wiedervorlage", 125, "w")], hoehe=20)
        for spalte in ("wann", "art", "betrag", "wv"):
            self.tv.column(spalte, stretch=False)
        rahmen.pack(fill="both", expand=True)
        self.tv.bind("<Double-1>", lambda e: self.bearbeiten())
        self.tv.bind("<Return>", lambda e: self.bearbeiten())
        self.tv.bind("<Delete>", lambda e: self.loeschen())
        unten = ttk.Frame(self)
        unten.pack(fill="x", pady=(8, 0))
        self.summe = ttk.Label(unten, text="", style="Klein.TLabel")
        self.summe.pack(side="left")
        knopf(unten, "Löschen", self.loeschen).pack(side="right")
        knopf(unten, "Bearbeiten", self.bearbeiten).pack(side="right", padx=6)
        knopf(unten, "Zum Brief", self.zum_brief, "Den zugehörigen Brief öffnen").pack(side="right")

    def _spaeter(self):
        if self._timer:
            self.after_cancel(self._timer)
        self._timer = self.after(300, self.neu_laden)

    def neu_laden(self) -> None:
        self._timer = None
        self.veraltet = False
        art = self.art.get()
        daten = self.app.db.aktivitaeten(art=None if art == "Alle" else art, suche=self.suche.get().strip())
        liste_leeren(self.tv)
        bezahlt, erhalten, minuten = Decimal("0"), Decimal("0"), 0
        for a in daten:
            mit = " – ".join(t for t in (a["absender"], a["ansprechpartner"]) if t)
            bezug = a["brief"] or a["anlass"] or ""
            if a["brief"] and a["anlass"]:
                bezug = f"{a['brief']} ({a['anlass']})"
            tags = ("rot",) if a["wiedervorlage"] and a["wiedervorlage"] <= dt.date.today() else ()
            self.tv.insert("", "end", iid=str(a["id"]), tags=tags, values=(
                hilfen.datum_text(a["zeitpunkt"]), f"{hilfen.aktivitaet_zeichen(a['art'])} {a['art']}",
                zeile_text(a), mit, bezug, betrag_mit_richtung(a), hilfen.datum_text(a["wiedervorlage"])))
            if a["art"] == "Zahlung" and a["betrag"] is not None:
                if a["richtung"] == "eingehend":
                    erhalten += a["betrag"]
                else:
                    bezahlt += a["betrag"]
            if a["art"] == "Telefonat":
                minuten += a["dauer_min"] or 0
        teile = [hilfen.anzahl(len(daten), "Eintrag", "Einträge")]
        if bezahlt or erhalten:
            teile.append(f"Zahlungen: {hilfen.betrag_text(bezahlt)} bezahlt, {hilfen.betrag_text(erhalten)} erhalten")
        if minuten:
            teile.append(f"Telefonate zusammen {minuten} Minuten")
        self.summe.configure(text="   ·   ".join(teile))

    def neu(self, art: str) -> None:
        if AktivitaetDialog(self, self.app.db, vorgaben={"art": art}).zeigen():
            self.neu_laden()
            self.app.geaendert(self)

    def bearbeiten(self) -> None:
        auswahl = self.tv.selection()
        if not auswahl:
            return
        daten = self.app.db.aktivitaet_holen(int(auswahl[0]))
        if daten and AktivitaetDialog(self, self.app.db, daten=daten).zeigen():
            self.neu_laden()
            self.app.geaendert(self)

    def loeschen(self) -> None:
        auswahl = self.tv.selection()
        if auswahl and self.app.fragen(f"{hilfen.anzahl(len(auswahl), 'Eintrag', 'Einträge')} löschen?"):
            for iid in auswahl:
                self.app.db.aktivitaet_loeschen(int(iid))
            self.neu_laden()
            self.app.geaendert(self)

    def zum_brief(self) -> None:
        auswahl = self.tv.selection()
        if auswahl:
            daten = self.app.db.aktivitaet_holen(int(auswahl[0]))
            if daten and daten["brief_id"]:
                self.app.brief_zeigen(daten["brief_id"])
            else:
                self.app.hinweis("Dieser Eintrag gehört zu keinem bestimmten Brief.")
