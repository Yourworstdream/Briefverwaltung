"""Tests für Datum, Beträge und IBAN (ohne Datenbank)."""
import datetime as dt
import unittest
from decimal import Decimal

import gemeinsam  # noqa: F401  (setzt den Suchpfad)
from briefe_app import hilfen
from briefe_app.hilfen import Eingabefehler

HEUTE = dt.date(2026, 10, 8)


class DatumTest(unittest.TestCase):
    def test_schreibweisen(self):
        faelle = {
            "08.10.2026": dt.date(2026, 10, 8), "8.10.26": dt.date(2026, 10, 8), "8.10.": dt.date(2026, 10, 8),
            "8.10": dt.date(2026, 10, 8), "2026-10-08": dt.date(2026, 10, 8), "08102026": dt.date(2026, 10, 8),
            "heute": HEUTE, "morgen": dt.date(2026, 10, 9), "gestern": dt.date(2026, 10, 7),
            "+14": dt.date(2026, 10, 22), "+2w": dt.date(2026, 10, 22), "+1m": dt.date(2026, 11, 8),
            "  ": None, "": None,
        }
        for text, erwartet in faelle.items():
            with self.subTest(text=text):
                self.assertEqual(hilfen.datum_lesen(text, HEUTE), erwartet)

    def test_ungueltig(self):
        for text in ("31.02.2026", "13.13.2026", "irgendwann", "1.1.123"):
            with self.subTest(text=text), self.assertRaises(Eingabefehler):
                hilfen.datum_lesen(text, HEUTE)

    def test_monatsende(self):
        self.assertEqual(hilfen.monate_addieren(dt.date(2026, 1, 31), 1), dt.date(2026, 2, 28))
        self.assertEqual(hilfen.monate_addieren(dt.date(2028, 1, 31), 1), dt.date(2028, 2, 29))
        self.assertEqual(hilfen.monate_addieren(dt.date(2026, 11, 15), 3), dt.date(2027, 2, 15))

    def test_uhrzeit(self):
        self.assertEqual(hilfen.zeit_lesen("14:30"), dt.time(14, 30))
        self.assertEqual(hilfen.zeit_lesen("9.05 Uhr"), dt.time(9, 5))
        self.assertEqual(hilfen.zeit_lesen("1430"), dt.time(14, 30))
        self.assertEqual(hilfen.zeit_lesen("8"), dt.time(8, 0))
        self.assertIsNone(hilfen.zeit_lesen(""))
        with self.assertRaises(Eingabefehler):
            hilfen.zeit_lesen("25:00")

    def test_texte(self):
        self.assertEqual(hilfen.datum_text(dt.date(2026, 1, 2)), "02.01.2026")
        self.assertEqual(hilfen.datum_text(dt.datetime(2026, 1, 2, 9, 5)), "02.01.2026 09:05")
        self.assertEqual(hilfen.datum_text(None), "")
        self.assertEqual(hilfen.frist_text(dt.date(2026, 10, 11), HEUTE), "in 3 Tagen")
        self.assertEqual(hilfen.frist_text(HEUTE, HEUTE), "heute fällig")
        self.assertEqual(hilfen.frist_text(dt.date(2026, 10, 6), HEUTE), "seit 2 Tagen überfällig")


class BetragTest(unittest.TestCase):
    def test_lesen(self):
        faelle = {"1.234,56 €": "1234.56", "12,5": "12.50", "1234.56": "1234.56", "1.500": "1500.00",
                  "-30": "-30.00", "49,90 EUR": "49.90", "1.234.567": "1234567.00"}
        for text, erwartet in faelle.items():
            with self.subTest(text=text):
                self.assertEqual(hilfen.betrag_lesen(text), Decimal(erwartet))
        self.assertIsNone(hilfen.betrag_lesen(""))
        for text in ("zwölf", "1,2,3"):
            with self.subTest(text=text), self.assertRaises(Eingabefehler):
                hilfen.betrag_lesen(text)

    def test_text(self):
        self.assertEqual(hilfen.betrag_text(Decimal("1234.5")), "1.234,50 €")
        self.assertEqual(hilfen.betrag_text(Decimal("-3")), "-3,00 €")
        self.assertEqual(hilfen.betrag_text(Decimal("7"), mit_zeichen=False), "7,00")
        self.assertEqual(hilfen.betrag_text(None), "")


class IbanTest(unittest.TestCase):
    def test_gueltig(self):
        self.assertEqual(hilfen.iban_pruefen("de89 3704 0044 0532 0130 00"), "DE89370400440532013000")
        self.assertEqual(hilfen.iban_pruefen("AT61 1904 3002 3457 3201"), "AT611904300234573201")
        self.assertEqual(hilfen.iban_formatieren("DE89370400440532013000"), "DE89 3704 0044 0532 0130 00")

    def test_ungueltig(self):
        for text in ("DE88 3704 0044 0532 0130 00",      # falsche Prüfziffer
                     "DE89 3704 0044 0532 0130 0",       # zu kurz
                     "1234", ""):
            with self.subTest(text=text), self.assertRaises(Eingabefehler):
                hilfen.iban_pruefen(text)

    def test_bic(self):
        self.assertEqual(hilfen.bic_pruefen("cobadeffxxx"), "COBADEFFXXX")
        self.assertEqual(hilfen.bic_pruefen("MALADE51"), "MALADE51")
        self.assertEqual(hilfen.bic_pruefen(""), "")
        with self.assertRaises(Eingabefehler):
            hilfen.bic_pruefen("ABC")


class SonstigesTest(unittest.TestCase):
    def test_anzahl_und_namen(self):
        self.assertEqual(hilfen.anzahl(1, "Foto", "Fotos"), "1 Foto")
        self.assertEqual(hilfen.anzahl(0, "Foto", "Fotos"), "0 Fotos")
        self.assertEqual(hilfen.person_name({"anrede": "Frau", "titel": "Dr.", "nachname": "Krämer",
                                             "funktion": "Kundenservice"}), "Frau Dr. Krämer (Kundenservice)")
        self.assertEqual(hilfen.kurz("a " * 50, 10), "a a a a a…")

    def test_jede_art_hat_ein_zeichen(self):
        for art in hilfen.AKTIVITAET_ARTEN:
            self.assertTrue(hilfen.aktivitaet_zeichen(art))


if __name__ == "__main__":
    unittest.main()
