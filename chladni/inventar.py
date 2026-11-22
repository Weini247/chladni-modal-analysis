"""Strombasierte GP2-Bestandsaufnahme und lokale Kontaktbögen."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from importlib.metadata import version
import io
import json
from pathlib import Path
import re
import sqlite3
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .provenienz import atomar_schreiben, dateihashes, json_schreiben

BILDFORMATE = {".heic", ".heif", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp"}
EXIF_FELDER = {271: "hersteller", 272: "modell", 274: "orientierung", 306: "datum_datei",
               33434: "belichtungszeit_s", 33437: "blendenzahl", 34855: "iso",
               36867: "aufnahmezeit", 36881: "utc_offset_aufnahme", 37386: "brennweite_mm",
               37521: "subsekunde_aufnahme", 42036: "objektiv"}


def registriere_heif() -> str | None:
    try:
        import pillow_heif
    except ModuleNotFoundError:
        return None
    pillow_heif.register_heif_opener()
    return version("pillow-heif")


def lade_bild(pfad: Path) -> Image.Image:
    with Image.open(pfad) as bild:
        return ImageOps.exif_transpose(bild).convert("RGB")


def bilddaten(pfad: Path) -> tuple[dict, Image.Image]:
    with Image.open(pfad) as bild:
        exif = bild.getexif()
        erweitert = exif.get_ifd(34665)
        meta = {name: str(erweitert.get(nr, exif.get(nr))) for nr, name in EXIF_FELDER.items()
                if nr in erweitert or nr in exif}
        meta["gps_tag_vorhanden"] = 34853 in exif
        groesse = bild.size
        formatname = bild.format
        bild.load()
        orientiert = ImageOps.exif_transpose(bild).convert("RGB")
    klein = orientiert.copy()
    klein.thumbnail((300, 230), Image.Resampling.LANCZOS)
    fingerabdruck = np.asarray(orientiert.convert("L").resize((9, 8), Image.Resampling.LANCZOS))
    bits = (fingerabdruck[:, 1:] > fingerabdruck[:, :-1]).flatten()
    dhash = np.packbits(bits).tobytes().hex()
    return {"format": formatname, "breite_px": groesse[0], "hoehe_px": groesse[1],
            "orientiert_breite_px": orientiert.width, "orientiert_hoehe_px": orientiert.height,
            "seitenverhaeltnis": round(orientiert.width / orientiert.height, 8), "exif": meta,
            "dhash64": dhash}, klein


def sichtbare_dateien(wurzel: Path, ausschluss: Path) -> list[Path]:
    import os

    dateien = []
    for ordner, unterordner, namen in os.walk(wurzel, followlinks=False):
        pfad = Path(ordner)
        unterordner[:] = [n for n in sorted(unterordner)
                         if not (pfad / n).resolve().is_relative_to(ausschluss)
                         and not (pfad / n).is_symlink()]
        dateien.extend(pfad / name for name in namen if not (pfad / name).is_symlink())
    return sorted(dateien, key=lambda p: p.relative_to(wurzel).as_posix().casefold())


def erfasse_datei(datei: Path, wurzel: Path, thumbs: Path, db: sqlite3.Connection,
                  decoder: str) -> dict:
    rel = datei.relative_to(wurzel).as_posix()
    stat = datei.stat()
    schluessel = f"{stat.st_size}:{stat.st_mtime_ns}:{decoder}"
    zeile = db.execute("SELECT eintrag FROM dateien WHERE pfad = ? AND cachekey = ?",
                       (rel, schluessel)).fetchone()
    if zeile:
        alt = json.loads(zeile[0])
        if "dhash64" not in alt or (thumbs / (alt["sha256"] + ".jpg")).is_file():
            return alt
    endung = datei.suffix.lower()
    eintrag = {
        "pfad": rel, "endung": endung, "bytes": stat.st_size,
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "status": "gehasht", "fehler": None,
    }
    try:
        eintrag["sha256"], eintrag["crc32"] = dateihashes(datei)
        if endung in BILDFORMATE:
            if endung in {".heic", ".heif"} and decoder.endswith(":kein-HEIF"):
                eintrag["status"] = "decoder_fehlt"
            else:
                daten, thumb = bilddaten(datei)
                thumb.save(thumbs / (eintrag["sha256"] + ".jpg"), quality=88)
                eintrag.update(daten)
                eintrag["status"] = "bild_dekodiert"
        elif endung == ".zip":
            with zipfile.ZipFile(datei) as archiv:
                eintrag["archiv_member"] = [
                    {"pfad": info.filename, "bytes": info.file_size, "crc32": f"{info.CRC:08x}"}
                    for info in archiv.infolist() if not info.is_dir()
                ]
                eintrag["status"] = "zip_verzeichnis_gelesen"
    except (OSError, ValueError, SyntaxError, RuntimeError, zipfile.BadZipFile) as fehler:
        eintrag.update(status="lesefehler", fehler=f"{type(fehler).__name__}: {fehler}")
    if eintrag["status"] != "lesefehler":
        db.execute("INSERT OR REPLACE INTO dateien VALUES (?, ?, ?)",
                   (rel, schluessel, json.dumps(eintrag)))
        db.commit()
    return eintrag


def gruppiere(daten: list[dict]) -> dict:
    hashes = defaultdict(list)
    for d in daten:
        if "sha256" in d:
            hashes[d["sha256"]].append(d["pfad"])
    bilder = [d for d in daten if "dhash64" in d]
    nahe = []
    for i, bild in enumerate(bilder):
        a = int(bild["dhash64"], 16)
        for b in bilder[i + 1:]:
            if bild["sha256"] == b["sha256"]:
                continue
            dist = (a ^ int(b["dhash64"], 16)).bit_count()
            if dist <= 4:
                nahe.append({"a": bild["pfad"], "b": b["pfad"], "dhash_hamming": dist})
    kandidaten = defaultdict(list)
    for d in bilder:
        teile = Path(d["pfad"]).parts[:-1]
        serienordner = teile[-2 if teile[-1] == "Ausgeschnitten" else -1] if teile else ""
        if "Chadni 2" in teile:
            kandidaten[serienordner].append(d)
    serien = []
    for name, gruppe in sorted(kandidaten.items()):
        treffer = re.fullmatch(r"(?:Bilder )?(\d{3,4})", name)
        zeiten = sorted({g["exif"]["aufnahmezeit"] for g in gruppe if "aufnahmezeit" in g["exif"]})
        serien.append({"ordner": name, "ordnerlabel_hz": int(treffer[1]) if treffer else None,
                       "aufnahmen_und_derivate": len(gruppe),
                       "als_ausgeschnitten_abgelegt": sum("Ausgeschnitten" in Path(g["pfad"]).parts for g in gruppe),
                       "zeit_exif_lokal_min": zeiten[0] if zeiten else None,
                       "zeit_exif_lokal_max": zeiten[-1] if zeiten else None,
                       "bilder": [g["pfad"] for g in gruppe]})
    return {"exakte_duplikate": {k: v for k, v in hashes.items() if len(v) > 1},
            "visuelle_pruefkandidaten": nahe, "messreihen_kandidaten": serien}


def abgleich_archiv(daten: list[dict]) -> list[dict]:
    nach_pfad = {d["pfad"]: d for d in daten}
    ergebnis = []
    for d in daten:
        if "archiv_member" not in d:
            continue
        ausgepackt = Path(d["pfad"]).with_suffix("")
        abweichungen, namensabgleich = [], []
        for m in d["archiv_member"]:
            rel = (ausgepackt / m["pfad"]).as_posix()
            lose = nach_pfad.get(rel)
            if lose is None:
                windows_pfad = "/".join(teil.rstrip(" .") for teil in rel.split("/"))
                kandidat = nach_pfad.get(windows_pfad)
                if kandidat and (kandidat["bytes"], kandidat.get("crc32")) == (m["bytes"], m["crc32"]):
                    namensabgleich.append({"zip": m["pfad"], "entpackt": windows_pfad})
                    lose = kandidat
            if lose is None or (lose["bytes"], lose.get("crc32")) != (m["bytes"], m["crc32"]):
                abweichungen.append(rel)
        ergebnis.append({"pfad": d["pfad"], "member": len(d["archiv_member"]),
                         "groesse_crc_passend": len(d["archiv_member"]) - len(abweichungen),
                         "abweichungen": abweichungen, "windows_namensabgleich": namensabgleich})
    return ergebnis


def kontaktboegen(daten: list[dict], thumbs: Path, ziel: Path) -> None:
    ziel.mkdir(parents=True, exist_ok=True)
    dekodiert = [d for d in daten if d["status"] == "bild_dekodiert"]
    schrift = ImageFont.load_default(size=15)
    klein = ImageFont.load_default(size=13)
    pro_seite, spalten, breite, hoehe = 35, 7, 230, 206
    for beginn in range(0, len(dekodiert), pro_seite):
        gruppe = dekodiert[beginn:beginn + pro_seite]
        seite = Image.new("RGB", (spalten * breite, 45 + 5 * hoehe), "#101b28")
        zeichnung = ImageDraw.Draw(seite)
        zeichnung.text((12, 12), f"GP2 HHU  ·  Kontaktbogen {beginn // pro_seite + 1:02d} "
                       f"·  {beginn + 1} bis {beginn + len(gruppe)} von {len(dekodiert)} Bildern",
                       fill="#f1f4f5", font=schrift)
        for i, d in enumerate(gruppe):
            x, y = i % spalten * breite, 43 + i // spalten * hoehe
            with Image.open(thumbs / (d["sha256"] + ".jpg")) as bild:
                bild.thumbnail((220, 160), Image.Resampling.LANCZOS)
                seite.paste(bild, (x + (breite - bild.width) // 2, y + (160 - bild.height) // 2))
            pfad = Path(d["pfad"])
            zusatz = pfad.parent.parent.name + " / Crop" if pfad.parent.name == "Ausgeschnitten" else pfad.parent.name
            zeichnung.text((x + 7, y + 164), f"{beginn+i+1:03d}  {pfad.name}", font=schrift, fill="#f1f4f5")
            zeichnung.text((x + 7, y + 183), zusatz, font=klein, fill="#9fbbc8")
        seite.save(ziel / f"kontakt-{beginn // pro_seite + 1:02d}.jpg", quality=88)


def inventarisiere(wurzel: Path, ziel: Path, projekt: Path, neu: bool = False) -> dict:
    wurzel, ziel, projekt = (p.resolve() for p in (wurzel, ziel, projekt))
    if wurzel.is_relative_to(projekt) or not ziel.is_relative_to(projekt) or not wurzel.is_dir():
        raise ValueError("Erwarte separate Quelldaten und ein Ziel innerhalb des Projekts.")
    ziel.mkdir(parents=True, exist_ok=True)
    thumbs = ziel / "vorschaubilder"
    thumbs.mkdir(exist_ok=True)
    heif = registriere_heif()
    decoder = f"v2:Pillow-{version('Pillow')}:{heif or 'kein-HEIF'}"
    with sqlite3.connect(ziel / "inventar-cache.sqlite") as db:
        db.execute("CREATE TABLE IF NOT EXISTS dateien (pfad TEXT PRIMARY KEY, cachekey TEXT, eintrag TEXT)")
        if neu:
            db.execute("DELETE FROM dateien")
            db.commit()
        dateien = sichtbare_dateien(wurzel, projekt)
        daten = [erfasse_datei(pfad, wurzel, thumbs, db, decoder) for pfad in dateien]
    ergebnis = {"schema": 1, "dekoder": decoder, "dateien": daten,
                "anzahl": len(daten), "bytes": sum(d["bytes"] for d in daten),
                "formate": dict(sorted(Counter(d["endung"] for d in daten).items())),
                "status": dict(Counter(d["status"] for d in daten)),
                "archivabgleich": abgleich_archiv(daten), **gruppiere(daten)}
    json_schreiben(ziel / "dateninventar.json", ergebnis)
    felder = ["pfad", "endung", "bytes", "mtime_utc", "sha256", "crc32", "status", "fehler",
              "format", "breite_px", "hoehe_px", "orientiert_breite_px", "orientiert_hoehe_px",
              "seitenverhaeltnis", "dhash64", "exif"]
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=felder, extrasaction="ignore")
    writer.writeheader()
    for d in daten:
        writer.writerow({**d, "exif": json.dumps(d["exif"], ensure_ascii=False) if "exif" in d else ""})
    atomar_schreiben(ziel / "dateninventar.csv", text.getvalue())
    kontaktboegen(daten, thumbs, ziel / "kontakt")
    return ergebnis


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rohdaten", type=Path)
    parser.add_argument("--ziel", default=Path("ausgaben/privat/inventar"), type=Path)
    parser.add_argument("--neu", action="store_true", help="Hash- und Dekodiercache ignorieren")
    args = parser.parse_args()
    bericht = inventarisiere(args.rohdaten, args.ziel, Path(__file__).resolve().parents[1], args.neu)
    print(f'{bericht["anzahl"]} Dateien, {bericht["bytes"]:,} Byte, {bericht["status"]}')
