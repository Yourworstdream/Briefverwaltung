"""Kleine Helfer: Datum, Geldbeträge, IBAN und die festen Auswahllisten.

Alles hier ist reines Python ohne Datenbank und ohne Oberfläche – deshalb gut testbar.
"""
from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal, InvalidOperation


class Eingabefehler(ValueError):
    """Eine Eingabe ist ungültig. Die Meldung wird der Benutzerin / dem Benutzer gezeigt."""


# ---------------------------------------------------------------- Auswahllisten

# Dringlichkeit 1–4: (Bezeichnung, Farbe, helle Hintergrundfarbe für Listen)
DRINGLICHKEIT = {
    1: ("niedrig", "#6b7f8e", "#eef2f5"),
    2: ("normal", "#2f7d4f", "#ffffff"),
    3: ("hoch", "#d17a00", "#fff1dc"),
    4: ("sehr dringend", "#c62828", "#fde2e2"),
}

STATUS = {
    "neu": "Neu",
    "in_bearbeitung": "In Bearbeitung",
    "wartet": "Wartet auf Antwort",
    "erledigt": "Erledigt",
}

ANLASS_STATUS = {"offen": "Offen", "erledigt": "Erledigt"}

ABSENDER_ARTEN = [
    "Behörde", "Firma", "Bank", "Versicherung", "Krankenkasse", "Vermieter",
    "Arzt / Praxis", "Schule", "Verein", "Privatperson", "Sonstiges",
]

# Arten von Aktivitäten und welche Zusatzfelder dafür sinnvoll sind
AKTIVITAET_ARTEN = {
    "Telefonat": {"zeichen": "☎", "felder": ("richtung", "telefonnummer", "dauer_min")},
    "Treffen": {"zeichen": "●", "felder": ("ort", "dauer_min")},
    "Zahlung": {"zeichen": "€", "felder": ("richtung", "betrag", "zahlungsart", "bankverbindung_id")},
    "E-Mail": {"zeichen": "@", "felder": ("richtung",)},
    "Brief verschickt": {"zeichen": "✉", "felder": ()},
    "Notiz": {"zeichen": "✎", "felder": ()},
    "Sonstiges": {"zeichen": "•", "felder": ("richtung", "ort", "dauer_min", "betrag")},
}

RICHTUNG = {
    "Telefonat": {"ausgehend": "Ich habe angerufen", "eingehend": "Ich wurde angerufen"},
    "Zahlung": {"ausgehend": "Ich habe bezahlt", "eingehend": "Ich habe Geld erhalten"},
    "E-Mail": {"ausgehend": "Gesendet", "eingehend": "Erhalten"},
    "Sonstiges": {"ausgehend": "Ausgehend", "eingehend": "Eingehend"},
}

ZAHLUNGSARTEN = ["Überweisung", "Lastschrift", "Dauerauftrag", "Bar", "Karte", "PayPal", "Sonstiges"]


def aktivitaet_zeichen(art: str) -> str:
    return AKTIVITAET_ARTEN.get(art, {"zeichen": "•"})["zeichen"]


# ---------------------------------------------------------------- Datum und Zeit

_MONATE_PLUS = re.compile(r"^\+\s*(\d{1,3})\s*([tTwWmM]?)$")


def monate_addieren(datum: dt.date, monate: int) -> dt.date:
    jahr, monat = divmod(datum.month - 1 + monate, 12)
    jahr += datum.year
    monat += 1
    tag = min(datum.day, [31, 29 if _schaltjahr(jahr) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][monat - 1])
    return dt.date(jahr, monat, tag)


def _schaltjahr(jahr: int) -> bool:
    return jahr % 4 == 0 and (jahr % 100 != 0 or jahr % 400 == 0)


