"""Fotos aus einem Ordner (z. B. „Briefe“ auf dem USB-Stick) in die Datenbank übernehmen.

Regeln:
- Jedes Foto direkt im Ordner wird ein eigener Brief.
- Ein Unterordner (z. B. „Briefe/Stadtwerke Rechnung/“) wird EIN Brief mit mehreren Seiten,
  der Name des Unterordners wird der Betreff.
- Fotos, die schon in der Datenbank sind (gleicher Inhalt = gleicher SHA-256-Wert), werden
  übersprungen. Man kann den Stick also beliebig oft einstecken.
- Auf dem Stick wird nichts verändert oder gelöscht.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import bilder
from .hilfen import anzahl

IGNORIEREN = {"thumbs.db", "desktop.ini", ".ds_store"}
KAMERA_NAME = re.compile(
    r"^(img|dsc|dscn|dscf|pxl|mvimg|photo|foto|bild|image|scan|cam|screenshot|whatsapp image|signal)[\W_-]*\d|^[\d\W_]+$",
    re.IGNORECASE)


@dataclass
class Gruppe:
    """Fotos, die zusammen einen Brief ergeben."""
    betreff: str
    dateien: list
    unterordner: bool = False


@dataclass
class Ergebnis:
    quelle: str
    neue_briefe: list = field(default_factory=list)
    neue_fotos: int = 0
    doppelt: int = 0
    fehler: list = field(default_factory=list)

    @property
    def etwas_neu(self) -> bool:
        return self.neue_fotos > 0

    def text(self) -> str:
        if self.neue_briefe:
            neu = "neuer Brief" if len(self.neue_briefe) == 1 else "neue Briefe"
            teile = [f"{len(self.neue_briefe)} {neu} importiert ({anzahl(self.neue_fotos, 'Foto', 'Fotos')})"]
        elif self.neue_fotos:
            teile = [f"{anzahl(self.neue_fotos, 'Foto', 'Fotos')} zu vorhandenen Briefen hinzugefügt"]
        else:
            teile = ["Keine neuen Fotos"]
        if self.doppelt:
            teile.append(f"{self.doppelt} schon vorhanden")
        if self.fehler:
            teile.append(anzahl(len(self.fehler), "Fehler", "Fehler"))
        return ", ".join(teile) + "."


def _natuerlich(name: str):
    """Sortiert „Seite 2“ vor „Seite 10“."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def ist_versteckt(pfad: Path) -> bool:
    name = pfad.name
    return name.startswith((".", "~", "._")) or name.lower() in IGNORIEREN


def passende_datei(pfad: Path) -> bool:
    return pfad.is_file() and not ist_versteckt(pfad) and pfad.suffix.lower() in bilder.ENDUNGEN


def betreff_aus_name(name: str) -> str:
    """Aus „Stadtwerke_Rechnung.jpg“ wird „Stadtwerke Rechnung“; Kameranamen wie „IMG_2026…“ ergeben „“."""
    stamm = Path(name).stem if Path(name).suffix.lower() in bilder.ENDUNGEN else name
    if KAMERA_NAME.search(stamm):
        return ""
    return re.sub(r"[_]+", " ", stamm).strip()


def briefe_ordner_finden(wurzel, ordnername: str = "Briefe") -> Path | None:
    """Sucht den Ordner (Groß-/Kleinschreibung egal) direkt im Hauptverzeichnis des Sticks."""
    wurzel = Path(wurzel)
    ziel = ordnername.strip().lower()
    if wurzel.name.lower() == ziel and wurzel.is_dir():
        return wurzel
    try:
        for eintrag in wurzel.iterdir():
            if eintrag.name.lower() == ziel and eintrag.is_dir():
                return eintrag
    except OSError:
        return None
    return None


def gruppen_sammeln(ordner) -> list:
    ordner = Path(ordner)
    gruppen = []
    try:
        eintraege = sorted(ordner.iterdir(), key=lambda p: _natuerlich(p.name))
    except OSError:
        return []
    for eintrag in eintraege:
        if ist_versteckt(eintrag):
            continue
        if eintrag.is_dir():
            dateien = sorted((p for p in eintrag.rglob("*") if passende_datei(p)
                              and not any(ist_versteckt(t) for t in p.relative_to(eintrag).parents if t.name)),
                             key=lambda p: [_natuerlich(t) for t in p.relative_to(eintrag).parts])
            if dateien:
                gruppen.append(Gruppe(eintrag.name.strip(), dateien, unterordner=True))
        elif passende_datei(eintrag):
            gruppen.append(Gruppe(betreff_aus_name(eintrag.name), [eintrag]))
    return gruppen


