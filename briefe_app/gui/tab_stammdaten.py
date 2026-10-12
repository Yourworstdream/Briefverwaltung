"""Reiter „Absender & Kontakte“ und „Anlässe“: Liste links, Angaben rechts."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import hilfen
from ..hilfen import Eingabefehler
from . import stil
from .dialoge import AnsprechpartnerDialog, BankDialog
from .tab_aktivitaeten import AktivitaetenListe
from .widgets import ScrollRahmen, knopf, liste, liste_leeren


class StammdatenTab(ttk.Frame):
    """Gemeinsamer Aufbau. Unterklassen liefern Spalten, Zeilen und das Formular."""

    titel = ""
    neu_text = "＋ Neu"
    spalten = []

    def __init__(self, eltern, app):
        super().__init__(eltern)
        self.app = app
        self.veraltet = True
        self.aktuell_id = None
        self.daten = None
        self.geaendert = False
        self._laedt = False
        self._timer = None

        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=12, pady=10)
        links = ttk.Frame(paned)
        oben = ttk.Frame(links)
        oben.pack(fill="x", pady=(0, 6))
        knopf(oben, self.neu_text, self.neu, style="Akzent.TButton").pack(side="left")
        self.suche = tk.StringVar()
        ttk.Entry(oben, textvariable=self.suche, width=20).pack(side="right")
        ttk.Label(oben, text="Suche").pack(side="right", padx=6)
        self.suche.trace_add("write", lambda *a: self._spaeter())
        self._filter_bauen(links)
        rahmen, self.tv = liste(links, self.spalten, hoehe=22)
        rahmen.pack(fill="both", expand=True)
        self.tv.bind("<<TreeviewSelect>>", self._auswahl)
        paned.add(links, weight=2)

        self.scroll = ScrollRahmen(paned, polster=(18, 4, 18, 24))
        paned.add(self.scroll, weight=3)
        self._paned = paned
        paned.bind("<Map>", self._aufteilen, add="+")
        f = self.scroll.innen
        f.columnconfigure(1, weight=1)
        kopf = ttk.Frame(f)
        kopf.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self.ueberschrift = ttk.Label(kopf, text="", style="Titel.TLabel")
        self.ueberschrift.pack(side="left")
        self.k_speichern = ttk.Button(kopf, text="Speichern", style="Akzent.TButton", command=self.speichern)
        self.k_speichern.pack(side="right")
        self.k_loeschen = ttk.Button(kopf, text="Löschen …", style="Gefahr.TButton", command=self.loeschen)
        self.k_loeschen.pack(side="right", padx=6)
        self.markierung = ttk.Label(kopf, text="", style="Warnung.TLabel")
        self.markierung.pack(side="right", padx=6)
        self._zeile = 1
        self._formular_bauen(f)
        self.leeren()

    def _aufteilen(self, _e=None):
        self._paned.unbind("<Map>")
        self.update_idletasks()
        if self._paned.winfo_width() > 300:
            self._paned.sashpos(0, int(self._paned.winfo_width() * 0.42))

    # ------------------------------------------------------------ für Unterklassen

    def _filter_bauen(self, eltern):
        pass

    def _formular_bauen(self, f):
        raise NotImplementedError

    def _zeilen(self, suche):
        raise NotImplementedError

    def _werte(self, zeile):
        raise NotImplementedError

    def _holen(self, id_):
        raise NotImplementedError

    def _anzeigen(self, daten):
        raise NotImplementedError

    def _formular_daten(self) -> dict:
        raise NotImplementedError

    def _db_speichern(self, daten) -> int:
        raise NotImplementedError

    def _db_loeschen(self, id_):
        raise NotImplementedError

    def _loeschen_frage(self, daten) -> str:
        raise NotImplementedError

    # ------------------------------------------------------------ Bausteine fürs Formular

    def feld(self, text, widget, sticky="ew"):
        ttk.Label(self.scroll.innen, text=text).grid(row=self._zeile, column=0, sticky="nw", pady=4, padx=(0, 10))
        widget.grid(row=self._zeile, column=1, columnspan=2, sticky=sticky, pady=4)
        self._zeile += 1
        return widget

    def eingabe(self, text, breite=40):
        var = tk.StringVar()
        var.trace_add("write", lambda *a: self.markieren())
        self.feld(text, ttk.Entry(self.scroll.innen, textvariable=var, width=breite))
        return var

    def textfeld(self, text, hoehe=4):
        feld = tk.Text(self.scroll.innen, height=hoehe, width=40, wrap="word", font=stil.schrift("normal"),
                       padx=6, pady=4)
        feld.bind("<<Modified>>", lambda e: feld.edit_modified() and (self.markieren(), feld.edit_modified(False)))
        self.feld(text, feld)
        return feld

    @staticmethod
    def text_setzen(feld: tk.Text, text):
        feld.delete("1.0", "end")
        feld.insert("1.0", text or "")
        feld.edit_modified(False)

    def abschnitt(self, titel, hinweis: str = ""):
        ttk.Separator(self.scroll.innen).grid(row=self._zeile, column=0, columnspan=3, sticky="ew", pady=(16, 10))
        self._zeile += 1
        zeile = ttk.Frame(self.scroll.innen)
        zeile.grid(row=self._zeile, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        self._zeile += 1
        ttk.Label(zeile, text=titel, style="Untertitel.TLabel").pack(side="left")
        if hinweis:
            ttk.Label(zeile, text=hinweis, style="Klein.TLabel").pack(side="left", padx=10)
        return zeile

    def knopfreihe(self):
        reihe = ttk.Frame(self.scroll.innen)
        reihe.grid(row=self._zeile, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self._zeile += 1
        return reihe

    def unterliste(self, spalten, hoehe=4):
        rahmen, tv = liste(self.scroll.innen, spalten, hoehe=hoehe)
        rahmen.grid(row=self._zeile, column=0, columnspan=3, sticky="ew")
        self._zeile += 1
        return tv

    def briefliste(self):
        tv = self.unterliste([("eingang", "Eingang", 90, "w"), ("betreff", "Betreff", 240, "w"),
                              ("frist", "Frist", 90, "w"), ("status", "Status", 120, "w")], hoehe=5)
        tv.column("eingang", stretch=False)
        tv.bind("<Double-1>", lambda e: tv.selection() and self.app.brief_zeigen(int(tv.selection()[0])))
        tv.bind("<Return>", lambda e: tv.selection() and self.app.brief_zeigen(int(tv.selection()[0])))
        ttk.Label(self.scroll.innen, text="Doppelklick öffnet den Brief.", style="Klein.TLabel").grid(
            row=self._zeile, column=0, columnspan=3, sticky="w")
        self._zeile += 1
        return tv

    @staticmethod
    def briefe_fuellen(tv, briefe):
        liste_leeren(tv)
        for b in briefe:
            tags = ("grau",) if b["status"] == "erledigt" else (f"d{b['dringlichkeit']}",)
            tv.insert("", "end", iid=str(b["id"]), tags=tags, values=(
                hilfen.datum_text(b["eingangsdatum"] or b["briefdatum"]), b["betreff"] or "(ohne Betreff)",
                hilfen.datum_text(b["frist"]), hilfen.STATUS[b["status"]]))

    # ------------------------------------------------------------ Ablauf

    def _spaeter(self):
        if self._timer:
            self.after_cancel(self._timer)
        self._timer = self.after(300, self.neu_laden)

    def neu_laden(self, auswahl_id=None) -> None:
        self._timer = None
        self.veraltet = False
        ziel = auswahl_id or self.aktuell_id
        self._laedt = True
        liste_leeren(self.tv)
        for zeile in self._zeilen(self.suche.get().strip()):
            werte, tags = self._werte(zeile)
            self.tv.insert("", "end", iid=str(zeile["id"]), values=werte, tags=tags)
        self._laedt = False
        if ziel and self.tv.exists(str(ziel)):
            self.tv.selection_set(str(ziel))
            self.tv.see(str(ziel))
            if ziel != self.aktuell_id or auswahl_id:
                self.zeigen(ziel)
            else:
                self.zeigen(ziel, nur_listen=True)
        elif self.aktuell_id and not self._holen(self.aktuell_id):
            self.leeren()

    def _auswahl(self, _e=None):
        if self._laedt:
            return
        auswahl = self.tv.selection()
        if not auswahl or int(auswahl[0]) == self.aktuell_id:
            return
        if not self.wechsel_erlaubt():
            if self.aktuell_id and self.tv.exists(str(self.aktuell_id)):
                self.tv.selection_set(str(self.aktuell_id))
            return
        self.zeigen(int(auswahl[0]))

    def auswaehlen(self, id_: int) -> None:
        if not self.wechsel_erlaubt():
            return
        self.suche.set("")
        if self._timer:
            self.after_cancel(self._timer)
        self.neu_laden(auswahl_id=id_)

    def zeigen(self, id_, nur_listen: bool = False) -> None:
        daten = self._holen(id_)
        if not daten:
            self.leeren()
            return
        self.aktuell_id, self.daten = id_, daten
        if not nur_listen or not self.geaendert:
            self._laedt = True
            self._anzeigen(daten)
            self._laedt = False
            self._markierung_weg()
        self._listen(daten)
        self.k_loeschen.state(["!disabled"])
        if not nur_listen:
            self.scroll.nach_oben()

    def leeren(self) -> None:
        """Formular für einen neuen Eintrag."""
        self.aktuell_id, self.daten = None, None
        self.tv.selection_set(())
        self._laedt = True
        self._anzeigen({})
        self._laedt = False
        self._markierung_weg()
        self._listen(None)
        self.k_loeschen.state(["disabled"])

    def _listen(self, daten):
        pass

    def neu(self) -> None:
        if self.wechsel_erlaubt():
            self.leeren()
            self.erstes_feld.focus_set()

    def markieren(self):
        if self._laedt or self.geaendert:
            return
        self.geaendert = True
        self.markierung.configure(text="● nicht gespeichert")

    def _markierung_weg(self):
        self.geaendert = False
        self.markierung.configure(text="")

    def speichern(self, neu_laden: bool = True) -> bool:
        daten = self._formular_daten()
        if self.aktuell_id:
            daten["id"] = self.aktuell_id
        neu_id = self._db_speichern(daten)
        self._markierung_weg()
        self.app.geaendert(self)
        self.app.status("Gespeichert.")
        if neu_laden:
            self.aktuell_id = neu_id
            self.neu_laden(auswahl_id=neu_id)
        return True

    def wechsel_erlaubt(self) -> bool:
        if not self.geaendert:
            return True
        if not self.aktuell_id and not (self._formular_daten().get("name") or "").strip():
            self._markierung_weg()               # angefangener neuer Eintrag ohne Namen: einfach verwerfen
            return True
        try:
            self.speichern(neu_laden=False)
            self.after_idle(self.neu_laden)
            return True
        except Eingabefehler as fehler:
            if self.app.fragen(f"Die Änderungen können nicht gespeichert werden:\n\n{fehler}\n\nÄnderungen verwerfen?"):
                self._markierung_weg()
                return True
            return False

    def loeschen(self) -> None:
        if not self.daten or not self.app.fragen(self._loeschen_frage(self.daten)):
            return
        self._db_loeschen(self.aktuell_id)
        self._markierung_weg()
        self.leeren()
        self.neu_laden()
        self.app.geaendert(self)


# ====================================================================== Absender

class AbsenderTab(StammdatenTab):
    titel = "Absender & Kontakte"
    neu_text = "＋ Neuer Absender"
    spalten = [("name", "Name", 200, "w"), ("art", "Art", 110, "w"), ("ort", "Ort", 110, "w"),
               ("briefe", "Briefe", 60, "center"), ("offen", "offen", 60, "center")]

    def _formular_bauen(self, f):
        self.name = self.eingabe("Name")
        self.erstes_feld = f.grid_slaves(row=self._zeile - 1, column=1)[0]
        self.art = ttk.Combobox(f, values=hilfen.ABSENDER_ARTEN, width=24)
        self.art.bind("<<ComboboxSelected>>", lambda e: self.markieren())
        self.art.bind("<KeyRelease>", lambda e: self.markieren())
        self.feld("Art", self.art, sticky="w")
        self.strasse = self.eingabe("Straße")
        reihe = ttk.Frame(f)
        self.plz, self.ort = tk.StringVar(), tk.StringVar()
        for var in (self.plz, self.ort):
            var.trace_add("write", lambda *a: self.markieren())
        ttk.Entry(reihe, textvariable=self.plz, width=8).pack(side="left")
        ttk.Entry(reihe, textvariable=self.ort).pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.feld("PLZ / Ort", reihe)
        self.telefon = self.eingabe("Telefon (Zentrale)")
        self.email = self.eingabe("E-Mail")
        self.webseite = self.eingabe("Webseite")
        self.kundennummer = self.eingabe("Meine Kundennummer")
        self.notizen = self.textfeld("Notizen", 3)

        self.abschnitt("Ansprechpartner", "Personen, mit denen du zu tun hast")
        self.ap_tv = self.unterliste([("name", "Name", 180, "w"), ("telefon", "Telefon", 130, "w"),
                                      ("email", "E-Mail", 180, "w"), ("erreichbar", "Erreichbar", 120, "w")])
        self.ap_tv.bind("<Double-1>", lambda e: self._ap_bearbeiten())
        reihe = self.knopfreihe()
        self.k_ap_neu = knopf(reihe, "＋ Ansprechpartner", self._ap_neu)
        self.k_ap_neu.pack(side="left")
        knopf(reihe, "Bearbeiten", self._ap_bearbeiten).pack(side="left", padx=4)
        knopf(reihe, "Löschen", self._ap_loeschen).pack(side="left")

        self.abschnitt("Bankverbindungen", "Wohin bezahlt wird")
        self.bank_tv = self.unterliste([("iban", "IBAN", 220, "w"), ("bic", "BIC", 110, "w"),
                                        ("bank", "Bank", 150, "w"), ("inhaber", "Kontoinhaber", 150, "w")], hoehe=3)
        self.bank_tv.bind("<Double-1>", lambda e: self._bank_bearbeiten())
        reihe = self.knopfreihe()
        self.k_bank_neu = knopf(reihe, "＋ Bankverbindung", self._bank_neu)
        self.k_bank_neu.pack(side="left")
        knopf(reihe, "Bearbeiten", self._bank_bearbeiten).pack(side="left", padx=4)
        knopf(reihe, "Löschen", self._bank_loeschen).pack(side="left")

        self.abschnitt("Briefe von diesem Absender")
        self.brief_tv = self.briefliste()
        self.abschnitt("Telefonate, Treffen, Zahlungen")
        self.akt = AktivitaetenListe(f, self.app, lambda: {"absender_id": self.aktuell_id} if self.aktuell_id else None)
        self.akt.grid(row=self._zeile, column=0, columnspan=3, sticky="ew")
        self._zeile += 1

    def _zeilen(self, suche):
        return self.app.db.absender_liste(suche)

    def _werte(self, a):
        return (a["name"], a["art"] or "", a["ort"] or "", a["briefe"] or "", a["offen"] or ""), ()

    def _holen(self, id_):
        return self.app.db.absender_holen(id_)

    def _anzeigen(self, a):
        self.ueberschrift.configure(text=a.get("name") or "Neuer Absender")
        for var, schluessel in ((self.name, "name"), (self.strasse, "strasse"), (self.plz, "plz"), (self.ort, "ort"),
                                (self.telefon, "telefon"), (self.email, "email"), (self.webseite, "webseite"),
                                (self.kundennummer, "kundennummer")):
            var.set(a.get(schluessel) or "")
        self.art.set(a.get("art") or "")
        self.text_setzen(self.notizen, a.get("notizen"))

    def _listen(self, a):
        db = self.app.db
        id_ = a["id"] if a else None
        liste_leeren(self.ap_tv)
        for ap in db.ansprechpartner_liste(id_):
            self.ap_tv.insert("", "end", iid=str(ap["id"]), values=(
                hilfen.person_name(ap), ap["telefon"] or ap["mobil"] or "", ap["email"] or "", ap["erreichbarkeit"] or ""))
        liste_leeren(self.bank_tv)
        for b in db.bankverbindungen(id_):
            self.bank_tv.insert("", "end", iid=str(b["id"]), values=(
                hilfen.iban_formatieren(b["iban"]), b["bic"] or "", b["bank"] or "", b["kontoinhaber"] or ""))
        self.briefe_fuellen(self.brief_tv, db.briefe(absender_id=id_) if id_ else [])
        self.akt.laden()
        zustand = ["!disabled"] if id_ else ["disabled"]
        self.k_ap_neu.state(zustand)
        self.k_bank_neu.state(zustand)

    def _formular_daten(self):
        return {"name": self.name.get(), "art": self.art.get(), "strasse": self.strasse.get(), "plz": self.plz.get(),
                "ort": self.ort.get(), "telefon": self.telefon.get(), "email": self.email.get(),
                "webseite": self.webseite.get(), "kundennummer": self.kundennummer.get(),
                "notizen": self.notizen.get("1.0", "end").strip()}

    def _db_speichern(self, daten):
        return self.app.db.absender_speichern(daten)

    def _db_loeschen(self, id_):
        self.app.db.absender_loeschen(id_)

    def _loeschen_frage(self, a):
        return (f"Absender „{a['name']}“ löschen?\n\nSeine Ansprechpartner und Bankverbindungen werden mit gelöscht. "
                "Die Briefe bleiben erhalten, haben dann aber keinen Absender mehr.")

    # Ansprechpartner und Bankverbindungen
    def _gewaehlt(self, tv):
        auswahl = tv.selection()
        return int(auswahl[0]) if auswahl else None

    def _nach_unterdialog(self):
        self._listen(self.daten)
        self.app.geaendert(self)

    def _ap_neu(self):
        if self.aktuell_id and AnsprechpartnerDialog(self, self.app.db, self.aktuell_id).zeigen():
            self._nach_unterdialog()

    def _ap_bearbeiten(self):
        id_ = self._gewaehlt(self.ap_tv)
        daten = self.app.db.ansprechpartner_holen(id_) if id_ else None
        if daten and AnsprechpartnerDialog(self, self.app.db, self.aktuell_id, daten).zeigen():
            self._nach_unterdialog()

    def _ap_loeschen(self):
        id_ = self._gewaehlt(self.ap_tv)
        if id_ and self.app.fragen("Diesen Ansprechpartner löschen?"):
            self.app.db.ansprechpartner_loeschen(id_)
            self._nach_unterdialog()

    def _bank_neu(self):
        if self.aktuell_id and BankDialog(self, self.app.db, self.aktuell_id).zeigen():
            self._nach_unterdialog()

    def _bank_bearbeiten(self):
        id_ = self._gewaehlt(self.bank_tv)
        daten = self.app.db.bankverbindung_holen(id_) if id_ else None
        if daten and BankDialog(self, self.app.db, self.aktuell_id, daten).zeigen():
            self._nach_unterdialog()

    def _bank_loeschen(self):
        id_ = self._gewaehlt(self.bank_tv)
        if id_ and self.app.fragen("Diese Bankverbindung löschen?"):
            self.app.db.bankverbindung_loeschen(id_)
            self._nach_unterdialog()


# ====================================================================== Anlässe

class AnlassTab(StammdatenTab):
    titel = "Anlässe"
    neu_text = "＋ Neuer Anlass"
    spalten = [("name", "Anlass", 220, "w"), ("status", "Status", 80, "w"), ("briefe", "Briefe", 60, "center"),
               ("offen", "offen", 60, "center"), ("letzter", "Letzter Brief", 100, "w")]

    def _filter_bauen(self, eltern):
        self.nur_offen = tk.BooleanVar(value=False)
        ttk.Checkbutton(eltern, text="nur offene Anlässe", variable=self.nur_offen,
                        command=self.neu_laden).pack(anchor="w", pady=(0, 6))

    def _formular_bauen(self, f):
        ttk.Label(f, text="Ein Anlass fasst Briefe zum selben Thema zusammen – auch von verschiedenen Absendern, "
                          "z. B. „Autounfall März 2026“ oder „Nebenkosten 2026“.", style="Klein.TLabel",
                  wraplength=520, justify="left").grid(row=self._zeile, column=0, columnspan=3, sticky="w", pady=(0, 8))
        self._zeile += 1
        self.name = self.eingabe("Name")
        self.erstes_feld = f.grid_slaves(row=self._zeile - 1, column=1)[0]
        self.status = ttk.Combobox(f, state="readonly", values=list(hilfen.ANLASS_STATUS.values()), width=14)
        self.status.bind("<<ComboboxSelected>>", lambda e: self.markieren())
        self.feld("Status", self.status, sticky="w")
        self.beschreibung = self.textfeld("Beschreibung", 4)
        self.abschnitt("Briefe zu diesem Anlass", "Zuordnen im Reiter „Briefe“: mehrere markieren → Gruppieren")
        self.brief_tv = self.briefliste()
        self.abschnitt("Telefonate, Treffen, Zahlungen")
        self.akt = AktivitaetenListe(f, self.app, lambda: {"anlass_id": self.aktuell_id} if self.aktuell_id else None)
        self.akt.grid(row=self._zeile, column=0, columnspan=3, sticky="ew")
        self._zeile += 1

    def _zeilen(self, suche):
        return self.app.db.anlaesse(suche, nur_offen=self.nur_offen.get())

    def _werte(self, a):
        tags = ("grau",) if a["status"] == "erledigt" else ()
        return (a["name"], hilfen.ANLASS_STATUS[a["status"]], a["briefe"] or "", a["offen"] or "",
                hilfen.datum_text(a["letzter_brief"])), tags

    def _holen(self, id_):
        return self.app.db.anlass_holen(id_)

    def _anzeigen(self, a):
        self.ueberschrift.configure(text=a.get("name") or "Neuer Anlass")
        self.name.set(a.get("name") or "")
        self.status.current(list(hilfen.ANLASS_STATUS).index(a.get("status") or "offen"))
        self.text_setzen(self.beschreibung, a.get("beschreibung"))

    def _listen(self, a):
        self.briefe_fuellen(self.brief_tv, self.app.db.briefe(anlass_id=a["id"]) if a else [])
        self.akt.laden()

    def _formular_daten(self):
        return {"name": self.name.get(), "status": list(hilfen.ANLASS_STATUS)[self.status.current()],
                "beschreibung": self.beschreibung.get("1.0", "end").strip()}

    def _db_speichern(self, daten):
        return self.app.db.anlass_speichern(daten)

    def _db_loeschen(self, id_):
        self.app.db.anlass_loeschen(id_)

    def _loeschen_frage(self, a):
        return f"Anlass „{a['name']}“ löschen?\n\nDie Briefe bleiben erhalten, sind dann aber keinem Anlass mehr zugeordnet."
