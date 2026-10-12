"""USB-Sticks erkennen – unter Windows, Linux und macOS, ohne Zusatzbibliotheken.

Ein Hintergrund-Thread schaut alle paar Sekunden nach, welche Laufwerke eingehängt sind.
Taucht ein neues auf und liegt darauf der Ordner „Briefe“, wird `bei_fund(laufwerk, ordner)`
aufgerufen. Ein Stick, der beim Programmstart schon steckt, wird ebenfalls erkannt.
"""
from __future__ import annotations

import os
import re
import sys
import threading
from dataclasses import dataclass

from .importer import briefe_ordner_finden

# So oft wird ein frisch eingesteckter Stick nach dem Ordner durchsucht, bevor wir aufgeben
# (direkt nach dem Einstecken ist das Dateisystem manchmal noch nicht lesbar).
VERSUCHE = 5
_FERTIG = -1

LINUX_ORTE = ("/media/", "/run/media/", "/mnt/", "/Volumes/")
LINUX_IGNORIEREN = {"proc", "sysfs", "tmpfs", "devtmpfs", "devpts", "cgroup", "cgroup2", "overlay", "squashfs",
                    "securityfs", "debugfs", "tracefs", "configfs", "fusectl", "mqueue", "hugetlbfs", "pstore",
                    "bpf", "autofs", "binfmt_misc", "efivarfs", "rpc_pipefs", "nsfs", "ramfs"}


@dataclass(frozen=True)
class Laufwerk:
    pfad: str
    name: str
    wechselbar: bool = True     # Wechseldatenträger (USB-Stick, SD-Karte)


def laufwerke() -> list:
    """Alle Laufwerke, auf denen ein USB-Stick sein könnte."""
    if sys.platform.startswith("win"):
        return list(_windows())
    if sys.platform == "darwin":
        return list(_macos())
    return list(_linux())


# ---------------------------------------------------------------- Windows

def _windows():
    import ctypes
    import string

    k32 = ctypes.windll.kernel32
    # Keine Windows-Meldung „Kein Datenträger im Laufwerk“ bei leeren Kartenlesern
    k32.SetErrorMode(0x0001 | 0x8000)
    maske = k32.GetLogicalDrives()
    system = (os.environ.get("SystemDrive") or "C:").upper()[:2]
    for nr, buchstabe in enumerate(string.ascii_uppercase):
        if not maske & (1 << nr):
            continue
        wurzel = f"{buchstabe}:\\"
        if wurzel[:2] == system:
            continue
        typ = k32.GetDriveTypeW(ctypes.c_wchar_p(wurzel))
        if typ not in (2, 3):       # 2 = Wechseldatenträger, 3 = Festplatte (manche USB-Sticks melden sich so)
            continue
        puffer = ctypes.create_unicode_buffer(261)
        if not k32.GetVolumeInformationW(ctypes.c_wchar_p(wurzel), puffer, 261, None, None, None, None, 0):
            continue                # kein Datenträger eingelegt
        name = puffer.value or ("USB-Laufwerk" if typ == 2 else "Laufwerk")
        yield Laufwerk(wurzel, f"{name} ({buchstabe}:)", typ == 2)


# ---------------------------------------------------------------- macOS

def _macos():
    try:
        eintraege = os.listdir("/Volumes")
    except OSError:
        return
    for name in eintraege:
        pfad = os.path.join("/Volumes", name)
        if os.path.realpath(pfad) == "/" or not os.path.isdir(pfad):
            continue
        yield Laufwerk(pfad, name, True)


# ---------------------------------------------------------------- Linux

def _entschluesseln(text: str) -> str:
    """/proc/mounts schreibt Leerzeichen als \\040 usw."""
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), text)


def linux_einhaengepunkte(inhalt: str):
    for zeile in inhalt.splitlines():
        teile = zeile.split()
        if len(teile) >= 3:
            yield teile[0], _entschluesseln(teile[1]), teile[2]