def datum_lesen(text: str | None, heute: dt.date | None = None) -> dt.date | None:
    """Liest ein Datum so, wie man es eintippt.

    Erlaubt sind z. B. „8.10.2026“, „08.10.26“, „8.10.“ (dieses Jahr), „2026-10-08“,
    „heute“, „morgen“, „gestern“, „+14“ (in 14 Tagen), „+2w“ (Wochen) und „+1m“ (Monate).
    Leerer Text ergibt None.
    """
    heute = heute or dt.date.today()
    text = (text or "").strip().lower()
    if not text:
        return None
    if text in ("heute", "h"):
        return heute
    if text in ("morgen", "m"):
        return heute + dt.timedelta(days=1)
    if text in ("übermorgen", "uebermorgen"):
        return heute + dt.timedelta(days=2)
    if text in ("gestern", "g"):
        return heute - dt.timedelta(days=1)
    plus = _MONATE_PLUS.match(text)
    if plus:
        zahl, einheit = int(plus.group(1)), plus.group(2).lower()
        if einheit == "w":
            return heute + dt.timedelta(weeks=zahl)
        if einheit == "m":
            return monate_addieren(heute, zahl)
        return heute + dt.timedelta(days=zahl)
    try:
        if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", text):
            jahr, monat, tag = (int(t) for t in text.split("-"))
            return dt.date(jahr, monat, tag)
        teile = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-]?(\d{2}|\d{4})?", text)
        if teile:
            tag, monat = int(teile.group(1)), int(teile.group(2))
            jahr_text = teile.group(3)
            if not jahr_text:
                jahr = heute.year
            elif len(jahr_text) == 2:
                jahr = 2000 + int(jahr_text)
            else:
                jahr = int(jahr_text)
            return dt.date(jahr, monat, tag)
        if re.fullmatch(r"\d{8}", text):          # 08102026
            return dt.date(int(text[4:]), int(text[2:4]), int(text[:2]))
    except ValueError:
        pass
    raise Eingabefehler(f"„{text}“ ist kein gültiges Datum. Beispiele: 08.10.2026, heute, +14")


def zeit_lesen(text: str | None) -> dt.time | None:
    """„14:30“, „14.30“, „1430“ oder „14“ → Uhrzeit; leer → None."""
    text = (text or "").strip().lower().replace("uhr", "").strip()
    if not text:
        return None
    if text == "jetzt":
        jetzt = dt.datetime.now()
        return dt.time(jetzt.hour, jetzt.minute)
    teile = re.fullmatch(r"(\d{1,2})(?:[:.]?(\d{2}))?", text)
    if teile:
        stunde, minute = int(teile.group(1)), int(teile.group(2) or 0)
        if stunde < 24 and minute < 60:
            return dt.time(stunde, minute)
    raise Eingabefehler(f"„{text}“ ist keine gültige Uhrzeit. Beispiel: 14:30")


def datum_text(datum: dt.date | dt.datetime | None) -> str:
    if not datum:
        return ""
    if isinstance(datum, dt.datetime):
        return datum.strftime("%d.%m.%Y %H:%M")
    return datum.strftime("%d.%m.%Y")


def zeit_text(zeitpunkt: dt.datetime | None) -> str:
    return zeitpunkt.strftime("%H:%M") if zeitpunkt else ""


def frist_text(frist: dt.date | None, heute: dt.date | None = None) -> str:
    """Wie viel Zeit bis zur Frist bleibt, z. B. „in 3 Tagen“ oder „seit 2 Tagen überfällig“."""
    if not frist:
        return ""
    heute = heute or dt.date.today()
    tage = (frist - heute).days
    if tage == 0:
        return "heute fällig"
    if tage == 1:
        return "morgen fällig"
    if tage > 1:
        return f"in {tage} Tagen"
    if tage == -1:
        return "seit gestern überfällig"
    return f"seit {-tage} Tagen überfällig"


# ---------------------------------------------------------------- Geld

