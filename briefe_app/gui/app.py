"""Das Hauptfenster: Reiter, Menü, Statuszeile, USB-Überwachung und Import im Hintergrund.

Wichtig für tkinter: Nur der Haupt-Thread darf die Oberfläche ändern. Die USB-Überwachung
und der Import laufen deshalb in eigenen Threads und schicken ihre Meldungen über eine
Warteschlange (queue), die das Hauptfenster alle 300 ms abholt.
"""
from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import __version__, bilder, importer, konfig
from ..datenbank import fehlertext
from ..hilfen import Eingabefehler
from ..usb import UsbWaechter
from . import stil
from .dialoge import AktivitaetDialog, EinstellungenDialog
from .tab_aktivitaeten import AktivitaetenTab
from .tab_briefe import BriefeTab
from .tab_sql import SqlTab
from .tab_stammdaten import AbsenderTab, AnlassTab, StammdatenTab
from .tab_uebersicht import UebersichtTab
from .widgets import Toast

try:
    import pymysql
except ImportError:            # pragma: no cover
    pymysql = None

HILFE = """So funktioniert die Briefverwaltung

1. Briefe mit dem Handy fotografieren und die Fotos auf einen USB-Stick
   in den Ordner „Briefe“ kopieren.
   • Ein Foto direkt im Ordner = ein Brief.
   • Ein Unterordner (z. B. „Briefe/Stromrechnung“) = EIN Brief mit mehreren
     Seiten; der Name des Unterordners wird der Betreff.

2. Stick einstecken – solange das Programm läuft, werden neue Fotos sofort
   importiert. Schon importierte Fotos werden erkannt und übersprungen.
   Auf dem Stick wird nichts gelöscht.

3. Im Reiter „Briefe“ jeden neuen Brief anklicken und ausfüllen:
   Absender, Ansprechpartner (＋), Bankverbindung (＋), Anlass,
   Dringlichkeit, Frist und Betrag. Neue Namen werden automatisch angelegt.

4. Gruppieren: Oben „Gruppieren nach Absender / Anlass“ wählen.
   Mehrere Briefe mit Strg oder Shift markieren → „Gruppieren …“ ordnet
   sie gemeinsam einem Absender oder Anlass zu.
   „Zusammenfassen“ macht aus mehreren Fotos EINEN Brief mit Seiten.

5. Telefonate, Treffen, Zahlungen, E-Mails und Notizen unter dem Brief
   (oder beim Absender / Anlass) mit den Knöpfen ☎ ● € ✎ eintragen.
   Eine „Wiedervorlage“ erinnert in der Übersicht an den nächsten Schritt.

6. Im Reiter „SQL“ kannst du eigene MySQL-Abfragen ausprobieren.

Datumsfelder verstehen: 08.10.2026 · 8.10. · heute · morgen · +14 · +2w · +1m

Tastenkürzel:  Strg+S speichern · Strg+N neuer Brief · Strg+F suchen
               Strg+I Ordner importieren · F1 diese Hilfe"""


