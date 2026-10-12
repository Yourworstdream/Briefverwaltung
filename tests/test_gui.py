"""Rauchtest der Oberfläche: Fenster aufbauen, alle Reiter laden, Dialoge öffnen.

Braucht MySQL (BRIEFE_TEST_MYSQL) und einen Bildschirm – unter Linux ohne Bildschirm z. B. mit
`xvfb-run -a python -m unittest discover -s tests`.
"""
import os
import tempfile
import traceback
import unittest
from decimal import Decimal
from pathlib import Path

import gemeinsam

try:
    import tkinter as tk
    _root = tk.Tk()
    _root.destroy()
    BILDSCHIRM = True
except Exception:          # kein tkinter oder kein Bildschirm
    BILDSCHIRM = False


@gemeinsam.braucht_mysql
@unittest.skipUnless(BILDSCHIRM, "kein Bildschirm für tkinter")
class OberflaecheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["BRIEFVERWALTUNG_KONFIG"] = os.path.join(self.tmp.name, "einstellungen.json")
        from briefe_app import konfig
        from briefe_app.gui import stil
        from briefe_app.gui.app import App

        self.db = gemeinsam.test_datenbank("gui")
        host, port, benutzer, passwort = gemeinsam.zugang()
        self.konfig = konfig.laden()
        self.konfig["mysql"].update(host=host, port=port, benutzer=benutzer, passwort=passwort, datenbank=self.db.name)
        self.konfig["usb"].update(aktiv=True, intervall=0.5, zusatz_ordner=[os.path.join(self.tmp.name, "stick")])
        self.fehler = []
        self.root = tk.Tk()
        self.root.withdraw()
        stil.einrichten(self.root)
        self.app = App(self.root, self.konfig, self.db.kopie())
        self.root.report_callback_exception = lambda *a: self.fehler.append("".join(traceback.format_exception(*a)))
        self.app.fragen = lambda text: True
        self.app.hinweis = lambda text: None

    def tearDown(self):
        try:
            if self.app.waechter:
                self.app.waechter.anhalten()
            self.app.db.schliessen()
            self.root.destroy()
        finally:
            gemeinsam.entfernen(self.db)
            self.tmp.cleanup()
            os.environ.pop("BRIEFVERWALTUNG_KONFIG", None)

    def warten(self, bedingung, sekunden=10):
        import time
        ende = time.time() + sekunden
        while time.time() < ende:
            self.root.update()
            if bedingung():
                return True
            time.sleep(0.05)
        return False

    def test_alles_einmal_anfassen(self):
        app, db = self.app, self.db
        # „Stick einstecken“: der Zusatzordner taucht mit einem Briefe-Ordner auf
        briefe = Path(self.tmp.name) / "stick" / "Briefe"
        briefe.mkdir(parents=True)
        (briefe / "Rechnung.png").write_bytes(gemeinsam.png(40, 60, (10, 20, 30)))
        self.assertTrue(self.warten(lambda: db.briefe()), "USB-Import hat nicht stattgefunden")
        self.assertTrue(self.warten(lambda: not app._import_laeuft))
        brief_id = db.briefe()[0]["id"]

        for tab in app.tabs:
            app.notebook.select(tab)
            self.root.update()
            tab.neu_laden()
        app.brief_zeigen(brief_id)
        self.root.update()
        formular = app.briefe.formular
        self.assertEqual(formular.brief["id"], brief_id)
        formular.betreff.set("Stromrechnung")
        formular.absender.set("Stadtwerke Test")
        formular.frist.var.set("+7")
        formular.betrag.set("49,90")
        formular.speichern()
        brief = db.brief_holen(brief_id)
        self.assertEqual((brief["betreff"], brief["absender"], brief["betrag"], brief["status"]),
                         ("Stromrechnung", "Stadtwerke Test", Decimal("49.90"), "in_bearbeitung"))

        app.absender_zeigen(brief["absender_id"])
        self.root.update()
        app.anlass_zeigen(db.anlass_id_fuer("Test-Anlass"))
        self.root.update()
        app.briefe_filter("neu")
        app.briefe.neuer_brief()
        self.root.update()
        app.briefe.gruppe.current(1)
        app.briefe._ansicht_geaendert()
        self.root.update()
        app.sql.beispiele.current(0)
        app.sql._beispiel()
        self.root.update()
        self.assertEqual(self.fehler, [])


if __name__ == "__main__":
    unittest.main()
