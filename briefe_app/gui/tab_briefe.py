"""Reiter „Briefe“: gruppierte Liste, Fotoanzeige und Formular für den ausgewählten Brief."""
from __future__ import annotations

import datetime as dt
import tkinter as tk
from collections import OrderedDict
from decimal import Decimal
from tkinter import ttk

from .. import hilfen
from ..hilfen import DRINGLICHKEIT, STATUS, Eingabefehler
from . import stil
from .bildanzeige import BildAnzeige
from .dialoge import AnsprechpartnerDialog, BankDialog, ZuordnenDialog
from .tab_aktivitaeten import AktivitaetenListe
from .widgets import DatumFeld, IdAuswahl, KopierLabel, ScrollRahmen, SuchCombobox, knopf, liste, liste_leeren

ANZEIGEN = [("offen", "Offene Briefe"), ("neu", "Neu – noch nicht bearbeitet"), ("dringend", "Dringende"),
            ("ueberfaellig", "Frist überschritten"), ("fristen", "Frist in den nächsten 7 Tagen"),
            ("wartet", "Wartet auf Antwort"), ("erledigt", "Erledigte"), (None, "Alle Briefe")]
GRUPPEN = [("absender", "Absender"), ("anlass", "Anlass"), ("dringlichkeit", "Dringlichkeit"), ("status", "Status"),
           ("monat", "Eingangsmonat"), ("keine", "nicht gruppieren")]
D_TEXT = {1: "niedrig", 2: "normal", 3: "hoch", 4: "sehr dringend"}
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
          "November", "Dezember"]


def brief_titel(b: dict) -> str:
    if (b.get("betreff") or "").strip():
        return b["betreff"]
    return "(neu – noch ohne Betreff)" if b.get("status") == "neu" else "(ohne Betreff)"


