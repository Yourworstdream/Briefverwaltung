"""Reiter „SQL“: eigene MySQL-Abfragen schreiben und das Ergebnis als Tabelle sehen."""
from __future__ import annotations

import csv
import datetime as dt
import time
import tkinter as tk
from decimal import Decimal
from tkinter import filedialog, ttk

from ..datenbank import beispiele_laden, ist_lesend, sql_aufteilen
from . import stil
from .widgets import knopf, liste_leeren

BEISPIELE = beispiele_laden()


def zelle(wert) -> str:
    if wert is None:
        return "NULL"
    if isinstance(wert, (bytes, bytearray)):
        return f"<Binärdaten, {len(wert) / 1024:.0f} KB>"
    if isinstance(wert, dt.datetime):
        return wert.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(wert, (dt.date, Decimal)):
        return str(wert)
    return " ".join(str(wert).split())[:300]


class SqlTab(ttk.Frame):
    def __init__(self, eltern, app):
        super().__init__(eltern, padding=(12, 10))
        self.app = app
        self.veraltet = True
        self._verbindung = None
        self._letztes = None

        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)

        links = ttk.Frame(paned)
        ttk.Label(links, text="Tabellen und Sichten", style="Untertitel.TLabel").pack(anchor="w", pady=(0, 6))
        self.tabellen = ttk.Treeview(links, show="tree", selectmode="browse")
        self.tabellen.pack(fill="both", expand=True)
        self.tabellen.bind("<Double-1>", self._tabelle_zeigen)
        self.tabellen.bind("<<TreeviewOpen>>", self._spalten_laden)
        ttk.Label(links, text="Doppelklick: Inhalt anzeigen", style="Klein.TLabel").pack(anchor="w", pady=(4, 0))
        paned.add(links, weight=1)

        rechts = ttk.Panedwindow(paned, orient="vertical")
        paned.add(rechts, weight=4)
        oben = ttk.Frame(rechts)
        leiste = ttk.Frame(oben)
        leiste.pack(fill="x", pady=(0, 6))
        knopf(leiste, "▶ Ausführen", self.ausfuehren, "Strg+Enter oder F5", style="Akzent.TButton").pack(side="left")
        ttk.Label(leiste, text="Beispiel").pack(side="left", padx=(16, 6))
        self.beispiele = ttk.Combobox(leiste, state="readonly", width=34, values=[b[0] for b in BEISPIELE])
        self.beispiele.pack(side="left")
        self.beispiele.bind("<<ComboboxSelected>>", self._beispiel)
        ttk.Label(leiste, text="Änderungen (UPDATE, DELETE …) werden vorher bestätigt.",
                  style="Klein.TLabel").pack(side="right")
        self.editor = tk.Text(oben, height=8, wrap="none", font=stil.schrift("mono"), undo=True, padx=8, pady=6)
        self.editor.pack(fill="both", expand=True)
        self.editor.insert("1.0", BEISPIELE[0][1])
        self.editor.bind("<Control-Return>", lambda e: (self.ausfuehren(), "break")[1])
        self.editor.bind("<F5>", lambda e: (self.ausfuehren(), "break")[1])
        rechts.add(oben, weight=1)

        unten = ttk.Frame(rechts)
        self.ergebnis = ttk.Treeview(unten, show="headings", selectmode="extended")
        senkrecht = ttk.Scrollbar(unten, orient="vertical", command=self.ergebnis.yview)
        waagrecht = ttk.Scrollbar(unten, orient="horizontal", command=self.ergebnis.xview)
        self.ergebnis.configure(yscrollcommand=senkrecht.set, xscrollcommand=waagrecht.set)
        self.ergebnis.grid(row=0, column=0, sticky="nsew", pady=(8, 0))
        senkrecht.grid(row=0, column=1, sticky="ns", pady=(8, 0))
        waagrecht.grid(row=1, column=0, sticky="ew")
        unten.rowconfigure(0, weight=1)
        unten.columnconfigure(0, weight=1)
        fuss = ttk.Frame(unten)
        fuss.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.meldung = ttk.Label(fuss, text="", style="Klein.TLabel")
        self.meldung.pack(side="left")
        self.k_csv = knopf(fuss, "Als CSV speichern …", self.csv_speichern, "Ergebnis für Excel/LibreOffice speichern")
        self.k_csv.pack(side="right")
        self.k_csv.state(["disabled"])
        rechts.add(unten, weight=3)

    def _db(self):
        """Eigene Verbindung, damit z. B. „USE andere_db“ das Programm nicht durcheinanderbringt."""
        if self._verbindung is None:
            self._verbindung = self.app.db.kopie()
        return self._verbindung

    def neu_laden(self) -> None:
        self.veraltet = False
        liste_leeren(self.tabellen)
        for t in self.app.db.tabellen():
            text = t["name"] + ("   (Sicht)" if t["typ"] == "VIEW" else "")
            knoten = self.tabellen.insert("", "end", iid=f"t:{t['name']}", text=text)
            self.tabellen.insert(knoten, "end", text="…")

    def _spalten_laden(self, _e=None):
        knoten = self.tabellen.focus()
        if not knoten.startswith("t:"):
            return
        self.tabellen.delete(*self.tabellen.get_children(knoten))
        for s in self.app.db.spalten(knoten[2:]):
            schluessel = {"PRI": "  [PK]", "UNI": "  [eindeutig]", "MUL": "  [FK/Index]"}
            self.tabellen.insert(knoten, "end", text=f"{s['name']}  {s['typ']}{schluessel.get(s['schluessel'], '')}")

    def _tabelle_zeigen(self, _e=None):
        knoten = self.tabellen.focus()
        if knoten.startswith("t:"):
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", f"SELECT *\nFROM `{knoten[2:]}`\nLIMIT 200;")
            self.ausfuehren()

    def _beispiel(self, _e=None):
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", BEISPIELE[self.beispiele.current()][1])
        self.ausfuehren()

    def ausfuehren(self) -> None:
        text = self.editor.get("sel.first", "sel.last") if self.editor.tag_ranges("sel") else self.editor.get("1.0", "end")
        befehle = sql_aufteilen(text)
        if not befehle:
            return
        aendernd = [b for b in befehle if not ist_lesend(b)]
        if aendernd and not self.app.fragen(
                "Diese Befehle verändern die Datenbank:\n\n" + "\n".join(b[:120] for b in aendernd[:5]) +
                "\n\nWirklich ausführen? Das lässt sich nicht rückgängig machen."):
            return
        start = time.perf_counter()
        try:
            ergebnisse = self._db().sql_ausfuehren(";\n".join(befehle))
        except Exception as fehler:                  # Fehler im SQL: verständlich anzeigen
            if "connect" in str(fehler).lower():
                self._verbindung = None              # beim nächsten Mal neu verbinden
            self.meldung.configure(text=f"Fehler: {fehler.args[-1] if getattr(fehler, 'args', None) else fehler}",
                                   style="Warnung.TLabel")
            self.bell()
            return
        dauer = time.perf_counter() - start
        mit_tabelle = [e for e in ergebnisse if e["spalten"]]
        letztes = mit_tabelle[-1] if mit_tabelle else None
        self._anzeigen(letztes)
        if letztes:
            text = f"{len(letztes['zeilen'])} Zeilen" + (" (gekürzt)" if letztes["mehr"] else "")
        else:
            text = f"{sum(max(e['betroffen'], 0) for e in ergebnisse)} Zeilen betroffen"
        if len(ergebnisse) > 1:
            text += f"  ·  {len(ergebnisse)} Befehle"
        self.meldung.configure(text=f"{text}  ·  {dauer:.3f} s".replace(".", ","), style="Klein.TLabel")
        if aendernd:
            self.app.geaendert(self)
            self.neu_laden()

    def _anzeigen(self, ergebnis) -> None:
        self._letztes = ergebnis
        liste_leeren(self.ergebnis)
        if not ergebnis:
            self.ergebnis.configure(columns=())
            self.k_csv.state(["disabled"])
            return
        spalten = [f"s{i}" for i in range(len(ergebnis["spalten"]))]
        self.ergebnis.configure(columns=spalten)
        schrift = stil.schrift("normal")
        for name, titel in zip(spalten, ergebnis["spalten"]):
            self.ergebnis.heading(name, text=titel, anchor="w")
            breiten = [schrift.measure(titel) + 24] + [schrift.measure(zelle(z[spalten.index(name)])) + 16
                                                       for z in ergebnis["zeilen"][:50]]
            self.ergebnis.column(name, width=min(320, max(breiten)), minwidth=50, stretch=False, anchor="w")
        for zeile in ergebnis["zeilen"]:
            self.ergebnis.insert("", "end", values=[zelle(w) for w in zeile])
        self.k_csv.state(["!disabled"])

    def csv_speichern(self) -> None:
        if not self._letztes:
            return
        pfad = filedialog.asksaveasfilename(parent=self, title="Ergebnis speichern", defaultextension=".csv",
                                            filetypes=[("CSV-Datei", "*.csv")], initialfile="abfrage.csv")
        if not pfad:
            return
        with open(pfad, "w", newline="", encoding="utf-8-sig") as datei:
            schreiber = csv.writer(datei, delimiter=";")
            schreiber.writerow(self._letztes["spalten"])
            for zeile in self._letztes["zeilen"]:
                schreiber.writerow(["" if w is None else (zelle(w) if isinstance(w, (bytes, bytearray)) else w)
                                    for w in zeile])
        self.app.status(f"Gespeichert: {pfad}")

    def schliessen(self) -> None:
        if self._verbindung:
            self._verbindung.schliessen()
            self._verbindung = None
