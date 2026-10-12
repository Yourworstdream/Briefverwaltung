"""Gemeinsame Helfer für die Tests.

Die Datenbank-Tests brauchen einen MySQL-Server. Zugang über die Umgebungsvariable
BRIEFE_TEST_MYSQL="host:port:benutzer:passwort", z. B.

    BRIEFE_TEST_MYSQL=localhost:3306:root:geheim python -m unittest discover -s tests -v

Ohne die Variable werden diese Tests übersprungen. Jeder Testlauf legt eine eigene
Datenbank bv_test_<nummer> an und löscht sie danach wieder.
"""
import os
import struct
import sys
import unittest
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from briefe_app.datenbank import Datenbank  # noqa: E402

ZUGANG = os.environ.get("BRIEFE_TEST_MYSQL", "")


def png(breite=8, hoehe=8, farbe=(64, 112, 160)) -> bytes:
    """Ein kleines einfarbiges PNG ohne Zusatzbibliotheken. Andere Farbe = anderer Inhalt."""
    def block(art, inhalt):
        return struct.pack(">I", len(inhalt)) + art + inhalt + struct.pack(">I", zlib.crc32(art + inhalt))
    zeilen = b"".join(b"\x00" + bytes(farbe) * breite for _ in range(hoehe))
    return (b"\x89PNG\r\n\x1a\n" + block(b"IHDR", struct.pack(">IIBBBBB", breite, hoehe, 8, 2, 0, 0, 0))
            + block(b"IDAT", zlib.compress(zeilen)) + block(b"IEND", b""))


def zugang():
    host, port, benutzer, passwort = (ZUGANG.split(":", 3) + ["", "", "", ""])[:4]
    return host or "localhost", int(port or 3306), benutzer or "root", passwort


def test_datenbank(name: str) -> Datenbank:
    host, port, benutzer, passwort = zugang()
    db = Datenbank(host, port, benutzer, passwort, f"bv_test_{name}_{os.getpid()}")
    return db


def entfernen(db: Datenbank) -> None:
    db.ausfuehren(f"DROP DATABASE IF EXISTS `{db.name}`")
    db.schliessen()


braucht_mysql = unittest.skipUnless(ZUGANG, "BRIEFE_TEST_MYSQL nicht gesetzt – Datenbank-Tests übersprungen")
