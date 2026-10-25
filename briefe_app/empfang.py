"""Handy-Empfang: ein kleiner Webserver im Heimnetz, an den die Handy-App gescannte Briefe schickt.

Ablauf:
    1. Das PC-Programm zeigt einen QR-Code mit Adresse und Zugangscode („Handy verbinden“).
    2. Die Handy-App scannt den QR-Code und merkt sich beides.
    3. Die App schickt jeden Brief als POST /api/briefe (multipart/form-data):
         - Teil „daten“:  JSON mit den erkannten Angaben (Absender, Frist, Betrag, IBAN …)
         - Teile „seite1“, „seite2“ …: die Fotos (JPEG)
       Der Zugangscode steht im Header „X-Briefe-Token“.
    4. Hier wird daraus ein Brief in der Datenbank – genau wie beim USB-Import.

Nur Geräte, die den Zugangscode kennen, können etwas schicken. Der Server lauscht nur im
eigenen Netz; die Daten gehen unverschlüsselt (http) durchs WLAN.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import socket
import threading
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import __version__, hilfen, importer
from .hilfen import Eingabefehler

STANDARD_PORT = 8765
MAX_GROESSE = 200 * 1024 * 1024          # mehr als 200 MB pro Brief wird abgelehnt
TOKEN_ZEICHEN = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # ohne 0/O und 1/I – gut abzutippen


# ---------------------------------------------------------------- Zugangscode und Adressen

def token_erzeugen() -> str:
    """Zugangscode wie „K7PX-M3QD-9TWB“ (60 Bit Zufall)."""
    zeichen = "".join(secrets.choice(TOKEN_ZEICHEN) for _ in range(12))
    return "-".join(zeichen[i:i + 4] for i in range(0, 12, 4))


def token_normalisieren(text: str | None) -> str:
    text = re.sub(r"[^A-Za-z0-9]", "", text or "").upper()
    return "-".join(text[i:i + 4] for i in range(0, len(text), 4))


def _privat(ip: str) -> bool:
    try:
        adresse = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return adresse.version == 4 and adresse.is_private and not adresse.is_loopback and not adresse.is_link_local


def lokale_adressen() -> list:
    """IPv4-Adressen dieses PCs im Heimnetz, die wahrscheinlichste zuerst."""
    gefunden = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 80))          # Testnetz-Adresse: es wird nichts gesendet
            gefunden.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        gefunden += socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        pass
    ergebnis = []
    for ip in gefunden:
        if _privat(ip) and ip not in ergebnis:
            ergebnis.append(ip)
    return ergebnis


def rechnername() -> str:
    return socket.gethostname() or "PC"


def verbindungsdaten(token: str, port: int, adressen=None) -> dict:
    """Inhalt des QR-Codes für die Handy-App."""
    adressen = lokale_adressen() if adressen is None else adressen
    return {"app": "briefverwaltung", "v": 1, "name": rechnername(), "token": token,
            "adressen": [f"http://{ip}:{port}" for ip in adressen]}


def qr_text(token: str, port: int, adressen=None) -> str:
    return json.dumps(verbindungsdaten(token, port, adressen), separators=(",", ":"), ensure_ascii=False)


# ---------------------------------------------------------------- multipart/form-data

class Teil:
    def __init__(self, name: str, dateiname: str | None, typ: str, daten: bytes):
        self.name, self.dateiname, self.typ, self.daten = name, dateiname, typ, daten

    def __repr__(self):
        return f"Teil({self.name!r}, {self.dateiname!r}, {self.typ!r}, {len(self.daten)} Bytes)"


def _kopfwerte(zeile: str) -> dict:
    """„form-data; name="seite1"; filename="a.jpg"“ → {"name": "seite1", "filename": "a.jpg"}"""
    werte = {}
    for teil in zeile.split(";")[1:]:
        schluessel, _, wert = teil.strip().partition("=")
        werte[schluessel.strip().lower()] = wert.strip().strip('"')
    return werte


def multipart_lesen(inhalt: bytes, content_type: str) -> list:
    """Zerlegt einen multipart/form-data-Body in seine Teile (ohne das in Python 3.13 entfernte cgi-Modul)."""
    treffer = re.search(r'boundary="?([^";]+)"?', content_type or "")
    if not content_type.lower().startswith("multipart/form-data") or not treffer:
        raise Eingabefehler("Erwartet wird multipart/form-data.")
    grenze = b"--" + treffer.group(1).encode("latin-1")
    teile = []
    stuecke = inhalt.split(grenze)
    for stueck in stuecke[1:]:
        if stueck.startswith(b"--"):              # Ende
            break
        if stueck.startswith(b"\r\n"):
            stueck = stueck[2:]
        kopf, trenner, daten = stueck.partition(b"\r\n\r\n")
        if not trenner:
            continue
        if daten.endswith(b"\r\n"):
            daten = daten[:-2]
        name, dateiname, typ = None, None, "text/plain"
        for zeile in kopf.decode("utf-8", "replace").split("\r\n"):
            feld, _, wert = zeile.partition(":")
            if feld.strip().lower() == "content-disposition":
                werte = _kopfwerte(wert)
                name, dateiname = werte.get("name"), werte.get("filename")
            elif feld.strip().lower() == "content-type":
                typ = wert.strip()
        if name:
            teile.append(Teil(name, dateiname, typ, daten))
    return teile


# ---------------------------------------------------------------- Brief anlegen

def _datum(text) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(text)[:10]) if text else None
    except ValueError:
        return None


def _betrag(text) -> Decimal | None:
    try:
        return hilfen.betrag_lesen(str(text)) if text not in (None, "") else None
    except Eingabefehler:
        return None


def _text(daten: dict, schluessel: str, laenge: int) -> str:
    wert = daten.get(schluessel)
    return " ".join(str(wert).split())[:laenge] if wert not in (None, "") else ""


def _person(name: str) -> dict:
    """„Frau Dr. Sabine Krämer“ → Anrede, Titel, Vor- und Nachname."""
    worte = name.split()
    ergebnis = {"anrede": None, "titel": None, "vorname": None, "nachname": ""}
    if worte and worte[0].rstrip(".").lower() in ("frau", "herr", "hr", "fr"):
        ergebnis["anrede"] = "Frau" if worte.pop(0).lower().startswith("f") else "Herr"
    titel = []
    while worte and worte[0].rstrip(".").lower() in ("dr", "prof", "dipl", "ing"):
        titel.append(worte.pop(0))
    ergebnis["titel"] = " ".join(titel) or None
    if len(worte) >= 2:
        ergebnis["vorname"], ergebnis["nachname"] = " ".join(worte[:-1]), worte[-1]
    elif worte:
        ergebnis["nachname"] = worte[0]
    return ergebnis


def _absender_ergaenzen(db, absender_id: int, daten: dict) -> None:
    """Leere Felder des Absenders mit den erkannten Angaben füllen – Vorhandenes wird nie überschrieben."""
    vorhanden = db.absender_holen(absender_id) or {}
    neu = {}
    for feld, schluessel, laenge in (("strasse", "absender_strasse", 200), ("plz", "absender_plz", 10),
                                     ("ort", "absender_ort", 100), ("telefon", "absender_telefon", 50),
                                     ("email", "absender_email", 200), ("webseite", "absender_webseite", 200),
                                     ("kundennummer", "kundennummer", 100)):
        wert = _text(daten, schluessel, laenge)
        if wert and not vorhanden.get(feld):
            neu[feld] = wert
    if neu:
        db.absender_speichern({"id": absender_id, **neu})


def _bankverbindung(db, absender_id: int, daten: dict) -> int | None:
    try:
        iban = hilfen.iban_pruefen(daten.get("iban"))
    except Eingabefehler:
        return None
    gefunden = db.wert("SELECT id FROM bankverbindung WHERE absender_id = %s AND iban = %s", (absender_id, iban))
    if gefunden:
        return gefunden
    try:
        bic = hilfen.bic_pruefen(daten.get("bic"))
    except Eingabefehler:
        bic = ""
    return db.bankverbindung_speichern({"absender_id": absender_id, "iban": iban, "bic": bic,
                                        "kontoinhaber": _text(daten, "absender", 200)})


def _ansprechpartner(db, absender_id: int, daten: dict) -> int | None:
    name = _text(daten, "ansprechpartner", 150)
    if not name:
        return None
    person = _person(name)
    if not person["nachname"]:
        return None
    gefunden = db.wert("SELECT id FROM ansprechpartner WHERE absender_id = %s AND nachname = %s",
                       (absender_id, person["nachname"]))
    if gefunden:
        return gefunden
    return db.ansprechpartner_speichern({
        "absender_id": absender_id, **person,
        "telefon": _text(daten, "ansprechpartner_telefon", 50),
        "email": _text(daten, "ansprechpartner_email", 200)})


def brief_vom_handy(db, daten: dict, seiten: list, quelle: str = "Handy") -> dict:
    """Legt aus den Angaben der Handy-App und den Fotos einen Brief an.

    seiten: [(dateiname, inhalt), …]. Ergebnis: {"ok", "brief_id", "neu", "seiten", "doppelt", "meldung"}.
    """
    uuid = _text(daten, "uuid", 36)
    if uuid:
        frueher = db.zeile("SELECT brief_id FROM handy_upload WHERE uuid = %s", (uuid,))
        if frueher and frueher["brief_id"] and db.brief_holen(frueher["brief_id"]):
            return {"ok": True, "brief_id": frueher["brief_id"], "neu": False, "seiten": 0, "doppelt": 0,
                    "meldung": f"Ist schon angekommen (Brief Nr. {frueher['brief_id']})."}
    if not seiten:
        raise Eingabefehler("Es wurden keine Fotos mitgeschickt.")

    mit_hash = [(name, inhalt, hashlib.sha256(inhalt).hexdigest()) for name, inhalt in seiten]
    neu = [(n, i, h) for n, i, h in mit_hash if not db.foto_mit_hash(h)]
    if not neu:
        vorhanden = db.foto_mit_hash(mit_hash[0][2])
        return {"ok": True, "brief_id": vorhanden["brief_id"], "neu": False, "seiten": 0, "doppelt": len(seiten),
                "meldung": f"Diese Fotos sind schon gespeichert (Brief Nr. {vorhanden['brief_id']})."}

    try:
        dringlichkeit = min(4, max(1, int(daten.get("dringlichkeit") or 2)))
    except (TypeError, ValueError):
        dringlichkeit = 2
    absender_name = _text(daten, "absender", 200)
    art = _text(daten, "art", 50)
    betreff = _text(daten, "betreff", 300) or " – ".join(t for t in (art, absender_name) if t)

    with db.transaktion():
        absender_id = db.absender_id_fuer(absender_name) if absender_name else None
        bank_id = ap_id = None
        if absender_id:
            _absender_ergaenzen(db, absender_id, daten)
            bank_id = _bankverbindung(db, absender_id, daten)
            ap_id = _ansprechpartner(db, absender_id, daten)
        brief_id = db.brief_neu(
            betreff, absender_id=absender_id, ansprechpartner_id=ap_id, bankverbindung_id=bank_id,
            anlass_id=db.anlass_id_fuer(_text(daten, "anlass", 200)),
            briefdatum=_datum(daten.get("briefdatum")), frist=_datum(daten.get("frist")),
            betrag=_betrag(daten.get("betrag")), aktenzeichen=_text(daten, "aktenzeichen", 100),
            dringlichkeit=dringlichkeit, status="neu",
            notizen=str(daten.get("notizen") or "").strip(),
            volltext=str(daten.get("volltext") or "").strip())
        for nr, (name, inhalt, sha) in enumerate(neu, start=1):
            dateiname = re.sub(r"[^\w.\- ]", "_", name or "") or f"seite{nr}.jpg"
            importer.foto_speichern(db, brief_id, dateiname, inhalt, sha, quelle)
        if uuid:
            db.ausfuehren("INSERT INTO handy_upload (uuid, brief_id, geraet) VALUES (%s, %s, %s)",
                          (uuid, brief_id, _text(daten, "geraet", 100) or None))
    doppelt = len(seiten) - len(neu)
    try:
        db.import_protokollieren(quelle, 1, len(neu), doppelt, 0, betreff)
    except Exception:
        pass
    return {"ok": True, "brief_id": brief_id, "neu": True, "seiten": len(neu), "doppelt": doppelt,
            "betreff": betreff, "meldung": f"Brief Nr. {brief_id} angelegt ({hilfen.anzahl(len(neu), 'Seite', 'Seiten')})."}


# ---------------------------------------------------------------- Webserver

class _Anfrage(BaseHTTPRequestHandler):
    server_version = f"Briefverwaltung/{__version__}"
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):        # keine Ausgaben in der Konsole
        pass

    @property
    def empfang(self) -> "Empfang":
        return self.server.empfang

    def _senden(self, code: int, daten: dict | None = None, html: str | None = None) -> None:
        if html is not None:
            inhalt, typ = html.encode("utf-8"), "text/html; charset=utf-8"
        else:
            inhalt, typ = json.dumps(daten or {}, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8"
        self.send_response(code)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(inhalt)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(inhalt)

    def _token_ok(self) -> bool:
        gesendet = token_normalisieren(self.headers.get("X-Briefe-Token"))
        erwartet = token_normalisieren(self.empfang.token)
        return bool(erwartet) and hmac.compare_digest(gesendet.encode(), erwartet.encode())

    def do_GET(self):
        pfad = urlparse(self.path).path
        if pfad == "/":
            self._senden(200, html="<!doctype html><meta charset=utf-8><title>Briefverwaltung</title>"
                                   "<h1>Briefverwaltung</h1><p>Der Handy-Empfang läuft. Die Verbindung "
                                   "zwischen Handy und PC klappt.</p>")
        elif pfad == "/api/info":
            if not self._token_ok():
                self._senden(401, {"ok": False, "meldung": "Falscher Zugangscode."})
                return
            self._senden(200, {"ok": True, "app": "briefverwaltung", "name": rechnername(), "version": __version__})
        else:
            self._senden(404, {"ok": False, "meldung": "Unbekannte Adresse."})

    def do_POST(self):
        if urlparse(self.path).path != "/api/briefe":
            self._senden(404, {"ok": False, "meldung": "Unbekannte Adresse."})
            return
        if not self._token_ok():
            self._senden(401, {"ok": False, "meldung": "Falscher Zugangscode. Bitte das Handy neu verbinden."})
            return
        try:
            laenge = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            laenge = 0
        if laenge <= 0:
            self._senden(411, {"ok": False, "meldung": "Die Länge der Daten fehlt."})
            return
        if laenge > MAX_GROESSE:
            self._senden(413, {"ok": False, "meldung": "Zu groß (höchstens 200 MB pro Brief)."})
            return
        inhalt = self.rfile.read(laenge)
        try:
            teile = multipart_lesen(inhalt, self.headers.get("Content-Type", ""))
            daten_teil = next((t for t in teile if t.name == "daten"), None)
            daten = json.loads(daten_teil.daten.decode("utf-8")) if daten_teil else {}
            if not isinstance(daten, dict):
                raise Eingabefehler("„daten“ muss ein JSON-Objekt sein.")
            seiten = [(t.dateiname or f"{t.name}.jpg", t.daten) for t in teile
                      if t.name.startswith("seite") and t.daten]
            ergebnis = self.empfang.verarbeiten(daten, seiten)
        except (Eingabefehler, ValueError) as fehler:
            self._senden(400, {"ok": False, "meldung": str(fehler)})
            return
        except Exception as fehler:              # z. B. Datenbank nicht erreichbar
            self._senden(500, {"ok": False, "meldung": f"Fehler auf dem PC: {fehler}"})
            return
        self._senden(200, ergebnis)


class Empfang:
    """Startet und stoppt den Server. db_erzeugen() liefert für jede Sendung eine eigene DB-Verbindung."""

    def __init__(self, token: str, db_erzeugen, port: int = STANDARD_PORT, bei_empfang=None, adresse: str = "0.0.0.0"):
        self.token = token
        self.port = int(port)
        self.adresse = adresse
        self.db_erzeugen = db_erzeugen
        self.bei_empfang = bei_empfang
        self._server = None
        self._thread = None
        self.fehler = None
        self._sperre = threading.Lock()          # Briefe nacheinander speichern, nie gleichzeitig

    def verarbeiten(self, daten: dict, seiten: list) -> dict:
        geraet = _text(daten, "geraet", 60)
        with self._sperre:
            db = self.db_erzeugen()
            try:
                ergebnis = brief_vom_handy(db, daten, seiten, f"Handy „{geraet}“" if geraet else "Handy")
            finally:
                db.schliessen()
        if self.bei_empfang:
            try:
                self.bei_empfang(ergebnis)
            except Exception:
                pass
        return ergebnis

    def starten(self) -> bool:
        if self.laeuft:
            return True
        try:
            server = ThreadingHTTPServer((self.adresse, self.port), _Anfrage)
        except OSError as fehler:
            self.fehler = (f"Port {self.port} ist schon belegt – läuft das Programm zweimal?"
                           if getattr(fehler, "errno", None) in (48, 98, 10048) else str(fehler))
            return False
        server.daemon_threads = True
        server.empfang = self
        self.port = server.server_address[1]
        self._server = server
        self.fehler = None
        self._thread = threading.Thread(target=server.serve_forever, name="Handy-Empfang", daemon=True)
        self._thread.start()
        return True

    def anhalten(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    @property
    def laeuft(self) -> bool:
        return self._server is not None
