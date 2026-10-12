"""Anzeige der Brief-Fotos: Seitenansicht mit Vorschauleiste und eine große Ansicht mit Zoom."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import tkinter as tk
import webbrowser
from collections import OrderedDict
from pathlib import Path
from tkinter import ttk

from .. import bilder, hilfen
from . import stil
from .widgets import Tooltip

try:
    from PIL import ImageTk
except ImportError:            # pragma: no cover
    ImageTk = None

ARBEITSGROESSE = 1800          # so groß wird ein Foto für die normale Anzeige höchstens gehalten


def datei_oeffnen(pfad: str) -> None:
    """Öffnet eine Datei mit dem passenden Programm des Betriebssystems."""
    if sys.platform.startswith("win"):
        os.startfile(pfad)  # noqa: S606 – Datei stammt aus der eigenen Datenbank
    elif sys.platform == "darwin":
        subprocess.Popen(["open", pfad])
    else:
        try:
            subprocess.Popen(["xdg-open", pfad])
        except OSError:
            webbrowser.open(Path(pfad).as_uri())


def foto_extern_oeffnen(db, foto: dict) -> None:
    ordner = Path(tempfile.gettempdir()) / "briefverwaltung"
    ordner.mkdir(exist_ok=True)
    name = re.sub(r"[^\w.\- ]", "_", foto["dateiname"]) or "foto"
    ziel = ordner / f"{foto['id']}_{name}"
    ziel.write_bytes(db.foto_inhalt(foto["id"]))
    datei_oeffnen(str(ziel))


class BildSpeicher:
    """Merkt sich die zuletzt geöffneten Fotos, damit Blättern schnell geht."""

    def __init__(self, groesse: int = 8):
        self.groesse = groesse
        self._daten = OrderedDict()

    def holen(self, db, foto: dict):
        schluessel = (foto["id"], foto.get("drehung", 0))
        if schluessel in self._daten:
            self._daten.move_to_end(schluessel)
            return self._daten[schluessel]
        bild = bilder.oeffnen(db.foto_inhalt(foto["id"]), foto.get("drehung", 0))
        if bild is not None:
            bild.thumbnail((ARBEITSGROESSE, ARBEITSGROESSE))
        self._daten[schluessel] = bild
        while len(self._daten) > self.groesse:
            self._daten.popitem(last=False)
        return bild


class BildAnzeige(ttk.Frame):
    """Zeigt die Seiten eines Briefes. bei_aenderung() wird nach Änderungen an den Seiten aufgerufen."""

    def __init__(self, eltern, app, bei_aenderung=None):
        super().__init__(eltern, style="Flaeche.TFrame")
        self.app = app
        self.bei_aenderung = bei_aenderung
        self.brief_id = None
        self.fotos = []
        self.index = 0
        self.speicher = BildSpeicher()
        self._tk_bild = None
        self._vorschau_bilder = []
        self._timer = None

        leiste = ttk.Frame(self, style="Leiste.TFrame", padding=(6, 6))
        leiste.pack(fill="x")
        self.k_zurueck = ttk.Button(leiste, text="◀", width=3, style="Kompakt.TButton", command=lambda: self.blaettern(-1))
        self.k_zurueck.pack(side="left")
        self.seite_text = ttk.Label(leiste, text="", style="Flaeche.TLabel", width=10, anchor="center")
        self.seite_text.pack(side="left", padx=2)
        self.k_vor = ttk.Button(leiste, text="▶", width=3, style="Kompakt.TButton", command=lambda: self.blaettern(1))
        self.k_vor.pack(side="left")
        self.k_mehr = ttk.Menubutton(leiste, text="Seite")
        self.k_mehr.pack(side="right")
        Tooltip(self.k_mehr, "Seite verschieben, abtrennen, löschen – oder weitere Fotos hinzufügen")
        menue = tk.Menu(self.k_mehr, tearoff=False)
        menue.add_command(label="Mit Bildbetrachter öffnen", command=self.extern)
        menue.add_command(label="Fotos/PDF als weitere Seiten hinzufügen …", command=self.hinzufuegen)
        menue.add_separator()
        menue.add_command(label="Seite nach vorne", command=lambda: self.verschieben(-1))
        menue.add_command(label="Seite nach hinten", command=lambda: self.verschieben(1))
        menue.add_command(label="Seite als eigenen Brief abtrennen", command=self.abtrennen)
        menue.add_separator()
        menue.add_command(label="Seite löschen …", command=self.loeschen)
        self.k_mehr["menu"] = menue

        self.canvas = tk.Canvas(self, background="#e6e9ee", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self._spaeter_zeichnen())
        self.canvas.bind("<Double-Button-1>", lambda e: self.gross())

        self.leiste_vorschau = tk.Canvas(self, height=84, background=stil.FLAECHE, highlightthickness=0)
        self.leiste_vorschau.pack(fill="x")
        unten = ttk.Frame(self, style="Leiste.TFrame", padding=(6, 4))
        unten.pack(fill="x")
        for text, befehl, tipp in (("⤢ Groß", self.gross, "Große Ansicht mit Zoom (auch Doppelklick aufs Bild)"),
                                   ("⟳", lambda: self.drehen(90), "Nach rechts drehen"),
                                   ("⟲", lambda: self.drehen(-90), "Nach links drehen")):
            k = ttk.Button(unten, text=text, style="Kompakt.TButton", command=befehl, width=0 if " " in text else 3)
            k.pack(side="right", padx=(4, 0))
            Tooltip(k, tipp)
        self.info = ttk.Label(unten, text="", style="FlaecheKlein.TLabel", anchor="w")
        self.info.pack(side="left", fill="x", expand=True)
        self._info_tipp = Tooltip(self.info, "")
        self._knoepfe()

    # ------------------------------------------------------------ Laden

    def zeigen(self, brief_id, index: int = 0) -> None:
        self.brief_id = brief_id
        self.fotos = self.app.db.fotos(brief_id) if brief_id else []
        self.index = max(0, min(index, len(self.fotos) - 1))
        self._vorschauleiste()
        self._zeichnen()
        self._knoepfe()

    def neu_laden(self) -> None:
        self.zeigen(self.brief_id, self.index)

    @property
    def foto(self):
        return self.fotos[self.index] if self.fotos else None

    def _knoepfe(self):
        mehrere = len(self.fotos) > 1
        self.k_zurueck.state(["!disabled"] if mehrere and self.index > 0 else ["disabled"])
        self.k_vor.state(["!disabled"] if mehrere and self.index < len(self.fotos) - 1 else ["disabled"])
        self.k_mehr.state(["!disabled"] if self.brief_id else ["disabled"])
        if self.fotos:
            self.seite_text.configure(text=f"Seite {self.index + 1}/{len(self.fotos)}")
        else:
            self.seite_text.configure(text="keine Seiten")

    # ------------------------------------------------------------ Zeichnen

    def _spaeter_zeichnen(self):
        if self._timer:
            self.after_cancel(self._timer)
        self._timer = self.after(60, self._zeichnen)

    def _zeichnen(self):
        self._timer = None
        c = self.canvas
        c.delete("all")
        breite, hoehe = max(c.winfo_width(), 50), max(c.winfo_height(), 50)
        foto = self.foto
        if not foto:
            text = ("Kein Brief ausgewählt" if not self.brief_id else
                    "Dieser Brief hat noch kein Foto.\n\n„Seite ▾“ → „Fotos/PDF hinzufügen …“")
            c.create_text(breite / 2, hoehe / 2, text=text, fill=stil.GRAU, justify="center",
                          font=stil.schrift("normal"))
            self.info.configure(text="")
            self._info_tipp.text = ""
            return
        bild = None
        if ImageTk is not None and bilder.ist_bild(foto["dateiname"]):
            bild = self.speicher.holen(self.app.db, foto)
        if bild is None:
            if foto["dateiname"].lower().endswith(".pdf"):
                text = "PDF-Dokument\n\nDoppelklick oder „Seite ▾ → Mit Bildbetrachter öffnen“"
            elif ImageTk is None:
                text = "Zum Anzeigen wird Pillow gebraucht:\npip install pillow"
            else:
                text = "Dieses Bild kann nicht angezeigt werden.\n„Seite ▾ → Mit Bildbetrachter öffnen“"
            c.create_text(breite / 2, hoehe / 2, text=text, fill=stil.GRAU, justify="center")
        else:
            rand = 12
            faktor = min((breite - 2 * rand) / bild.width, (hoehe - 2 * rand) / bild.height, 1.5)
            groesse = (max(1, int(bild.width * faktor)), max(1, int(bild.height * faktor)))
            self._tk_bild = ImageTk.PhotoImage(bild.resize(groesse))
            x, y = breite / 2, hoehe / 2
            c.create_rectangle(x - groesse[0] / 2 + 3, y - groesse[1] / 2 + 3, x + groesse[0] / 2 + 3,
                               y + groesse[1] / 2 + 3, fill="#c9ced6", outline="")
            c.create_image(x, y, image=self._tk_bild)
        teile = [hilfen.kurz(foto["dateiname"], 28), f"{foto['groesse'] / 1024 / 1024:.1f} MB".replace(".", ",")]
        datum = foto.get("aufgenommen_am") or foto.get("importiert_am")
        if datum:
            teile.append(hilfen.datum_text(datum.date() if hasattr(datum, "date") else datum))
        self.info.configure(text="  ·  ".join(teile))
        self._info_tipp.text = (f"{foto['dateiname']}\nimportiert {hilfen.datum_text(foto.get('importiert_am'))}"
                                f"\naus {foto.get('quelle') or 'Dateiauswahl'}")

    def _vorschauleiste(self):
        c = self.leiste_vorschau
        c.delete("all")
        self._vorschau_bilder = []
        if len(self.fotos) < 2:
            c.configure(height=1)
            return
        c.configure(height=84)
        x = 8
        for nr, foto in enumerate(self.fotos):
            tk_bild = None
            if ImageTk is not None and foto.get("vorschau"):
                kleines = bilder.oeffnen(bytes(foto["vorschau"]), foto.get("drehung", 0))
                if kleines is not None:
                    kleines.thumbnail((70, 70))
                    tk_bild = ImageTk.PhotoImage(kleines)
                    self._vorschau_bilder.append(tk_bild)
            breite = tk_bild.width() if tk_bild else 50
            markiert = nr == self.index
            c.create_rectangle(x - 3, 4, x + breite + 3, 80, outline=stil.AKZENT if markiert else stil.RAND,
                               width=3 if markiert else 1, tags=(f"s{nr}",))
            if tk_bild:
                c.create_image(x, 42, image=tk_bild, anchor="w", tags=(f"s{nr}",))
            else:
                c.create_text(x + 25, 42, text=str(nr + 1), fill=stil.GRAU, tags=(f"s{nr}",))
            c.tag_bind(f"s{nr}", "<Button-1>", lambda e, n=nr: self.gehe_zu(n))
            x += breite + 12

    # ------------------------------------------------------------ Aktionen

    def gehe_zu(self, index: int) -> None:
        self.index = max(0, min(index, len(self.fotos) - 1))
        self._vorschauleiste()
        self._zeichnen()
        self._knoepfe()

    def blaettern(self, schritt: int) -> None:
        if self.fotos:
            self.gehe_zu(self.index + schritt)

    def drehen(self, grad: int) -> None:
        if not self.foto:
            return
        self.app.db.foto_drehen(self.foto["id"], grad)
        self.neu_laden()

    def gross(self) -> None:
        if not self.foto:
            return
        if not bilder.ist_bild(self.foto["dateiname"]) or ImageTk is None:
            self.extern()
            return
        GrossAnsicht(self, self.app, self.fotos, self.index)

    def extern(self) -> None:
        if self.foto:
            foto_extern_oeffnen(self.app.db, self.foto)

    def hinzufuegen(self) -> None:
        if self.brief_id:
            self.app.dateien_zu_brief(self.brief_id)

    def verschieben(self, schritt: int) -> None:
        if not self.foto:
            return
        self.app.db.foto_seite_verschieben(self.foto["id"], schritt)
        self.index = max(0, min(self.index + schritt, len(self.fotos) - 1))
        self.neu_laden()

    def abtrennen(self) -> None:
        if not self.foto:
            return
        if len(self.fotos) < 2:
            self.app.hinweis("Der Brief hat nur diese eine Seite.")
            return
        neu_id = self.app.db.foto_als_neuer_brief(self.foto["id"])
        self.index = max(0, self.index - 1)
        self.neu_laden()
        if self.bei_aenderung:
            self.bei_aenderung(neu_id)

    def loeschen(self) -> None:
        if not self.foto:
            return
        if not self.app.fragen(f"Seite {self.index + 1} („{self.foto['dateiname']}“) wirklich löschen?\n"
                               "Das Foto ist danach auch aus der Datenbank entfernt."):
            return
        self.app.db.foto_loeschen(self.foto["id"])
        self.index = max(0, self.index - 1)
        self.neu_laden()
        if self.bei_aenderung:
            self.bei_aenderung(None)


class GrossAnsicht(tk.Toplevel):
    """Großes Fenster mit Zoom (Mausrad), Verschieben (Maus ziehen) und Blättern (← →)."""

    def __init__(self, eltern, app, fotos, index):
        super().__init__(eltern)
        self.app, self.fotos, self.index = app, fotos, index
        self.title("Brief ansehen")
        hoehe = int(self.winfo_screenheight() * 0.85)
        self.geometry(f"{int(hoehe * 0.8)}x{hoehe}+40+20")
        self.configure(background="#2b2f36")
        leiste = ttk.Frame(self, padding=6)
        leiste.pack(fill="x")
        ttk.Button(leiste, text="◀", width=3, command=lambda: self.blaettern(-1)).pack(side="left")
        self.text = ttk.Label(leiste, text="")
        self.text.pack(side="left", padx=8)
        ttk.Button(leiste, text="▶", width=3, command=lambda: self.blaettern(1)).pack(side="left")
        ttk.Button(leiste, text="Einpassen (0)", command=self.einpassen).pack(side="left", padx=(16, 0))
        ttk.Button(leiste, text="100 %", command=lambda: self.zoom_setzen(1.0)).pack(side="left", padx=4)
        ttk.Label(leiste, text="Mausrad = Zoom · Ziehen = Verschieben · Esc = Schließen",
                  style="Klein.TLabel").pack(side="right")
        self.canvas = tk.Canvas(self, background="#2b2f36", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.bild = None
        self.faktor = None
        self._tk_bild = None
        self.canvas.bind("<Configure>", lambda e: self.faktor is None and self._zeichnen())
        self.canvas.bind("<MouseWheel>", self._rad)
        self.canvas.bind("<Button-4>", self._rad)
        self.canvas.bind("<Button-5>", self._rad)
        self.canvas.bind("<ButtonPress-1>", lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind("<B1-Motion>", lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Left>", lambda e: self.blaettern(-1))
        self.bind("<Right>", lambda e: self.blaettern(1))
        self.bind("<plus>", lambda e: self.zoom_um(1.25))
        self.bind("<KP_Add>", lambda e: self.zoom_um(1.25))
        self.bind("<minus>", lambda e: self.zoom_um(0.8))
        self.bind("<KP_Subtract>", lambda e: self.zoom_um(0.8))
        self.bind("0", lambda e: self.einpassen())
        self._laden()
        self.focus_set()

    def _laden(self):
        foto = self.fotos[self.index]
        self.bild = bilder.oeffnen(self.app.db.foto_inhalt(foto["id"]), foto.get("drehung", 0))
        self.text.configure(text=f"Seite {self.index + 1} von {len(self.fotos)} – {foto['dateiname']}")
        self.einpassen()

    def blaettern(self, schritt):
        neu = self.index + schritt
        if 0 <= neu < len(self.fotos):
            self.index = neu
            self._laden()

    def _passend(self) -> float:
        b, h = max(self.canvas.winfo_width(), 100), max(self.canvas.winfo_height(), 100)
        return min(b / self.bild.width, h / self.bild.height)

    def einpassen(self):
        self.faktor = None
        self._zeichnen()

    def zoom_setzen(self, faktor):
        self.faktor = faktor
        self._zeichnen()

    def zoom_um(self, mal, x=None, y=None):
        if self.bild is None:
            return
        alt = self.faktor or self._passend()
        neu = max(0.05, min(alt * mal, 4.0, 9000 / max(self.bild.width, self.bild.height)))
        c = self.canvas
        x = c.winfo_width() / 2 if x is None else x
        y = c.winfo_height() / 2 if y is None else y
        # Punkt unter der Maus soll an derselben Stelle bleiben
        bx, by = c.canvasx(x) / alt, c.canvasy(y) / alt
        self.faktor = neu
        self._zeichnen()
        c.xview_moveto(max(0.0, (bx * neu - x) / max(1, self.bild.width * neu)))
        c.yview_moveto(max(0.0, (by * neu - y) / max(1, self.bild.height * neu)))

    def _rad(self, e):
        if getattr(e, "num", None) == 4 or getattr(e, "delta", 0) > 0:
            self.zoom_um(1.2, e.x, e.y)
        else:
            self.zoom_um(1 / 1.2, e.x, e.y)

    def _zeichnen(self):
        c = self.canvas
        c.delete("all")
        if self.bild is None:
            c.create_text(c.winfo_width() / 2, c.winfo_height() / 2, text="Bild kann nicht angezeigt werden",
                          fill="#ffffff")
            return
        faktor = self.faktor or self._passend()
        groesse = (max(1, int(self.bild.width * faktor)), max(1, int(self.bild.height * faktor)))
        self._tk_bild = ImageTk.PhotoImage(self.bild.resize(groesse))
        b, h = max(c.winfo_width(), groesse[0]), max(c.winfo_height(), groesse[1])
        c.create_image(b / 2, h / 2, image=self._tk_bild)
        c.configure(scrollregion=(0, 0, b, h))
        if self.faktor is None:
            c.xview_moveto(0)
            c.yview_moveto(0)
