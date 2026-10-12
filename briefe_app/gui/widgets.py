"""Wiederverwendbare Bausteine der Oberfläche."""
from __future__ import annotations

import calendar
import datetime as dt
import tkinter as tk
from tkinter import ttk

from .. import hilfen
from . import stil

LEER = "—"


class ScrollRahmen(ttk.Frame):
    """Ein Rahmen mit senkrechter Bildlaufleiste; der Inhalt kommt in `.innen`."""

    def __init__(self, eltern, polster=(14, 10, 14, 18), stilname="TFrame", **kw):
        super().__init__(eltern, **kw)
        hintergrund = ttk.Style(self).lookup(stilname, "background") or stil.HINTERGRUND
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, background=hintergrund)
        leiste = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=leiste.set)
        self.innen = ttk.Frame(self.canvas, padding=polster, style=stilname)
        self._fenster = self.canvas.create_window(0, 0, window=self.innen, anchor="nw")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        leiste.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.innen.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._fenster, width=e.width))
        ScrollRahmen._mausrad_einrichten(self)

    @staticmethod
    def _mausrad_einrichten(widget):
        """Einmal für das ganze Programm: Mausrad scrollt den Rahmen unter dem Mauszeiger.

        Auswahlfelder und Zahlenfelder ändern beim Drehen am Mausrad sonst ihren Wert –
        beim Scrollen durch ein Formular würde man so aus Versehen etwas verstellen.
        """
        root = widget._root()
        if getattr(root, "_mausrad_eingerichtet", False):
            return
        root._mausrad_eingerichtet = True
        for ereignis in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            root.bind_all(ereignis, ScrollRahmen._rad, add="+")
            for klasse in ("TCombobox", "TSpinbox"):
                root.bind_class(klasse, ereignis, lambda e: (ScrollRahmen._rad(e), "break")[1])

    @staticmethod
    def _rad(event):
        try:
            unter = event.widget.winfo_containing(event.x_root, event.y_root)
        except (KeyError, AttributeError, tk.TclError):
            return
        if unter is None or isinstance(unter, (tk.Text, ttk.Treeview, tk.Listbox)):
            return                        # die scrollen selbst
        while unter is not None and not isinstance(unter, ScrollRahmen):
            unter = unter.master
        if unter is None or unter.innen.winfo_reqheight() <= unter.canvas.winfo_height():
            return
        if getattr(event, "num", None) == 4:
            schritt = -1
        elif getattr(event, "num", None) == 5:
            schritt = 1
        else:
            schritt = -1 if event.delta > 0 else 1
        unter.canvas.yview_scroll(schritt * 2, "units")

    def nach_oben(self):
        self.canvas.yview_moveto(0)


class Tooltip:
    def __init__(self, widget, text: str):
        self.widget, self.text, self.fenster = widget, text, None
        widget.bind("<Enter>", self._zeigen, add="+")
        widget.bind("<Leave>", self._weg, add="+")
        widget.bind("<ButtonPress>", self._weg, add="+")

    def _zeigen(self, _e=None):
        if self.fenster or not self.text:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.fenster = tk.Toplevel(self.widget)
        self.fenster.wm_overrideredirect(True)
        self.fenster.wm_geometry(f"+{x}+{y}")
        tk.Label(self.fenster, text=self.text, background="#333a42", foreground="#ffffff", padx=8, pady=4,
                 justify="left", font=stil.schrift("klein")).pack()

    def _weg(self, _e=None):
        if self.fenster:
            self.fenster.destroy()
            self.fenster = None


def knopf(eltern, text, befehl, tipp: str = "", **kw) -> ttk.Button:
    k = ttk.Button(eltern, text=text, command=befehl, **kw)
    if tipp:
        Tooltip(k, tipp)
    return k


# ---------------------------------------------------------------- Datum

