"""Batchlauf für registrierte GP2-Aufnahmen, Sensitivität und Modellvergleich."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import csv
import hashlib
from importlib.metadata import version
import io
import json
from pathlib import Path
import re

import numpy as np
from PIL import Image

from .abbildungen import bildtafel, spektrum_abbildung, sweep_abbildung, ueberlagerung
from .bildpipeline import BildParameter, Geometrie, analysiere_bild, diagnostik, jaccard, linienabstand
from .eigenmoden import Platte, berechne_eigenmoden
from .frequenzen import Frequenzbeleg, bewertete_frequenz, lese_hz
from .inventar import lade_bild, registriere_heif
from .mustervergleich import rangliste, rekonstruiere
from .provenienz import atomar_schreiben, dateihashes, json_schreiben, quellpfad
from .registrierung import verfeinere_ecken

PROJEKT = Path(__file__).resolve().parents[1]
VERGLEICH = {"IMG_1597", "IMG_1601", "IMG_1457", "IMG_3115", "0_3843Hz"}
TAFELN = VERGLEICH | {"IMG_3070"}


def lese_json(datei: Path) -> dict | list:
    return json.loads(datei.read_text(encoding="utf-8-sig"))


def lade_registrierungen(datei: Path, inventar: dict) -> list[dict]:
    index = {(Path(p).parent.name, Path(p).name): p for p in inventar if "Ausgeschnitten" not in Path(p).parts}
    liste = []
    with datei.open(encoding="utf-8-sig", newline="") as strom:
        for z in csv.DictReader(strom, delimiter=";"):
            l, t, r, b, w, h, sx, sy = (float(z[k]) for k in ("l", "t", "r", "b", "w", "h", "sx", "sy"))
            serie, ident = z["serie"], z["id"]
            if not re.fullmatch(r"[A-Za-z0-9_-]+", ident):
                raise ValueError(f"Ungültige ID: {ident}")
            filename = ident + "." + z["endung"]
            pfad = index[(serie, filename)]
            quelle = "Rechtes Multimeter" if serie == "Bilder 380" else "Multimeter"
            text = z["anzeige"] + " kHz"
            belege = []
            if serie != "1":
                belege.append(Frequenzbeleg(serie, serie, float(serie.split()[-1]), "ordnername", "heuristisch", "ordner"))
            if z["anzeige"].endswith(" A"):
                belege.append(Frequenzbeleg(quelle, z["anzeige"], None, "sichtablesung",
                                           "manuell_gelesen", "anderes_observable"))
            elif z["anzeige"]:
                belege.append(Frequenzbeleg(quelle, text, lese_hz(text), "sichtablesung", "manuell_gelesen", "einzelbild"))
            if z.get("strom_a"):
                belege.append(Frequenzbeleg("Linkes Multimeter", z["strom_a"] + " A", None,
                                           "sichtablesung", "manuell_gelesen", "anderes_observable"))
            if z["handschrift_hz"]:
                text = z["handschrift_hz"] + " Hz"
                belege.append(Frequenzbeleg("Handschrift", text, lese_hz(text), "sichtablesung",
                                           "manuell_gelesen", "einzelbild"))
            if z["dateinamen_hz"]:
                belege.append(Frequenzbeleg("Dateiname", filename, float(z["dateinamen_hz"]),
                                            "dateinamenskonvention", "heuristisch", "einzelbild"))
            ecken = ((l/w, t/h), (r/w, t/h), (r/w, b/h), (l/w, b/h))
            if z.get("ecken_xy"):
                ecken = tuple((float(x)/w, float(y)/h)
                              for x,y in (paar.split(",") for paar in z["ecken_xy"].split("|")))
            geom = Geometrie(ecken, (sx/w, sy/h))
            liste.append({"id": ident, "pfad": pfad, "serie": serie, "geom": geom,
                          "eckmethode": z.get("methode") or "lokaler_kantengradient",
                          "anzeige_roi": [float(v) for v in z["roi"].split(",")] if z["roi"] else None,
                          "klasse": z.get("klasse") or "Platte mit Sandmuster und Messgerät",
                          "belege": belege})
    if len(liste) != len({e["id"] for e in liste}):
        raise ValueError("Analyse-IDs müssen eindeutig sein.")
    return liste


def varianten(bild, geom: Geometrie, p: BildParameter, cfg: dict):
    for schwelle in cfg["schwellen_pilot"]:
        yield f"schwelle_{schwelle}", analysiere_bild(bild, geom, replace(p, schwelle=schwelle))
    ecken = np.asarray(geom.ecken)
    muster = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]])
    for vorzeichen in (-1, 1):
        e = tuple(map(tuple, np.clip(ecken + vorzeichen * cfg["eckenstoerung_rel"] * muster, 0, 1)))
        yield f"ecken_{vorzeichen:+d}", analysiere_bild(bild, replace(geom, ecken=e), p)
    yield "lokal", analysiere_bild(bild, geom, replace(p, schwelle=cfg["lokal_schwelle"]), "lokal")


def verarbeite(e: dict, roh: Path, ziel: Path, cfg: dict, inv: dict, modelle: list, signatur: str) -> dict:
    ident = e["id"]
    quelle = quellpfad(roh, e["pfad"])
    sha = dateihashes(quelle)[0]
    if sha != inv["sha256"]:
        raise ValueError(f"{ident}: SHA-256 weicht vom Inventar ab.")
    ordner = ziel / ident
    datei = ordner / "analyse.json"
    cachekey = hashlib.sha256((signatur + sha + repr(e)).encode()).hexdigest()
    if datei.is_file():
        alt = lese_json(datei)
        if alt.get("cachekey") == cachekey and all((ordner / n).is_file() for n in alt["artefakte"]):
            return alt
    ordner.mkdir(parents=True, exist_ok=True)
    bild = lade_bild(quelle)
    if e["eckmethode"] == "manuell":
        geom, fit = e["geom"], {}
    elif e["eckmethode"] == "lokaler_kantengradient":
        geom, fit = verfeinere_ecken(bild, e["geom"])
    else:
        raise ValueError(f"Unbekannte Eckmethode: {e['eckmethode']}")
    p = BildParameter(**cfg["bild_parameter"])
    res = analysiere_bild(bild, geom, p)
    if not res.linien.any():
        raise ValueError(f"{ident}: keine auswertbaren Skelettpixel.")
    f = bewertete_frequenz(e["belege"])
    zahlen = diagnostik(res)
    preview = bild.copy()
    preview.thumbnail((1050, 950))
    preview.save(ordner / "original-vorschau.jpg", quality=92)
    Image.fromarray(res.rgb).save(ordner / "platte.png")
    Image.fromarray(ueberlagerung(res.rgb, res.linien, res.gueltig)).save(ordner / "linien.png")
    artefakte = ["original-vorschau.jpg", "platte.png", "linien.png", "raster.npz"]
    stoerungen = {}
    raster = {"sand": res.sand, "linien": res.linien, "sicht": res.gueltig, "score": res.sandscore}
    pruefe_stoerungen = e["serie"] == cfg["serie_pilot"] or ident in TAFELN
    for name, anderes in varianten(bild, geom, p, cfg) if pruefe_stoerungen else ():
        diagnose = diagnostik(anderes)
        stoerungen[name] = {"sand_jaccard_zur_basis": jaccard(res.sand, anderes.sand, res.gueltig & anderes.gueltig),
                            "abdeckung_rel": diagnose["abdeckung_rel"],
                            "breite_edt_median_rel": diagnose["breite_edt_median_rel"]}
        raster[f"{name}_linien"], raster[f"{name}_sicht"] = anderes.linien, anderes.gueltig
    np.savez_compressed(ordner / "raster.npz", **raster)
    ranking, feld, modelltext = [], None, ""
    if ident in VERGLEICH:
        vergleich = analysiere_bild(bild, geom, replace(p, raster=128))
        ranking = rangliste(modelle, vergleich.linien, vergleich.gueltig, f["hz"])
        if ranking:
            erster = ranking[0]
            modell = next(m for m in modelle if m.rand == erster.rand)
            feld = rekonstruiere(modell, erster, 272)
            modelltext = f"Modell · {erster.rand} #{'/'.join(map(str, erster.moden))}"
            np.save(ordner / "modellfeld.npy", feld)
            artefakte.append("modellfeld.npy")
    if ident in TAFELN:
        freqquelle = next((b.quelle for b in e["belege"] if b.hz == f["hz"] and
                           b.konfidenz == "manuell_gelesen"), "Foto")
        freq = f"{f['hz']:g} Hz ({freqquelle})" if f["hz"] is not None else f["status"].capitalize()
        bildtafel(bild, res, f"Sandstruktur bei {freq}", f"{ident}   /   GP2 HHU   /   "
                  "Registrierung und Farbsegmentierung", zahlen, ordner / "bildtafel", feld, modelltext)
        artefakte.extend(["bildtafel.png", "bildtafel.svg", "bildtafel.pdf"])
    frequenzranking = sorted(ranking, key=lambda k: k.abstand_hz) if ranking and f["hz"] is not None else []
    bericht = {"id": ident, "pfad": e["pfad"], "serie": e["serie"], "klasse": e["klasse"],
               "sha256": sha, "exif": inv.get("exif", {}), "cachekey": cachekey, "hz": f["hz"],
               "frequenzstatus": f["status"], "frequenzbelege": [asdict(b) for b in e["belege"]],
               "anzeige_roi": e["anzeige_roi"], "geometrie_seed": asdict(e["geom"]),
               "geometrie": asdict(geom), "registrierung": {"methode": e["eckmethode"], **fit},
               **zahlen, "sensitivitaet": stoerungen,
               "bildranking": [asdict(k) for k in ranking], "vergleichsraster": 128 if ranking else None,
               "frequenzranking": [asdict(k) for k in frequenzranking], "artefakte": artefakte}
    json_schreiben(datei, bericht)
    return bericht


def sweep(zeilen: list[dict], ziel: Path, cfg: dict) -> list[dict]:
    gruppe = [d for d in zeilen if d["serie"] == cfg["serie_pilot"] and d["hz"] is not None]
    referenz = next((z for z in gruppe if z["id"] == cfg["sweep_referenz"]), None)
    if referenz is None:
        return []
    bilder = {}
    with np.load(ziel / referenz["id"] / "raster.npz") as ref:
        for zeile in gruppe:
            q = ziel / zeile["id"]
            with Image.open(q / "platte.png") as bild:
                bilder[zeile["id"]] = np.asarray(bild)
            with np.load(q / "raster.npz") as a:
                abstand = linienabstand(a["linien"], ref["linien"], a["sicht"] & ref["sicht"])
                zeile["abstand_referenz_rel"], zeile["abstand_referenz_q95_rel"] = abstand or (None, None)
                sensitiv = {}
                for name in zeile["sensitivitaet"]:
                    paar = linienabstand(a[name+"_linien"], ref[name+"_linien"], a[name+"_sicht"] & ref[name+"_sicht"])
                    sensitiv[name] = paar[0] if paar else None
                zeile["abstand_varianten_rel"] = sensitiv
            zeile["abstand_referenz_rel_bereich"] = [v for k, v in sensitiv.items() if k != "lokal" and v is not None]
            zeile["abdeckung_rel_bereich"] = [v["abdeckung_rel"] for k, v in zeile["sensitivitaet"].items()
                                              if k != "lokal" and v["abdeckung_rel"] is not None]
    sweep_abbildung(gruppe, bilder, ziel / "sweep-4122-4128")
    return sorted(gruppe, key=lambda z: (z["hz"], z["id"]))


def export_csv(pfad: Path, zeilen: list[dict]) -> None:
    felder = ["id", "serie", "pfad", "sha256", "hz", "frequenzstatus", "abdeckung_rel",
              "breite_edt_median_rel", "skelett_komponenten_8", "endpunkte_8", "verzweigungscluster_8",
              "abstand_referenz_rel", "abstand_referenz_q95_rel", "fehler"]
    aus = io.StringIO()
    w = csv.DictWriter(aus, fieldnames=felder, extrasaction="ignore")
    w.writeheader()
    w.writerows(zeilen)
    atomar_schreiben(pfad, aus.getvalue())


def batch(rohdaten: Path, konfig: Path, registrierungen: Path) -> int:
    registriere_heif()
    cfg = lese_json(konfig)
    ziel = (PROJEKT / cfg["ausgabe"]).resolve()
    if not ziel.is_relative_to(PROJEKT):
        raise ValueError("Ausgaben müssen im Forschungsprojekt liegen.")
    ziel.mkdir(parents=True, exist_ok=True)
    inv_pfad = PROJEKT / cfg["inventar"]
    inventar = {d["pfad"]: d for d in lese_json(inv_pfad)["dateien"]}
    bilder = lade_registrierungen(registrierungen, inventar)
    libs = {p: version(p) for p in ("numpy", "scipy", "pillow", "pillow-heif", "scikit-image", "matplotlib")}
    analyse_module = ("abbildungen", "auswertung", "bildpipeline", "eigenmoden", "frequenzen",
                      "inventar", "mustervergleich", "provenienz", "registrierung")
    code = {name: dateihashes(Path(__file__).with_name(name + ".py"))[0] for name in analyse_module}
    signatur = json.dumps([cfg, libs, code], sort_keys=True)
    platte = Platte(**cfg["platte"])
    modelle = [berechne_eigenmoden(platte, rand, cfg["grad"], cfg["moden"], cfg["radius_m"], cfg["feder_n_m"])
               for rand in cfg["modellvergleich"]]
    zeilen, fehler = [], []
    for e in bilder:
        try:
            erg = verarbeite(e, rohdaten, ziel, cfg, inventar[e["pfad"]], modelle, signatur)
        except (OSError, ValueError, KeyError, ArithmeticError, np.linalg.LinAlgError) as exc:
            fehler.append({"id": e["id"], "pfad": e["pfad"], "serie": e["serie"],
                            "frequenzstatus": "nicht_ausgewertet", "fehler": str(exc)})
            print(f"{e['id']}: {exc}", flush=True)
        else:
            zeilen.append(erg)
            print(f"{erg['id']}: {erg['frequenzstatus']}", flush=True)
    sweep_zeilen = sweep(zeilen, ziel, cfg)
    export_csv(ziel / "kennzahlen.csv", zeilen + fehler)
    export_csv(ziel / "sweep.csv", sweep_zeilen)
    json_schreiben(ziel / "atlas.json", {"versionen": libs, "code_sha256": code, "konfiguration": cfg,
                                        "registrierungen_sha256": dateihashes(registrierungen)[0],
                                        "inventar_sha256": dateihashes(inv_pfad)[0],
                                        "bilder": zeilen, "fehler": fehler})
    ziel_modell = PROJEKT / "ausgaben" / "modelle"
    ziel_modell.mkdir(parents=True, exist_ok=True)
    spektrum_abbildung(ziel_modell / "befestigungsvergleich")
    print(f"{len(zeilen)} verarbeitet; {len(fehler)} fehlgeschlagen.", flush=True)
    return int(bool(fehler))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("rohdaten", type=Path)
    ap.add_argument("--konfig", type=Path, default=PROJEKT / "konfiguration/pilot.json")
    ap.add_argument("--registrierungen", type=Path, default=PROJEKT / "konfiguration/registrierungen.csv")
    args = ap.parse_args()
    raise SystemExit(batch(args.rohdaten, args.konfig, args.registrierungen))
