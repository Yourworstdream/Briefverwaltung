"""Startet die Briefverwaltung unter Windows per Doppelklick – ohne schwarzes Konsolenfenster."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from briefverwaltung import befehlszeile  # noqa: E402

sys.exit(befehlszeile([]))
