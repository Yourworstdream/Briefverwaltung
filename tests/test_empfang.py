"""Tests für den Handy-Empfang: so, wie die Android-App Briefe schickt."""
import datetime as dt
import json
import unittest
import urllib.error
import urllib.request
import uuid
from decimal import Decimal

import gemeinsam
from briefe_app import empfang
from briefe_app.hilfen import Eingabefehler


def multipart(daten: dict, seiten, grenze="----briefe1234") -> tuple:
    """Baut den Body wie die App: Teil „daten“ (JSON) und Teile „seite1“, „seite2“ … (Fotos)."""
    teile = [(f'--{grenze}\r\nContent-Disposition: form-data; name="daten"\r\n'
              'Content-Type: application/json; charset=utf-8\r\n\r\n').encode() + json.dumps(daten).encode() + b"\r\n"]
    for nr, inhalt in enumerate(seiten, start=1):
        teile.append((f'--{grenze}\r\nContent-Disposition: form-data; name="seite{nr}"; filename="seite{nr}.jpg"\r\n'
                      'Content-Type: image/jpeg\r\n\r\n').encode() + inhalt + b"\r\n")
    teile.append(f"--{grenze}--\r\n".encode())
    return b"".join(teile), f"multipart/form-data; boundary={grenze}"


class OhneDatenbankTest(unittest.TestCase):
    def test_token(self):
        token = empfang.token_erzeugen()
        self.assertRegex(token, r"^[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$")
        self.assertNotEqual(token, empfang.token_erzeugen())
        self.assertEqual(empfang.token_normalisieren(" k7px m3qd-9twb "), "K7PX-M3QD-9TWB")

    def test_multipart_mit_binaerdaten(self):
        foto = b"\xff\xd8\r\n--keine-grenze\r\n\x00\r\n\r\n\xff\xd9"      # Bytes, die wie Trenner aussehen
        body, typ = multipart({"betreff": "Größe ü"}, [foto, b"zweite"])
        teile = empfang.multipart_lesen(body, typ)
        self.assertEqual([t.name for t in teile], ["daten", "seite1", "seite2"])
        self.assertEqual(json.loads(teile[0].daten), {"betreff": "Größe ü"})
        self.assertEqual(teile[1].daten, foto)
        self.assertEqual((teile[1].dateiname, teile[1].typ), ("seite1.jpg", "image/jpeg"))
        with self.assertRaises(Eingabefehler):
            empfang.multipart_lesen(body, "application/json")

    def test_qr_inhalt(self):
        daten = json.loads(empfang.qr_text("ABCD-EFGH-JKLM", 8765, ["192.168.178.23"]))
        self.assertEqual(daten["app"], "briefverwaltung")
        self.assertEqual(daten["token"], "ABCD-EFGH-JKLM")
        self.assertEqual(daten["adressen"], ["http://192.168.178.23:8765"])

    def test_adressen_sind_privat(self):
        for ip in empfang.lokale_adressen():
            self.assertTrue(empfang._privat(ip), ip)
        self.assertTrue(empfang._privat("192.168.1.5"))
        self.assertFalse(empfang._privat("127.0.0.1"))
        self.assertFalse(empfang._privat("8.8.8.8"))

    def test_person(self):
        self.assertEqual(empfang._person("Frau Dr. Sabine Krämer"),
                         {"anrede": "Frau", "titel": "Dr.", "vorname": "Sabine", "nachname": "Krämer"})
        self.assertEqual(empfang._person("Herr Becker")["nachname"], "Becker")