class Kalender(tk.Toplevel):
    """Kleiner Monatskalender zum Anklicken."""

    def __init__(self, feld: "DatumFeld"):
        super().__init__(feld)
        self.feld = feld
        self.title("Datum wählen")
        self.transient(feld.winfo_toplevel())
        self.resizable(False, False)
        self.configure(background=stil.FLAECHE)
        try:
            start = feld.wert() or dt.date.today()
        except hilfen.Eingabefehler:
            start = dt.date.today()
        self.jahr, self.monat = start.year, start.month
        self.rahmen = tk.Frame(self, background=stil.FLAECHE, padx=8, pady=8)
        self.rahmen.pack()
        self._zeichnen()
        self.update_idletasks()
        x = feld.winfo_rootx()
        y = feld.winfo_rooty() + feld.winfo_height() + 2
        x = min(x, self.winfo_screenwidth() - self.winfo_reqwidth() - 10)
        y = min(y, self.winfo_screenheight() - self.winfo_reqheight() - 60)
        self.wm_geometry(f"+{x}+{y}")
        self.bind("<Escape>", lambda e: self.destroy())
        self._vorher = self.grab_current()
        self.after(20, self._fokus)

    def destroy(self):
        vorher = getattr(self, "_vorher", None)
        super().destroy()
        if vorher is not None:            # der Dialog dahinter soll modal bleiben
            try:
                vorher.grab_set()
            except tk.TclError:
                pass

    def _fokus(self):
        try:
            self.grab_set()
            self.focus_force()
        except tk.TclError:
            pass

    def _zeichnen(self):
        for kind in self.rahmen.winfo_children():
            kind.destroy()
        monate = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
                  "November", "Dezember"]
        kopf = tk.Frame(self.rahmen, background=stil.FLAECHE)
        kopf.grid(row=0, column=0, columnspan=7, sticky="ew")
        tk.Button(kopf, text="◀", relief="flat", background=stil.FLAECHE, command=lambda: self._blaettern(-1)).pack(side="left")
        tk.Label(kopf, text=f"{monate[self.monat - 1]} {self.jahr}", background=stil.FLAECHE,
                 font=stil.schrift("fett")).pack(side="left", expand=True)
        tk.Button(kopf, text="▶", relief="flat", background=stil.FLAECHE, command=lambda: self._blaettern(1)).pack(side="right")
        for spalte, tag in enumerate(["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]):
            tk.Label(self.rahmen, text=tag, background=stil.FLAECHE, foreground=stil.GRAU,
                     font=stil.schrift("klein"), width=3).grid(row=1, column=spalte)
        heute = dt.date.today()
        try:
            gewaehlt = self.feld.wert()
        except hilfen.Eingabefehler:
            gewaehlt = None
        for zeile, woche in enumerate(calendar.Calendar().monthdatescalendar(self.jahr, self.monat), start=2):
            for spalte, tag in enumerate(woche):
                farbe = stil.TEXT if tag.month == self.monat else stil.HELLGRAU
                hg = stil.AKZENT if tag == gewaehlt else (stil.AKZENT_HELL if tag == heute else stil.FLAECHE)
                tk.Button(self.rahmen, text=str(tag.day), width=3, relief="flat", background=hg,
                          foreground="#ffffff" if tag == gewaehlt else farbe, activebackground=stil.AKZENT_HELL,
                          command=lambda t=tag: self._waehlen(t)).grid(row=zeile, column=spalte, padx=1, pady=1)
        fuss = tk.Frame(self.rahmen, background=stil.FLAECHE)
        fuss.grid(row=9, column=0, columnspan=7, sticky="ew", pady=(4, 0))
        tk.Button(fuss, text="Heute", relief="flat", background=stil.AKZENT_HELL,
                  command=lambda: self._waehlen(dt.date.today())).pack(side="left")
        tk.Button(fuss, text="Leeren", relief="flat", background=stil.FLAECHE,
                  command=lambda: self._waehlen(None)).pack(side="right")

    def _blaettern(self, schritt):
        self.monat += schritt
        if self.monat == 0:
            self.jahr, self.monat = self.jahr - 1, 12
        elif self.monat == 13:
            self.jahr, self.monat = self.jahr + 1, 1
        self._zeichnen()

    def _waehlen(self, tag):
        self.feld.setzen(tag)
        self.feld.geaendert()
        self.destroy()


class DatumFeld(ttk.Frame):
    """Eingabe für ein Datum mit Kalender. Versteht auch „heute“, „morgen“, „+14“ usw."""

    def __init__(self, eltern, breite: int = 12, bei_aenderung=None, **kw):
        super().__init__(eltern, **kw)
        self.var = tk.StringVar()
        self.bei_aenderung = bei_aenderung
        self.eingabe = ttk.Entry(self, textvariable=self.var, width=breite)
        self.eingabe.pack(side="left", fill="x", expand=True)
        k = ttk.Button(self, text="▾", width=2, style="Klein.TButton", command=self._kalender, takefocus=False)
        k.pack(side="left", padx=(2, 0))
        Tooltip(self.eingabe, "z. B. 08.10.2026, heute, morgen, +14 (Tage), +2w, +1m")
        self.eingabe.bind("<FocusOut>", lambda e: self.formatieren())
        self.eingabe.bind("<Return>", lambda e: self.formatieren())
        self.var.trace_add("write", lambda *a: self.geaendert())

    def geaendert(self):
        if self.bei_aenderung:
            self.bei_aenderung()

    def _kalender(self):
        self.formatieren()
        Kalender(self)

    def formatieren(self) -> None:
        try:
            datum = self.wert()
        except hilfen.Eingabefehler:
            self.eingabe.configure(style="Fehler.TEntry")
            return
        self.eingabe.configure(style="TEntry")
        text = hilfen.datum_text(datum)
        if text != self.var.get():
            self.var.set(text)

    def wert(self) -> dt.date | None:
        return hilfen.datum_lesen(self.var.get())

    def setzen(self, datum) -> None:
        self.var.set(hilfen.datum_text(datum) if datum else "")
        self.eingabe.configure(style="TEntry")


# ---------------------------------------------------------------- Auswahlfelder

class SuchCombobox(ttk.Combobox):
    """Eingabefeld mit Vorschlägen. Beim Tippen werden nur passende Einträge angeboten."""

    def __init__(self, eltern, werte=(), **kw):
        super().__init__(eltern, **kw)
        self._alle = list(werte)
        self.configure(values=self._alle)
        self.bind("<KeyRelease>", self._filtern, add="+")

    def werte_setzen(self, werte) -> None:
        self._alle = list(werte)
        self.configure(values=self._alle)

    def _filtern(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        text = self.get().strip().lower()
        self.configure(values=[w for w in self._alle if text in w.lower()] if text else self._alle)


class IdAuswahl(ttk.Combobox):
    """Feste Auswahlliste, die zu jedem angezeigten Text eine Datenbank-ID kennt. „—“ = keine Auswahl."""

    def __init__(self, eltern, leer_text: str = LEER, **kw):
        kw.setdefault("state", "readonly")
        super().__init__(eltern, **kw)
        self.leer_text = leer_text
        self._ids = [None]
        self.configure(values=[leer_text])
        self.current(0)

    def optionen(self, paare, behalten: bool = True) -> None:
        """paare: [(id, text), …]"""
        alt = self.id if behalten else None
        self._ids = [None] + [p[0] for p in paare]
        self.configure(values=[self.leer_text] + [p[1] for p in paare])
        self.id = alt

    @property
    def id(self):
        nr = self.current()
        return self._ids[nr] if 0 <= nr < len(self._ids) else None

    @id.setter
    def id(self, wert):
        self.current(self._ids.index(wert) if wert in self._ids else 0)

    @property
    def anzahl(self) -> int:
        return len(self._ids) - 1


class KopierLabel(ttk.Label):
    """Text, der beim Anklicken in die Zwischenablage kopiert wird."""

    def __init__(self, eltern, **kw):
        kw.setdefault("style", "Info.TLabel")
        kw.setdefault("cursor", "hand2")
        super().__init__(eltern, **kw)
        self._kopiertext = ""
        self.bind("<Button-1>", self._kopieren)
        Tooltip(self, "Anklicken zum Kopieren")

    def setzen(self, text: str, kopiertext: str | None = None) -> None:
        self.configure(text=text)
        self._kopiertext = kopiertext if kopiertext is not None else text

    def _kopieren(self, _e=None):
        if not self._kopiertext:
            return
        self.clipboard_clear()
        self.clipboard_append(self._kopiertext)
        alt = self.cget("text")
        self.configure(text="✓ kopiert")
        self.after(900, lambda: self.winfo_exists() and self.configure(text=alt))


# ---------------------------------------------------------------- Listen

def liste(eltern, spalten, hoehe: int = 10, auswahl: str = "browse", baum: bool = False):
    """Erzeugt eine Tabelle (Treeview) mit Bildlaufleiste.

    spalten: [(schluessel, ueberschrift, breite, ausrichtung), …]
    Gibt (rahmen, treeview) zurück.
    """
    rahmen = ttk.Frame(eltern)
    namen = [s[0] for s in spalten]
    tv = ttk.Treeview(rahmen, columns=namen, show="tree headings" if baum else "headings", height=hoehe,
                      selectmode=auswahl)
    for schluessel, titel, breite, ausrichtung in spalten:
        tv.heading(schluessel, text=titel, anchor="w" if ausrichtung == "w" else ausrichtung)
        tv.column(schluessel, width=breite, minwidth=40, anchor=ausrichtung, stretch=ausrichtung == "w")
    leiste = ttk.Scrollbar(rahmen, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=leiste.set)
    tv.grid(row=0, column=0, sticky="nsew")
    leiste.grid(row=0, column=1, sticky="ns")
    rahmen.rowconfigure(0, weight=1)
    rahmen.columnconfigure(0, weight=1)
    tv.tag_configure("grau", foreground=stil.HELLGRAU)
    tv.tag_configure("gruppe", background=stil.GRUPPE, font=stil.schrift("fett"))
    for stufe, (_n, farbe, hell) in hilfen.DRINGLICHKEIT.items():
        tv.tag_configure(f"d{stufe}", background=hell)
    tv.tag_configure("rot", foreground=stil.ROT)
    return rahmen, tv


def liste_leeren(tv: ttk.Treeview) -> None:
    tv.delete(*tv.get_children())


class Karte(ttk.Frame):
    """Kachel mit großer Zahl für die Übersicht. Der farbige Streifen links zeigt die Bedeutung. Anklickbar."""

    def __init__(self, eltern, titel: str, farbe: str = stil.RAND, hinweis: str = "", befehl=None):
        super().__init__(eltern, style="Karte.TFrame")
        streifen = tk.Frame(self, background=farbe, width=5)
        streifen.pack(side="left", fill="y")
        innen = ttk.Frame(self, style="Flaeche.TFrame", padding=(12, 8, 14, 10))
        innen.pack(side="left", fill="both", expand=True)
        self.zahl = ttk.Label(innen, text="0", style="KarteZahl.TLabel")
        self.zahl.pack(anchor="w")
        self.titel = ttk.Label(innen, text=titel, style="KarteText.TLabel")
        self.titel.pack(anchor="w")
        if hinweis:
            Tooltip(self, hinweis)
        if befehl:
            for w in (self, streifen, innen, self.zahl, self.titel):
                w.bind("<Button-1>", lambda e: befehl())
                w.configure(cursor="hand2")

    def setzen(self, wert) -> None:
        self.zahl.configure(text=str(wert))


class Toast(tk.Toplevel):
    """Kurze Meldung unten rechts am Bildschirm, verschwindet von selbst."""

    def __init__(self, eltern, titel: str, text: str, knopf_text: str = "", befehl=None, sekunden: int = 8):
        super().__init__(eltern)
        self.wm_overrideredirect(True)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        rahmen = tk.Frame(self, background=stil.FLAECHE, highlightthickness=1, highlightbackground=stil.AKZENT,
                          padx=14, pady=10)
        rahmen.pack(fill="both", expand=True)
        tk.Label(rahmen, text=titel, background=stil.FLAECHE, foreground=stil.AKZENT_DUNKEL,
                 font=stil.schrift("untertitel"), anchor="w").pack(fill="x")
        tk.Label(rahmen, text=text, background=stil.FLAECHE, foreground=stil.TEXT, justify="left",
                 wraplength=340, anchor="w").pack(fill="x", pady=(2, 6))
        zeile = tk.Frame(rahmen, background=stil.FLAECHE)
        zeile.pack(fill="x")
        if knopf_text and befehl:
            ttk.Button(zeile, text=knopf_text, style="Akzent.TButton",
                       command=lambda: (self.destroy(), befehl())).pack(side="left")
        ttk.Button(zeile, text="Schließen", command=self.destroy).pack(side="right")
        self.update_idletasks()
        breite, hoehe = max(380, self.winfo_reqwidth()), self.winfo_reqheight()
        x = self.winfo_screenwidth() - breite - 24
        y = self.winfo_screenheight() - hoehe - 64
        self.wm_geometry(f"{breite}x{hoehe}+{x}+{y}")
        self.after(sekunden * 1000, lambda: self.winfo_exists() and self.destroy())