def _linux_wechselbar(geraet: str, sys_block: str = "/sys/class/block") -> bool:
    if not geraet.startswith("/dev/"):
        return False
    name = os.path.basename(os.path.realpath(geraet))
    pfad = os.path.realpath(os.path.join(sys_block, name))
    if "/usb" in pfad:
        return True
    for kandidat in (pfad, os.path.dirname(pfad)):          # Partition → zugehörige Festplatte
        try:
            with open(os.path.join(kandidat, "removable"), encoding="ascii") as datei:
                if datei.read().strip() == "1":
                    return True
        except OSError:
            pass
    return False


def _linux(mounts: str = "/proc/self/mounts"):
    try:
        with open(mounts, encoding="utf-8", errors="replace") as datei:
            inhalt = datei.read()
    except OSError:
        return
    gesehen = set()
    for geraet, punkt, typ in linux_einhaengepunkte(inhalt):
        if typ in LINUX_IGNORIEREN or punkt in gesehen or punkt == "/":
            continue
        wechselbar = _linux_wechselbar(geraet)
        if wechselbar or punkt.startswith(LINUX_ORTE):
            gesehen.add(punkt)
            yield Laufwerk(punkt, os.path.basename(punkt.rstrip("/")) or punkt, wechselbar)


# ---------------------------------------------------------------- Überwachung

class UsbWaechter:
    """Prüft regelmäßig die Laufwerke und meldet neue Sticks mit Briefe-Ordner."""

    def __init__(self, bei_fund, ordnername: str = "Briefe", intervall: float = 2.0, zusatz_ordner=(),
                 quelle=laufwerke):
        self.bei_fund = bei_fund
        self.ordnername = ordnername or "Briefe"
        self.intervall = max(0.5, float(intervall or 2.0))
        self.zusatz_ordner = [o for o in (zusatz_ordner or []) if o]
        self._quelle = quelle
        self._bekannt = {}           # Pfad → Zahl der Versuche oder _FERTIG
        self._erster_lauf = True
        self._sperre = threading.Lock()
        self._stopp = threading.Event()
        self._stopp.set()
        self._thread = None
        self.letzter_fehler = None

    def _aktuelle(self) -> dict:
        aktuell = {lw.pfad: lw for lw in self._quelle()}
        for ordner in self.zusatz_ordner:
            if os.path.isdir(ordner):
                aktuell.setdefault(ordner, Laufwerk(ordner, os.path.basename(ordner.rstrip("/\\")) or ordner, True))
        return aktuell

    def pruefen(self, erzwingen: bool = False) -> list:
        """Ein Durchgang. Mit erzwingen=True werden alle steckenden Laufwerke erneut durchsucht."""
        with self._sperre:
            aktuell = self._aktuelle()
            for pfad in list(self._bekannt):
                if pfad not in aktuell:                      # Stick wurde abgezogen
                    del self._bekannt[pfad]
            funde = []
            for pfad, laufwerk in aktuell.items():
                zustand = None if erzwingen else self._bekannt.get(pfad)
                if zustand == _FERTIG:
                    continue
                if zustand is None and self._erster_lauf and not laufwerk.wechselbar and not erzwingen:
                    self._bekannt[pfad] = _FERTIG            # feste Platte, die schon beim Start da war
                    continue
                ordner = briefe_ordner_finden(pfad, self.ordnername)
                if ordner:
                    self._bekannt[pfad] = _FERTIG
                    funde.append((laufwerk, ordner))
                else:
                    versuche = (zustand or 0) + 1
                    self._bekannt[pfad] = _FERTIG if versuche >= VERSUCHE or erzwingen else versuche
            self._erster_lauf = False
        for laufwerk, ordner in funde:
            self.bei_fund(laufwerk, ordner)
        return funde

    def _lauf(self, stopp: threading.Event) -> None:
        while not stopp.is_set():
            try:
                self.pruefen()
                self.letzter_fehler = None
            except Exception as fehler:          # die Überwachung darf nie ganz stehen bleiben
                self.letzter_fehler = fehler
            stopp.wait(self.intervall)

    def starten(self) -> None:
        if self.laeuft:
            return
        self._stopp = threading.Event()          # jeder Thread bekommt sein eigenes Stopp-Signal
        self._thread = threading.Thread(target=self._lauf, args=(self._stopp,), name="USB-Waechter", daemon=True)
        self._thread.start()

    def anhalten(self) -> None:
        self._stopp.set()

    @property
    def laeuft(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stopp.is_set())
