#!/usr/bin/env python3
"""Briefverwaltung – Startdatei.

    python briefverwaltung.py                    Programm mit Oberfläche starten
    python briefverwaltung.py --import ORDNER    Fotos aus einem Ordner importieren (ohne Oberfläche)
    python briefverwaltung.py --waechter         nur die USB-Überwachung, ohne Oberfläche (z. B. im Autostart)
    python briefverwaltung.py --schema           das SQL-Schema der Datenbank ausgeben

Die Zugangsdaten zur MySQL-Datenbank stehen in ~/.briefverwaltung/einstellungen.json
(beim ersten Start fragt das Programm danach).
"""
from __future__ import annotations

import argparse
import os
import sys
import time

if sys.version_info < (3, 8):
    sys.exit("Die Briefverwaltung braucht Python 3.8 oder neuer.")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from briefe_app import __version__, importer, konfig  # noqa: E402
from briefe_app.datenbank import SCHEMA, Datenbank, DatenbankFehler  # noqa: E402


def _verbinden():
    daten = konfig.laden()
    if not konfig.vorhanden():
        print("Noch keine Einstellungen vorhanden – starte das Programm einmal mit Oberfläche,", file=sys.stderr)
        print(f"oder lege {konfig.pfad()} an (Vorlage siehe README).", file=sys.stderr)
    return daten, Datenbank.aus_konfig(daten)


def _fortschritt(nr, gesamt, name):
    print(f"\r  {nr}/{gesamt}  {name[:60]:<60}", end="", flush=True)


def ordner_importieren(ordner: str) -> int:
    _daten, db = _verbinden()
    gefunden = importer.briefe_ordner_finden(ordner) if os.path.isdir(ordner) else None
    ziel = gefunden or ordner
    ergebnis = importer.importieren(db, ziel, f"Ordner {ziel}", fortschritt=_fortschritt)
    print()
    print(ergebnis.text())
    for fehler in ergebnis.fehler:
        print("  Fehler:", fehler, file=sys.stderr)
    db.schliessen()
    return 1 if ergebnis.fehler else 0


def waechter() -> int:
    from briefe_app.usb import UsbWaechter

    daten, db = _verbinden()
    u = daten["usb"]

    def gefunden(laufwerk, ordner):
        print(f"{time.strftime('%H:%M:%S')}  Stick „{laufwerk.name}“ erkannt: {ordner}")
        ergebnis = importer.importieren(db, ordner, f"USB-Stick „{laufwerk.name}“", fortschritt=_fortschritt)
        print()
        print(f"{time.strftime('%H:%M:%S')}  {ergebnis.text()}")
        for fehler in ergebnis.fehler:
            print("  Fehler:", fehler, file=sys.stderr)

    w = UsbWaechter(gefunden, ordnername=u["ordnername"], intervall=u["intervall"], zusatz_ordner=u.get("zusatz_ordner"))
    print(f"Briefverwaltung {__version__}: warte auf USB-Sticks mit dem Ordner „{u['ordnername']}“ …  (Strg+C = Ende)")
    try:
        while True:
            w.pruefen()
            time.sleep(w.intervall)
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        db.schliessen()
    return 0


def befehlszeile(argumente: list) -> int:
    parser = argparse.ArgumentParser(description=f"Briefverwaltung {__version__}")
    parser.add_argument("--import", dest="ordner", metavar="ORDNER",
                        help="Fotos aus diesem Ordner (oder seinem Unterordner „Briefe“) importieren")
    parser.add_argument("--waechter", action="store_true", help="nur USB-Überwachung, ohne Oberfläche")
    parser.add_argument("--schema", action="store_true", help="SQL-Schema ausgeben")
    args = parser.parse_args(argumente)

    if args.schema:
        print(SCHEMA.read_text(encoding="utf-8"))
        return 0
    try:
        if args.ordner:
            return ordner_importieren(args.ordner)
        if args.waechter:
            return waechter()
    except DatenbankFehler as fehler:
        print(f"Datenbank: {fehler}", file=sys.stderr)
        return 1

    try:
        from briefe_app import gui
    except ImportError:
        print("tkinter fehlt. Unter Linux z. B. installieren mit:  sudo apt install python3-tk", file=sys.stderr)
        return 1
    return gui.starten()


if __name__ == "__main__":
    sys.exit(befehlszeile(sys.argv[1:]))
