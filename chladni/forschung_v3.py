
"""Getrennte reproduzierbare Analysestufen und Eingangs-/Ausgangsprovenienz."""
from __future__ import annotations

from argparse import ArgumentParser
from importlib.metadata import version
from pathlib import Path
import platform

from .auswertung import PROJEKT, lese_json
from .provenienz import dateihashes, json_schreiben
from .v3_pfade import BASIS, KONFIG, V1, V2, V3, Eingaben, audit_v2, integritaet

MODULE = (
    "v3_pfade","bildvalidierung_v3","invers_v3","forschung_v3","figuren_v3",
    "bildpipeline","registrierung","eigenmoden","inverse_modelle","mustervergleich","plattenmechanik"
)


def _dateien(ziel: Path) -> list[Path]:
    ergebnisse = [ziel/n for n in ("v2-audit.json","bildstudie.json","gap.json")]
    for unterordner,suffixe in (("bildvarianten",{".npz"}),("figuren",{".png",".svg",".pdf"})):
        ergebnisse += sorted(p for p in (ziel/unterordner).iterdir() if p.suffix in suffixe)
    return [p for p in ergebnisse if p.is_file()]


def _manifest(e: Eingaben, vorher: dict, nachher: dict) -> None:
    audit = lese_json(e.ziel/"v2-audit.json") if (e.ziel/"v2-audit.json").is_file() else None
    eingang = audit["eingangspruefung"] if audit else None
    quellennamen = ("atlas.json","mechanik.json","invers.json","inverse_validierung.json",
                     "inverse_felder.npz","laufmanifest.json")
    dateien = _dateien(e.ziel)
    v1_liste = lese_json(e.v1/"atlas.json")["bilder"]
    raster = {q["id"]:dateihashes(e.v1/q["id"]/"raster.npz")[0] for q in v1_liste}
    json_schreiben(e.ziel/"laufmanifest.json",{
        "schema":3,"v2_basis_commit":BASIS,
        "python":platform.python_version(),
        "bibliotheken":{p:version(p) for p in ("numpy","scipy","pillow","pillow-heif","scikit-image","matplotlib")},
        "konfiguration_sha256":dateihashes(e.konfig)[0],
        "protokoll_sha256":dateihashes(PROJEKT/"dokumentation/V3_PROTOKOLL.md")[0],
        "v1_atlas_sha256":dateihashes(e.v1/"atlas.json")[0],
        "v1_raster_sha256":raster,
        "v2_eingaben":{n:dateihashes(e.v2/n)[0] for n in quellennamen},
        "code_sha256":{n:dateihashes(Path(__file__).with_name(n+".py"))[0] for n in MODULE},
        "rohdaten_v2_eingang":eingang,
        "rohdaten_vorher":vorher,
        "rohdaten_nachher":nachher,
        "artefakte":{p.relative_to(e.ziel).as_posix():dateihashes(p)[0] for p in dateien},
    })


def main() -> None:
    ap=ArgumentParser(description=__doc__)
    ap.add_argument("stufe",choices=("audit","bilder","gap","figuren","showcase","alle"))
    ap.add_argument("--rohdaten",type=Path,default=PROJEKT.parent)
    ap.add_argument("--v1",type=Path,default=V1)
    ap.add_argument("--v2",type=Path,default=V2)
    ap.add_argument("--ziel",type=Path,default=V3)
    ap.add_argument("--konfig",type=Path,default=KONFIG)
    a=ap.parse_args()
    if a.stufe=="showcase":
        from .figuren_v3 import showcase
        showcase()
        return
    e=Eingaben(a.rohdaten,a.v1,a.v2,a.ziel,a.konfig)
    if not (e.v2/"invers.json").is_file() or not (e.v1/"atlas.json").is_file():
        ap.error("Experimentlauf benötigt private V1-/V2-Analysedaten. "
                 "Ohne GP2-Archiv: python -m werkzeuge.v3_modellpaket")
    cfg=lese_json(e.konfig)
    if cfg["schema"]!=3:
        ap.error("V3-Konfiguration mit Schema 3 erforderlich.")
    arch=lese_json(e.v2/"invers.json")["synthetische_schwellen"]
    if cfg["gap"]["schwellen"]!=arch:
        ap.error("Die Akzeptanzgrenzen müssen der archivierten V2-Kalibrierung entsprechen.")
    vorher=integritaet(e)
    if vorher["abweichungen"] or vorher["fehlende"] or vorher["unbekannte"]:
        raise SystemExit(f"Rohdaten vor dem Lauf abweichend: {vorher}")
    print(f"Vorher: {vorher['dateien']} Quelldateien nach SHA-256 verifiziert.",flush=True)
    if a.stufe in {"audit","alle"}:
        audit=audit_v2(e)
        if any(not q["archiv_ok"] or not q["bytegleich"] for q in audit["artefakte"]):
            raise SystemExit("V2-Abweichungen im Prüfprotokoll.")
    if a.stufe in {"bilder","alle"}:
        from .bildvalidierung_v3 import bildstudie
        bildstudie(e,cfg)
    if a.stufe in {"gap","alle"}:
        from .invers_v3 import gap_studie
        gap_studie(e,cfg)
    if a.stufe in {"figuren","alle"}:
        from .figuren_v3 import abbildungen
        abbildungen(e)
    nachher=integritaet(e)
    if vorher!=nachher:
        raise SystemExit(f"Rohdaten haben sich während des Laufs geändert: {nachher}")
    if a.stufe in {"alle","figuren"}:
        _manifest(e,vorher,nachher)
    print(f"Nachher: {nachher['dateien']} Quelldateien nach SHA-256 verifiziert.",flush=True)


if __name__=="__main__":
    main()
