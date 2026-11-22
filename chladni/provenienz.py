"""Dateiidentitäten, referenzierte Pfade und atomare Exporte."""
from pathlib import Path
import hashlib
import json
import os
import tempfile


def dateihashes(datei: Path) -> tuple[str, str]:
    from zlib import crc32

    sha, crc = hashlib.sha256(), 0
    with datei.open("rb") as strom:
        while block := strom.read(1024 * 1024):
            sha.update(block)
            crc = crc32(block, crc)
    return sha.hexdigest(), f"{crc:08x}"


def quellpfad(wurzel: Path, relativ: str) -> Path:
    wurzel = wurzel.resolve()
    pfad = (wurzel / relativ).resolve()
    if not pfad.is_relative_to(wurzel) or not pfad.is_file():
        raise ValueError(f"Keine Quelldatei innerhalb des Datenwurzelpfads: {relativ}")
    return pfad


def atomar_schreiben(pfad: Path, inhalt: str) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=pfad.parent, delete=False, mode="w",
                                     encoding="utf-8", newline="") as tmp:
        temporär = Path(tmp.name)
        tmp.write(inhalt)
    try:
        os.replace(temporär, pfad)
    finally:
        temporär.unlink(missing_ok=True)


def json_schreiben(pfad: Path, daten: object) -> None:
    atomar_schreiben(pfad, json.dumps(daten, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