def betrag_lesen(text: str | None) -> Decimal | None:
    """„1.234,56 €“, „1234.56“, „12,5“ oder „-30“ → Decimal mit zwei Nachkommastellen."""
    text = (text or "").strip().replace("€", "").replace("EUR", "").replace(" ", "").replace(" ", "")
    if not text:
        return None
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif text.count(".") > 1 or re.fullmatch(r"-?\d{1,3}(\.\d{3})+", text):
        text = text.replace(".", "")              # 1.234 = Tausenderpunkt
    try:
        wert = Decimal(text)
    except InvalidOperation:
        raise Eingabefehler(f"„{text}“ ist kein gültiger Betrag. Beispiel: 49,90") from None
    if not wert.is_finite() or abs(wert) >= Decimal("10000000000"):
        raise Eingabefehler("Der Betrag ist zu groß.")
    return wert.quantize(Decimal("0.01"))


def betrag_text(wert, mit_zeichen: bool = True) -> str:
    """Decimal → „1.234,56 €“; None → „“."""
    if wert is None or wert == "":
        return ""
    text = f"{Decimal(wert):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} €" if mit_zeichen else text


# ---------------------------------------------------------------- IBAN / BIC

# Länge der IBAN je Land (Auswahl; andere Länder: 15–34 Zeichen)
IBAN_LAENGE = {
    "DE": 22, "AT": 20, "CH": 21, "LI": 21, "LU": 20, "NL": 18, "BE": 16, "FR": 27, "IT": 27,
    "ES": 24, "PT": 25, "PL": 28, "CZ": 24, "DK": 18, "SE": 24, "NO": 15, "FI": 18, "GB": 22,
    "IE": 22, "HU": 28, "HR": 21, "SI": 19, "SK": 24, "GR": 27, "TR": 26, "RO": 24, "BG": 22,
}


def iban_normalisieren(text: str | None) -> str:
    return re.sub(r"[\s\-]", "", (text or "")).upper()


def iban_pruefen(text: str | None) -> str:
    """Prüft eine IBAN (Länge und Prüfziffer) und gibt sie ohne Leerzeichen zurück."""
    iban = iban_normalisieren(text)
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", iban):
        raise Eingabefehler("Die IBAN muss mit dem Ländercode beginnen, z. B. DE12 3456 7890 1234 5678 90.")
    erwartet = IBAN_LAENGE.get(iban[:2])
    if erwartet and len(iban) != erwartet:
        raise Eingabefehler(f"Eine IBAN aus {iban[:2]} hat {erwartet} Zeichen – eingegeben wurden {len(iban)}.")
    umgestellt = iban[4:] + iban[:4]
    zahl = "".join(str(int(z, 36)) for z in umgestellt)
    if int(zahl) % 97 != 1:
        raise Eingabefehler("Die Prüfziffer der IBAN stimmt nicht – bitte auf Tippfehler prüfen.")
    return iban


def iban_formatieren(iban: str | None) -> str:
    iban = iban_normalisieren(iban)
    return " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))


def bic_pruefen(text: str | None) -> str:
    bic = re.sub(r"\s", "", text or "").upper()
    if bic and not re.fullmatch(r"[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?", bic):
        raise Eingabefehler("Die BIC hat 8 oder 11 Zeichen, z. B. MALADE51KLK.")
    return bic


# ---------------------------------------------------------------- Sonstiges

def anzahl(zahl: int, einzahl: str, mehrzahl: str) -> str:
    """anzahl(1, "Foto", "Fotos") → „1 Foto“, anzahl(3, …) → „3 Fotos“."""
    return f"{zahl} {einzahl if zahl == 1 else mehrzahl}"


def kurz(text: str | None, laenge: int = 60) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= laenge else text[: laenge - 1] + "…"


def person_name(ap: dict | None) -> str:
    """Anzeigename eines Ansprechpartners, z. B. „Frau Dr. Müller (Sachbearbeitung)“."""
    if not ap:
        return ""
    name = " ".join(t for t in (ap.get("anrede"), ap.get("titel"), ap.get("vorname"), ap.get("nachname")) if t)
    if ap.get("funktion"):
        name += f" ({ap['funktion']})"
    return name
