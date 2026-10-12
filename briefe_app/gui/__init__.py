"""Die Oberfläche (tkinter). Start mit `starten()`."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox


def starten(konfig_daten: dict | None = None) -> int:
    from .. import konfig
    from ..datenbank import Datenbank, DatenbankFehler, treiber_pruefen
    from . import stil
    from .app import App
    from .dialoge import EinstellungenDialog

    root = tk.Tk()
    root.withdraw()
    root.title("Briefverwaltung")
    stil.einrichten(root)
    try:
        treiber_pruefen()
    except DatenbankFehler as fehler:
        messagebox.showerror("Briefverwaltung", str(fehler))
        root.destroy()
        return 1

    konfig_daten = konfig_daten or konfig.laden()
    try:
        db = Datenbank.aus_konfig(konfig_daten)
    except DatenbankFehler as fehler:
        # Erster Start oder Server nicht erreichbar: Zugangsdaten abfragen
        dialog = EinstellungenDialog(root, konfig_daten, fehlermeldung=str(fehler), willkommen=not konfig.vorhanden())
        if not dialog.zeigen():
            root.destroy()
            return 1
        konfig_daten, db = dialog.konfig, dialog.db
        konfig.speichern(konfig_daten)
    else:
        if not konfig.vorhanden():
            konfig.speichern(konfig_daten)

    root.deiconify()
    App(root, konfig_daten, db)
    root.mainloop()
    return 0
