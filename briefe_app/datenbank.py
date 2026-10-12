"""Alle Zugriffe auf die MySQL-Datenbank.

Die Oberfläche spricht nie selbst SQL, sondern ruft die Methoden der Klasse `Datenbank` auf.
Alle Werte werden als Parameter (%s) übergeben – nie per Text zusammengesetzt –, damit
Eingaben wie „O'Brien“ keine SQL-Befehle verändern können (SQL-Injection).
"""
from __future__ import annotations

import contextlib
import datetime as dt
import re
from decimal import Decimal
from pathlib import Path

from .hilfen import STATUS, Eingabefehler, bic_pruefen, iban_pruefen

try:
    import pymysql
except ImportError:            # pragma: no cover – wird in treiber_pruefen() gemeldet
    pymysql = None

SCHEMA = Path(__file__).with_name("schema.sql")
BEISPIELE = Path(__file__).with_name("beispiel_abfragen.sql")

ABSENDER_FELDER = ("name", "art", "strasse", "plz", "ort", "telefon", "email", "webseite", "kundennummer", "notizen")
ANSPRECHPARTNER_FELDER = ("absender_id", "anrede", "titel", "vorname", "nachname", "funktion", "telefon", "mobil",
                          "email", "erreichbarkeit", "notizen")
BANK_FELDER = ("absender_id", "kontoinhaber", "iban", "bic", "bank", "bemerkung")
ANLASS_FELDER = ("name", "beschreibung", "status")
BRIEF_FELDER = ("betreff", "absender_id", "ansprechpartner_id", "bankverbindung_id", "anlass_id", "briefdatum",
                "eingangsdatum", "frist", "dringlichkeit", "status", "betrag", "aktenzeichen", "notizen")
AKTIVITAET_FELDER = ("art", "zeitpunkt", "betreff", "notizen", "brief_id", "absender_id", "ansprechpartner_id",
                     "anlass_id", "richtung", "dauer_min", "ort", "telefonnummer", "betrag", "zahlungsart",
                     "bankverbindung_id", "wiedervorlage")
# Textspalten, die NOT NULL sind: leer bleibt hier '' statt NULL
NICHT_NULL = {"betreff", "nachname", "name", "iban", "art"}

LESENDE_BEFEHLE = ("select", "show", "describe", "desc", "explain", "with", "help")

_FEHLT = object()          # „Parameter wurde nicht angegeben“ (None heißt: Feld leeren)


class DatenbankFehler(Exception):
    """Verbindungs- oder Einrichtungsproblem mit verständlicher Meldung."""


def treiber_pruefen() -> None:
    if pymysql is None:
        raise DatenbankFehler("Das Python-Paket PyMySQL fehlt.\nInstallieren mit:  pip install pymysql")


def fehlertext(fehler: Exception, host: str = "", port: int | str = "") -> str:
    """Macht aus einer MySQL-Fehlermeldung einen Hinweis, mit dem man etwas anfangen kann."""
    code = fehler.args[0] if getattr(fehler, "args", None) else None
    if code in (2003, 2005, 2006, 2013):
        return (f"Der MySQL-Server unter {host}:{port} ist nicht erreichbar.\n"
                "Läuft MySQL? (XAMPP: im Control Panel bei „MySQL“ auf „Start“ klicken.)")
    if code == 1045:
        return "Benutzername oder Passwort ist falsch."
    if code == 1698:
        return ("Der Benutzer „root“ darf sich unter Linux meist nur mit „sudo mysql“ anmelden.\n"
                "Lege einen eigenen MySQL-Benutzer an – die Befehle stehen in der README.")
    if code in (1044, 1142):
        return "Dieser MySQL-Benutzer hat keine Rechte für die Datenbank.\n" + str(fehler.args[-1])
    return f"MySQL-Fehler {code}: {fehler.args[-1] if getattr(fehler, 'args', None) else fehler}"


def sql_aufteilen(text: str) -> list:
    """Teilt ein SQL-Skript an „;“ in einzelne Befehle – nicht in Texten oder Kommentaren."""
    befehle, aktuell = [], []
    i, n = 0, len(text)
    while i < n:
        z = text[i]
        if z in "'\"`":
            ende = i + 1
            while ende < n:
                if text[ende] == "\\" and z != "`":
                    ende += 2
                    continue
                if text[ende] == z:
                    if ende + 1 < n and text[ende + 1] == z:      # '' im Text
                        ende += 2
                        continue
                    break
                ende += 1
            aktuell.append(text[i:ende + 1])
            i = ende + 1
            continue
        if text.startswith("--", i) and (i + 2 >= n or text[i + 2] in " \t\r\n") or z == "#":
            ende = text.find("\n", i)
            i = n if ende < 0 else ende
            continue
        if text.startswith("/*", i):
            ende = text.find("*/", i + 2)
            i = n if ende < 0 else ende + 2
            aktuell.append(" ")
            continue
        if z == ";":
            befehl = "".join(aktuell).strip()
            if befehl:
                befehle.append(befehl)
            aktuell = []
        else:
            aktuell.append(z)
        i += 1
    rest = "".join(aktuell).strip()
    if rest:
        befehle.append(rest)
    return befehle


