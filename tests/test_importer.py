"""Tests für den Import der Fotos."""
import tempfile
import unittest
from pathlib import Path

import gemeinsam
from briefe_app import importer


def stick_anlegen(wurzel: Path) -> Path:
    """Baut einen Ordner wie auf dem USB-Stick nach."""
    briefe = wurzel / "Briefe"
    (briefe / "Stadtwerke Rechnung").mkdir(parents=True)
    (briefe / "IMG_20261008_101010.jpg").write_bytes(gemeinsam.png(farbe=(1, 2, 3)))
    (briefe / "Finanzamt_Bescheid.png").write_bytes(gemeinsam.png(farbe=(4, 5, 6)))
    (briefe / "notiz.txt").write_text("kein Foto")
    (briefe / ".versteckt.jpg").write_bytes(gemeinsam.png(farbe=(7, 8, 9)))
    (briefe / "Thumbs.db").write_bytes(b"x")
    for nr in (10, 2, 1):
        (briefe / "Stadtwerke Rechnung" / f"Seite {nr}.png").write_bytes(gemeinsam.png(farbe=(nr, nr, nr)))
    return briefe


class SammelnTest(unittest.TestCase):
    def test_gruppen(self):
        with tempfile.TemporaryDirectory() as tmp:
            gruppen = importer.gruppen_sammeln(stick_anlegen(Path(tmp)))
        self.assertEqual([(g.betreff, [p.name for p in g.dateien], g.unterordner) for g in gruppen], [
            ("Finanzamt Bescheid", ["Finanzamt_Bescheid.png"], False),
            ("", ["IMG_20261008_101010.jpg"], False),
            ("Stadtwerke Rechnung", ["Seite 1.png", "Seite 2.png", "Seite 10.png"], True),
        ])

    def test_betreff_aus_dateiname(self):
        self.assertEqual(importer.betreff_aus_name("Mahnung_Telekom.jpg"), "Mahnung Telekom")
        for name in ("IMG_20261008_101010.jpg", "PXL_20261008.jpg", "DSC01234.JPG", "20261008_101010.jpg",
                     "WhatsApp Image 2026-10-08 at 10.10.jpeg", "Scan 3.pdf"):
            with self.subTest(name=name):
                self.assertEqual(importer.betreff_aus_name(name), "")

    def test_ergebnistext(self):
        e = importer.Ergebnis("Stick", neue_briefe=[1], neue_fotos=1, doppelt=2)
        self.assertEqual(e.text(), "1 neuer Brief importiert (1 Foto), 2 schon vorhanden.")
        self.assertEqual(importer.Ergebnis("x").text(), "Keine neuen Fotos.")


@gemeinsam.braucht_mysql
class ImportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = gemeinsam.test_datenbank("import")

    @classmethod
    def tearDownClass(cls):
        gemeinsam.entfernen(cls.db)

    def setUp(self):
        self.db.ausfuehren("DELETE FROM brief")
        self.db.ausfuehren("DELETE FROM import_protokoll")

    def test_import_und_doppelte(self):
        with tempfile.TemporaryDirectory() as tmp:
            ordner = stick_anlegen(Path(tmp))
            schritte = []
            erg = importer.importieren(self.db, ordner, "Test-Stick", fortschritt=lambda *a: schritte.append(a))
            self.assertEqual((len(erg.neue_briefe), erg.neue_fotos, erg.doppelt, erg.fehler), (3, 5, 0, []))
            self.assertEqual(schritte[-1][:2], (5, 5))
            briefe = {b["betreff"]: b for b in self.db.briefe()}
            self.assertEqual(briefe["Stadtwerke Rechnung"]["fotos"], 3)
            self.assertTrue(all(b["status"] == "neu" and b["eingangsdatum"] for b in briefe.values()))
            seiten = self.db.fotos(briefe["Stadtwerke Rechnung"]["id"])
            self.assertEqual([(f["seite"], f["dateiname"]) for f in seiten],
                             [(1, "Seite 1.png"), (2, "Seite 2.png"), (3, "Seite 10.png")])
            self.assertEqual(self.db.foto_inhalt(seiten[0]["id"]), gemeinsam.png(farbe=(1, 1, 1)))

            # Stick noch einmal einstecken: nichts Neues
            erg = importer.importieren(self.db, ordner, "Test-Stick")
            self.assertEqual((erg.neue_briefe, erg.neue_fotos, erg.doppelt), ([], 0, 5))

            # Eine Seite kommt dazu → landet beim vorhandenen Brief
            (ordner / "Stadtwerke Rechnung" / "Seite 11.png").write_bytes(gemeinsam.png(farbe=(11, 11, 11)))
            erg = importer.importieren(self.db, ordner, "Test-Stick")
            self.assertEqual((erg.neue_briefe, erg.neue_fotos), ([], 1))
            self.assertEqual(self.db.brief_holen(briefe["Stadtwerke Rechnung"]["id"])["fotos"], 4)
        self.assertEqual(len(self.db.letzte_importe(10)), 3)

    def test_gleiches_foto_zweimal_auf_dem_stick(self):
        with tempfile.TemporaryDirectory() as tmp:
            ordner = Path(tmp)
            (ordner / "a.png").write_bytes(gemeinsam.png(farbe=(20, 20, 20)))
            (ordner / "b.png").write_bytes(gemeinsam.png(farbe=(20, 20, 20)))
            erg = importer.importieren(self.db, ordner)
        self.assertEqual((len(erg.neue_briefe), erg.doppelt), (1, 1))

    def test_grosse_fotos_in_stuecken(self):
        alt = self.db.teilgroesse
        self.db.teilgroesse = 1000
        try:
            inhalt = gemeinsam.png(200, 200, (30, 40, 50)) + bytes(range(256)) * 20
            with tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / "gross.png").write_bytes(inhalt)
                erg = importer.importieren(self.db, tmp)
            foto = self.db.fotos(erg.neue_briefe[0])[0]
            self.assertGreater(self.db.wert("SELECT COUNT(*) FROM foto_teil WHERE foto_id = %s", (foto["id"],)), 3)
            self.assertEqual(self.db.foto_inhalt(foto["id"]), inhalt)
        finally:
            self.db.teilgroesse = alt

    def test_dateien_zu_brief_hinzufuegen(self):
        brief_id = self.db.brief_neu("Handschriftlich")
        with tempfile.TemporaryDirectory() as tmp:
            pfade = []
            for nr in range(2):
                pfad = Path(tmp) / f"seite{nr}.png"
                pfad.write_bytes(gemeinsam.png(farbe=(90 + nr, 0, 0)))
                pfade.append(pfad)
            erg = importer.dateien_hinzufuegen(self.db, brief_id, pfade)
            self.assertEqual((erg.neue_fotos, erg.fehler), (2, []))
            erg = importer.dateien_hinzufuegen(self.db, brief_id, pfade[:1])
            self.assertEqual(erg.neue_fotos, 0)
            self.assertIn("schon bei Brief", erg.fehler[0])
        self.assertEqual([f["seite"] for f in self.db.fotos(brief_id)], [1, 2])


if __name__ == "__main__":
    unittest.main()