@gemeinsam.braucht_mysql
class EmpfangTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = gemeinsam.test_datenbank("empfang")
        cls.angekommen = []
        cls.empfang = empfang.Empfang("TEST-CODE-1234", cls.db.kopie, port=0, adresse="127.0.0.1",
                                      bei_empfang=cls.angekommen.append)
        assert cls.empfang.starten(), cls.empfang.fehler
        cls.url = f"http://127.0.0.1:{cls.empfang.port}"

    @classmethod
    def tearDownClass(cls):
        cls.empfang.anhalten()
        gemeinsam.entfernen(cls.db)

    def setUp(self):
        for tabelle in ("handy_upload", "brief", "absender", "anlass"):
            self.db.ausfuehren(f"DELETE FROM {tabelle}")

    def senden(self, daten, seiten, token="test-code-1234"):
        body, typ = multipart(daten, seiten)
        anfrage = urllib.request.Request(self.url + "/api/briefe", data=body, method="POST",
                                         headers={"Content-Type": typ, "X-Briefe-Token": token})
        try:
            with urllib.request.urlopen(anfrage, timeout=10) as antwort:
                return antwort.status, json.loads(antwort.read())
        except urllib.error.HTTPError as fehler:
            return fehler.code, json.loads(fehler.read())

    def test_info_und_zugangscode(self):
        anfrage = urllib.request.Request(self.url + "/api/info", headers={"X-Briefe-Token": "TEST-CODE-1234"})
        with urllib.request.urlopen(anfrage, timeout=5) as antwort:
            self.assertEqual(json.loads(antwort.read())["app"], "briefverwaltung")
        with self.assertRaises(urllib.error.HTTPError) as falsch:
            urllib.request.urlopen(urllib.request.Request(self.url + "/api/info",
                                                          headers={"X-Briefe-Token": "FALSCH"}), timeout=5)
        self.assertEqual(falsch.exception.code, 401)
        code, antwort = self.senden({"betreff": "x"}, [gemeinsam.png()], token="falsch")
        self.assertEqual(code, 401)
        self.assertEqual(self.db.briefe(), [])
        with urllib.request.urlopen(self.url + "/", timeout=5) as antwort:
            self.assertIn("Handy-Empfang läuft", antwort.read().decode())

    def test_brief_mit_allen_angaben(self):
        kennung = str(uuid.uuid4())
        daten = {
            "uuid": kennung, "geraet": "Pixel 7", "art": "Rechnung", "betreff": "Jahresabrechnung Strom 2025",
            "absender": "Stadtwerke Kaiserslautern", "absender_strasse": "Bismarckstraße 14",
            "absender_plz": "67655", "absender_ort": "Kaiserslautern", "absender_telefon": "0631 8001-0",
            "absender_email": "service@swk-kl.de", "kundennummer": "KD-4471120",
            "ansprechpartner": "Frau Sabine Krämer", "ansprechpartner_telefon": "0631 8001-2214",
            "iban": "DE89 3704 0044 0532 0130 00", "bic": "COBADEFFXXX",
            "briefdatum": "2026-10-01", "frist": "2026-10-20", "betrag": "184.32", "aktenzeichen": "RE-2026-118422",
            "dringlichkeit": 3, "anlass": "Strom 2026", "notizen": "Ratenzahlung möglich?",
            "volltext": "Stadtwerke Kaiserslautern\nJahresabrechnung Strom 2025\nNachzahlung 184,32 €",
        }
        code, antwort = self.senden(daten, [gemeinsam.png(farbe=(1, 2, 3)), gemeinsam.png(farbe=(4, 5, 6))])
        self.assertEqual(code, 200, antwort)
        self.assertTrue(antwort["neu"])
        self.assertEqual(antwort["seiten"], 2)
        b = self.db.brief_holen(antwort["brief_id"])
        self.assertEqual((b["betreff"], b["absender"], b["anlass"], b["frist"], b["briefdatum"], b["betrag"],
                          b["aktenzeichen"], b["dringlichkeit"], b["status"], b["fotos"]),
                         ("Jahresabrechnung Strom 2025", "Stadtwerke Kaiserslautern", "Strom 2026",
                          dt.date(2026, 10, 20), dt.date(2026, 10, 1), Decimal("184.32"), "RE-2026-118422", 3, "neu", 2))
        absender = self.db.absender_holen(b["absender_id"])
        self.assertEqual((absender["plz"], absender["telefon"], absender["kundennummer"]),
                         ("67655", "0631 8001-0", "KD-4471120"))
        bank = self.db.bankverbindung_holen(b["bankverbindung_id"])
        self.assertEqual((bank["iban"], bank["bic"]), ("DE89370400440532013000", "COBADEFFXXX"))
        ap = self.db.ansprechpartner_holen(b["ansprechpartner_id"])
        self.assertEqual((ap["anrede"], ap["vorname"], ap["nachname"], ap["telefon"]),
                         ("Frau", "Sabine", "Krämer", "0631 8001-2214"))
        self.assertIn("Nachzahlung", self.db.volltext(b["id"]))
        self.assertEqual([x["id"] for x in self.db.briefe(suche="Nachzahlung")], [b["id"]],
                         "der erkannte Text ist durchsuchbar")
        self.assertEqual(self.angekommen[-1]["brief_id"], b["id"])

        # Das Handy schickt nach einem Verbindungsabbruch noch einmal: kein zweiter Brief
        code, antwort = self.senden(daten, [gemeinsam.png(farbe=(1, 2, 3)), gemeinsam.png(farbe=(4, 5, 6))])
        self.assertEqual((code, antwort["neu"], antwort["brief_id"]), (200, False, b["id"]))
        # Zweiter Brief desselben Absenders: Bankverbindung und Ansprechpartner werden wiederverwendet
        daten2 = dict(daten, uuid=str(uuid.uuid4()), betreff="Abschlagsänderung")
        code, antwort = self.senden(daten2, [gemeinsam.png(farbe=(7, 8, 9))])
        b2 = self.db.brief_holen(antwort["brief_id"])
        self.assertEqual((b2["bankverbindung_id"], b2["ansprechpartner_id"]),
                         (b["bankverbindung_id"], b["ansprechpartner_id"]))
        self.assertEqual(len(self.db.bankverbindungen(b["absender_id"])), 1)

    def test_wenig_angaben_und_ungueltige_werte(self):
        daten = {"uuid": str(uuid.uuid4()), "art": "Brief", "absender": "", "iban": "DE00 kaputt",
                 "frist": "irgendwann", "betrag": "viel", "dringlichkeit": 9}
        code, antwort = self.senden(daten, [gemeinsam.png(farbe=(10, 20, 30))])
        self.assertEqual(code, 200, antwort)
        b = self.db.brief_holen(antwort["brief_id"])
        self.assertEqual((b["betreff"], b["absender_id"], b["frist"], b["betrag"], b["dringlichkeit"]),
                         ("Brief", None, None, None, 4))

    def test_fehlerfaelle(self):
        code, antwort = self.senden({"uuid": str(uuid.uuid4())}, [])
        self.assertEqual(code, 400)
        self.assertIn("keine Fotos", antwort["meldung"])
        foto = gemeinsam.png(farbe=(40, 50, 60))
        code, erstes = self.senden({"uuid": str(uuid.uuid4())}, [foto])
        code, antwort = self.senden({"uuid": str(uuid.uuid4())}, [foto])        # gleiches Foto, neue Sendung
        self.assertEqual((code, antwort["neu"], antwort["brief_id"]), (200, False, erstes["brief_id"]))
        self.assertEqual(len(self.db.briefe()), 1)


@gemeinsam.braucht_mysql
class MigrationTest(unittest.TestCase):
    def test_alte_datenbank_bekommt_neue_spalte(self):
        db = gemeinsam.test_datenbank("migration")
        try:
            db.ausfuehren("ALTER TABLE brief DROP COLUMN volltext")       # so sah Version 1 aus
            db.schema_anlegen()
            self.assertIn("volltext", [s["name"] for s in db.spalten("brief")])
            db.brief_neu("Test", volltext="Hallo")
            self.assertEqual(db.briefe(suche="Hallo")[0]["betreff"], "Test")
        finally:
            gemeinsam.entfernen(db)


if __name__ == "__main__":
    unittest.main()
