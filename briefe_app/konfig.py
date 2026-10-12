"""Einstellungen (Datenbank-Zugang, USB-Überwachung) laden und speichern.

Die Datei liegt in ~/.briefverwaltung/einstellungen.json. Mit der Umgebungsvariablen
BRIEFVERWALTUNG_KONFIG kann man eine andere Datei angeben (z. B. für Tests).
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

STANDARD = {
    "mysql": {
        "host": "localhost",
        "port": 3306,
        "benutzer": "root",
        "passwort": "",
        "passwort_speichern": True,
        "datenbank": "briefverwaltung",
    },
    "usb": {
        "aktiv": True,
        "ordnername": "Briefe",
        "intervall": 2.0,
        "zusatz_ordner": [],          # weitere Orte, an denen nach dem Ordner gesucht wird
    },
    "ansicht": {
        "gruppierung": "absender",
        "status_filter": "offen",
    },
}


def pfad() -> Path:
    eigener = os.environ.get("BRIEFVERWALTUNG_KONFIG")
    if eigener:
        return Path(eigener)
    return Path.home() / ".briefverwaltung" / "einstellungen.json"


def _mischen(basis: dict, neu: dict) -> dict:
    ergebnis = copy.deepcopy(basis)
    for schluessel, wert in (neu or {}).items():
        if isinstance(wert, dict) and isinstance(ergebnis.get(schluessel), dict):
            ergebnis[schluessel] = _mischen(ergebnis[schluessel], wert)
        else:
            ergebnis[schluessel] = wert
    return ergebnis


def laden() -> dict:
    datei = pfad()
    try:
        gelesen = json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        gelesen = {}
    return _mischen(STANDARD, gelesen)


def vorhanden() -> bool:
    return pfad().exists()


def speichern(konfig: dict) -> None:
    datei = pfad()
    datei.parent.mkdir(parents=True, exist_ok=True)
    daten = copy.deepcopy(konfig)
    if not daten["mysql"].get("passwort_speichern", True):
        daten["mysql"]["passwort"] = ""
    tmp = datei.with_suffix(".tmp")
    tmp.write_text(json.dumps(daten, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)                   # Passwort nur für den eigenen Benutzer lesbar
    except OSError:
        pass
    os.replace(tmp, datei)
