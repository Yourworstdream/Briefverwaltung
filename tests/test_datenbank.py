"""Tests für die Datenbankschicht."""
import datetime as dt
import unittest
from decimal import Decimal

import gemeinsam
from briefe_app.datenbank import ist_lesend, sql_aufteilen
from briefe_app.hilfen import Eingabefehler


class SqlTextTest(unittest.TestCase):
    def test_aufteilen(self):
        text = """-- Kommentar; mit Semikolon
        SELECT 'a;b' AS x;  /* auch; hier */ SELECT "c;d", `e;f` FROM t # Ende;
        ;
        INSERT INTO t VALUES ('O''Brien; ok', 'Back\\\\slash;')"""
        self.assertEqual(sql_aufteilen(text), [
            "SELECT 'a;b' AS x",
            'SELECT "c;d", `e;f` FROM t',
            "INSERT INTO t VALUES ('O''Brien; ok', 'Back\\\\slash;')",
        ])

    def test_schema_laesst_sich_aufteilen(self):
        from briefe_app.datenbank import SCHEMA
        befehle = sql_aufteilen(SCHEMA.read_text(encoding="utf-8"))
        self.assertGreater(len(befehle), 10)
        self.assertTrue(all(b.split()[0].upper() in ("CREATE", "INSERT") for b in befehle))

    def test_lesend(self):
        for befehl in ("SELECT 1", "  show tables", "DESCRIBE brief", "WITH x AS (SELECT 1) SELECT * FROM x",
                       "(SELECT 1)"):
            self.assertTrue(ist_lesend(befehl), befehl)
        for befehl in ("UPDATE brief SET status='neu'", "DELETE FROM brief", "DROP TABLE x", ""):
            self.assertFalse(ist_lesend(befehl), befehl)