def beispiele_laden() -> list:
    """Die Beispiel-Abfragen aus beispiel_abfragen.sql: [(name, sql), …]. Jede beginnt mit „-- ## Name“."""
    try:
        text = BEISPIELE.read_text(encoding="utf-8")
    except OSError:
        return [("Alle Briefe", "SELECT * FROM v_briefe;")]
    beispiele = []
    for teil in re.split(r"^-- ## ", text, flags=re.MULTILINE)[1:]:
        name, _, sql = teil.partition("\n")
        beispiele.append((name.strip(), sql.strip()))
    return beispiele


def ist_lesend(befehl: str) -> bool:
    wort = re.match(r"\s*\(?\s*(\w+)", befehl or "")
    return bool(wort) and wort.group(1).lower() in LESENDE_BEFEHLE


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _wert_fuer_db(feld: str, wert):
    if isinstance(wert, str):
        wert = wert.strip()
        if not wert and feld not in NICHT_NULL:
            return None
    return wert


class Datenbank:
    def __init__(self, host: str = "localhost", port: int = 3306, benutzer: str = "root", passwort: str = "",
                 datenbank: str = "briefverwaltung", anlegen: bool = True):
        treiber_pruefen()
        if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", datenbank or ""):
            raise DatenbankFehler("Der Datenbankname darf nur Buchstaben, Ziffern und _ enthalten.")
        self._zugang = dict(host=host, port=int(port), benutzer=benutzer, passwort=passwort, datenbank=datenbank)
        self.name = datenbank
        self.info = f"{benutzer}@{host}:{port} / {datenbank}"
        self._in_transaktion = False
        try:
            self.conn = self._verbinden(datenbank)
        except pymysql.MySQLError as fehler:
            if not (anlegen and fehler.args and fehler.args[0] == 1049):       # 1049 = Datenbank unbekannt
                raise DatenbankFehler(fehlertext(fehler, host, port)) from fehler
            try:
                ohne = self._verbinden(None)
                with ohne.cursor() as cur:
                    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{datenbank}` "
                                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                ohne.close()
                self.conn = self._verbinden(datenbank)
            except pymysql.MySQLError as fehler2:
                raise DatenbankFehler(fehlertext(fehler2, host, port)) from fehler2
        if anlegen:
            self.schema_anlegen()
        self.max_paket = int(self.wert("SELECT @@max_allowed_packet") or 1048576)
        # Bildinhalt in Stücken speichern, die sicher in ein MySQL-Paket passen
        self.teilgroesse = max(32 * 1024, min(8 * 1024 * 1024, (self.max_paket - 8192) // 2))

    def _verbinden(self, datenbank):
        z = self._zugang
        return pymysql.connect(host=z["host"], port=z["port"], user=z["benutzer"], password=z["passwort"],
                               database=datenbank, charset="utf8mb4", autocommit=True, connect_timeout=5)

    @classmethod
    def aus_konfig(cls, konfig: dict, anlegen: bool = True) -> "Datenbank":
        m = konfig["mysql"]
        return cls(m["host"], m["port"], m["benutzer"], m["passwort"], m["datenbank"], anlegen=anlegen)

    def kopie(self) -> "Datenbank":
        """Eine zweite, unabhängige Verbindung (z. B. für den Import im Hintergrund)."""
        z = self._zugang
        return Datenbank(z["host"], z["port"], z["benutzer"], z["passwort"], z["datenbank"], anlegen=False)

    def schliessen(self) -> None:
        with contextlib.suppress(Exception):
            self.conn.close()

    # ------------------------------------------------------------ Grundbausteine

    def _lebendig(self) -> None:
        """Prüft die Verbindung und baut sie bei Bedarf neu auf (z. B. nach dem Standby des PCs)."""
        try:
            self.conn.ping()
        except pymysql.MySQLError:
            if self._in_transaktion:
                raise                          # mitten in einer Transaktion nie still neu verbinden
            with contextlib.suppress(Exception):
                self.conn.close()
            self.conn = self._verbinden(self.name)

    def _cursor(self):
        self._lebendig()
        return self.conn.cursor()

    def abfrage(self, sql: str, parameter=()) -> list:
        with self._cursor() as cur:
            cur.execute(sql, parameter)
            if cur.description is None:
                return []
            namen = [d[0] for d in cur.description]
            return [dict(zip(namen, zeile)) for zeile in cur.fetchall()]

    def zeile(self, sql: str, parameter=()) -> dict | None:
        zeilen = self.abfrage(sql, parameter)
        return zeilen[0] if zeilen else None

    def wert(self, sql: str, parameter=()):
        with self._cursor() as cur:
            cur.execute(sql, parameter)
            gefunden = cur.fetchone()
            return gefunden[0] if gefunden else None

    def ausfuehren(self, sql: str, parameter=()) -> int:
        """Führt einen Befehl aus und gibt die neue ID (INSERT) bzw. die Zahl der Zeilen zurück."""
        with self._cursor() as cur:
            cur.execute(sql, parameter)
            return cur.lastrowid or cur.rowcount

    @contextlib.contextmanager
    def transaktion(self):
        """Alles im with-Block wird gemeinsam gespeichert – oder bei einem Fehler gar nicht."""
        if self._in_transaktion:                 # verschachtelt: die äußere Transaktion zählt
            yield
            return
        self._lebendig()
        self.conn.begin()
        self._in_transaktion = True
        try:
            yield
        except BaseException:
            self.conn.rollback()
            raise
        else:
            self.conn.commit()
        finally:
            self._in_transaktion = False

    def schema_anlegen(self) -> None:
        for befehl in sql_aufteilen(SCHEMA.read_text(encoding="utf-8")):
            self.ausfuehren(befehl)

    def _speichern(self, tabelle: str, felder: tuple, daten: dict) -> int:
        werte = {f: _wert_fuer_db(f, daten[f]) for f in felder if f in daten}
        try:
            if daten.get("id"):
                if werte:
                    setzen = ", ".join(f"`{f}` = %s" for f in werte)
                    self.ausfuehren(f"UPDATE `{tabelle}` SET {setzen} WHERE id = %s", (*werte.values(), daten["id"]))
                return int(daten["id"])
            spalten = ", ".join(f"`{f}`" for f in werte)
            platz = ", ".join(["%s"] * len(werte))
            return self.ausfuehren(f"INSERT INTO `{tabelle}` ({spalten}) VALUES ({platz})", tuple(werte.values()))
        except pymysql.err.IntegrityError as fehler:
            if fehler.args[0] == 1062:
                raise Eingabefehler("Diesen Eintrag gibt es schon (gleicher Name bzw. gleiche IBAN).") from fehler
            raise

    def _loeschen(self, tabelle: str, id_: int) -> None:
        self.ausfuehren(f"DELETE FROM `{tabelle}` WHERE id = %s", (id_,))

    # ------------------------------------------------------------ Absender

    def absender_liste(self, suche: str = "") -> list:
        sql = """SELECT a.*,
                        (SELECT COUNT(*) FROM brief b WHERE b.absender_id = a.id) AS briefe,
                        (SELECT COUNT(*) FROM brief b WHERE b.absender_id = a.id AND b.status <> 'erledigt') AS offen
                 FROM absender a"""
        parameter = ()
        if suche:
            sql += " WHERE a.name LIKE %s OR a.ort LIKE %s OR a.kundennummer LIKE %s OR a.art LIKE %s"
            parameter = (_like(suche),) * 4
        return self.abfrage(sql + " ORDER BY a.name", parameter)

    def absender_namen(self) -> list:
        return [z["name"] for z in self.abfrage("SELECT name FROM absender ORDER BY name")]

    def absender_holen(self, id_: int) -> dict | None:
        return self.zeile("SELECT * FROM absender WHERE id = %s", (id_,))

    def absender_speichern(self, daten: dict) -> int:
        if "name" in daten and not (daten["name"] or "").strip():
            raise Eingabefehler("Bitte einen Namen für den Absender eingeben.")
        return self._speichern("absender", ABSENDER_FELDER, daten)

    def absender_loeschen(self, id_: int) -> None:
        self._loeschen("absender", id_)

    def absender_id_fuer(self, name: str | None) -> int | None:
        """ID des Absenders mit diesem Namen – wird angelegt, wenn es ihn noch nicht gibt."""
        name = (name or "").strip()
        if not name:
            return None
        gefunden = self.wert("SELECT id FROM absender WHERE name = %s", (name,))
        return gefunden or self.absender_speichern({"name": name})

    # ------------------------------------------------------------ Ansprechpartner

    def ansprechpartner_liste(self, absender_id: int | None) -> list:
        if not absender_id:
            return []
        return self.abfrage("SELECT * FROM ansprechpartner WHERE absender_id = %s ORDER BY nachname, vorname",
                            (absender_id,))

    def ansprechpartner_holen(self, id_: int) -> dict | None:
        return self.zeile("SELECT * FROM ansprechpartner WHERE id = %s", (id_,))

    def ansprechpartner_speichern(self, daten: dict) -> int:
        if not daten.get("absender_id") and not daten.get("id"):
            raise Eingabefehler("Ein Ansprechpartner gehört immer zu einem Absender.")
        if not ((daten.get("nachname") or "").strip() or (daten.get("vorname") or "").strip()):
            raise Eingabefehler("Bitte mindestens einen Namen für den Ansprechpartner eingeben.")
        return self._speichern("ansprechpartner", ANSPRECHPARTNER_FELDER, daten)

    def ansprechpartner_loeschen(self, id_: int) -> None:
        self._loeschen("ansprechpartner", id_)

    # ------------------------------------------------------------ Bankverbindungen

    def bankverbindungen(self, absender_id: int | None) -> list:
        if not absender_id:
            return []
        return self.abfrage("SELECT * FROM bankverbindung WHERE absender_id = %s ORDER BY bank, iban", (absender_id,))

    def bankverbindung_holen(self, id_: int) -> dict | None:
        return self.zeile("SELECT * FROM bankverbindung WHERE id = %s", (id_,))

    def bankverbindung_speichern(self, daten: dict) -> int:
        daten = dict(daten)
        if not daten.get("absender_id") and not daten.get("id"):
            raise Eingabefehler("Eine Bankverbindung gehört immer zu einem Absender.")
        if "iban" in daten:
            daten["iban"] = iban_pruefen(daten["iban"])
        if "bic" in daten:
            daten["bic"] = bic_pruefen(daten["bic"])
        return self._speichern("bankverbindung", BANK_FELDER, daten)

    def bankverbindung_loeschen(self, id_: int) -> None:
        self._loeschen("bankverbindung", id_)

    # ------------------------------------------------------------ Anlässe

    def anlaesse(self, suche: str = "", nur_offen: bool = False) -> list:
        sql = """SELECT an.*,
                        (SELECT COUNT(*) FROM brief b WHERE b.anlass_id = an.id) AS briefe,
                        (SELECT COUNT(*) FROM brief b WHERE b.anlass_id = an.id AND b.status <> 'erledigt') AS offen,
                        (SELECT MAX(COALESCE(b.eingangsdatum, b.briefdatum)) FROM brief b
                          WHERE b.anlass_id = an.id) AS letzter_brief
                 FROM anlass an WHERE 1 = 1"""
        parameter = []
        if nur_offen:
            sql += " AND an.status = 'offen'"
        if suche:
            sql += " AND (an.name LIKE %s OR an.beschreibung LIKE %s)"
            parameter += [_like(suche)] * 2
        return self.abfrage(sql + " ORDER BY an.status = 'erledigt', an.name", tuple(parameter))

    def anlass_namen(self) -> list:
        return [z["name"] for z in self.abfrage("SELECT name FROM anlass ORDER BY status = 'erledigt', name")]

    def anlass_holen(self, id_: int) -> dict | None:
        return self.zeile("SELECT * FROM anlass WHERE id = %s", (id_,))

    def anlass_speichern(self, daten: dict) -> int:
        if "name" in daten and not (daten["name"] or "").strip():
            raise Eingabefehler("Bitte einen Namen für den Anlass eingeben.")
        return self._speichern("anlass", ANLASS_FELDER, daten)

    def anlass_loeschen(self, id_: int) -> None:
        self._loeschen("anlass", id_)

    def anlass_id_fuer(self, name: str | None) -> int | None:
        name = (name or "").strip()
        if not name:
            return None
        gefunden = self.wert("SELECT id FROM anlass WHERE name = %s", (name,))
        return gefunden or self.anlass_speichern({"name": name})

    # ------------------------------------------------------------ Briefe

    def briefe(self, suche: str = "", status: str | None = None, absender_id: int | None = None,
               anlass_id: int | None = None) -> list:
        """Briefe aus der Sicht v_briefe. status: None = alle, „offen“ = alles außer erledigt."""
        sql, parameter = "SELECT * FROM v_briefe WHERE 1 = 1", []
        if status == "offen":
            sql += " AND status <> 'erledigt'"
        elif status == "dringend":
            sql += " AND status <> 'erledigt' AND dringlichkeit >= 3"
        elif status == "ueberfaellig":
            sql += " AND status <> 'erledigt' AND frist < CURDATE()"
        elif status == "fristen":
            sql += " AND status <> 'erledigt' AND frist BETWEEN CURDATE() AND CURDATE() + INTERVAL 7 DAY"
        elif status:
            sql += " AND status = %s"
            parameter.append(status)
        if absender_id:
            sql += " AND absender_id = %s"
            parameter.append(absender_id)
        if anlass_id:
            sql += " AND anlass_id = %s"
            parameter.append(anlass_id)
        if suche:
            sql += (" AND (betreff LIKE %s OR absender LIKE %s OR anlass LIKE %s OR aktenzeichen LIKE %s"
                    " OR notizen LIKE %s)")
            parameter += [_like(suche)] * 5
        sql += (" ORDER BY status = 'erledigt', dringlichkeit DESC, frist IS NULL, frist,"
                " COALESCE(eingangsdatum, briefdatum) DESC, id DESC")
        return self.abfrage(sql, tuple(parameter))

    def brief_holen(self, id_: int) -> dict | None:
        return self.zeile("SELECT * FROM v_briefe WHERE id = %s", (id_,))

    def brief_speichern(self, daten: dict) -> int:
        if "dringlichkeit" in daten and int(daten["dringlichkeit"] or 0) not in (1, 2, 3, 4):
            raise Eingabefehler("Die Dringlichkeit muss zwischen 1 und 4 liegen.")
        if "status" in daten and daten["status"] not in STATUS:
            raise Eingabefehler(f"Unbekannter Status „{daten['status']}“.")
        return self._speichern("brief", BRIEF_FELDER, daten)

    def brief_neu(self, betreff: str = "", **felder) -> int:
        felder.setdefault("eingangsdatum", dt.date.today())
        return self.brief_speichern({"betreff": betreff, **felder})

    def brief_loeschen(self, id_: int) -> None:
        self._loeschen("brief", id_)

    def briefe_zuordnen(self, ids, absender_id=_FEHLT, anlass_id=_FEHLT, dringlichkeit=_FEHLT, status=_FEHLT) -> None:
        """Setzt für mehrere Briefe auf einmal Absender, Anlass, Dringlichkeit und/oder Status (= gruppieren)."""
        ids = [int(i) for i in ids]
        if not ids:
            return
        platz = ", ".join(["%s"] * len(ids))
        with self.transaktion():
            if absender_id is not _FEHLT:
                # Ansprechpartner/Bankverbindung eines anderen Absenders passen dann nicht mehr
                self.ausfuehren(
                    f"""UPDATE brief SET absender_id = %s,
                          ansprechpartner_id = IF(ansprechpartner_id IN
                              (SELECT id FROM ansprechpartner WHERE absender_id = %s), ansprechpartner_id, NULL),
                          bankverbindung_id = IF(bankverbindung_id IN
                              (SELECT id FROM bankverbindung WHERE absender_id = %s), bankverbindung_id, NULL)
                        WHERE id IN ({platz})""",
                    (absender_id, absender_id or 0, absender_id or 0, *ids))
            for feld, wert in (("anlass_id", anlass_id), ("dringlichkeit", dringlichkeit), ("status", status)):
                if wert is not _FEHLT:
                    self.ausfuehren(f"UPDATE brief SET {feld} = %s WHERE id IN ({platz})", (wert, *ids))

    def briefe_zusammenfassen(self, ziel_id: int, andere_ids) -> None:
        """Hängt die Seiten (und Aktivitäten) der anderen Briefe an den Ziel-Brief an und löscht die anderen."""
        andere_ids = [int(i) for i in andere_ids if int(i) != int(ziel_id)]
        if not andere_ids:
            return
        with self.transaktion():
            ziel = self.zeile("SELECT * FROM brief WHERE id = %s", (ziel_id,))
            if not ziel:
                raise Eingabefehler("Der Ziel-Brief existiert nicht mehr.")
            ergaenzen, notizen = {}, []
            for anderer_id in andere_ids:
                anderer = self.zeile("SELECT * FROM brief WHERE id = %s", (anderer_id,))
                if not anderer:
                    continue
                for feld in ("absender_id", "ansprechpartner_id", "bankverbindung_id", "anlass_id", "briefdatum",
                             "frist", "betrag", "aktenzeichen"):
                    if ziel[feld] is None and anderer[feld] is not None and feld not in ergaenzen:
                        ergaenzen[feld] = anderer[feld]
                if (anderer["betreff"] or "").strip() and not (ziel["betreff"] or "").strip() and "betreff" not in ergaenzen:
                    ergaenzen["betreff"] = anderer["betreff"]
                if anderer["dringlichkeit"] > ziel["dringlichkeit"]:
                    ergaenzen["dringlichkeit"] = max(anderer["dringlichkeit"], ergaenzen.get("dringlichkeit", 0))
                if anderer["notizen"]:
                    notizen.append(anderer["notizen"])
                # int(): MariaDB liefert COALESCE(MAX(…), 0) als Dezimalzahl
                start = int(self.wert("SELECT COALESCE(MAX(seite), 0) FROM foto WHERE brief_id = %s", (ziel_id,)))
                for nr, foto in enumerate(self.abfrage(
                        "SELECT id FROM foto WHERE brief_id = %s ORDER BY seite, id", (anderer_id,)), start=start + 1):
                    self.ausfuehren("UPDATE foto SET brief_id = %s, seite = %s WHERE id = %s", (ziel_id, nr, foto["id"]))
                self.ausfuehren("UPDATE aktivitaet SET brief_id = %s WHERE brief_id = %s", (ziel_id, anderer_id))
                self.ausfuehren("DELETE FROM brief WHERE id = %s", (anderer_id,))
            if notizen:                                      # Notizen der anderen Briefe anhängen
                ergaenzen["notizen"] = "\n\n".join(([ziel["notizen"]] if ziel["notizen"] else []) + notizen)
            if ergaenzen:
                self._speichern("brief", BRIEF_FELDER, {"id": ziel_id, **ergaenzen})

    # ------------------------------------------------------------ Fotos (Seiten)

    def fotos(self, brief_id: int) -> list:
        return self.abfrage(
            """SELECT id, brief_id, seite, dateiname, mime, groesse, sha256, breite, hoehe, drehung,
                      aufgenommen_am, importiert_am, quelle, vorschau
               FROM foto WHERE brief_id = %s ORDER BY seite, id""", (brief_id,))

    def foto_holen(self, foto_id: int) -> dict | None:
        return self.zeile("SELECT * FROM foto WHERE id = %s", (foto_id,))

    def foto_inhalt(self, foto_id: int) -> bytes:
        teile = self.abfrage("SELECT daten FROM foto_teil WHERE foto_id = %s ORDER BY nr", (foto_id,))
        return b"".join(bytes(t["daten"]) for t in teile)

    def foto_mit_hash(self, sha256: str) -> dict | None:
        return self.zeile("SELECT id, brief_id, seite FROM foto WHERE sha256 = %s", (sha256,))

    def foto_anlegen(self, brief_id: int, inhalt: bytes, dateiname: str, sha256: str, mime: str | None = None,
                     seite: int | None = None, breite=None, hoehe=None, aufgenommen_am=None, quelle=None,
                     vorschau: bytes | None = None) -> int:
        """Speichert ein Foto. Bitte innerhalb von transaktion() aufrufen."""
        if seite is None:
            seite = int(self.wert("SELECT COALESCE(MAX(seite), 0) + 1 FROM foto WHERE brief_id = %s", (brief_id,)))
        if vorschau and len(vorschau) > self.teilgroesse:
            vorschau = None
        foto_id = self.ausfuehren(
            """INSERT INTO foto (brief_id, seite, dateiname, mime, groesse, sha256, breite, hoehe,
                                 aufgenommen_am, quelle, vorschau)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (brief_id, seite, dateiname[:255], mime, len(inhalt), sha256, breite, hoehe, aufgenommen_am,
             (quelle or "")[:500] or None, vorschau))
        for nr, start in enumerate(range(0, max(len(inhalt), 1), self.teilgroesse)):
            self.ausfuehren("INSERT INTO foto_teil (foto_id, nr, daten) VALUES (%s, %s, %s)",
                            (foto_id, nr, inhalt[start:start + self.teilgroesse]))
        return foto_id

    def foto_drehen(self, foto_id: int, grad: int) -> None:
        self.ausfuehren("UPDATE foto SET drehung = MOD(drehung + %s + 360, 360) WHERE id = %s", (grad % 360, foto_id))

    def seiten_nummerieren(self, brief_id: int) -> None:
        for nr, foto in enumerate(self.abfrage("SELECT id FROM foto WHERE brief_id = %s ORDER BY seite, id",
                                               (brief_id,)), start=1):
            self.ausfuehren("UPDATE foto SET seite = %s WHERE id = %s", (nr, foto["id"]))

    def foto_loeschen(self, foto_id: int) -> None:
        foto = self.foto_holen(foto_id)
        if foto:
            with self.transaktion():
                self._loeschen("foto", foto_id)
                self.seiten_nummerieren(foto["brief_id"])

    def foto_seite_verschieben(self, foto_id: int, schritt: int) -> None:
        """Seite eine Position nach vorne (-1) oder hinten (+1) schieben."""
        foto = self.foto_holen(foto_id)
        if not foto:
            return
        ids = [f["id"] for f in self.abfrage("SELECT id FROM foto WHERE brief_id = %s ORDER BY seite, id",
                                             (foto["brief_id"],))]
        alt = ids.index(foto_id)
        neu = max(0, min(len(ids) - 1, alt + schritt))
        ids.insert(neu, ids.pop(alt))
        with self.transaktion():
            for nr, id_ in enumerate(ids, start=1):
                self.ausfuehren("UPDATE foto SET seite = %s WHERE id = %s", (nr, id_))

    def foto_als_neuer_brief(self, foto_id: int) -> int:
        """Trennt eine Seite ab und macht daraus einen eigenen Brief (gleicher Absender und Anlass)."""
        foto = self.foto_holen(foto_id)
        if not foto:
            raise Eingabefehler("Das Foto existiert nicht mehr.")
        alt = self.zeile("SELECT * FROM brief WHERE id = %s", (foto["brief_id"],))
        with self.transaktion():
            neu_id = self.brief_speichern({
                "betreff": Path(foto["dateiname"]).stem, "absender_id": alt["absender_id"],
                "anlass_id": alt["anlass_id"], "eingangsdatum": alt["eingangsdatum"], "status": "neu"})
            self.ausfuehren("UPDATE foto SET brief_id = %s, seite = 1 WHERE id = %s", (neu_id, foto_id))
            self.seiten_nummerieren(alt["id"])
        return neu_id

    # ------------------------------------------------------------ Aktivitäten

    def aktivitaeten(self, brief_id=None, absender_id=None, anlass_id=None, art=None, suche: str = "",
                     grenze: int | None = None) -> list:
        sql, parameter = "SELECT * FROM v_aktivitaeten WHERE 1 = 1", []
        if brief_id:
            sql += " AND brief_id = %s"
            parameter.append(brief_id)
        if absender_id:
            sql += " AND (absender_id = %s OR brief_id IN (SELECT id FROM brief WHERE absender_id = %s))"
            parameter += [absender_id, absender_id]
        if anlass_id:
            sql += " AND (anlass_id = %s OR brief_id IN (SELECT id FROM brief WHERE anlass_id = %s))"
            parameter += [anlass_id, anlass_id]
        if art:
            sql += " AND art = %s"
            parameter.append(art)
        if suche:
            sql += (" AND (betreff LIKE %s OR notizen LIKE %s OR absender LIKE %s OR ansprechpartner LIKE %s"
                    " OR brief LIKE %s OR anlass LIKE %s)")
            parameter += [_like(suche)] * 6
        sql += " ORDER BY zeitpunkt DESC, id DESC"
        if grenze:
            sql += f" LIMIT {int(grenze)}"
        return self.abfrage(sql, tuple(parameter))

    def aktivitaet_holen(self, id_: int) -> dict | None:
        return self.zeile("SELECT * FROM v_aktivitaeten WHERE id = %s", (id_,))

    def aktivitaet_speichern(self, daten: dict) -> int:
        daten = dict(daten)
        if not (daten.get("art") or "").strip() and not daten.get("id"):
            raise Eingabefehler("Bitte die Art der Aktivität wählen (Telefonat, Treffen, Zahlung …).")
        if not daten.get("zeitpunkt") and not daten.get("id"):
            daten["zeitpunkt"] = dt.datetime.now().replace(second=0, microsecond=0)
        if daten.get("richtung") not in (None, "", "eingehend", "ausgehend"):
            raise Eingabefehler("Die Richtung muss „eingehend“ oder „ausgehend“ sein.")
        if daten.get("brief_id"):
            # Absender und Anlass vom Brief übernehmen, damit die Aktivität auch dort auftaucht
            brief = self.zeile("SELECT absender_id, anlass_id FROM brief WHERE id = %s", (daten["brief_id"],))
            if brief:
                for feld in ("absender_id", "anlass_id"):
                    if not daten.get(feld):
                        daten[feld] = brief[feld]
        return self._speichern("aktivitaet", AKTIVITAET_FELDER, daten)

    def aktivitaet_loeschen(self, id_: int) -> None:
        self._loeschen("aktivitaet", id_)

    # ------------------------------------------------------------ Übersicht

    def kennzahlen(self) -> dict:
        werte = self.zeile(
            """SELECT
                 COUNT(*) AS gesamt,
                 COALESCE(SUM(status = 'neu'), 0) AS neu,
                 COALESCE(SUM(status <> 'erledigt'), 0) AS offen,
                 COALESCE(SUM(status <> 'erledigt' AND dringlichkeit >= 3), 0) AS dringend,
                 COALESCE(SUM(status <> 'erledigt' AND frist < CURDATE()), 0) AS ueberfaellig,
                 COALESCE(SUM(status <> 'erledigt' AND frist BETWEEN CURDATE() AND CURDATE() + INTERVAL 7 DAY), 0)
                     AS fristen,
                 COALESCE(SUM(IF(status <> 'erledigt' AND betrag > 0, GREATEST(betrag - bezahlt, 0), 0)), 0)
                     AS offener_betrag
               FROM v_briefe""") or {}
        werte = {k: Decimal(str(v or 0)) if k == "offener_betrag" else int(v or 0) for k, v in werte.items()}
        werte["absender"] = int(self.wert("SELECT COUNT(*) FROM absender") or 0)
        werte["aktivitaeten_30"] = int(self.wert(
            "SELECT COUNT(*) FROM aktivitaet WHERE zeitpunkt >= NOW() - INTERVAL 30 DAY") or 0)
        return werte

    def naechste_fristen(self, tage: int = 30) -> list:
        return self.abfrage(
            """SELECT * FROM v_briefe WHERE status <> 'erledigt' AND frist IS NOT NULL
                 AND frist <= CURDATE() + INTERVAL %s DAY ORDER BY frist, dringlichkeit DESC""", (int(tage),))

    def wiedervorlagen(self, tage: int = 14) -> list:
        return self.abfrage(
            """SELECT * FROM v_aktivitaeten WHERE wiedervorlage IS NOT NULL
                 AND wiedervorlage BETWEEN CURDATE() - INTERVAL 7 DAY AND CURDATE() + INTERVAL %s DAY
               ORDER BY wiedervorlage""", (int(tage),))

    def briefe_je_absender(self, grenze: int = 8) -> list:
        return self.abfrage(
            f"""SELECT COALESCE(absender, '(ohne Absender)') AS name, COUNT(*) AS anzahl,
                       SUM(status <> 'erledigt') AS offen
                FROM v_briefe GROUP BY absender ORDER BY anzahl DESC, name LIMIT {int(grenze)}""")

    def import_protokollieren(self, quelle: str, neue_briefe: int, neue_fotos: int, doppelt: int, fehler: int,
                              meldung: str = "") -> int:
        return self.ausfuehren(
            """INSERT INTO import_protokoll (quelle, neue_briefe, neue_fotos, doppelt, fehler, meldung)
               VALUES (%s, %s, %s, %s, %s, %s)""", (quelle[:500], neue_briefe, neue_fotos, doppelt, fehler, meldung))

    def letzte_importe(self, grenze: int = 5) -> list:
        return self.abfrage(f"SELECT * FROM import_protokoll ORDER BY zeitpunkt DESC, id DESC LIMIT {int(grenze)}")

    # ------------------------------------------------------------ SQL-Fenster

    def tabellen(self) -> list:
        return self.abfrage(
            """SELECT table_name AS name, table_type AS typ FROM information_schema.tables
               WHERE table_schema = DATABASE() ORDER BY table_type, table_name""")

    def spalten(self, tabelle: str) -> list:
        return self.abfrage(
            """SELECT column_name AS name, column_type AS typ, is_nullable AS leer_erlaubt, column_key AS schluessel
               FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = %s
               ORDER BY ordinal_position""", (tabelle,))

    def sql_ausfuehren(self, text: str, max_zeilen: int = 2000) -> list:
        """Führt einen oder mehrere SQL-Befehle aus.

        Ergebnis: Liste mit einem Eintrag je Befehl: {"befehl", "spalten", "zeilen", "betroffen", "mehr"}.
        """
        ergebnisse = []
        for befehl in sql_aufteilen(text):
            with self._cursor() as cur:
                cur.execute(befehl)
                spalten = [d[0] for d in cur.description] if cur.description else []
                zeilen = list(cur.fetchmany(max_zeilen + 1)) if spalten else []
                mehr = len(zeilen) > max_zeilen
                if mehr:
                    zeilen = zeilen[:max_zeilen]
                    cur.fetchall()
                ergebnisse.append({"befehl": befehl, "spalten": spalten, "zeilen": zeilen,
                                   "betroffen": cur.rowcount, "mehr": mehr})
        return ergebnisse