class App:
    def __init__(self, root: tk.Tk, konfig_daten: dict, db):
        self.root, self.konfig, self.db = root, konfig_daten, db
        self.nachrichten = queue.Queue()
        self.waechter = None
        self._import_laeuft = False
        self._warteschlange = []
        self._status_timer = None
        self._fortschritt_zeit = 0.0
        self._vorheriger_tab = None

        root.title("Briefverwaltung")
        breite = min(1500, root.winfo_screenwidth() - 40)
        hoehe = min(920, root.winfo_screenheight() - 80)
        root.geometry(f"{breite}x{hoehe}+20+10")
        root.minsize(1050, 640)
        root.report_callback_exception = self._fehler
        root.protocol("WM_DELETE_WINDOW", self.beenden)
        self._symbol()

        self._menue()
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)
        self.uebersicht = UebersichtTab(self.notebook, self)
        self.briefe = BriefeTab(self.notebook, self)
        self.absender = AbsenderTab(self.notebook, self)
        self.anlaesse = AnlassTab(self.notebook, self)
        self.aktivitaeten = AktivitaetenTab(self.notebook, self)
        self.sql = SqlTab(self.notebook, self)
        self.tabs = [self.uebersicht, self.briefe, self.absender, self.anlaesse, self.aktivitaeten, self.sql]
        for tab, text in zip(self.tabs, ("Übersicht", "Briefe", "Absender & Kontakte", "Anlässe",
                                         "Telefonate, Treffen, Zahlungen", "SQL")):
            self.notebook.add(tab, text=text)
        self.notebook.bind("<<NotebookTabChanged>>", self._tab_gewechselt)

        leiste = ttk.Frame(root, style="Leiste.TFrame")
        leiste.pack(fill="x", side="bottom")
        ttk.Separator(root).pack(fill="x", side="bottom")
        self.status_text = ttk.Label(leiste, text="", style="Status.TLabel")
        self.status_text.pack(side="left")
        self.db_text = ttk.Label(leiste, text="", style="Status.TLabel")
        self.db_text.pack(side="right")
        self.usb_label = ttk.Label(leiste, text="", style="Status.TLabel", cursor="hand2")
        self.usb_label.pack(side="right", padx=12)
        self.usb_label.bind("<Button-1>", lambda e: self.usb_jetzt_pruefen())

        for taste, befehl in (("<Control-s>", self.speichern), ("<Control-n>", self.briefe.neuer_brief),
                              ("<Control-i>", self.ordner_importieren), ("<F1>", self.hilfe),
                              ("<Control-f>", self.suchen)):
            root.bind_all(taste, lambda e, b=befehl: (b(), "break")[1])

        self._db_anzeigen()
        self.usb_starten()
        self.notebook.select(self.uebersicht)
        self.root.after(300, self._nachrichten_abholen)

    # ------------------------------------------------------------ Kleinigkeiten

    def _symbol(self):
        """Ein kleiner Briefumschlag als Fenstersymbol (nur mit Pillow)."""
        if not bilder.pillow_da():
            return
        try:
            from PIL import Image, ImageDraw, ImageTk
            bild = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            zeichnen = ImageDraw.Draw(bild)
            zeichnen.rounded_rectangle((4, 14, 60, 52), radius=6, fill=stil.AKZENT)
            zeichnen.line((8, 18, 32, 36, 56, 18), fill="#ffffff", width=4, joint="curve")
            self._symbol_bild = ImageTk.PhotoImage(bild)
            self.root.iconphoto(True, self._symbol_bild)
        except Exception:
            pass

    def _menue(self):
        leiste = tk.Menu(self.root)
        datei = tk.Menu(leiste, tearoff=False)
        datei.add_command(label="Fotos aus Ordner importieren …", accelerator="Strg+I", command=self.ordner_importieren)
        datei.add_command(label="USB-Stick jetzt prüfen", command=self.usb_jetzt_pruefen)
        datei.add_separator()
        datei.add_command(label="Einstellungen …", command=self.einstellungen)
        datei.add_separator()
        datei.add_command(label="Beenden", command=self.beenden)
        leiste.add_cascade(label="Datei", menu=datei)
        neu = tk.Menu(leiste, tearoff=False)
        neu.add_command(label="Brief", accelerator="Strg+N", command=lambda: self.briefe.neuer_brief())
        neu.add_command(label="Absender", command=lambda: self._neu_in(self.absender))
        neu.add_command(label="Anlass", command=lambda: self._neu_in(self.anlaesse))
        neu.add_separator()
        for art in ("Telefonat", "Treffen", "Zahlung", "E-Mail", "Brief verschickt", "Notiz"):
            neu.add_command(label=art, command=lambda a=art: self._aktivitaet_neu(a))
        leiste.add_cascade(label="Neu", menu=neu)
        hilfe = tk.Menu(leiste, tearoff=False)
        hilfe.add_command(label="Kurzanleitung", accelerator="F1", command=self.hilfe)
        hilfe.add_command(label="Über …", command=self.ueber)
        leiste.add_cascade(label="Hilfe", menu=hilfe)
        self.root.configure(menu=leiste)

    def status(self, text: str, sekunden: int = 6) -> None:
        self.status_text.configure(text=text)
        if self._status_timer:
            self.root.after_cancel(self._status_timer)
        self._status_timer = self.root.after(sekunden * 1000, lambda: self.status_text.configure(text="")) \
            if sekunden else None

    def hinweis(self, text: str) -> None:
        messagebox.showinfo("Hinweis", text, parent=self.root)

    def fragen(self, text: str) -> bool:
        return messagebox.askyesno("Bitte bestätigen", text, parent=self.root)

    def _fehler(self, art, wert, tb):
        """Fehler in Knopf-Befehlen landen hier statt unsichtbar in der Konsole."""
        if isinstance(wert, Eingabefehler):
            messagebox.showwarning("Bitte prüfen", str(wert), parent=self.root)
            return
        traceback.print_exception(art, wert, tb)
        if pymysql is not None and isinstance(wert, pymysql.MySQLError):
            m = self.konfig["mysql"]
            messagebox.showerror("Datenbankfehler", fehlertext(wert, m["host"], m["port"]), parent=self.root)
            return
        messagebox.showerror("Fehler", f"{art.__name__}: {wert}", parent=self.root)

    def _db_anzeigen(self):
        self.db_text.configure(text=f"MySQL: {self.db.info}")

    def konfig_speichern(self) -> None:
        try:
            konfig.speichern(self.konfig)
        except OSError as fehler:
            self.status(f"Einstellungen konnten nicht gespeichert werden: {fehler}")

    def suchen(self):
        tab = self._aktueller_tab()
        if tab is self.briefe:
            self.briefe.suchfeld.focus_set()
        else:
            self.notebook.select(self.briefe)
            self.root.after(50, self.briefe.suchfeld.focus_set)

    # ------------------------------------------------------------ Reiter

    def _aktueller_tab(self):
        name = self.notebook.select()
        return next((t for t in self.tabs if str(t) == name), None)

    def _wechsel_erlaubt(self, tab) -> bool:
        if tab is self.briefe:
            return self.briefe.formular.wechsel_erlaubt()
        if isinstance(tab, StammdatenTab):
            return tab.wechsel_erlaubt()
        return True

    def _tab_gewechselt(self, _e=None):
        tab = self._aktueller_tab()
        vorher = self._vorheriger_tab
        if vorher is not None and vorher is not tab and not self._wechsel_erlaubt(vorher):
            self.notebook.select(vorher)          # löst das Ereignis erneut aus, dann ist vorher == tab
            return
        self._vorheriger_tab = tab
        if tab is not None and tab.veraltet:
            tab.neu_laden()

    def geaendert(self, quelle=None) -> None:
        """Etwas in der Datenbank hat sich geändert: die anderen Reiter beim nächsten Anzeigen neu laden."""
        for tab in self.tabs:
            if tab is not quelle:
                tab.veraltet = True

    def _zeigen(self, tab):
        self._vorheriger_tab = tab          # Wechsel ist schon geprüft
        self.notebook.select(tab)

    def brief_zeigen(self, brief_id: int) -> None:
        aktuell = self._aktueller_tab()
        if aktuell is not self.briefe and not self._wechsel_erlaubt(aktuell):
            return
        self._zeigen(self.briefe)
        self.briefe.auswaehlen(brief_id)

    def briefe_filter(self, status, suche: str = "") -> None:
        self._zeigen(self.briefe)
        if self.briefe.formular.wechsel_erlaubt():
            self.briefe.filter_setzen(status, suche)

    def absender_zeigen(self, absender_id: int) -> None:
        self._zeigen(self.absender)
        self.absender.auswaehlen(absender_id)

    def anlass_zeigen(self, anlass_id: int) -> None:
        self._zeigen(self.anlaesse)
        self.anlaesse.auswaehlen(anlass_id)

    def _neu_in(self, tab):
        aktuell = self._aktueller_tab()
        if aktuell is not tab and not self._wechsel_erlaubt(aktuell):
            return
        self._zeigen(tab)
        if tab.veraltet:
            tab.neu_laden()
        tab.neu()

    def _aktivitaet_neu(self, art):
        vorgaben = {"art": art}
        if self._aktueller_tab() is self.briefe and self.briefe.aktuell_id:
            vorgaben["brief_id"] = self.briefe.aktuell_id
        elif self._aktueller_tab() is self.absender and self.absender.aktuell_id:
            vorgaben["absender_id"] = self.absender.aktuell_id
        elif self._aktueller_tab() is self.anlaesse and self.anlaesse.aktuell_id:
            vorgaben["anlass_id"] = self.anlaesse.aktuell_id
        if AktivitaetDialog(self.root, self.db, vorgaben=vorgaben).zeigen():
            self.geaendert()
            self._aktueller_tab().neu_laden()

    def speichern(self):
        tab = self._aktueller_tab()
        if tab is self.briefe:
            self.briefe.formular.speichern()
        elif isinstance(tab, StammdatenTab):
            tab.speichern()

    # ------------------------------------------------------------ USB und Import

    def usb_text(self) -> str:
        u = self.konfig["usb"]
        if not u.get("aktiv"):
            return "USB-Import ist ausgeschaltet (Datei → Einstellungen)"
        if self._import_laeuft:
            return "Importiere Fotos …"
        return f"USB-Überwachung aktiv – wartet auf einen Stick mit dem Ordner „{u['ordnername']}“"

    def _usb_anzeigen(self):
        self.usb_label.configure(text=("● " if self.konfig["usb"].get("aktiv") else "○ ") + self.usb_text())

    def usb_starten(self) -> None:
        if self.waechter:
            self.waechter.anhalten()
            self.waechter = None
        u = self.konfig["usb"]
        if u.get("aktiv"):
            self.waechter = UsbWaechter(lambda lw, ordner: self.nachrichten.put(("usb", lw, ordner)),
                                        ordnername=u["ordnername"], intervall=u["intervall"],
                                        zusatz_ordner=u.get("zusatz_ordner"))
            self.waechter.starten()
        self._usb_anzeigen()

    def usb_jetzt_pruefen(self) -> None:
        u = self.konfig["usb"]
        waechter = self.waechter or UsbWaechter(lambda lw, ordner: self.nachrichten.put(("usb", lw, ordner)),
                                                ordnername=u["ordnername"], zusatz_ordner=u.get("zusatz_ordner"))

        def pruefen():
            try:
                funde = waechter.pruefen(erzwingen=True)
                self.nachrichten.put(("usb_geprueft", len(funde)))
            except Exception as fehler:
                self.nachrichten.put(("import_fehler", "USB-Prüfung", str(fehler)))

        threading.Thread(target=pruefen, daemon=True).start()
        self.status("Suche nach USB-Sticks …")

    def ordner_importieren(self) -> None:
        ordner = filedialog.askdirectory(parent=self.root, title="Ordner mit Brief-Fotos wählen", mustexist=True)
        if ordner:
            self.import_starten(Path(ordner), f"Ordner {ordner}", usb=False)

    def dateien_zu_brief(self, brief_id: int) -> None:
        typen = " ".join(f"*{e}" for e in sorted(bilder.ENDUNGEN))
        pfade = filedialog.askopenfilenames(parent=self.root, title="Fotos oder PDF als weitere Seiten hinzufügen",
                                            filetypes=[("Fotos und PDF", typen), ("Alle Dateien", "*.*")])
        if not pfade:
            return
        ergebnis = importer.dateien_hinzufuegen(self.db, brief_id, pfade)
        self.geaendert(self.briefe)
        self.briefe.neu_laden(auswahl_id=brief_id)
        self.briefe.bild.zeigen(brief_id, index=10 ** 6)
        if ergebnis.fehler:
            self.hinweis("\n".join(ergebnis.fehler))
        else:
            self.status(f"{ergebnis.neue_fotos} Seite(n) hinzugefügt.")

    def import_starten(self, ordner: Path, quelle: str, usb: bool = True) -> None:
        if self._import_laeuft:
            self._warteschlange.append((ordner, quelle, usb))
            return
        self._import_laeuft = True
        self._usb_anzeigen()
        self.status(f"Importiere aus {quelle} …", 0)
        threading.Thread(target=self._import_arbeit, args=(ordner, quelle, usb), daemon=True).start()

    def _import_arbeit(self, ordner, quelle, usb):
        db = None
        try:
            db = self.db.kopie()          # eigene Verbindung für diesen Thread
            ergebnis = importer.importieren(
                db, ordner, quelle, fortschritt=lambda nr, gesamt, name: self.nachrichten.put(
                    ("fortschritt", nr, gesamt, name)))
            self.nachrichten.put(("import_fertig", ergebnis, usb))
        except Exception as fehler:
            self.nachrichten.put(("import_fehler", quelle, str(fehler)))
        finally:
            if db:
                db.schliessen()

    def _nachrichten_abholen(self):
        try:
            while True:
                nachricht = self.nachrichten.get_nowait()
                self._nachricht(nachricht)
        except queue.Empty:
            pass
        finally:
            self.root.after(300, self._nachrichten_abholen)

    def _nachricht(self, nachricht):
        art = nachricht[0]
        if art == "usb":
            _, laufwerk, ordner = nachricht
            self.import_starten(ordner, f"USB-Stick „{laufwerk.name}“")
        elif art == "fortschritt":
            _, nr, gesamt, name = nachricht
            if time.monotonic() - self._fortschritt_zeit > 0.15 or nr == gesamt:
                self._fortschritt_zeit = time.monotonic()
                self.status(f"Importiere Foto {nr} von {gesamt}: {name}", 0)
        elif art == "usb_geprueft":
            if nachricht[1] == 0 and not self._import_laeuft:
                self.status("")
                self.hinweis(f"Kein USB-Stick mit dem Ordner „{self.konfig['usb']['ordnername']}“ gefunden.\n\n"
                             "Steckt der Stick richtig? Liegt der Ordner direkt auf dem Stick (nicht in einem "
                             "Unterordner)?")
        elif art == "import_fertig":
            _, ergebnis, usb = nachricht
            self._import_beendet()
            self.status(f"{ergebnis.quelle}: {ergebnis.text()}", 12)
            self.geaendert()
            tab = self._aktueller_tab()
            if tab is not None and (tab is not self.briefe or not self.briefe.formular.geaendert):
                tab.neu_laden()
            text = ergebnis.text()
            if ergebnis.fehler:
                text += "\n\n" + "\n".join(ergebnis.fehler[:3]) + ("\n…" if len(ergebnis.fehler) > 3 else "")
            if usb:
                text += "\nDu kannst den Stick jetzt abziehen."
            Toast(self.root, "USB-Import" if usb else "Import", text,
                  "Neue Briefe ansehen" if ergebnis.neue_briefe else "",
                  (lambda: self.briefe_filter("neu")) if ergebnis.neue_briefe else None,
                  sekunden=15 if ergebnis.neue_briefe or ergebnis.fehler else 6)
        elif art == "import_fehler":
            _, quelle, text = nachricht
            self._import_beendet()
            messagebox.showerror("Import fehlgeschlagen", f"{quelle}:\n\n{text}", parent=self.root)

    def _import_beendet(self):
        self._import_laeuft = False
        self._usb_anzeigen()
        if self._warteschlange:
            self.import_starten(*self._warteschlange.pop(0))

    # ------------------------------------------------------------ Einstellungen, Hilfe, Beenden

    def einstellungen(self) -> None:
        if not self._wechsel_erlaubt(self._aktueller_tab()):
            return
        dialog = EinstellungenDialog(self.root, self.konfig)
        neu = dialog.zeigen()
        if not neu:
            return
        alt_mysql = dict(self.konfig["mysql"])
        self.konfig = neu
        self.konfig_speichern()
        if alt_mysql != neu["mysql"]:
            self.db.schliessen()
            self.db = dialog.db
            self.sql.schliessen()
            self._db_anzeigen()
            self.geaendert()
            self._aktueller_tab().neu_laden()
        else:
            dialog.db.schliessen()
        self.usb_starten()
        self.status("Einstellungen gespeichert.")

    def hilfe(self) -> None:
        fenster = tk.Toplevel(self.root)
        fenster.title("Kurzanleitung")
        fenster.transient(self.root)
        text = tk.Text(fenster, width=78, height=38, wrap="word", padx=16, pady=14, font=stil.schrift("normal"),
                       relief="flat")
        text.insert("1.0", HILFE)
        text.configure(state="disabled")
        text.pack(fill="both", expand=True)
        ttk.Button(fenster, text="Schließen", command=fenster.destroy).pack(pady=8)
        fenster.bind("<Escape>", lambda e: fenster.destroy())

    def ueber(self) -> None:
        messagebox.showinfo("Über", f"Briefverwaltung {__version__}\n\nBriefe als Fotos in einer MySQL-Datenbank "
                                    f"verwalten.\n\nDatenbank: {self.db.info}\n"
                                    f"Einstellungen: {konfig.pfad()}", parent=self.root)

    def beenden(self) -> None:
        for tab in (self.briefe, self.absender, self.anlaesse):
            if not self._wechsel_erlaubt(tab):
                self._zeigen(tab)
                return
        if self._import_laeuft and not self.fragen("Es läuft gerade ein Import. Trotzdem beenden?"):
            return
        if self.waechter:
            self.waechter.anhalten()
        self.sql.schliessen()
        self.db.schliessen()
        self.root.destroy()
