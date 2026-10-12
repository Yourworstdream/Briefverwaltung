"""Bilder einlesen: Größe, Aufnahmedatum, Vorschaubild und Drehung.

Dafür wird Pillow gebraucht (pip install pillow). Fotos im HEIC-Format (iPhone) gehen
zusätzlich mit pillow-heif. Ohne Pillow werden Fotos trotzdem importiert – nur die Anzeige
im Programm fehlt dann (man kann sie aber mit dem Bildbetrachter des Systems öffnen).
"""
from __future__ import annotations

import datetime as dt
import io
import mimetypes
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:            # pragma: no cover
    Image = ImageOps = None

try:                           # optional: HEIC-Fotos vom iPhone
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:              # pragma: no cover
    pillow_heif = None

BILD_ENDUNGEN = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".heic", ".heif"}
DOKUMENT_ENDUNGEN = {".pdf"}
ENDUNGEN = BILD_ENDUNGEN | DOKUMENT_ENDUNGEN
VORSCHAU_PIXEL = 360

_MIME = {".heic": "image/heic", ".heif": "image/heif", ".webp": "image/webp", ".jpg": "image/jpeg",
         ".jpeg": "image/jpeg", ".png": "image/png", ".pdf": "application/pdf"}


def pillow_da() -> bool:
    return Image is not None


def mime_fuer(dateiname: str) -> str:
    endung = Path(dateiname).suffix.lower()
    return _MIME.get(endung) or mimetypes.guess_type(dateiname)[0] or "application/octet-stream"


def ist_bild(dateiname: str) -> bool:
    return Path(dateiname).suffix.lower() in BILD_ENDUNGEN


def _aufnahmedatum(bild) -> dt.datetime | None:
    try:
        exif = bild.getexif()
        text = exif.get_ifd(0x8769).get(36867) or exif.get(306)       # DateTimeOriginal, sonst DateTime
        if text:
            return dt.datetime.strptime(str(text).strip("\x00 ")[:19], "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return None


def bild_infos(inhalt: bytes) -> dict:
    """Breite, Höhe (aufrecht), Aufnahmedatum und ein kleines JPEG-Vorschaubild."""
    infos = {"breite": None, "hoehe": None, "aufgenommen_am": None, "vorschau": None}
    if Image is None:
        return infos
    try:
        with Image.open(io.BytesIO(inhalt)) as bild:
            infos["aufgenommen_am"] = _aufnahmedatum(bild)
            aufrecht = ImageOps.exif_transpose(bild)
            infos["breite"], infos["hoehe"] = aufrecht.size
            klein = aufrecht.convert("RGB")
            klein.thumbnail((VORSCHAU_PIXEL, VORSCHAU_PIXEL))
            puffer = io.BytesIO()
            klein.save(puffer, "JPEG", quality=78, optimize=True)
            infos["vorschau"] = puffer.getvalue()
    except Exception:
        pass                    # kein lesbares Bild (z. B. PDF) – dann eben ohne Vorschau
    return infos


def oeffnen(inhalt: bytes, drehung: int = 0):
    """Öffnet ein Bild aufrecht (EXIF) und um `drehung` Grad im Uhrzeigersinn gedreht. None, wenn nicht möglich."""
    if Image is None or not inhalt:
        return None
    try:
        bild = Image.open(io.BytesIO(inhalt))
        bild = ImageOps.exif_transpose(bild)
        if bild.mode not in ("RGB", "RGBA"):
            bild = bild.convert("RGB")
        return drehen(bild, drehung)
    except Exception:
        return None


def drehen(bild, drehung: int):
    drehung = drehung % 360
    if drehung == 90:
        return bild.transpose(Image.Transpose.ROTATE_270)
    if drehung == 180:
        return bild.transpose(Image.Transpose.ROTATE_180)
    if drehung == 270:
        return bild.transpose(Image.Transpose.ROTATE_90)
    return bild