@gemeinsam.braucht_mysql
class DatenbankTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = gemeinsam.test_datenbank("db")

    @classmethod
    def tearDownClass(cls):
        gemeinsam.entfernen(cls.db)

    def setUp(self):
        for tabelle in ("aktivitaet", "brief", "anlass", "absender"):
            self.db.ausfuehren(f"DELETE FROM {tabelle}")

    def foto(self, brief_id, nr):
        inhalt = gemeinsam.png(farbe=(brief_id % 250, nr, 200))
        with self.db.transaktion():
            return self.db.foto_anlegen(brief_id, inhalt, f"seite{nr}.png", f"{brief_id:032d}{nr:032d}")

    def test_schema_mehrfach_anlegen(self):
        self.db.schema_anlegen()
        namen = {t["name"] for t in self.db.tabellen()}
        self.assertTrue({"brief", "foto", "foto_teil", "absender", "ansprechpartner", "bankverbindung", "anlass",
                         "aktivitaet", "v_briefe", "v_aktivitaeten"} <= namen)

    def test_absender_und_kontakte(self):
        a = self.db.absender_id_fuer("Stadtwerke")
        self.assertEqual(self.db.absender_id_fuer("  Stadtwerke "), a)
        self.assertIsNone(self.db.absender_id_fuer(""))
        with self.assertRaises(Eingabefehler):
            self.db.absender_speichern({"name": "STADTWERKE"})        # Groß-/Kleinschreibung egal
        with self.assertRaises(Eingabefehler):
            self.db.absender_speichern({"name": " "})
        with self.assertRaises(Eingabefehler):
            self.db.ansprechpartner_speichern({"absender_id": a, "telefon": "123"})
        ap = self.db.ansprechpartner_speichern({"absender_id": a, "anrede": "Frau", "nachname": "O'Brien",
                                                "telefon": "0631 1", "email": ""})
        self.assertIsNone(self.db.ansprechpartner_holen(ap)["email"], "leere Felder werden NULL")
        with self.assertRaises(Eingabefehler):
            self.db.bankverbindung_speichern({"absender_id": a, "iban": "DE00 1234"})
        bank = self.db.bankverbindung_speichern({"absender_id": a, "iban": "de89 3704 0044 0532 0130 00",
                                                 "bic": "cobadeffxxx"})
        gespeichert = self.db.bankverbindung_holen(bank)
        self.assertEqual((gespeichert["iban"], gespeichert["bic"]), ("DE89370400440532013000", "COBADEFFXXX"))
        with self.assertRaises(Eingabefehler):
            self.db.bankverbindung_speichern({"absender_id": a, "iban": "DE89370400440532013000"})

        brief = self.db.brief_neu("Rechnung", absender_id=a, ansprechpartner_id=ap, bankverbindung_id=bank)
        self.db.absender_loeschen(a)
        b = self.db.brief_holen(brief)
        self.assertEqual((b["absender_id"], b["ansprechpartner_id"], b["bankverbindung_id"]), (None, None, None))
        self.assertEqual(self.db.ansprechpartner_liste(a), [])

    def test_brief_pruefungen_und_filter(self):
        with self.assertRaises(Eingabefehler):
            self.db.brief_speichern({"betreff": "x", "dringlichkeit": 5})
        with self.assertRaises(Eingabefehler):
            self.db.brief_speichern({"betreff": "x", "status": "unbekannt"})
        heute = dt.date.today()
        alt = self.db.brief_neu("Mahnung 100% sicher", frist=heute - dt.timedelta(days=1), dringlichkeit=4)
        bald = self.db.brief_neu("Bescheid", frist=heute + dt.timedelta(days=3))
        fertig = self.db.brief_neu("Erledigt", status="erledigt", frist=heute - dt.timedelta(days=9))
        ids = lambda **kw: [b["id"] for b in self.db.briefe(**kw)]  # noqa: E731
        self.assertEqual(ids(), [alt, bald, fertig])
        self.assertEqual(ids(status="offen"), [alt, bald])
        self.assertEqual(ids(status="ueberfaellig"), [alt])
        self.assertEqual(ids(status="fristen"), [bald])
        self.assertEqual(ids(status="dringend"), [alt])
        self.assertEqual(ids(status="erledigt"), [fertig])
        self.assertEqual(ids(suche="100%"), [alt])
        self.assertEqual(ids(suche="%"), [alt], "% wird wörtlich gesucht")
        k = self.db.kennzahlen()
        self.assertEqual((k["offen"], k["ueberfaellig"], k["fristen"], k["dringend"]), (2, 1, 1, 1))

    def test_gruppieren(self):
        stadtwerke = self.db.absender_id_fuer("Stadtwerke")
        bank = self.db.absender_id_fuer("Bank")
        ap = self.db.ansprechpartner_speichern({"absender_id": stadtwerke, "nachname": "Krämer"})
        b1 = self.db.brief_neu("a", absender_id=stadtwerke, ansprechpartner_id=ap)
        b2 = self.db.brief_neu("b")
        anlass = self.db.anlass_id_fuer("Umzug")
        self.db.briefe_zuordnen([b1, b2], absender_id=bank, anlass_id=anlass, dringlichkeit=3)
        for b in (self.db.brief_holen(b1), self.db.brief_holen(b2)):
            self.assertEqual((b["absender"], b["anlass"], b["dringlichkeit"]), ("Bank", "Umzug", 3))
        self.assertIsNone(self.db.brief_holen(b1)["ansprechpartner_id"], "Ansprechpartner passte nicht mehr")
        self.db.briefe_zuordnen([b2], anlass_id=None)
        self.assertIsNone(self.db.brief_holen(b2)["anlass_id"])
        self.assertEqual(self.db.brief_holen(b1)["anlass_id"], anlass)
        self.assertEqual([a["briefe"] for a in self.db.anlaesse()], [1])

    def test_zusammenfassen_und_trennen(self):
        ziel = self.db.brief_neu("", dringlichkeit=2)
        anderer = self.db.brief_neu("Rechnung", dringlichkeit=4, betrag=Decimal("12.30"), notizen="Seite 2")
        self.foto(ziel, 1)
        self.foto(anderer, 1)
        self.foto(anderer, 2)
        self.db.aktivitaet_speichern({"art": "Telefonat", "brief_id": anderer})
        self.db.briefe_zusammenfassen(ziel, [anderer, ziel])
        self.assertIsNone(self.db.brief_holen(anderer))
        b = self.db.brief_holen(ziel)
        self.assertEqual((b["betreff"], b["dringlichkeit"], b["betrag"], b["fotos"], b["notizen"]),
                         ("Rechnung", 4, Decimal("12.30"), 3, "Seite 2"))
        self.assertEqual([f["seite"] for f in self.db.fotos(ziel)], [1, 2, 3])
        self.assertEqual(len(self.db.aktivitaeten(brief_id=ziel)), 1)

        fotos = self.db.fotos(ziel)
        self.db.foto_seite_verschieben(fotos[2]["id"], -1)
        self.assertEqual([f["id"] for f in self.db.fotos(ziel)], [fotos[0]["id"], fotos[2]["id"], fotos[1]["id"]])
        neu = self.db.foto_als_neuer_brief(fotos[0]["id"])
        self.assertEqual([f["seite"] for f in self.db.fotos(ziel)], [1, 2])
        self.assertEqual(self.db.brief_holen(neu)["fotos"], 1)
        self.db.foto_loeschen(self.db.fotos(ziel)[0]["id"])
        self.assertEqual([f["seite"] for f in self.db.fotos(ziel)], [1])
        self.db.foto_drehen(fotos[1]["id"], -90)
        self.assertEqual(self.db.foto_holen(fotos[1]["id"])["drehung"], 270)
        self.db.brief_loeschen(ziel)
        self.assertIsNone(self.db.foto_holen(fotos[1]["id"]), "Fotos werden mit dem Brief gelöscht")

    def test_aktivitaeten_und_zahlungen(self):
        a = self.db.absender_id_fuer("Vermieter")
        anlass = self.db.anlass_id_fuer("Nebenkosten")
        brief = self.db.brief_neu("Abrechnung", absender_id=a, anlass_id=anlass, betrag=Decimal("100"))
        zahlung = self.db.aktivitaet_speichern({"art": "Zahlung", "brief_id": brief, "betrag": Decimal("60"),
                                                "richtung": "ausgehend"})
        self.db.aktivitaet_speichern({"art": "Treffen", "absender_id": a, "ort": "Büro",
                                      "zeitpunkt": dt.datetime(2026, 1, 2, 10, 0),
                                      "wiedervorlage": dt.date.today() + dt.timedelta(days=2)})
        gespeichert = self.db.aktivitaet_holen(zahlung)
        self.assertEqual((gespeichert["absender"], gespeichert["anlass"]), ("Vermieter", "Nebenkosten"),
                         "Absender und Anlass kommen vom Brief")
        self.assertEqual(self.db.brief_holen(brief)["bezahlt"], Decimal("60.00"))
        self.assertEqual(self.db.kennzahlen()["offener_betrag"], Decimal("40.00"))
        self.assertEqual(len(self.db.aktivitaeten(absender_id=a)), 2)
        self.assertEqual(len(self.db.aktivitaeten(anlass_id=anlass)), 1)
        self.assertEqual([x["art"] for x in self.db.aktivitaeten(art="Treffen")], ["Treffen"])
        self.assertEqual(len(self.db.wiedervorlagen()), 1)
        with self.assertRaises(Eingabefehler):
            self.db.aktivitaet_speichern({"art": "Telefonat", "richtung": "seitwärts"})

    def test_sql_fenster(self):
        self.db.brief_neu("Test")
        ergebnisse = self.db.sql_ausfuehren("SELECT betreff FROM brief; SELECT COUNT(*) AS n FROM brief;"
                                            "UPDATE brief SET dringlichkeit = 3")
        self.assertEqual(ergebnisse[0]["zeilen"], [("Test",)])
        self.assertEqual(ergebnisse[1]["spalten"], ["n"])
        self.assertEqual(ergebnisse[2]["betroffen"], 1)
        self.assertEqual(self.db.sql_ausfuehren("SELECT 1 UNION SELECT 2", max_zeilen=1)[0]["mehr"], True)
        self.assertIn("betreff", [s["name"] for s in self.db.spalten("brief")])

    def test_beispielabfragen_laufen(self):
        from briefe_app.datenbank import beispiele_laden
        beispiele = beispiele_laden()
        self.assertGreaterEqual(len(beispiele), 5)
        for name, sql in beispiele:
            with self.subTest(name=name):
                self.assertTrue(all(ist_lesend(b) for b in sql_aufteilen(sql)), "Beispiele ändern nichts")
                self.db.sql_ausfuehren(sql)

    def test_transaktion_rollt_zurueck(self):
        with self.assertRaises(RuntimeError):
            with self.db.transaktion():
                self.db.brief_neu("wird zurückgenommen")
                raise RuntimeError("Absturz")
        self.assertEqual(self.db.briefe(), [])

    def test_zweite_verbindung(self):
        kopie = self.db.kopie()
        try:
            kopie.brief_neu("aus der Kopie")
            self.assertEqual([b["betreff"] for b in self.db.briefe()], ["aus der Kopie"])
        finally:
            kopie.schliessen()


if __name__ == "__main__":
    unittest.main()