def _foto_speichern(db, brief_id: int, pfad: Path, inhalt: bytes, sha: str, quelle: str) -> dict:
    infos = bilder.bild_infos(inhalt) if bilder.ist_bild(pfad.name) else {}
    db.foto_anlegen(brief_id, inhalt, pfad.name, sha, mime=bilder.mime_fuer(pfad.name),
                    breite=infos.get("breite"), hoehe=infos.get("hoehe"),
                    aufgenommen_am=infos.get("aufgenommen_am"), quelle=quelle, vorschau=infos.get("vorschau"))
    return infos


def _lesen(pfad: Path, ergebnis: Ergebnis):
    try:
        inhalt = pfad.read_bytes()
    except OSError as fehler:
        ergebnis.fehler.append(f"{pfad.name}: nicht lesbar ({fehler.strerror or fehler})")
        return None, None
    return inhalt, hashlib.sha256(inhalt).hexdigest()


def importieren(db, ordner, quelle: str | None = None, fortschritt=None, protokollieren: bool = True) -> Ergebnis:
    """Übernimmt alle neuen Fotos aus `ordner`. fortschritt(nr, gesamt, dateiname) wird je Datei aufgerufen."""
    ordner = Path(ordner)
    quelle = quelle or str(ordner)
    ergebnis = Ergebnis(quelle)
    gruppen = gruppen_sammeln(ordner)
    gesamt = sum(len(g.dateien) for g in gruppen)
    nr = 0
    gesehen = set()
    for gruppe in gruppen:
        neu, vorhandener_brief = [], None
        for pfad in gruppe.dateien:
            nr += 1
            if fortschritt:
                fortschritt(nr, gesamt, pfad.name)
            inhalt, sha = _lesen(pfad, ergebnis)
            if inhalt is None:
                continue
            vorhanden = db.foto_mit_hash(sha)
            if vorhanden or sha in gesehen:
                ergebnis.doppelt += 1
                if vorhanden and vorhandener_brief is None:
                    vorhandener_brief = vorhanden["brief_id"]
                continue
            gesehen.add(sha)
            neu.append((pfad, inhalt, sha))
        if not neu:
            continue
        try:
            with db.transaktion():
                # Neue Seiten in einem Unterordner gehören zum schon importierten Brief
                brief_id = vorhandener_brief if gruppe.unterordner else None
                neuer_brief = brief_id is None
                if neuer_brief:
                    brief_id = db.brief_neu(betreff=gruppe.betreff, status="neu")
                erstes_datum = None
                for pfad, inhalt, sha in neu:
                    infos = _foto_speichern(db, brief_id, pfad, inhalt, sha, f"{quelle} › {pfad.relative_to(ordner)}")
                    erstes_datum = erstes_datum or infos.get("aufgenommen_am")
                if neuer_brief and erstes_datum:
                    # Fotografiert wird meist am Tag, an dem der Brief ankommt
                    db.brief_speichern({"id": brief_id, "eingangsdatum": erstes_datum.date()})
            ergebnis.neue_fotos += len(neu)
            if neuer_brief:
                ergebnis.neue_briefe.append(brief_id)
        except Exception as fehler:            # eine kaputte Gruppe soll den Rest nicht aufhalten
            namen = ", ".join(p.name for p, _, _ in neu[:3]) + (" …" if len(neu) > 3 else "")
            ergebnis.fehler.append(f"{namen}: {fehler}")
    if protokollieren and (gesamt or ergebnis.fehler):
        try:
            db.import_protokollieren(quelle, len(ergebnis.neue_briefe), ergebnis.neue_fotos, ergebnis.doppelt,
                                     len(ergebnis.fehler), "\n".join(ergebnis.fehler))
        except Exception:
            pass
    return ergebnis


def dateien_hinzufuegen(db, brief_id: int, pfade) -> Ergebnis:
    """Hängt ausgewählte Dateien als weitere Seiten an einen vorhandenen Brief an."""
    ergebnis = Ergebnis("Dateiauswahl")
    for pfad in (Path(p) for p in pfade):
        inhalt, sha = _lesen(pfad, ergebnis)
        if inhalt is None:
            continue
        vorhanden = db.foto_mit_hash(sha)
        if vorhanden:
            ergebnis.doppelt += 1
            ergebnis.fehler.append(f"{pfad.name}: ist schon bei Brief Nr. {vorhanden['brief_id']} gespeichert")
            continue
        with db.transaktion():
            _foto_speichern(db, brief_id, pfad, inhalt, sha, str(pfad))
        ergebnis.neue_fotos += 1
    return ergebnis
