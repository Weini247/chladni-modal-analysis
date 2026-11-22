"""Quellengebundene Frequenzangaben für fotografierte Anregungen."""
from __future__ import annotations

from dataclasses import dataclass
import csv
import io
import math
from pathlib import Path
import re
import subprocess

from PIL import Image, ImageEnhance, ImageOps

@dataclass(frozen=True)
class Frequenzbeleg:
    quelle: str
    rohtext: str
    hz: float | None
    methode: str
    konfidenz: str
    rolle: str
    ocr_konfidenz: float | None = None


def bewertete_frequenz(belege: list[Frequenzbeleg], toleranz_hz: float = 0.3,
                       plausibel_hz: tuple[float, float] = (50, 10000)) -> dict:
    direkt = [b for b in belege if b.rolle == "einzelbild" and b.hz is not None]
    if any(not math.isfinite(b.hz) or not plausibel_hz[0] <= b.hz <= plausibel_hz[1] for b in direkt):
        return {"hz": None, "status": "unplausibel"}
    if direkt and max(b.hz for b in direkt) - min(b.hz for b in direkt) > toleranz_hz:
        return {"hz": None, "status": "widerspruch"}
    bestaetigt = [b for b in direkt if b.konfidenz == "manuell_gelesen"]
    if bestaetigt:
        return {"hz": bestaetigt[0].hz, "status": "manuell_gelesen"}
    return {"hz": None, "status": "zu_pruefen" if direkt else "unbekannt"}


def lese_hz(text: str) -> float | None:
    treffer = re.fullmatch(r"\s*(\d{1,5}(?:[,.]\d{1,4})?)\s*(k?hz)\s*", text, flags=re.I)
    if not treffer:
        return None
    multiplikator = 1000 if treffer[2].lower() == "khz" else 1
    return float(treffer[1].replace(",", ".")) * multiplikator


def extrahiere_ocr(bild: Image.Image, box: tuple[float, float, float, float],
                   programm: str = "tesseract", einheit: str | None = None) -> list[Frequenzbeleg]:
    """Lokales Tesseract auf rechteckiger ROI, vier Orientierungen, TSV-Konfidenzen."""
    if len(box) != 4 or not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1):
        raise ValueError("OCR-Bereich als (links, oben, rechts, unten) in [0,1] angeben.")
    roi = bild.crop(tuple(round(v * bild.size[i % 2]) for i, v in enumerate(box)))
    roi = ImageEnhance.Contrast(ImageOps.grayscale(roi)).enhance(2)
    belege = []
    for grad in (0, 90, 180, 270):
        teil = roi.rotate(grad, expand=True)
        if teil.width < 384:
            teil = teil.resize((384, round(teil.height * 384 / teil.width)))
        buffer = io.BytesIO()
        teil.save(buffer, format="PNG")
        aufruf = subprocess.run([programm, "stdin", "stdout", "--psm", "7", "tsv"],
                                 input=buffer.getvalue(), capture_output=True, check=True, timeout=20)
        zeilen = list(csv.DictReader(io.StringIO(aufruf.stdout.decode("utf-8")), delimiter="\t"))
        worte = [z for z in zeilen if z["text"].strip() and float(z["conf"]) >= 0]
        if not worte:
            continue
        roh = " ".join(z["text"].strip() for z in worte)
        beleg = Frequenzbeleg(f"ROI {box} · {grad}°", roh,
                              lese_hz(roh) or (lese_hz(roh + " " + einheit) if einheit else None),
                              "tesseract", "ocr_ungeprueft", "einzelbild",
                              min(float(z["conf"]) for z in worte))
        belege.append(beleg)
    return belege
