"""Farben, Schriften und das Aussehen der ttk-Elemente."""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from ..hilfen import DRINGLICHKEIT

HINTERGRUND = "#f3f5f8"
FLAECHE = "#ffffff"
RAND = "#d7dde4"
TEXT = "#1f2933"
GRAU = "#66788a"
HELLGRAU = "#9aa7b4"
AKZENT = "#2563eb"
AKZENT_DUNKEL = "#1d4ed8"
AKZENT_HELL = "#e7efff"
GRUPPE = "#eef1f5"
GRUEN = "#2f7d4f"
ROT = "#c62828"
ORANGE = "#d17a00"

SCHRIFT = {}


def schrift(name: str) -> tkfont.Font:
    return SCHRIFT[name]


def einrichten(root: tk.Tk) -> ttk.Style:
    basis = tkfont.nametofont("TkDefaultFont")
    familie = basis.actual("family")
    groesse = max(10, abs(int(basis.actual("size"))))
    basis.configure(size=groesse)
    for name in ("TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(name).configure(family=familie, size=groesse)
    SCHRIFT.update({
        "normal": basis,
        "fett": tkfont.Font(root, family=familie, size=groesse, weight="bold"),
        "klein": tkfont.Font(root, family=familie, size=groesse - 1),
        "titel": tkfont.Font(root, family=familie, size=groesse + 5, weight="bold"),
        "untertitel": tkfont.Font(root, family=familie, size=groesse + 1, weight="bold"),
        "zahl": tkfont.Font(root, family=familie, size=groesse + 14, weight="bold"),
        "mono": tkfont.Font(root, family="Courier New" if root.tk.call("tk", "windowingsystem") == "win32"
                            else "DejaVu Sans Mono", size=groesse),
    })

    stil = ttk.Style(root)
    if "clam" in stil.theme_names():
        stil.theme_use("clam")
    root.configure(background=HINTERGRUND)
    root.option_add("*Text.background", FLAECHE)
    root.option_add("*Text.foreground", TEXT)
    root.option_add("*Text.relief", "flat")
    root.option_add("*Text.highlightThickness", 1)
    root.option_add("*Text.highlightColor", AKZENT)
    root.option_add("*Text.highlightBackground", RAND)
    root.option_add("*TCombobox*Listbox.font", basis)
    root.option_add("*Menu.background", FLAECHE)
    root.option_add("*Menu.activeBackground", AKZENT)
    root.option_add("*Menu.activeForeground", "#ffffff")

    stil.configure(".", background=HINTERGRUND, foreground=TEXT, font=basis, bordercolor=RAND,
                   lightcolor=HINTERGRUND, darkcolor=RAND, focuscolor=AKZENT)
    stil.configure("TFrame", background=HINTERGRUND)
    stil.configure("Flaeche.TFrame", background=FLAECHE)
    stil.configure("Karte.TFrame", background=FLAECHE, relief="solid", borderwidth=1)
    stil.configure("Leiste.TFrame", background=FLAECHE)
    stil.configure("TLabel", background=HINTERGRUND, foreground=TEXT)
    stil.configure("Flaeche.TLabel", background=FLAECHE)
    stil.configure("Titel.TLabel", font=SCHRIFT["titel"])
    stil.configure("Untertitel.TLabel", font=SCHRIFT["untertitel"])
    stil.configure("Klein.TLabel", font=SCHRIFT["klein"], foreground=GRAU)
    stil.configure("FlaecheKlein.TLabel", font=SCHRIFT["klein"], foreground=GRAU, background=FLAECHE)
    stil.configure("Info.TLabel", foreground=AKZENT_DUNKEL)
    stil.configure("Warnung.TLabel", foreground=ROT, font=SCHRIFT["fett"])
    stil.configure("Ok.TLabel", foreground=GRUEN)
    stil.configure("KarteZahl.TLabel", background=FLAECHE, font=SCHRIFT["zahl"])
    stil.configure("KarteText.TLabel", background=FLAECHE, foreground=GRAU)
    stil.configure("Status.TLabel", background=FLAECHE, foreground=GRAU, padding=(8, 3))

    stil.configure("TButton", padding=(10, 4), background="#e9edf2")
    stil.map("TButton", background=[("active", "#dde3ea"), ("disabled", HINTERGRUND)],
             foreground=[("disabled", HELLGRAU)])
    stil.configure("Akzent.TButton", background=AKZENT, foreground="#ffffff", bordercolor=AKZENT_DUNKEL)
    stil.map("Akzent.TButton", background=[("active", AKZENT_DUNKEL), ("disabled", "#a9bff0")],
             foreground=[("disabled", "#eef3ff")])
    stil.configure("Klein.TButton", padding=(4, 1))
    stil.configure("Gefahr.TButton", foreground=ROT)
    stil.configure("Kompakt.TButton", padding=(6, 3))
    stil.configure("Toolbutton", padding=(8, 3), background=HINTERGRUND)
    stil.map("Toolbutton", background=[("selected", AKZENT_HELL), ("active", "#e3e8ee")],
             foreground=[("selected", AKZENT_DUNKEL)], bordercolor=[("selected", AKZENT)])

    stil.configure("TEntry", fieldbackground=FLAECHE, padding=(5, 3))
    stil.map("TEntry", bordercolor=[("focus", AKZENT)], lightcolor=[("focus", AKZENT)])
    stil.configure("Fehler.TEntry", fieldbackground="#fde8e8")
    stil.configure("TCombobox", fieldbackground=FLAECHE, padding=(5, 3), arrowsize=14)
    stil.map("TCombobox", fieldbackground=[("readonly", FLAECHE)], bordercolor=[("focus", AKZENT)])
    stil.configure("TSpinbox", fieldbackground=FLAECHE, padding=(5, 3))
    stil.configure("TCheckbutton", background=HINTERGRUND)
    stil.configure("Flaeche.TCheckbutton", background=FLAECHE)
    stil.configure("TRadiobutton", background=HINTERGRUND)
    stil.configure("TLabelframe", background=HINTERGRUND, bordercolor=RAND)
    stil.configure("TLabelframe.Label", background=HINTERGRUND, foreground=GRAU, font=SCHRIFT["fett"])

    stil.configure("TNotebook", background=HINTERGRUND, borderwidth=0, tabmargins=(8, 6, 8, 0))
    stil.configure("TNotebook.Tab", padding=(16, 7), background="#e3e8ee", foreground=GRAU, font=SCHRIFT["fett"])
    stil.map("TNotebook.Tab", background=[("selected", FLAECHE)], foreground=[("selected", AKZENT_DUNKEL)])

    zeile = max(24, SCHRIFT["normal"].metrics("linespace") + 8)
    stil.configure("Treeview", background=FLAECHE, fieldbackground=FLAECHE, rowheight=zeile, bordercolor=RAND)
    stil.map("Treeview", background=[("selected", AKZENT)], foreground=[("selected", "#ffffff")])
    stil.configure("Treeview.Heading", background="#e9edf2", foreground=GRAU, font=SCHRIFT["fett"], padding=(6, 4))
    stil.map("Treeview.Heading", background=[("active", "#dde3ea")])
    stil.configure("TPanedwindow", background=HINTERGRUND)
    stil.configure("Sash", sashthickness=6, gripcount=0)

    # Knöpfe für die Dringlichkeit, jeweils in ihrer Farbe
    for stufe, (_name, farbe, hell) in DRINGLICHKEIT.items():
        stil.configure(f"D{stufe}.Toolbutton", background=FLAECHE, foreground=farbe, bordercolor=RAND,
                       font=SCHRIFT["normal"], padding=(6, 3), relief="solid", borderwidth=1)
        stil.map(f"D{stufe}.Toolbutton", background=[("selected", farbe), ("active", hell)],
                 foreground=[("selected", "#ffffff")])
    return stil
