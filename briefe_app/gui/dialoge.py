"""Eingabefenster: Ansprechpartner, Bankverbindung, Aktivität (Telefonat, Treffen, Zahlung …),
Zuordnen mehrerer Briefe und die Einstellungen (Datenbank-Zugang, USB-Überwachung)."""
from __future__ import annotations

import copy
import datetime as dt
import tkinter as tk
from decimal import Decimal
from tkinter import messagebox, ttk

from .. import hilfen
from ..hilfen import Eingabefehler
from . import stil
from .widgets import DatumFeld, IdAuswahl, SuchCombobox, Tooltip


class Dialog(tk.Toplevel):
    """Grundgerüst: modales Fenster mit Inhalt, Fehlerzeile und Knöpfen unten."""

    def __init__(self, eltern, titel: str, knopf_text: str = "Speichern"):
        super().__init__(eltern)
        self.withdraw()
        self.title(titel)
        if eltern.winfo_toplevel().winfo_viewable():      # an ein verstecktes Fenster gebunden wäre es unsichtbar
            self.transient(eltern.winfo_toplevel())
        self.resizable(True, False)
        self.configure(background=stil.HINTERGRUND)
        self.ergebnis = None
        self.inhalt = ttk.Frame(self, padding=(18, 14, 18, 6))
        self.inhalt.pack(fill="both", expand=True)
        self.inhalt.columnconfigure(1, weight=1)
        self.fehler = ttk.Label(self, text="", style="Warnung.TLabel", wraplength=480, padding=(18, 0))
        self.fehler.pack(fill="x")
        self.knoepfe = ttk.Frame(self, padding=(18, 8, 18, 14))
        self.knoepfe.pack(fill="x")
        ttk.Button(self.knoepfe, text=knopf_text, style="Akzent.TButton", command=self._ok).pack(side="right")
        ttk.Button(self.knoepfe, text="Abbrechen", command=self.destroy).pack(side="right", padx=(0, 8))
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Control-Return>", lambda e: self._ok())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._zeile = 0

    def feld(self, text: str, widget, hinweis: str = "", spalten: int = 1):
        ttk.Label(self.inhalt, text=text).grid(row=self._zeile, column=0, sticky="nw", pady=4, padx=(0, 12))
        widget.grid(row=self._zeile, column=1, columnspan=spalten, sticky="ew", pady=4)
        if hinweis:
            Tooltip(widget, hinweis)
        self._zeile += 1
        return widget

    def eingabe(self, text: str, wert: str = "", breite: int = 36, hinweis: str = "") -> tk.StringVar:
        var = tk.StringVar(value=wert or "")
        self.feld(text, ttk.Entry(self.inhalt, textvariable=var, width=breite), hinweis)
        return var

    def textfeld(self, text: str, wert: str = "", hoehe: int = 4) -> tk.Text:
        feld = tk.Text(self.inhalt, height=hoehe, width=40, wrap="word", font=stil.schrift("normal"), padx=6, pady=4)
        feld.insert("1.0", wert or "")
        self.feld(text, feld)
        return feld

    def zeigen(self, fokus=None):
        """Zeigt das Fenster mittig über dem Hauptfenster und wartet, bis es geschlossen wird."""
        self.update_idletasks()
        eltern = self.master.winfo_toplevel()
        if eltern.winfo_viewable():
            x = eltern.winfo_rootx() + max(0, (eltern.winfo_width() - self.winfo_reqwidth()) // 2)
            y = eltern.winfo_rooty() + max(0, (eltern.winfo_height() - self.winfo_reqheight()) // 3)
        else:
            x = max(0, (self.winfo_screenwidth() - self.winfo_reqwidth()) // 2)
            y = max(0, (self.winfo_screenheight() - self.winfo_reqheight()) // 3)
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.lift()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        (fokus or self).focus_set()
        self.wait_window()
        return self.ergebnis

    def _ok(self):
        try:
            self.ergebnis = self.speichern()
        except Eingabefehler as fehler:
            self.fehler.configure(text=str(fehler))
            self.bell()
            return
        self.destroy()

    def speichern(self):                  # in den Unterklassen
        return True


def text_aus(feld: tk.Text) -> str:
    return feld.get("1.0", "end").strip()


# ---------------------------------------------------------------- Ansprechpartner

class AnsprechpartnerDialog(Dialog):
    def __init__(self, eltern, db, absender_id: int, daten: dict | None = None):
        daten = daten or {}
        super().__init__(eltern, "Ansprechpartner bearbeiten" if daten.get("id") else "Neuer Ansprechpartner")
        self.db, self.absender_id, self.daten = db, absender_id, daten
        absender = db.absender_holen(absender_id) or {}
        ttk.Label(self.inhalt, text=f"bei {absender.get('name', '')}", style="Untertitel.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self._zeile = 1
        self.anrede = ttk.Combobox(self.inhalt, values=["Frau", "Herr", "Divers", ""], width=10)
        self.anrede.set(daten.get("anrede") or "")
        self.feld("Anrede", self.anrede)
        self.titel = self.eingabe("Titel", daten.get("titel"), hinweis="z. B. Dr.")
        self.vorname = self.eingabe("Vorname", daten.get("vorname"))
        self.nachname = self.eingabe("Nachname", daten.get("nachname"))
        self.funktion = self.eingabe("Funktion / Abteilung", daten.get("funktion"), hinweis="z. B. Sachbearbeitung")
        self.telefon = self.eingabe("Telefon", daten.get("telefon"))
        self.mobil = self.eingabe("Mobil", daten.get("mobil"))
        self.email = self.eingabe("E-Mail", daten.get("email"))
        self.erreichbar = self.eingabe("Erreichbar", daten.get("erreichbarkeit"), hinweis="z. B. Mo–Do 8–12 Uhr")
        self.notizen = self.textfeld("Notizen", daten.get("notizen"), 3)

    def speichern(self):
        return self.db.ansprechpartner_speichern({
            "id": self.daten.get("id"), "absender_id": self.absender_id, "anrede": self.anrede.get(),
            "titel": self.titel.get(), "vorname": self.vorname.get(), "nachname": self.nachname.get(),
            "funktion": self.funktion.get(), "telefon": self.telefon.get(), "mobil": self.mobil.get(),
            "email": self.email.get(), "erreichbarkeit": self.erreichbar.get(), "notizen": text_aus(self.notizen)})


# ---------------------------------------------------------------- Bankverbindung

class BankDialog(Dialog):
    def __init__(self, eltern, db, absender_id: int, daten: dict | None = None):
        daten = daten or {}
        super().__init__(eltern, "Bankverbindung bearbeiten" if daten.get("id") else "Neue Bankverbindung")
        self.db, self.absender_id, self.daten = db, absender_id, daten
        absender = db.absender_holen(absender_id) or {}
        ttk.Label(self.inhalt, text=f"von {absender.get('name', '')}", style="Untertitel.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self._zeile = 1
        self.inhaber = self.eingabe("Kontoinhaber", daten.get("kontoinhaber") or absender.get("name", ""))
        self.iban = self.eingabe("IBAN", hilfen.iban_formatieren(daten.get("iban")), 40)
        self.iban_info = ttk.Label(self.inhalt, text="", style="Klein.TLabel")
        self.iban_info.grid(row=self._zeile, column=1, sticky="w")
        self._zeile += 1
        self.bic = self.eingabe("BIC", daten.get("bic"), hinweis="freiwillig – innerhalb der EU nicht nötig")
        self.bank = self.eingabe("Bank", daten.get("bank"))
        self.bemerkung = self.eingabe("Bemerkung", daten.get("bemerkung"), hinweis="z. B. „nur für Nebenkosten“")
        self.iban.trace_add("write", lambda *a: self._iban_pruefen())

    def _iban_pruefen(self):
        text = hilfen.iban_normalisieren(self.iban.get())
        if len(text) < 15:
            self.iban_info.configure(text="", style="Klein.TLabel")
            return
        try:
            hilfen.iban_pruefen(text)
            self.iban_info.configure(text="✓ IBAN ist gültig", style="Ok.TLabel")
        except Eingabefehler as fehler:
            self.iban_info.configure(text=str(fehler), style="Klein.TLabel")

    def speichern(self):
        return self.db.bankverbindung_speichern({
            "id": self.daten.get("id"), "absender_id": self.absender_id, "kontoinhaber": self.inhaber.get(),
            "iban": self.iban.get(), "bic": self.bic.get(), "bank": self.bank.get(), "bemerkung": self.bemerkung.get()})


# ---------------------------------------------------------------- Aktivität

class AktivitaetDialog(Dialog):
    """Telefonat, Treffen, Zahlung, E-Mail, Notiz … dokumentieren.

    vorgaben: z. B. {"art": "Telefonat", "brief_id": 3, "absender_id": 1}
    """

    def __init__(self, eltern, db, daten: dict | None = None, vorgaben: dict | None = None):
        daten = dict(daten or {})
        for schluessel, wert in (vorgaben or {}).items():
            daten.setdefault(schluessel, wert)
        art = daten.get("art") or "Telefonat"
        if not daten.get("id") and daten.get("brief_id"):
            self._vom_brief_uebernehmen(db, daten, art)
        super().__init__(eltern, f"{art} bearbeiten" if daten.get("id") else "Neu dokumentieren")
        self.db, self.daten = db, daten
        self.resizable(True, True)

        # Art als Reihe von Knöpfen
        self.art = tk.StringVar(value=art)
        reihe = ttk.Frame(self.inhalt)
        for name in hilfen.AKTIVITAET_ARTEN:
            ttk.Radiobutton(reihe, text=f"{hilfen.aktivitaet_zeichen(name)} {name}", value=name, variable=self.art,
                            style="Toolbutton", command=self._art_geaendert).pack(side="left", padx=(0, 3))
        self.feld("Art", reihe)

        zeit = daten.get("zeitpunkt") or dt.datetime.now().replace(second=0, microsecond=0)
        zeile = ttk.Frame(self.inhalt)
        self.datum = DatumFeld(zeile)
        self.datum.setzen(zeit.date() if isinstance(zeit, dt.datetime) else zeit)
        self.datum.pack(side="left")
        ttk.Label(zeile, text="Uhrzeit").pack(side="left", padx=(12, 6))
        self.uhrzeit = tk.StringVar(value=hilfen.zeit_text(zeit) if isinstance(zeit, dt.datetime) else "")
        ttk.Entry(zeile, textvariable=self.uhrzeit, width=7).pack(side="left")
        ttk.Button(zeile, text="Jetzt", style="Klein.TButton", command=self._jetzt).pack(side="left", padx=6)
        self.feld("Wann", zeile)

        self.betreff = self.eingabe("Betreff", daten.get("betreff"), 50, hinweis="Worum ging es? (kurz)")

        self.absender = SuchCombobox(self.inhalt, db.absender_namen())
        self.absender.set(self._absender_name(daten.get("absender_id")))
        self.feld("Mit wem (Absender)", self.absender, "Neue Namen werden automatisch als Absender angelegt")
        self.absender.bind("<<ComboboxSelected>>", lambda e: self._absender_geaendert())
        self.absender.bind("<FocusOut>", lambda e: self._absender_geaendert())

        self.ansprechpartner = IdAuswahl(self.inhalt)
        self.feld("Ansprechpartner", self.ansprechpartner)
        self.ansprechpartner.bind("<<ComboboxSelected>>", lambda e: self._nummer_uebernehmen())

        self.brief = IdAuswahl(self.inhalt, leer_text="— kein bestimmter Brief —")
        self.feld("Zu Brief", self.brief)
        self.anlass = SuchCombobox(self.inhalt, db.anlass_namen())
        anlass = db.anlass_holen(daten["anlass_id"]) if daten.get("anlass_id") else None
        self.anlass.set(anlass["name"] if anlass else "")
        self.feld("Anlass", self.anlass, "Thema, zu dem das gehört – neue Namen werden angelegt")

        # Zusatzfelder, die je nach Art ein- oder ausgeblendet werden
        self.zusatz = {}
        self.richtung = tk.StringVar(value=daten.get("richtung") or "ausgehend")
        self.richtung_rahmen = ttk.Frame(self.inhalt)
        self.richtung_knoepfe = [ttk.Radiobutton(self.richtung_rahmen, value=w, variable=self.richtung)
                                 for w in ("ausgehend", "eingehend")]
        for k in self.richtung_knoepfe:
            k.pack(side="left", padx=(0, 12))
        self._zusatzfeld("richtung", "Richtung", self.richtung_rahmen)
        self.telefonnummer = tk.StringVar(value=daten.get("telefonnummer") or "")
        self._zusatzfeld("telefonnummer", "Telefonnummer", ttk.Entry(self.inhalt, textvariable=self.telefonnummer))
        self.dauer = tk.StringVar(value=str(daten["dauer_min"]) if daten.get("dauer_min") else "")
        self._zusatzfeld("dauer_min", "Dauer (Minuten)", ttk.Spinbox(self.inhalt, from_=0, to=1440, increment=5,
                                                                     textvariable=self.dauer, width=8))
        self.ort = tk.StringVar(value=daten.get("ort") or "")
        self._zusatzfeld("ort", "Ort", ttk.Entry(self.inhalt, textvariable=self.ort))
        self.betrag = tk.StringVar(value=hilfen.betrag_text(daten.get("betrag"), False))
        self._zusatzfeld("betrag", "Betrag (€)", ttk.Entry(self.inhalt, textvariable=self.betrag, width=14))
        self.zahlungsart = ttk.Combobox(self.inhalt, values=hilfen.ZAHLUNGSARTEN)
        self.zahlungsart.set(daten.get("zahlungsart") or "Überweisung")
        self._zusatzfeld("zahlungsart", "Zahlungsart", self.zahlungsart)
        self.bank = IdAuswahl(self.inhalt)
        self._zusatzfeld("bankverbindung_id", "Bankverbindung", self.bank)

        self.notizen = tk.Text(self.inhalt, height=6, width=50, wrap="word", font=stil.schrift("normal"),
                               padx=6, pady=4)
        self.notizen.insert("1.0", daten.get("notizen") or "")
        self.notiz_label = ttk.Label(self.inhalt, text="Notizen / Ergebnis")
        self.notiz_label.grid(row=99, column=0, sticky="nw", pady=4)
        self.notizen.grid(row=99, column=1, sticky="nsew", pady=4)
        self.inhalt.rowconfigure(99, weight=1)
        self.wiedervorlage = DatumFeld(self.inhalt)
        self.wiedervorlage.setzen(daten.get("wiedervorlage"))
        ttk.Label(self.inhalt, text="Wiedervorlage").grid(row=100, column=0, sticky="w", pady=4)
        self.wiedervorlage.grid(row=100, column=1, sticky="w", pady=4)
        Tooltip(self.wiedervorlage.eingabe, "An welchem Tag soll ich mich wieder darum kümmern? (erscheint in der Übersicht)")

        if daten.get("id"):
            ttk.Button(self.knoepfe, text="Löschen", style="Gefahr.TButton", command=self._loeschen).pack(side="left")

        self._absender_geaendert(erst=True)
        self._art_geaendert()

    @staticmethod
    def _vom_brief_uebernehmen(db, daten: dict, art: str) -> None:
        """Neuer Eintrag zu einem Brief: Absender, Ansprechpartner, Anlass – bei Zahlungen auch
        den noch offenen Betrag und die Bankverbindung – gleich vom Brief übernehmen."""
        brief = db.brief_holen(daten["brief_id"])
        if not brief:
            return
        for feld in ("absender_id", "ansprechpartner_id", "anlass_id", "bankverbindung_id"):
            if not daten.get(feld):
                daten[feld] = brief[feld]
        if art == "Zahlung":
            if daten.get("betrag") is None and brief["betrag"]:
                offen = Decimal(brief["betrag"]) - Decimal(brief["bezahlt"] or 0)
                daten["betrag"] = offen if offen > 0 else None
            if not daten.get("betreff"):
                daten["betreff"] = brief["betreff"]

    def _zusatzfeld(self, schluessel, text, widget):
        label = ttk.Label(self.inhalt, text=text)
        zeile = 20 + len(self.zusatz)
        label.grid(row=zeile, column=0, sticky="w", pady=4, padx=(0, 12))
        widget.grid(row=zeile, column=1, sticky="ew" if schluessel not in ("dauer_min", "betrag") else "w", pady=4)
        self.zusatz[schluessel] = (label, widget)

    def _absender_name(self, absender_id):
        if not absender_id:
            return ""
        a = self.db.absender_holen(absender_id)
        return a["name"] if a else ""

    def _absender_id(self, anlegen: bool = False):
        name = self.absender.get().strip()
        if not name:
            return None
        if anlegen:
            return self.db.absender_id_fuer(name)
        return self.db.wert("SELECT id FROM absender WHERE name = %s", (name,))

    def _absender_geaendert(self, erst: bool = False):
        absender_id = self._absender_id()
        aps = self.db.ansprechpartner_liste(absender_id)
        self.ansprechpartner.optionen([(a["id"], hilfen.person_name(a)) for a in aps], behalten=not erst)
        self.bank.optionen([(b["id"], f"{hilfen.iban_formatieren(b['iban'])}  {b['bank'] or ''}".strip())
                            for b in self.db.bankverbindungen(absender_id)], behalten=not erst)
        briefe = self.db.briefe(absender_id=absender_id) if absender_id else self.db.briefe(status="offen")
        auswahl = [(b["id"], f"{hilfen.datum_text(b['eingangsdatum'] or b['briefdatum'])}  "
                             f"{b['betreff'] or '(ohne Betreff)'}") for b in briefe[:300]]
        if self.daten.get("brief_id") and self.daten["brief_id"] not in [b[0] for b in auswahl]:
            brief = self.db.brief_holen(self.daten["brief_id"])
            if brief:
                auswahl.insert(0, (brief["id"], brief["betreff"] or "(ohne Betreff)"))
        self.brief.optionen(auswahl, behalten=not erst)
        if erst:
            self.ansprechpartner.id = self.daten.get("ansprechpartner_id")
            self.bank.id = self.daten.get("bankverbindung_id")
            self.brief.id = self.daten.get("brief_id")
            if not self.daten.get("id") and self.ansprechpartner.id is None and self.ansprechpartner.anzahl == 1:
                self.ansprechpartner.current(1)
            if not self.daten.get("id") and self.bank.id is None and self.bank.anzahl == 1:
                self.bank.current(1)
            self._nummer_uebernehmen()

    def _nummer_uebernehmen(self):
        if self.telefonnummer.get().strip() or not self.ansprechpartner.id:
            return
        ap = self.db.ansprechpartner_holen(self.ansprechpartner.id)
        if ap:
            self.telefonnummer.set(ap.get("telefon") or ap.get("mobil") or "")

    def _art_geaendert(self):
        art = self.art.get()
        sichtbar = set(hilfen.AKTIVITAET_ARTEN.get(art, {}).get("felder", ()))
        for schluessel, (label, widget) in self.zusatz.items():
            if schluessel in sichtbar:
                label.grid()
                widget.grid()
            else:
                label.grid_remove()
                widget.grid_remove()
        texte = hilfen.RICHTUNG.get(art, hilfen.RICHTUNG["Sonstiges"])
        for knopf, wert in zip(self.richtung_knoepfe, ("ausgehend", "eingehend")):
            knopf.configure(text=texte[wert])
        self.notiz_label.configure(text={"Telefonat": "Was wurde besprochen?", "Treffen": "Ergebnis / Protokoll",
                                         "Zahlung": "Verwendungszweck / Notiz"}.get(art, "Notizen"))
        if not self.daten.get("id"):
            self.title(f"{art} dokumentieren")

    def _jetzt(self):
        jetzt = dt.datetime.now()
        self.datum.setzen(jetzt.date())
        self.uhrzeit.set(jetzt.strftime("%H:%M"))

    def _loeschen(self):
        if messagebox.askyesno("Löschen", "Diesen Eintrag wirklich löschen?", parent=self):
            self.db.aktivitaet_loeschen(self.daten["id"])
            self.ergebnis = "geloescht"
            self.destroy()

    def speichern(self):
        art = self.art.get()
        datum = self.datum.wert()
        if not datum:
            raise Eingabefehler("Bitte ein Datum eingeben.")
        zeit = hilfen.zeit_lesen(self.uhrzeit.get()) or dt.time(0, 0)
        felder = hilfen.AKTIVITAET_ARTEN.get(art, {}).get("felder", ())
        dauer = self.dauer.get().strip()
        if dauer and not dauer.isdigit():
            raise Eingabefehler("Die Dauer bitte in ganzen Minuten angeben, z. B. 15.")
        betrag = hilfen.betrag_lesen(self.betrag.get()) if "betrag" in felder else None
        if art == "Zahlung" and betrag is None:
            raise Eingabefehler("Bitte den gezahlten Betrag eingeben.")
        return self.db.aktivitaet_speichern({
            "id": self.daten.get("id"), "art": art, "zeitpunkt": dt.datetime.combine(datum, zeit),
            "betreff": self.betreff.get(), "notizen": text_aus(self.notizen),
            "brief_id": self.brief.id, "absender_id": self._absender_id(anlegen=True),
            "ansprechpartner_id": self.ansprechpartner.id, "anlass_id": self.db.anlass_id_fuer(self.anlass.get()),
            "richtung": self.richtung.get() if "richtung" in felder else None,
            "telefonnummer": self.telefonnummer.get() if "telefonnummer" in felder else None,
            "dauer_min": int(dauer) if dauer and "dauer_min" in felder else None,
            "ort": self.ort.get() if "ort" in felder else None,
            "betrag": betrag,
            "zahlungsart": self.zahlungsart.get() if "zahlungsart" in felder else None,
            "bankverbindung_id": self.bank.id if "bankverbindung_id" in felder else None,
            "wiedervorlage": self.wiedervorlage.wert(),
        })


# ---------------------------------------------------------------- mehrere Briefe zuordnen

class ZuordnenDialog(Dialog):
    """Mehrere Briefe gemeinsam einem Absender und/oder Anlass zuordnen (= gruppieren)."""

    UNVERAENDERT = "(nicht ändern)"

    def __init__(self, eltern, db, anzahl: int):
        super().__init__(eltern, "Briefe gruppieren", "Übernehmen")
        self.db = db
        ttk.Label(self.inhalt, text=f"{hilfen.anzahl(anzahl, 'Brief', 'Briefe')} gemeinsam zuordnen",
                  style="Untertitel.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        ttk.Label(self.inhalt, text="Leer lassen = Zuordnung entfernen.", style="Klein.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self._zeile = 2
        self.absender = SuchCombobox(self.inhalt, [self.UNVERAENDERT] + db.absender_namen(), width=40)
        self.absender.set(self.UNVERAENDERT)
        self.feld("Absender", self.absender, "Gleicher Absender – neue Namen werden angelegt")
        self.anlass = SuchCombobox(self.inhalt, [self.UNVERAENDERT] + db.anlass_namen(), width=40)
        self.anlass.set(self.UNVERAENDERT)
        self.feld("Anlass", self.anlass, "Gleicher Anlass, z. B. „Nebenkosten 2026“ – neue Namen werden angelegt")
        self.dringlichkeit = ttk.Combobox(self.inhalt, state="readonly",
                                          values=[self.UNVERAENDERT] + [d[0] for d in hilfen.DRINGLICHKEIT.values()])
        self.dringlichkeit.current(0)
        self.feld("Dringlichkeit", self.dringlichkeit)
        self.status = ttk.Combobox(self.inhalt, state="readonly", values=[self.UNVERAENDERT] + list(hilfen.STATUS.values()))
        self.status.current(0)
        self.feld("Status", self.status)

    def speichern(self):
        ergebnis = {}
        if self.absender.get() != self.UNVERAENDERT:
            ergebnis["absender_id"] = self.db.absender_id_fuer(self.absender.get())
        if self.anlass.get() != self.UNVERAENDERT:
            ergebnis["anlass_id"] = self.db.anlass_id_fuer(self.anlass.get())
        if self.dringlichkeit.current() > 0:
            ergebnis["dringlichkeit"] = self.dringlichkeit.current()
        if self.status.current() > 0:
            ergebnis["status"] = list(hilfen.STATUS)[self.status.current() - 1]
        return ergebnis


# ---------------------------------------------------------------- Einstellungen

class EinstellungenDialog(Dialog):
    """Zugang zur MySQL-Datenbank und USB-Überwachung. Beim Speichern wird die Verbindung geprüft."""

    def __init__(self, eltern, konfig: dict, fehlermeldung: str = "", nur_verbindung: bool = False,
                 willkommen: bool = False):
        super().__init__(eltern, "Briefverwaltung einrichten" if willkommen else "Einstellungen",
                         "Verbinden und speichern")
        from ..datenbank import Datenbank      # erst hier, damit der Dialog auch ohne PyMySQL aufgeht
        self._Datenbank = Datenbank
        self.konfig = copy.deepcopy(konfig)
        self.db = None
        m, u = self.konfig["mysql"], self.konfig["usb"]

        if willkommen:
            ttk.Label(self.inhalt, text="Willkommen!", style="Titel.TLabel").grid(row=0, column=0, columnspan=2,
                                                                                 sticky="w")
            ttk.Label(self.inhalt, text="Die Briefe werden in einer MySQL-Datenbank gespeichert. Bitte gib ein, "
                                        "wie das Programm sie erreicht. Die Datenbank selbst wird automatisch "
                                        "angelegt.", wraplength=480, justify="left").grid(
                row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))
        ttk.Label(self.inhalt, text="MySQL-Datenbank", style="Untertitel.TLabel").grid(row=2, column=0, sticky="w")
        self._zeile = 3
        self.host = self.eingabe("Server", m["host"], hinweis="„localhost“, wenn MySQL auf diesem PC läuft")
        self.port = self.eingabe("Port", str(m["port"]), 8)
        self.benutzer = self.eingabe("Benutzer", m["benutzer"])
        self.passwort = tk.StringVar(value=m["passwort"])
        self.feld("Passwort", ttk.Entry(self.inhalt, textvariable=self.passwort, show="•"))
        self.merken = tk.BooleanVar(value=m.get("passwort_speichern", True))
        self.feld("", ttk.Checkbutton(self.inhalt, text="Passwort auf diesem PC merken", variable=self.merken))
        self.datenbank = self.eingabe("Datenbank", m["datenbank"],
                                      hinweis="Wird automatisch angelegt, wenn es sie noch nicht gibt")
        ttk.Label(self.inhalt, text="XAMPP: Benutzer „root“, Passwort leer.  Linux: siehe README.",
                  style="Klein.TLabel").grid(row=self._zeile, column=1, sticky="w")
        self._zeile += 1

        self.usb_aktiv = tk.BooleanVar(value=u["aktiv"])
        self.ordnername = tk.StringVar(value=u["ordnername"])
        self.intervall = tk.StringVar(value=str(u["intervall"]))
        self.zusatz = None
        if not nur_verbindung:
            ttk.Separator(self.inhalt).grid(row=self._zeile, column=0, columnspan=2, sticky="ew", pady=12)
            self._zeile += 1
            ttk.Label(self.inhalt, text="USB-Stick", style="Untertitel.TLabel").grid(row=self._zeile, column=0, sticky="w")
            self._zeile += 1
            self.feld("", ttk.Checkbutton(self.inhalt, text="Fotos automatisch importieren, sobald ein Stick "
                                                            "eingesteckt wird", variable=self.usb_aktiv))
            self.feld("Ordner auf dem Stick", ttk.Entry(self.inhalt, textvariable=self.ordnername),
                      "Name des Ordners mit den Fotos (Groß-/Kleinschreibung egal)")
            self.feld("Prüfen alle (Sekunden)", ttk.Spinbox(self.inhalt, from_=1, to=60, textvariable=self.intervall,
                                                            width=6))
            self.zusatz = self.textfeld("Weitere Orte", "\n".join(u.get("zusatz_ordner") or []), 2)
            Tooltip(self.zusatz, "Optional, ein Pfad pro Zeile – z. B. ein Netzlaufwerk, das wie ein Stick\n"
                                 "behandelt wird. Darin wird ebenfalls nach dem Ordner gesucht.")
        if fehlermeldung:
            self.fehler.configure(text=fehlermeldung)

    def speichern(self):
        m = self.konfig["mysql"]
        port = self.port.get().strip()
        if not port.isdigit():
            raise Eingabefehler("Der Port ist eine Zahl, meistens 3306.")
        m.update(host=self.host.get().strip() or "localhost", port=int(port), benutzer=self.benutzer.get().strip(),
                 passwort=self.passwort.get(), passwort_speichern=self.merken.get(),
                 datenbank=self.datenbank.get().strip())
        u = self.konfig["usb"]
        try:
            intervall = float(self.intervall.get().replace(",", "."))
        except ValueError:
            raise Eingabefehler("Das Prüf-Intervall ist eine Zahl in Sekunden, z. B. 2.") from None
        u.update(aktiv=self.usb_aktiv.get(), ordnername=self.ordnername.get().strip() or "Briefe",
                 intervall=max(1.0, intervall))
        if self.zusatz is not None:
            u["zusatz_ordner"] = [z.strip() for z in text_aus(self.zusatz).splitlines() if z.strip()]
        self.fehler.configure(text="Verbinde …")
        self.update_idletasks()
        from ..datenbank import DatenbankFehler
        try:
            self.db = self._Datenbank.aus_konfig(self.konfig)
        except DatenbankFehler as fehler:
            raise Eingabefehler(str(fehler)) from None
        return self.konfig
