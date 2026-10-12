"""Tests für die USB-Erkennung – mit erfundenen Laufwerken, ganz ohne echten Stick."""
import os
import tempfile
import time
import unittest
from pathlib import Path

import gemeinsam  # noqa: F401
from briefe_app import usb
from briefe_app.importer import briefe_ordner_finden
from briefe_app.usb import Laufwerk, UsbWaechter


class LinuxTest(unittest.TestCase):
    def test_einhaengepunkte_lesen(self):
        inhalt = ("/dev/sdb1 /media/max/MEIN\\040STICK vfat rw 0 0\n"
                  "proc /proc proc rw 0 0\n")
        self.assertEqual(list(usb.linux_einhaengepunkte(inhalt)),
                         [("/dev/sdb1", "/media/max/MEIN STICK", "vfat"), ("proc", "/proc", "proc")])

    def test_nur_passende_laufwerke(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".mounts") as datei:
            datei.write("/dev/nvme0n1p2 / ext4 rw 0 0\n"
                        "proc /proc proc rw 0 0\n"
                        "tmpfs /run/media/max tmpfs rw 0 0\n"
                        "/dev/sdx1 /media/max/STICK vfat rw 0 0\n"
                        "/dev/sdy1 /run/media/max/KARTE exfat rw 0 0\n"
                        "/dev/nvme0n1p3 /home ext4 rw 0 0\n")
        try:
            pfade = [lw.pfad for lw in usb._linux(datei.name)]
        finally:
            os.unlink(datei.name)
        self.assertEqual(pfade, ["/media/max/STICK", "/run/media/max/KARTE"])


class OrdnerTest(unittest.TestCase):
    def test_gross_kleinschreibung_egal(self):
        with tempfile.TemporaryDirectory() as wurzel:
            (Path(wurzel) / "BRIEFE").mkdir()
            self.assertEqual(briefe_ordner_finden(wurzel, "Briefe"), Path(wurzel) / "BRIEFE")
            self.assertIsNone(briefe_ordner_finden(wurzel, "Fotos"))
            self.assertIsNone(briefe_ordner_finden(os.path.join(wurzel, "gibt-es-nicht")))


class WaechterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.wurzel = Path(self.tmp.name)
        self.laufwerke = {}
        self.funde = []

    def tearDown(self):
        self.tmp.cleanup()

    def stick(self, name, wechselbar=True, mit_ordner=True):
        pfad = self.wurzel / name
        pfad.mkdir(exist_ok=True)
        if mit_ordner:
            (pfad / "Briefe").mkdir(exist_ok=True)
        self.laufwerke[str(pfad)] = Laufwerk(str(pfad), name, wechselbar)
        return pfad

    def waechter(self):
        return UsbWaechter(lambda lw, ordner: self.funde.append((lw.name, ordner.name)),
                           quelle=lambda: list(self.laufwerke.values()))

    def test_ablauf(self):
        self.stick("STICK_SCHON_DA")
        self.stick("FESTPLATTE", wechselbar=False)
        w = self.waechter()
        w.pruefen()
        # Ein beim Start steckender Stick zählt, eine feste Platte nicht
        self.assertEqual(self.funde, [("STICK_SCHON_DA", "Briefe")])
        w.pruefen()
        self.assertEqual(len(self.funde), 1, "derselbe Stick darf nicht ständig neu gemeldet werden")

        self.stick("NEU", wechselbar=False)          # auch „feste“ Laufwerke, die später auftauchen
        w.pruefen()
        self.assertEqual(self.funde[-1], ("NEU", "Briefe"))

        del self.laufwerke[str(self.wurzel / "STICK_SCHON_DA")]   # abziehen …
        w.pruefen()
        self.stick("STICK_SCHON_DA")                              # … und wieder einstecken
        w.pruefen()
        self.assertEqual(self.funde[-1], ("STICK_SCHON_DA", "Briefe"))
        self.assertEqual(len(self.funde), 3)

        w.pruefen(erzwingen=True)                   # „Jetzt prüfen“ findet alle mit Ordner
        self.assertEqual(sorted(f[0] for f in self.funde[3:]), ["FESTPLATTE", "NEU", "STICK_SCHON_DA"])

    def test_ordner_erscheint_kurz_nach_dem_einstecken(self):
        w = self.waechter()
        w.pruefen()
        pfad = self.stick("LANGSAM", mit_ordner=False)
        w.pruefen()
        self.assertEqual(self.funde, [])
        (pfad / "briefe").mkdir()
        w.pruefen()
        self.assertEqual(self.funde, [("LANGSAM", "briefe")])

    def test_ohne_ordner_wird_aufgegeben(self):
        w = self.waechter()
        w.pruefen()
        pfad = self.stick("OHNE", mit_ordner=False)
        for _ in range(usb.VERSUCHE + 1):
            w.pruefen()
        (pfad / "Briefe").mkdir()
        w.pruefen()
        self.assertEqual(self.funde, [], "nach einigen Versuchen wird der Stick nicht mehr durchsucht")

    def test_zusatzordner(self):
        ordner = self.wurzel / "netz"
        (ordner / "Briefe").mkdir(parents=True)
        w = UsbWaechter(lambda lw, o: self.funde.append(lw.pfad), quelle=lambda: [], zusatz_ordner=[str(ordner)])
        w.pruefen()
        self.assertEqual(self.funde, [str(ordner)])

    def test_thread_starten_und_anhalten(self):
        self.stick("THREAD")
        w = UsbWaechter(lambda lw, o: self.funde.append(lw.name), intervall=0.5,
                        quelle=lambda: list(self.laufwerke.values()))
        w.starten()
        try:
            for _ in range(40):
                if self.funde:
                    break
                time.sleep(0.05)
            self.assertTrue(w.laeuft)
            self.assertEqual(self.funde, ["THREAD"])
        finally:
            w.anhalten()
        self.assertFalse(w.laeuft)
        w.starten()                    # gleich wieder starten muss gehen
        self.assertTrue(w.laeuft)
        w.anhalten()

    def test_echte_laufwerksliste_stuerzt_nicht_ab(self):
        self.assertIsInstance(usb.laufwerke(), list)


if __name__ == "__main__":
    unittest.main()
