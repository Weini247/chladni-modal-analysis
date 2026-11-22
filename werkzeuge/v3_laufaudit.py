
"""Prüfe Dateiidentitäten, Rohdatenprotokoll und getrennte V3-Neuberechnung."""
from argparse import ArgumentParser
from pathlib import Path

from chladni.auswertung import PROJEKT, lese_json
from chladni.provenienz import dateihashes, quellpfad
from chladni.v3_pfade import BASIS, V3, Eingaben, integritaet


def _geprueft(ziel: Path) -> dict:
    m=lese_json(ziel/"laufmanifest.json")
    if m["schema"]!=3 or m["v2_basis_commit"]!=BASIS:
        raise ValueError("Ausgangspunkt des Laufmanifests weicht ab.")
    audit=m["rohdaten_v2_eingang"]
    vorher,nachher=m["rohdaten_vorher"],m["rohdaten_nachher"]
    if vorher!=nachher or any(nachher[k] for k in ("abweichungen","fehlende","unbekannte")):
        raise ValueError("Das Rohdatenprotokoll weist Abweichungen aus.")
    if (audit["inventar_sha256"]!=nachher["inventar_sha256"] or audit["quellen"]!=nachher["dateien"]
            or any(audit[k] for k in ("hashfehler","fehlende_quellen","unbekannte_quellen"))):
        raise ValueError("Der V3-Eingang stimmt nicht mit dem unabhängigen V2-Eingang überein.")
    for name,digest in m["artefakte"].items():
        if dateihashes(quellpfad(ziel,name))[0]!=digest:
            raise ValueError(f"Artefakt weicht von seinem Manifest ab: {name}")
    return m


def main() -> None:
    ap=ArgumentParser(description=__doc__)
    ap.add_argument("--rohdaten",type=Path,default=PROJEKT.parent)
    ap.add_argument("--ziel",type=Path,default=V3)
    ap.add_argument("--wiederholung",type=Path,default=V3/"nachrechnung")
    args=ap.parse_args()
    e=Eingaben(args.rohdaten,ziel=args.ziel)
    if args.ziel.resolve()==args.wiederholung.resolve():
        ap.error("Ein separater Ordner für die Wiederholung ist erforderlich.")
    links,rechts=(_geprueft(z) for z in (args.ziel,args.wiederholung))
    a,b=links["artefakte"],rechts["artefakte"]
    abweichend=sorted(name for name in a.keys()|b.keys() if a.get(name)!=b.get(name))
    if abweichend:
        raise SystemExit("Abweichende Artefakte: "+", ".join(abweichend))
    if links["rohdaten_nachher"]!=integritaet(e):
        raise SystemExit("Der aktuelle Rohdatenbestand weicht vom Abschlussmanifest ab.")
    print(f"V3: {len(a)} bytegleiche Artefakte in zwei getrennten Läufen.",flush=True)
    print(f"Rohdaten: {links['rohdaten_nachher']['dateien']} Quellen ohne SHA-256-, Bestands- oder Inventarabweichung.",flush=True)


if __name__=="__main__":
    main()
