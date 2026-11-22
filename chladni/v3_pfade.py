"""Gemeinsame lokale Eingaben und versionierte Verzeichnisse für V3."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .auswertung import PROJEKT, lese_json
from .inventar import sichtbare_dateien
from .provenienz import dateihashes, json_schreiben, quellpfad

V1 = PROJEKT / "ausgaben/privat/analyse"
V2 = PROJEKT / "ausgaben/privat/v2"
V3 = PROJEKT / "ausgaben/privat/v3"
KONFIG = PROJEKT / "konfiguration/v3.json"
INVENTAR = PROJEKT / "ausgaben/privat/inventar/dateninventar.json"
BASIS = "9c202ed85e6b9a530fb8e65d806c84805cb56117"


@dataclass(frozen=True)
class Eingaben:
    roh: Path
    v1: Path = V1
    v2: Path = V2
    ziel: Path = V3
    konfig: Path = KONFIG

    def __post_init__(self) -> None:
        roh, ziel = self.roh.resolve(), self.ziel.resolve()
        if not roh.is_dir() or roh.is_relative_to(PROJEKT):
            raise ValueError("Separate, vorhandene Rohdatenwurzel angeben.")
        if not ziel.is_relative_to(V3.resolve()):
            raise ValueError("Ergebnisse gehören in den privaten V3-Ausgabeordner.")

    def original(self, bild: dict, *, verifizieren: bool = True) -> Path:
        pfad = quellpfad(self.roh, bild["pfad"])
        if verifizieren and dateihashes(pfad)[0] != bild["sha256"]:
            raise ValueError(f"SHA-256 des Originals abweichend: {bild['id']}")
        return pfad


def integritaet(e: Eingaben) -> dict:
    i = lese_json(INVENTAR)
    roh = e.roh.resolve()
    erwartet = {q["pfad"]:q["sha256"] for q in i["dateien"]}
    aktuell = {p.relative_to(roh).as_posix() for p in sichtbare_dateien(roh, PROJEKT)}
    abweichungen = []
    for name in sorted(aktuell & erwartet.keys()):
        if dateihashes(quellpfad(roh,name))[0] != erwartet[name]:
            abweichungen.append(name)
    return {"dateien":len(aktuell), "inventar_sha256":dateihashes(INVENTAR)[0],
            "abweichungen":abweichungen,"fehlende":sorted(erwartet.keys()-aktuell),
            "unbekannte":sorted(aktuell-erwartet.keys())}


def audit_v2(e: Eingaben) -> dict:
    original = lese_json(e.v2/"laufmanifest.json")
    wiederholung = e.v2/"v3-reproduktion"
    baseline = lese_json(e.v2/"v3-eingang/baseline.json")
    artefakte = []
    for name, digest in original["artefakte"].items():
        a, b = dateihashes(e.v2/name)[0], dateihashes(wiederholung/name)[0]
        artefakte.append({"datei":name, "archiv_ok":a==digest, "bytegleich":a==b})
    bericht = {"basis_commit":BASIS, "eingangspruefung":baseline, "artefakte":artefakte}
    json_schreiben(e.ziel/"v2-audit.json", bericht)
    if not all(q["archiv_ok"] and q["bytegleich"] for q in artefakte):
        print("V2-Reproduktionsabweichungen siehe v2-audit.json", flush=True)
    else:
        print(f"V2: {len(artefakte)} Artefakte bytegleich reproduziert.", flush=True)
    return bericht
