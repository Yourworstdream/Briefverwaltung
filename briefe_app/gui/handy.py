"""Fenster „Handy verbinden“: QR-Code mit Adresse und Zugangscode für die Handy-App."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import empfang
from . import stil
from .widgets import KopierLabel

try:
    import qrcode
except ImportError:            # pragma: no cover – dann eben nur Text zum Abtippen
    qrcode = None

try:
    from PIL import ImageTk
except ImportError:            # pragma: no cover
    ImageTk = None


def qr_bild(text: str, groesse: int = 300):
    """Ein QR-Code als Bild für tkinter – oder None, wenn das Paket qrcode fehlt."""
    if qrcode is None or ImageTk is None:
        return None
    code = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    code.add_data(text)
    code.make(fit=True)
    bild = code.make_image(fill_color="black", back_color="white")
    bild = (bild.get_image() if hasattr(bild, "get_image") else bild._img).convert("RGB")
    return ImageTk.PhotoImage(bild.resize((groesse, groesse), resample=0))


class HandyDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("Handy verbinden")
        self.transient(app.root)
        self.configure(background=stil.HINTERGRUND)
        self.resizable(False, False)
        rahmen = ttk.Frame(self, padding=(22, 18))
        rahmen.pack(fill="both", expand=True)

        links = ttk.Frame(rahmen)
        links.grid(row=0, column=0, sticky="n")
        self.qr = tk.Label(links, background="#ffffff", borderwidth=0)
        self.qr.pack()
        rechts = ttk.Frame(rahmen, padding=(22, 0, 0, 0))
        rechts.grid(row=0, column=1, sticky="n")

        ttk.Label(rechts, text="Handy-App verbinden", style="Titel.TLabel").pack(anchor="w")
        schritte = ("1.  Handy und PC müssen im selben WLAN sein.\n"
                    "2.  In der App „Briefverwaltung“ auf  PC verbinden  tippen.\n"
                    "3.  Diesen QR-Code scannen – fertig.\n\n"
                    "Danach schickt die App gescannte Briefe direkt hierher.\n"
                    "Ist der PC aus, warten die Briefe auf dem Handy.")
        ttk.Label(rechts, text=schritte, justify="left").pack(anchor="w", pady=(8, 14))

        ttk.Label(rechts, text="Ohne QR-Code von Hand eintippen:", style="Untertitel.TLabel").pack(anchor="w")
        tabelle = ttk.Frame(rechts)
        tabelle.pack(anchor="w", pady=(4, 0))
        ttk.Label(tabelle, text="Adresse").grid(row=0, column=0, sticky="nw", padx=(0, 10))
        self.adressen = ttk.Frame(tabelle)
        self.adressen.grid(row=0, column=1, sticky="w")
        ttk.Label(tabelle, text="Code").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(4, 0))
        self.code = KopierLabel(tabelle, font=stil.schrift("untertitel"))
        self.code.grid(row=1, column=1, sticky="w", pady=(4, 0))

        self.status = ttk.Label(rechts, text="", wraplength=420, justify="left")
        self.status.pack(anchor="w", pady=(14, 0))
        ttk.Label(rechts, text="Windows fragt beim ersten Mal, ob Python im Netzwerk erreichbar sein darf:\n"
                               "„Zugriff zulassen“ für private Netzwerke wählen.",
                  style="Klein.TLabel", justify="left").pack(anchor="w", pady=(8, 0))

        knoepfe = ttk.Frame(rahmen)
        knoepfe.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        ttk.Button(knoepfe, text="Schließen", style="Akzent.TButton", command=self.destroy).pack(side="right")
        ttk.Button(knoepfe, text="Neuen Code erzeugen", command=self._neuer_code).pack(side="left")
        self.bind("<Escape>", lambda e: self.destroy())
        self.anzeigen()

    def anzeigen(self) -> None:
        h = self.app.konfig["handy"]
        adressen = empfang.lokale_adressen()
        laeuft = self.app.empfang is not None and self.app.empfang.laeuft
        port = self.app.empfang.port if laeuft else h["port"]
        for kind in self.adressen.winfo_children():
            kind.destroy()
        for ip in adressen or ["(keine Netzwerkverbindung gefunden)"]:
            l = KopierLabel(self.adressen)
            l.setzen(f"http://{ip}:{port}" if adressen else ip)
            l.pack(anchor="w")
        self.code.setzen(h["token"])
        self._qr_bild = qr_bild(empfang.qr_text(h["token"], port, adressen)) if adressen else None
        if self._qr_bild:
            self.qr.configure(image=self._qr_bild, text="", width=300, height=300)
        else:
            self.qr.configure(image="", width=36, height=16, font=stil.schrift("normal"), fg=stil.GRAU,
                              text="QR-Code nicht möglich\n\n" + ("pip install qrcode" if qrcode is None
                                                                 else "Kein Netzwerk gefunden"))
        if not h.get("aktiv"):
            self.status.configure(text="Der Handy-Empfang ist ausgeschaltet (Datei → Einstellungen).",
                                  style="Warnung.TLabel")
        elif laeuft:
            self.status.configure(text=f"● Empfang läuft auf Port {port}.", style="Ok.TLabel")
        else:
            fehler = self.app.empfang.fehler if self.app.empfang else ""
            self.status.configure(text=f"Der Empfang konnte nicht starten: {fehler}", style="Warnung.TLabel")

    def _neuer_code(self) -> None:
        if self.app.fragen("Neuen Zugangscode erzeugen?\n\nBereits verbundene Handys müssen danach den neuen "
                           "QR-Code scannen."):
            self.app.konfig["handy"]["token"] = empfang.token_erzeugen()
            self.app.konfig_speichern()
            self.app.empfang_starten()
            self.anzeigen()
