"""Reproduzierbare Forschungsprozesse der V2 mit getrennten Stufen."""
from __future__ import annotations

from argparse import ArgumentParser
from importlib.metadata import version
from pathlib import Path
import platform

from .auswertung import PROJEKT, lese_json
from .eigenmoden import Platte
from .forschungsatlas import erzeuge_atlas
from .plattenmechanik import Anschluss, modellstudie
from .provenienz import dateihashes, json_schreiben


def main() -> int:
    ap=ArgumentParser(description=__doc__)
    ap.add_argument("stufe",choices=("atlas","mechanik","invers","abbildungen","alle"))
    ap.add_argument("--v1",type=Path,default=PROJEKT/"ausgaben/privat/analyse")
    ap.add_argument("--ziel",type=Path,default=PROJEKT/"ausgaben/privat/v2")
    ap.add_argument("--g0",type=Path,help="Separater G0-Artefaktordner")
    ap.add_argument("--konfig",type=Path,default=PROJEKT/"konfiguration/v2.json")
    a=ap.parse_args()
    z=a.ziel.resolve()
    if not z.is_relative_to(PROJEKT/"ausgaben/privat/v2") or a.v1.resolve().is_relative_to(z):
        ap.error("V2-Ziel im privaten Projektbereich, V1-Eingabe in einem getrennten Ordner angeben.")
    g0=(a.g0 or z/"g0").resolve()
    c=lese_json(a.konfig)
    if c["schema"]!=2:
        ap.error("Konfiguration mit Schema 2 erforderlich.")
    p,k=Platte(**c["platte"]), Anschluss(**c["anschluss"])
    if a.stufe in {"atlas","alle"}:
        erzeuge_atlas(a.v1,z,g0,c["atlas"]["max_schritt_hz"])
    if a.stufe in {"mechanik","alle"}:
        if not modellstudie(z,p,k)["benchmark"]["bestanden"]:
            return 1
    if a.stufe in {"invers","alle"}:
        from .inverse_studie import inversionsstudie
        inversionsstudie(a.v1,z,p,k,c)
    if a.stufe in {"abbildungen","alle"}:
        from .forschungsfiguren import abbildungen
        abbildungen(a.v1,z,g0)
    if a.stufe=="alle":
        module=("forschung","forschungsatlas","plattenmechanik","inverse_modelle","inverse_studie","forschungsfiguren")
        dateien=[z/name for name in ("atlas.json","mechanik.json","invers.json","inverse_validierung.json",
                                     "inverse_felder.npz","frequenznachbarn.csv","aufnahmenachbarn.csv")]
        dateien.extend(sorted(f for f in (z/"figuren").iterdir() if f.suffix in {".png",".svg",".pdf"}))
        json_schreiben(z/"laufmanifest.json",{"schema":2,"python":platform.python_version(),"konfiguration":c,
            "konfiguration_sha256":dateihashes(a.konfig)[0],"v1_sha256":dateihashes(a.v1/"atlas.json")[0],
            "g0_sha256":dateihashes(g0/"bildpruefung.json")[0],
            "code_sha256":{s:dateihashes(Path(__file__).with_name(s+".py"))[0] for s in module},
            "bibliotheken":{p:version(p) for p in ("numpy","scipy","pillow","scikit-image","matplotlib")},
            "artefakte":{f.relative_to(z).as_posix():dateihashes(f)[0] for f in dateien}})
    return 0


if __name__=="__main__":
    raise SystemExit(main())