class BriefeTab(ttk.Frame):
    def __init__(self, eltern, app):
        super().__init__(eltern)
        self.app = app
        self.veraltet = True
        self.aktuell_id = None
        self._briefe = {}
        self._zu = set()                 # zugeklappte Gruppen
        self._laedt = False
        self._timer = None
        self.sortierung = None           # (spalte, absteigend)

        leiste = ttk.Frame(self, padding=(12, 10, 12, 6))
        leiste.pack(fill="x")
        knopf(leiste, "＋ Neuer Brief", self.neuer_brief, "Leeren Brief anlegen (Strg+N)",
              style="Akzent.TButton").pack(side="left")
        knopf(leiste, "Fotos importieren …", self.app.ordner_importieren,
              "Fotos aus einem beliebigen Ordner übernehmen").pack(side="left", padx=6)
        ttk.Separator(leiste, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Label(leiste, text="Anzeigen").pack(side="left", padx=(0, 6))
        self.anzeigen = ttk.Combobox(leiste, state="readonly", width=27, values=[a[1] for a in ANZEIGEN])
        self.anzeigen.pack(side="left")
        ttk.Label(leiste, text="Gruppieren nach").pack(side="left", padx=(14, 6))
        self.gruppe = ttk.Combobox(leiste, state="readonly", width=17, values=[g[1] for g in GRUPPEN])
        self.gruppe.pack(side="left")
        self.suche = tk.StringVar()
        suchfeld = ttk.Entry(leiste, textvariable=self.suche, width=26)
        suchfeld.pack(side="right")
        ttk.Label(leiste, text="Suche").pack(side="right", padx=(12, 6))
        self.suchfeld = suchfeld

        ansicht = app.konfig.get("ansicht", {})
        self.anzeigen.current(next((i for i, a in enumerate(ANZEIGEN) if a[0] == ansicht.get("status_filter")), 0))
        self.gruppe.current(next((i for i, g in enumerate(GRUPPEN) if g[0] == ansicht.get("gruppierung")), 0))
        self.anzeigen.bind("<<ComboboxSelected>>", lambda e: self._ansicht_geaendert())
        self.gruppe.bind("<<ComboboxSelected>>", lambda e: self._ansicht_geaendert())
        self.suche.trace_add("write", lambda *a: self._spaeter_laden())

        self.paned = ttk.Panedwindow(self, orient="horizontal")
        self.paned.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        links = ttk.Frame(self.paned)
        rahmen, self.tv = liste(links, [
            ("dringlichkeit", "Dringlichkeit", 105, "w"), ("absender", "Absender", 130, "w"),
            ("anlass", "Anlass", 110, "w"), ("eingang", "Eingang", 86, "w"), ("frist", "Frist", 90, "w"),
            ("status", "Status", 115, "w"), ("seiten", "Seiten", 52, "center")],
            hoehe=20, auswahl="extended", baum=True)
        self.tv.heading("#0", text="Betreff")
        self.tv.column("#0", width=230, minwidth=140, stretch=True)
        for spalte in ("dringlichkeit", "eingang", "frist", "status", "seiten"):
            self.tv.column(spalte, stretch=False)
        for spalte in ("absender", "anlass"):
            self.tv.column(spalte, minwidth=70)
        for spalte in ("#0", "dringlichkeit", "absender", "anlass", "eingang", "frist", "status"):
            self.tv.heading(spalte, command=lambda s=spalte: self._sortieren(s))
        rahmen.pack(fill="both", expand=True)
        unten = ttk.Frame(links)
        unten.pack(fill="x", pady=(6, 0))
        self.auswahl_text = ttk.Label(unten, text="", style="Klein.TLabel")
        self.auswahl_text.pack(side="left")
        self.k_loeschen = knopf(unten, "Löschen", self.loeschen, "Ausgewählte Briefe mit allen Fotos löschen")
        self.k_loeschen.pack(side="right")
        self.k_erledigt = knopf(unten, "✓ Erledigt", self.erledigt, "Ausgewählte Briefe als erledigt markieren")
        self.k_erledigt.pack(side="right", padx=4)
        self.k_zusammen = knopf(unten, "Zusammenfassen", self.zusammenfassen,
                                "Mehrere Fotos/Briefe sind eigentlich EIN Brief mit mehreren Seiten")
        self.k_zusammen.pack(side="right")
        self.k_gruppieren = knopf(unten, "Gruppieren …", self.gruppieren,
                                  "Ausgewählte Briefe gemeinsam einem Absender oder Anlass zuordnen")
        self.k_gruppieren.pack(side="right", padx=4)
        self.paned.add(links, weight=4)

        self.bild = BildAnzeige(self.paned, app, bei_aenderung=self._seiten_geaendert)
        self.paned.add(self.bild, weight=3)
        self.formular = BriefFormular(self.paned, app, self)
        self.paned.add(self.formular, weight=3)
        self.paned.bind("<Map>", self._aufteilen, add="+")

        self.tv.bind("<<TreeviewSelect>>", self._auswahl)
        self.tv.bind("<<TreeviewOpen>>", lambda e: self._zu.discard(self.tv.focus()))
        self.tv.bind("<<TreeviewClose>>", lambda e: self._zu.add(self.tv.focus()))
        self.tv.bind("<Delete>", lambda e: self.loeschen())
        self.tv.bind("<Button-3>", self._kontextmenue)
        self.tv.bind("<Button-2>", self._kontextmenue)
        self._knoepfe_aktualisieren([])

    def _aufteilen(self, _e=None):
        """Beim ersten Anzeigen: Liste 40 %, Foto 26 %, Formular 34 % der Breite."""
        self.paned.unbind("<Map>")
        self.update_idletasks()
        breite = self.paned.winfo_width()
        if breite > 300:
            self.paned.sashpos(0, int(breite * 0.40))
            self.paned.sashpos(1, int(breite * 0.66))

    # ------------------------------------------------------------ Laden und Anzeigen

    def _ansicht_geaendert(self):
        ansicht = self.app.konfig.setdefault("ansicht", {})
        ansicht["status_filter"] = ANZEIGEN[self.anzeigen.current()][0]
        ansicht["gruppierung"] = GRUPPEN[self.gruppe.current()][0]
        self.app.konfig_speichern()
        self.neu_laden()

    def _spaeter_laden(self):
        if self._timer:
            self.after_cancel(self._timer)
        self._timer = self.after(300, self.neu_laden)

    def filter_setzen(self, status: str | None, suche: str = "") -> None:
        self.anzeigen.current(next((i for i, a in enumerate(ANZEIGEN) if a[0] == status), 0))
        self.suche.set(suche)
        self.neu_laden()

    def _gruppen(self, briefe, art):
        """Teilt die Briefe in Gruppen auf: [(schluessel, titel, [briefe])]."""
        if art == "keine":
            return [(None, None, briefe)]
        gruppen = OrderedDict()
        for b in briefe:
            if art == "absender":
                schluessel, titel = b["absender_id"] or 0, b["absender"] or "(noch ohne Absender)"
            elif art == "anlass":
                schluessel, titel = b["anlass_id"] or 0, b["anlass"] or "(keinem Anlass zugeordnet)"
            elif art == "dringlichkeit":
                schluessel, titel = -b["dringlichkeit"], DRINGLICHKEIT[b["dringlichkeit"]][0].capitalize()
            elif art == "status":
                schluessel, titel = list(STATUS).index(b["status"]), STATUS[b["status"]]
            else:
                datum = b["eingangsdatum"] or b["briefdatum"]
                schluessel = -(datum.year * 12 + datum.month) if datum else 1
                titel = f"{MONATE[datum.month - 1]} {datum.year}" if datum else "(ohne Datum)"
            gruppen.setdefault(schluessel, (titel, []))[1].append(b)
        if art in ("absender", "anlass"):
            # Nicht zugeordnete Briefe zuerst – um die muss man sich noch kümmern
            reihenfolge = sorted(gruppen, key=lambda k: (k != 0, gruppen[k][0].lower()))
        else:
            reihenfolge = sorted(gruppen)
        return [(k, gruppen[k][0], gruppen[k][1]) for k in reihenfolge]

    def _sortieren(self, spalte):
        if self.sortierung and self.sortierung[0] == spalte:
            self.sortierung = (spalte, not self.sortierung[1])
        else:
            self.sortierung = (spalte, spalte in ("dringlichkeit", "eingang"))
        self.neu_laden()

    def _sortiert(self, briefe):
        if not self.sortierung:
            return briefe
        spalte, absteigend = self.sortierung
        ferne = dt.date(9999, 12, 31) if not absteigend else dt.date(1, 1, 1)
        schluessel = {
            "#0": lambda b: brief_titel(b).lower(),
            "dringlichkeit": lambda b: b["dringlichkeit"],
            "absender": lambda b: (b["absender"] or "").lower(),
            "anlass": lambda b: (b["anlass"] or "").lower(),
            "eingang": lambda b: b["eingangsdatum"] or b["briefdatum"] or ferne,
            "frist": lambda b: b["frist"] or ferne,
            "status": lambda b: list(STATUS).index(b["status"]),
        }[spalte]
        return sorted(briefe, key=schluessel, reverse=absteigend)

    def _werte(self, b):
        frist = hilfen.datum_text(b["frist"])
        if b["frist"] and b["status"] != "erledigt" and b["frist"] < dt.date.today():
            frist += "  überfällig"
        return (D_TEXT[b["dringlichkeit"]], b["absender"] or "", b["anlass"] or "",
                hilfen.datum_text(b["eingangsdatum"]), frist, STATUS[b["status"]], b["fotos"] or "–")

    def _tags(self, b):
        if b["status"] == "erledigt":
            return ("grau",)
        tags = [f"d{b['dringlichkeit']}"]
        if b["frist"] and b["frist"] < dt.date.today():
            tags.append("rot")
        return tuple(tags)

    def neu_laden(self, auswahl_id: int | None = None) -> None:
        self._timer = None
        self.veraltet = False
        status = ANZEIGEN[self.anzeigen.current()][0]
        briefe = self._sortiert(self.app.db.briefe(suche=self.suche.get().strip(), status=status))
        self._briefe = {b["id"]: b for b in briefe}
        art = GRUPPEN[self.gruppe.current()][0]
        alte_auswahl = [i for i in self.ausgewaehlte_ids() if i in self._briefe]
        ziel = auswahl_id or self.aktuell_id
        self._laedt = True
        liste_leeren(self.tv)
        sichtbar = [s for s in ("dringlichkeit", "absender", "anlass", "eingang", "frist", "status", "seiten")
                    if s != art]
        self.tv.configure(displaycolumns=sichtbar)
        for schluessel, titel, gruppe in self._gruppen(briefe, art):
            eltern = ""
            if titel is not None:
                gid = f"g{schluessel}"
                dringend = sum(1 for b in gruppe if b["dringlichkeit"] >= 3 and b["status"] != "erledigt")
                text = f"{titel}  ({len(gruppe)}" + (f", {dringend} dringend)" if dringend else ")")
                self.tv.insert("", "end", iid=gid, text=text, open=gid not in self._zu, tags=("gruppe",))
                eltern = gid
            for b in gruppe:
                self.tv.insert(eltern, "end", iid=f"b{b['id']}", text=brief_titel(b), values=self._werte(b),
                               tags=self._tags(b))
        self._laedt = False
        if auswahl_id is not None and auswahl_id not in alte_auswahl:
            alte_auswahl = [auswahl_id]
        auswahl = [f"b{i}" for i in (alte_auswahl or [ziel]) if i in self._briefe]
        if ziel and ziel not in self._briefe and auswahl_id is None:
            ziel = None
        if auswahl:
            self.tv.selection_set(auswahl)
            fokus = f"b{ziel}" if ziel in self._briefe else auswahl[0]
            self.tv.focus(fokus)
            self.tv.see(fokus)
        if ziel != self.aktuell_id or ziel is None:
            self.oeffnen(ziel if ziel in self._briefe else None)
        else:
            self.bild.neu_laden()
        self._knoepfe_aktualisieren(self.ausgewaehlte_ids())

    def zeile_aktualisieren(self, brief_id: int) -> None:
        b = self.app.db.brief_holen(brief_id)
        if b and self.tv.exists(f"b{brief_id}"):
            self._briefe[brief_id] = b
            self.tv.item(f"b{brief_id}", text=brief_titel(b), values=self._werte(b), tags=self._tags(b))

    def ausgewaehlte_ids(self) -> list:
        return [int(i[1:]) for i in self.tv.selection() if i.startswith("b")]

    def _knoepfe_aktualisieren(self, ids):
        self.auswahl_text.configure(text=f"{len(ids)} ausgewählt" if len(ids) > 1 else "")
        for k in (self.k_gruppieren, self.k_erledigt, self.k_loeschen):
            k.state(["!disabled"] if ids else ["disabled"])
        self.k_zusammen.state(["!disabled"] if len(ids) > 1 else ["disabled"])

    def _auswahl(self, _e=None):
        if self._laedt:
            return
        ids = self.ausgewaehlte_ids()
        self._knoepfe_aktualisieren(ids)
        fokus = self.tv.focus()
        brief_id = int(fokus[1:]) if fokus.startswith("b") and int(fokus[1:]) in ids else (ids[0] if ids else None)
        if brief_id is None or brief_id == self.aktuell_id:
            return
        gespeichert = self.formular.geaendert
        if not self.formular.wechsel_erlaubt():
            if self.aktuell_id and self.tv.exists(f"b{self.aktuell_id}"):
                self.tv.selection_set(f"b{self.aktuell_id}")
            return
        self.oeffnen(brief_id)
        if gespeichert:
            self.after_idle(self.neu_laden)

    def oeffnen(self, brief_id) -> None:
        self.aktuell_id = brief_id
        self.formular.zeigen(brief_id)
        self.bild.zeigen(brief_id)

    def auswaehlen(self, brief_id: int) -> None:
        """Brief in der Liste markieren und öffnen – bei Bedarf werden Filter zurückgesetzt."""
        if not self.formular.wechsel_erlaubt():
            return
        if brief_id not in self._briefe:
            self.anzeigen.current(len(ANZEIGEN) - 1)        # „Alle Briefe“
            self.suche.set("")
            if self._timer:
                self.after_cancel(self._timer)
        self.tv.selection_set(())
        self.neu_laden(auswahl_id=brief_id)

    def _seiten_geaendert(self, neuer_brief_id=None):
        self.neu_laden()
        self.app.geaendert(self)
        if neuer_brief_id:
            self.app.status(f"Seite abgetrennt – neuer Brief Nr. {neuer_brief_id}.")

    # ------------------------------------------------------------ Aktionen

    def neuer_brief(self) -> None:
        if not self.formular.wechsel_erlaubt():
            return
        neu_id = self.app.db.brief_neu("", status="in_bearbeitung")
        self.app.geaendert(self)
        if ANZEIGEN[self.anzeigen.current()][0] not in ("offen", None):
            self.anzeigen.current(0)
        self.suche.set("")
        self.tv.selection_set(())
        self.neu_laden(auswahl_id=neu_id)
        self.formular.betreff_feld.focus_set()

    def gruppieren(self) -> None:
        ids = self.ausgewaehlte_ids()
        if not ids or not self.formular.wechsel_erlaubt():
            return
        aenderungen = ZuordnenDialog(self, self.app.db, len(ids)).zeigen()
        if aenderungen:
            self.app.db.briefe_zuordnen(ids, **aenderungen)
            self.aktuell_id = None
            self.neu_laden(auswahl_id=ids[0])
            self.app.geaendert(self)
            self.app.status(f"{hilfen.anzahl(len(ids), 'Brief', 'Briefe')} zugeordnet.")

    def zusammenfassen(self) -> None:
        ids = self.ausgewaehlte_ids()
        if len(ids) < 2 or not self.formular.wechsel_erlaubt():
            return
        ziel = self.aktuell_id if self.aktuell_id in ids else ids[0]
        seiten = sum(int(self._briefe[i]["fotos"] or 0) for i in ids if i in self._briefe)
        if not self.app.fragen(f"Die {len(ids)} ausgewählten Briefe zu EINEM Brief mit "
                               f"{hilfen.anzahl(seiten, 'Seite', 'Seiten')} zusammenfassen?\n\n"
                               f"Er heißt dann „{brief_titel(self._briefe[ziel])}“. Telefonate, Zahlungen usw. "
                               "werden mit übernommen."):
            return
        self.app.db.briefe_zusammenfassen(ziel, [i for i in ids if i != ziel])
        self.aktuell_id = None
        self.tv.selection_set(())
        self.neu_laden(auswahl_id=ziel)
        self.app.geaendert(self)

    def erledigt(self) -> None:
        ids = self.ausgewaehlte_ids()
        if ids and self.formular.wechsel_erlaubt():
            self.app.db.briefe_zuordnen(ids, status="erledigt")
            self.aktuell_id = None
            self.neu_laden()
            self.app.geaendert(self)

    def setzen(self, **werte) -> None:
        ids = self.ausgewaehlte_ids()
        if ids and self.formular.wechsel_erlaubt():
            self.app.db.briefe_zuordnen(ids, **werte)
            self.aktuell_id = None
            self.neu_laden()
            self.app.geaendert(self)

    def loeschen(self) -> None:
        ids = self.ausgewaehlte_ids()
        if not ids:
            return
        text = (f"„{brief_titel(self._briefe[ids[0]])}“" if len(ids) == 1 and ids[0] in self._briefe
                else f"{len(ids)} Briefe")
        if not self.app.fragen(f"{text} mit allen Fotos endgültig löschen?\n\n"
                               "Telefonate, Zahlungen usw. bleiben erhalten, gehören dann aber zu keinem Brief mehr."):
            return
        for brief_id in ids:
            self.app.db.brief_loeschen(brief_id)
        self.formular.geaendert = False
        self.aktuell_id = None
        self.tv.selection_set(())
        self.neu_laden()
        self.app.geaendert(self)

    def _kontextmenue(self, event):
        zeile = self.tv.identify_row(event.y)
        if zeile.startswith("b") and zeile not in self.tv.selection():
            self.tv.selection_set(zeile)
            self.tv.focus(zeile)
        if not self.ausgewaehlte_ids():
            return
        menue = tk.Menu(self, tearoff=False)
        menue.add_command(label="Gruppieren (Absender / Anlass zuordnen) …", command=self.gruppieren)
        if len(self.ausgewaehlte_ids()) > 1:
            menue.add_command(label="Zu einem Brief zusammenfassen", command=self.zusammenfassen)
        dringlich = tk.Menu(menue, tearoff=False)
        for stufe, (name, _f, _h) in DRINGLICHKEIT.items():
            dringlich.add_command(label=name, command=lambda s=stufe: self.setzen(dringlichkeit=s))
        menue.add_cascade(label="Dringlichkeit", menu=dringlich)
        status = tk.Menu(menue, tearoff=False)
        for schluessel, name in STATUS.items():
            status.add_command(label=name, command=lambda s=schluessel: self.setzen(status=s))
        menue.add_cascade(label="Status", menu=status)
        menue.add_separator()
        menue.add_command(label="Löschen …", command=self.loeschen)
        menue.tk_popup(event.x_root, event.y_root)


class BriefFormular(ttk.Frame):
    """Alle Angaben zu einem Brief. Änderungen werden mit „Speichern“ (Strg+S) oder beim Wechsel gespeichert."""

    def __init__(self, eltern, app, tab: BriefeTab):
        super().__init__(eltern)
        self.app, self.tab = app, tab
        self.brief = None
        self.geaendert = False
        self._laedt = False
        self._absender_id = None
        self._status_beruehrt = False
        self.scroll = ScrollRahmen(self, polster=(16, 10, 16, 20))
        self.scroll.pack(fill="both", expand=True)
        f = self.scroll.innen
        f.columnconfigure(1, weight=1)
        self._eingaben = []

        kopf = ttk.Frame(f)
        kopf.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.titel = ttk.Label(kopf, text="Brief", style="Titel.TLabel")
        self.titel.pack(side="left")
        self.k_speichern = ttk.Button(kopf, text="Speichern", style="Akzent.TButton", command=self.speichern)
        self.k_speichern.pack(side="right")
        self.markierung = ttk.Label(kopf, text="", style="Warnung.TLabel")
        self.markierung.pack(side="right", padx=8)
        self.unterzeile = ttk.Label(f, text="", style="Klein.TLabel")
        self.unterzeile.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 10))
        self._zeile = 2

        self.betreff = tk.StringVar()
        self.betreff_feld = self._feld("Betreff", ttk.Entry(f, textvariable=self.betreff))

        self.absender = SuchCombobox(f)
        self._feld("Absender", self.absender, [("✎", self._absender_oeffnen, "Absender ansehen und bearbeiten")])
        for ereignis in ("<<ComboboxSelected>>", "<FocusOut>", "<Return>"):
            self.absender.bind(ereignis, lambda e: self._absender_geaendert(), add="+")

        self.ap = IdAuswahl(f)
        self._feld("Ansprechpartner", self.ap, [("＋", self._ap_neu, "Neuen Ansprechpartner eintragen"),
                                                ("✎", self._ap_bearbeiten, "Ansprechpartner bearbeiten")])
        self.ap.bind("<<ComboboxSelected>>", lambda e: (self._markieren(), self._infos()))
        self.ap_info = ttk.Frame(f)
        self.ap_info.grid(row=self._zeile, column=1, columnspan=2, sticky="w")
        self._zeile += 1

        self.bank = IdAuswahl(f)
        self._feld("Bankverbindung", self.bank, [("＋", self._bank_neu, "Neue Bankverbindung eintragen"),
                                                 ("✎", self._bank_bearbeiten, "Bankverbindung bearbeiten")])
        self.bank.bind("<<ComboboxSelected>>", lambda e: (self._markieren(), self._infos()))
        self.bank_info = ttk.Frame(f)
        self.bank_info.grid(row=self._zeile, column=1, columnspan=2, sticky="w")
        self._zeile += 1

        self.anlass = SuchCombobox(f)
        self._feld("Anlass", self.anlass, [("✎", self._anlass_oeffnen, "Anlass ansehen")])
        self.anlass.bind("<<ComboboxSelected>>", lambda e: self._markieren(), add="+")

        self.dringlichkeit = tk.IntVar(value=2)
        reihe = ttk.Frame(f)
        for stufe, (name, _farbe, _hell) in DRINGLICHKEIT.items():
            k = ttk.Radiobutton(reihe, text=name, value=stufe, variable=self.dringlichkeit,
                                style=f"D{stufe}.Toolbutton", command=self._markieren)
            k.pack(side="left", padx=(0, 3))
            self._eingaben.append(k)
        self._feld("Dringlichkeit", reihe, eingabe=False)

        self.status = ttk.Combobox(f, state="readonly", values=list(STATUS.values()), width=22)
        self._feld("Status", self.status, sticky="w")
        self.status.bind("<<ComboboxSelected>>", lambda e: (setattr(self, "_status_beruehrt", True), self._markieren()))

        self.briefdatum = DatumFeld(f, bei_aenderung=self._markieren)
        self._feld("Briefdatum", self.briefdatum, eingabe=False, sticky="w")
        self.eingang = DatumFeld(f, bei_aenderung=self._markieren)
        self._feld("Eingegangen am", self.eingang, eingabe=False, sticky="w")
        self._eingaben += [self.briefdatum.eingabe, self.eingang.eingabe]

        reihe = ttk.Frame(f)
        self.frist = DatumFeld(reihe, bei_aenderung=lambda: (self._markieren(), self._frist_info()))
        self.frist.pack(side="left")
        self.frist_info = ttk.Label(reihe, text="")
        self.frist_info.pack(side="left", padx=10)
        self._feld("Frist / fällig", reihe, eingabe=False)
        self._eingaben.append(self.frist.eingabe)

        reihe = ttk.Frame(f)
        self.betrag = tk.StringVar()
        betrag_feld = ttk.Entry(reihe, textvariable=self.betrag, width=14)
        betrag_feld.pack(side="left")
        ttk.Label(reihe, text="€").pack(side="left", padx=(4, 0))
        self._feld("Betrag", reihe, eingabe=False)
        self._eingaben.append(betrag_feld)
        self.bezahlt_info = ttk.Label(f, text="", style="Klein.TLabel")
        self.bezahlt_info.grid(row=self._zeile, column=1, columnspan=2, sticky="w")
        self._zeile += 1

        self.aktenzeichen = tk.StringVar()
        self._feld("Aktenzeichen", ttk.Entry(f, textvariable=self.aktenzeichen))

        self.notizen = tk.Text(f, height=5, width=30, wrap="word", font=stil.schrift("normal"), padx=6, pady=4)
        self._feld("Notizen", self.notizen)
        self.notizen.bind("<<Modified>>", self._text_geaendert)

        reihe = ttk.Frame(f)
        reihe.grid(row=self._zeile, column=1, columnspan=2, sticky="ew", pady=(6, 0))
        self._zeile += 1
        self.k_loeschen = ttk.Button(reihe, text="Brief löschen …", style="Gefahr.TButton", command=self.tab.loeschen)
        self.k_loeschen.pack(side="right")
        self.k_verwerfen = ttk.Button(reihe, text="Änderungen verwerfen", command=self.verwerfen)
        self.k_verwerfen.pack(side="left")

        ttk.Separator(f).grid(row=self._zeile, column=0, columnspan=3, sticky="ew", pady=14)
        self._zeile += 1
        ttk.Label(f, text="Telefonate, Treffen, Zahlungen", style="Untertitel.TLabel").grid(
            row=self._zeile, column=0, columnspan=3, sticky="w", pady=(0, 6))
        self._zeile += 1
        self.aktivitaeten = AktivitaetenListe(f, app, self._kontext, bei_aenderung=self._akt_geaendert, kompakt=True)
        self.aktivitaeten.grid(row=self._zeile, column=0, columnspan=3, sticky="nsew")

        for var in (self.betreff, self.betrag, self.aktenzeichen):
            var.trace_add("write", lambda *a: self._markieren())
        self.absender.bind("<KeyRelease>", lambda e: self._markieren(), add="+")
        self.anlass.bind("<KeyRelease>", lambda e: self._markieren(), add="+")
        self.zeigen(None)

    def _feld(self, text, widget, knoepfe=(), eingabe=True, sticky="ew"):
        f = self.scroll.innen
        ttk.Label(f, text=text).grid(row=self._zeile, column=0, sticky="nw", pady=4, padx=(0, 10))
        widget.grid(row=self._zeile, column=1, columnspan=1 if knoepfe else 2, sticky=sticky, pady=4)
        if knoepfe:
            rahmen = ttk.Frame(f)
            rahmen.grid(row=self._zeile, column=2, sticky="w", padx=(4, 0))
            for zeichen, befehl, tipp in knoepfe:
                k = knopf(rahmen, zeichen, befehl, tipp, width=3, style="Klein.TButton")
                k.pack(side="left", padx=(0, 2))
                self._eingaben.append(k)
        if eingabe:
            self._eingaben.append(widget)
        self._zeile += 1
        return widget

    def _kontext(self):
        return {"brief_id": self.brief["id"]} if self.brief else None

    # ------------------------------------------------------------ Anzeigen

    def zeigen(self, brief_id) -> None:
        db = self.app.db
        self._laedt = True
        self.brief = db.brief_holen(brief_id) if brief_id else None
        b = self.brief or {}
        self.absender.werte_setzen(db.absender_namen())
        self.anlass.werte_setzen(db.anlass_namen())
        self.betreff.set(b.get("betreff") or "")
        self.absender.set(b.get("absender") or "")
        self._absender_id = b.get("absender_id")
        self._listen_laden(self._absender_id)
        self.ap.id = b.get("ansprechpartner_id")
        self.bank.id = b.get("bankverbindung_id")
        self.anlass.set(b.get("anlass") or "")
        self.dringlichkeit.set(b.get("dringlichkeit") or 2)
        self.status.current(list(STATUS).index(b.get("status") or "neu"))
        self.briefdatum.setzen(b.get("briefdatum"))
        self.eingang.setzen(b.get("eingangsdatum"))
        self.frist.setzen(b.get("frist"))
        self.betrag.set(hilfen.betrag_text(b.get("betrag"), False))
        self.aktenzeichen.set(b.get("aktenzeichen") or "")
        self.notizen.configure(state="normal")
        self.notizen.delete("1.0", "end")
        self.notizen.insert("1.0", b.get("notizen") or "")
        self.notizen.edit_modified(False)
        self.notizen.edit_reset()
        self._status_beruehrt = False
        self._laedt = False
        self._markierung_weg()
        zustand = ["!disabled"] if self.brief else ["disabled"]
        for w in self._eingaben:
            if isinstance(w, tk.Text):
                continue
            if isinstance(w, ttk.Combobox) and not isinstance(w, SuchCombobox) and self.brief:
                w.state(["!disabled", "readonly"])
            else:
                w.state(zustand)
        self.notizen.configure(state="normal" if self.brief else "disabled")
        self.k_loeschen.state(zustand)
        if self.brief:
            self.titel.configure(text=f"Brief Nr. {b['id']}")
            teile = [hilfen.anzahl(int(b["fotos"] or 0), "Seite", "Seiten"),
                     "angelegt " + hilfen.datum_text(b["erstellt_am"])]
            if b["geaendert_am"] and b["geaendert_am"] != b["erstellt_am"]:
                teile.append("geändert " + hilfen.datum_text(b["geaendert_am"]))
            self.unterzeile.configure(text="  ·  ".join(teile))
        else:
            self.titel.configure(text="Kein Brief ausgewählt")
            self.unterzeile.configure(text="Links einen Brief anklicken – oder einen USB-Stick mit dem Ordner "
                                           "„Briefe“ einstecken.")
        self._infos()
        self._frist_info()
        self._bezahlt_info()
        self.aktivitaeten.laden()
        self.scroll.nach_oben()

    def _listen_laden(self, absender_id, vorschlagen: bool = False):
        db = self.app.db
        aps = db.ansprechpartner_liste(absender_id)
        banken = db.bankverbindungen(absender_id)
        self.ap.optionen([(a["id"], hilfen.person_name(a) or "(ohne Namen)") for a in aps])
        self.bank.optionen([(k["id"], f"{hilfen.iban_formatieren(k['iban'])}  {k['bank'] or ''}".strip())
                            for k in banken])
        if vorschlagen:
            # Gibt es nur einen Ansprechpartner / eine Bankverbindung, gleich vorschlagen
            if self.ap.id is None and len(aps) == 1:
                self.ap.id = aps[0]["id"]
            if self.bank.id is None and len(banken) == 1:
                self.bank.id = banken[0]["id"]

    def _infos(self):
        for rahmen in (self.ap_info, self.bank_info):
            for kind in rahmen.winfo_children():
                kind.destroy()
        db = self.app.db
        ap = db.ansprechpartner_holen(self.ap.id) if self.ap.id else None
        if ap:
            for zeichen, schluessel in (("☎", "telefon"), ("Mobil", "mobil"), ("✉", "email")):
                if ap.get(schluessel):
                    l = KopierLabel(self.ap_info)
                    l.setzen(f"{zeichen} {ap[schluessel]}", ap[schluessel])
                    l.pack(anchor="w")
            if ap.get("erreichbarkeit"):
                ttk.Label(self.ap_info, text="erreichbar " + ap["erreichbarkeit"], style="Klein.TLabel").pack(anchor="w")
        bank = db.bankverbindung_holen(self.bank.id) if self.bank.id else None
        if bank:
            l = KopierLabel(self.bank_info)
            l.setzen(f"IBAN {hilfen.iban_formatieren(bank['iban'])}", bank["iban"])
            l.pack(anchor="w")
            zeile = ttk.Frame(self.bank_info)
            zeile.pack(anchor="w")
            if bank.get("bic"):
                l = KopierLabel(zeile)
                l.setzen(f"BIC {bank['bic']}", bank["bic"])
                l.pack(side="left", padx=(0, 10))
            if bank.get("kontoinhaber"):
                ttk.Label(zeile, text=bank["kontoinhaber"], style="Klein.TLabel").pack(side="left")

    def _frist_info(self):
        try:
            frist = self.frist.wert()
        except Eingabefehler:
            self.frist_info.configure(text="ungültiges Datum", foreground=stil.ROT)
            return
        text = hilfen.frist_text(frist)
        if not frist:
            farbe = stil.GRAU
        elif frist < dt.date.today():
            farbe = stil.ROT
        elif (frist - dt.date.today()).days <= 3:
            farbe = stil.ORANGE
        else:
            farbe = stil.GRUEN
        self.frist_info.configure(text=text, foreground=farbe)

    def _bezahlt_info(self):
        b = self.brief
        if not b or not (b.get("bezahlt") or b.get("betrag")):
            self.bezahlt_info.configure(text="")
            return
        bezahlt = Decimal(b.get("bezahlt") or 0)
        text = f"bezahlt {hilfen.betrag_text(bezahlt)}"
        if b.get("betrag"):
            offen = Decimal(b["betrag"]) - bezahlt
            text += f"  ·  offen {hilfen.betrag_text(max(offen, Decimal('0')))}" if offen > 0 else "  ·  ✓ vollständig"
        self.bezahlt_info.configure(text=text)

    # ------------------------------------------------------------ Änderungen

    def _markieren(self, *_):
        if self._laedt or not self.brief:
            return
        if not self.geaendert:
            self.geaendert = True
            self.markierung.configure(text="● nicht gespeichert")
            self.k_speichern.state(["!disabled"])
            self.k_verwerfen.state(["!disabled"])

    def _markierung_weg(self):
        self.geaendert = False
        self.markierung.configure(text="")
        self.k_speichern.state(["disabled"])
        self.k_verwerfen.state(["disabled"])

    def _text_geaendert(self, _e=None):
        if self.notizen.edit_modified():
            self._markieren()
            self.notizen.edit_modified(False)

    def _absender_geaendert(self):
        if self._laedt or not self.brief:
            return
        name = self.absender.get().strip()
        absender_id = self.app.db.wert("SELECT id FROM absender WHERE name = %s", (name,)) if name else None
        if absender_id == self._absender_id:
            return
        self._absender_id = absender_id
        self.ap.id = None
        self.bank.id = None
        self._listen_laden(absender_id, vorschlagen=True)
        self._infos()
        self._markieren()

    def _absender_sicherstellen(self):
        """Legt den eingetippten Absender an (falls neu) und gibt seine ID zurück."""
        name = self.absender.get().strip()
        if not name:
            self.app.hinweis("Bitte zuerst den Absender eintragen – Ansprechpartner und Bankverbindungen "
                             "gehören immer zu einem Absender.")
            self.absender.focus_set()
            return None
        absender_id = self.app.db.absender_id_fuer(name)
        if absender_id != self._absender_id:
            self._absender_id = absender_id
            self._listen_laden(absender_id)
            self._markieren()
        self.absender.werte_setzen(self.app.db.absender_namen())
        return absender_id

    def _ap_neu(self):
        absender_id = self._absender_sicherstellen()
        if absender_id:
            neu = AnsprechpartnerDialog(self, self.app.db, absender_id).zeigen()
            if neu:
                self._listen_laden(absender_id)
                self.ap.id = neu
                self._markieren()
                self._infos()
                self.app.geaendert(self.tab)

    def _ap_bearbeiten(self):
        if not self.ap.id:
            self._ap_neu()
            return
        daten = self.app.db.ansprechpartner_holen(self.ap.id)
        if daten and AnsprechpartnerDialog(self, self.app.db, daten["absender_id"], daten).zeigen():
            self._listen_laden(self._absender_id)
            self._infos()
            self.app.geaendert(self.tab)

    def _bank_neu(self):
        absender_id = self._absender_sicherstellen()
        if absender_id:
            neu = BankDialog(self, self.app.db, absender_id).zeigen()
            if neu:
                self._listen_laden(absender_id)
                self.bank.id = neu
                self._markieren()
                self._infos()
                self.app.geaendert(self.tab)

    def _bank_bearbeiten(self):
        if not self.bank.id:
            self._bank_neu()
            return
        daten = self.app.db.bankverbindung_holen(self.bank.id)
        if daten and BankDialog(self, self.app.db, daten["absender_id"], daten).zeigen():
            self._listen_laden(self._absender_id)
            self._infos()
            self.app.geaendert(self.tab)

    def _absender_oeffnen(self):
        absender_id = self._absender_sicherstellen()
        if absender_id and self.wechsel_erlaubt():
            self.app.absender_zeigen(absender_id)

    def _anlass_oeffnen(self):
        if not self.anlass.get().strip():
            self.app.hinweis("Trage einen Anlass ein (z. B. „Nebenkosten 2026“), um Briefe zum selben Thema "
                             "zu gruppieren.")
            return
        if self.wechsel_erlaubt():
            self.app.anlass_zeigen(self.app.db.anlass_id_fuer(self.anlass.get()))

    def _akt_geaendert(self, art):
        self.brief = self.app.db.brief_holen(self.brief["id"]) if self.brief else None
        self._bezahlt_info()
        b = self.brief
        if art == "Zahlung" and b and b["betrag"] and b["status"] != "erledigt" \
                and Decimal(b["bezahlt"] or 0) >= Decimal(b["betrag"]) and not self.geaendert:
            if self.app.fragen("Der Betrag ist vollständig bezahlt. Brief als erledigt markieren?"):
                self.app.db.brief_speichern({"id": b["id"], "status": "erledigt"})
                self.zeigen(b["id"])
                self.tab.neu_laden()
                return
        if b:
            self.tab.zeile_aktualisieren(b["id"])

    def _daten(self) -> dict:
        # Zuerst alles prüfen, erst dann evtl. neue Absender/Anlässe anlegen
        briefdatum, eingang, frist = self.briefdatum.wert(), self.eingang.wert(), self.frist.wert()
        betrag = hilfen.betrag_lesen(self.betrag.get())
        status = list(STATUS)[self.status.current()]
        if status == "neu" and not self._status_beruehrt:
            status = "in_bearbeitung"            # wer etwas einträgt, bearbeitet den Brief
        db = self.app.db
        absender_id = db.absender_id_fuer(self.absender.get())
        if absender_id != self._absender_id:
            self._absender_id = absender_id
            self._listen_laden(absender_id)
        return {"id": self.brief["id"], "betreff": self.betreff.get(), "absender_id": absender_id,
                "ansprechpartner_id": self.ap.id, "bankverbindung_id": self.bank.id,
                "anlass_id": db.anlass_id_fuer(self.anlass.get()), "briefdatum": briefdatum, "eingangsdatum": eingang,
                "frist": frist, "dringlichkeit": self.dringlichkeit.get(), "status": status, "betrag": betrag,
                "aktenzeichen": self.aktenzeichen.get(), "notizen": self.notizen.get("1.0", "end").strip()}

    def speichern(self, neu_laden: bool = True) -> bool:
        if not self.brief or not self.geaendert:
            return True
        self.app.db.brief_speichern(self._daten())
        brief_id = self.brief["id"]
        self._markierung_weg()
        self.app.geaendert(self.tab)
        self.app.status("Gespeichert.")
        if neu_laden:
            self.zeigen(brief_id)
            self.tab.neu_laden(auswahl_id=brief_id)
        else:
            self.tab.veraltet = True             # Liste beim nächsten Anzeigen auffrischen
        return True

    def verwerfen(self):
        if self.brief:
            self.zeigen(self.brief["id"])

    def wechsel_erlaubt(self) -> bool:
        """Vor dem Wechsel zu einem anderen Brief: Änderungen speichern (oder auf Wunsch verwerfen)."""
        if not self.geaendert:
            return True
        try:
            return self.speichern(neu_laden=False)
        except Eingabefehler as fehler:
            if self.app.fragen(f"Die Änderungen können nicht gespeichert werden:\n\n{fehler}\n\nÄnderungen verwerfen?"):
                self._markierung_weg()
                return True
            return False
