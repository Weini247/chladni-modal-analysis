"""Quantitativer Atlas, räumliche Profile und Nachbarschaft im Frequenzraum."""
from __future__ import annotations

import csv
import io
from itertools import pairwise
from pathlib import Path

import numpy as np

from .auswertung import lese_json
from .bildpipeline import jaccard, linienabstand
from .mustervergleich import transformiere
from .provenienz import atomar_schreiben, dateihashes, json_schreiben


def raumdichte(sand: np.ndarray, sicht: np.ndarray, felder: int = 4) -> list[list[float | None]]:
    """Bedeckung pro Plattenzelle. Maskierte Pixel gehören nicht zur Bezugsfläche."""
    if sand.shape != sicht.shape or sand.ndim != 2 or not 1 <= felder <= min(sand.shape):
        raise ValueError("Sand und Sicht benötigen ein gemeinsames Raster.")
    ergebnis = []
    for s, v in zip(np.array_split(sand,felder,axis=0), np.array_split(sicht,felder,axis=0), strict=True):
        ergebnis.append([float(np.count_nonzero(a & b)/b.sum()) if b.any() else None
                         for a,b in zip(np.array_split(s,felder,axis=1), np.array_split(v,felder,axis=1), strict=True)])
    return ergebnis


def paar(a: dict, b: dict, raster_a: dict, raster_b: dict) -> dict:
    sicht = raster_a["sicht"] & raster_b["sicht"]
    dist = linienabstand(raster_a["linien"],raster_b["linien"],sicht)
    return {"a":a["id"],"b":b["id"],"hz_a":a["hz"],"hz_b":b["hz"],
            "delta_hz":float(b["hz"]-a["hz"]),
            "delta_abdeckung":float(b["abdeckung_rel"]-a["abdeckung_rel"]),
            "iou_sand":jaccard(raster_a["sand"],raster_b["sand"],sicht),
            "linienabstand_rel":dist[0] if dist is not None else None,
            "linienabstand_q95_rel":dist[1] if dist is not None else None}


def _csv(pfad: Path, zeilen: list[dict]) -> None:
    if not zeilen:
        raise ValueError("Ein leerer Forschungsexport braucht ein Schema.")
    aus = io.StringIO()
    w = csv.DictWriter(aus, fieldnames=list(zeilen[0]))
    w.writeheader()
    w.writerows(zeilen)
    atomar_schreiben(pfad,aus.getvalue())


def erzeuge_atlas(v1: Path, ziel: Path, g0: Path, max_schritt_hz: float = 2.0) -> dict:
    a_pfad = v1/"atlas.json"
    a = lese_json(a_pfad)
    bilder, raster, gruppen, paare, chronologie = [], {}, {}, [], []
    for z in a["bilder"]:
        qp = v1/z["id"]/"raster.npz"
        with np.load(qp) as r:
            d = {name:r[name] for name in ("sand","sicht","linien")}
        raster[z["id"]] = d
        sand,sicht,linie = (d[k] for k in ("sand","sicht","linien"))
        d4 = [jaccard(sand,transformiere(sand,c),sicht & transformiere(sicht,c)) for c in range(8)]
        y,x = np.indices(sand.shape)/np.asarray(sand.shape)[:,None,None] - 0.5
        radius = np.hypot(x,y)
        rings = []
        for innen,aussen in pairwise([0.,.12,.25,.38,.5,.72]):
            v = sicht & (radius>=innen) & (radius<aussen)
            rings.append(float((sand&v).sum()/v.sum()) if v.any() else None)
        # Kontinuierliche Diagnostik. Schwache Skelettbelegung markiert Fälle zum Ansehen.
        flags = []
        if z["klasse"].startswith("Platte mit diffusem"):
            flags.append("diffuses_oder_schwaches_muster")
        if np.linalg.norm(np.asarray(z["schraube_xy"])-0.5) > .05:
            flags.append("schraube_ueber_5_prozent_vom_bildzentrum")
        if z["frequenzstatus"] != "manuell_gelesen":
            flags.append(z["frequenzstatus"])
        bilder.append({**{k:z[k] for k in ("id","pfad","sha256","serie","hz","frequenzstatus","frequenzbelege",
                       "geometrie","registrierung","abdeckung_rel","breite_edt_median_rel","klasse","exif",
                       "skelettpixel","skelett_komponenten_8","endpunkte_8","verzweigungscluster_8",
                       "eingeschlossene_hintergrundregionen_4")},
                       "d4_sand_iou":d4,"dichte_4x4":raumdichte(sand,sicht),"radiale_dichte":rings,
                       "linienpixel_pro_sichtpixel":float(linie.sum()/sicht.sum()),
                       "flags":flags,"raster_sha256":dateihashes(qp)[0]})
        gruppen.setdefault(z["serie"],[]).append(bilder[-1])
    zusammen = []
    for serie, gruppe in sorted(gruppen.items()):
        hz_gruppen: dict[float,list] = {}
        for z in gruppe:
            if z["hz"] is not None:
                hz_gruppen.setdefault(z["hz"],[]).append(z)
        for freq1,freq2 in pairwise(sorted(hz_gruppen)):
            if freq2-freq1 <= max_schritt_hz:
                for a0 in hz_gruppen[freq1]:
                    for b0 in hz_gruppen[freq2]:
                        paare.append({"serie":serie,**paar(a0,b0,raster[a0["id"]],raster[b0["id"]])})
        wiederholungen = [{"hz":f,"bilder":[z["id"] for z in g]} for f,g in sorted(hz_gruppen.items()) if len(g)>1]
        ausgabe_wiederholung = []
        for gruppe_w in wiederholungen:
            from itertools import combinations
            for aa,bb in combinations(gruppe_w["bilder"],2):
                a0,b0 = next(z for z in gruppe if z["id"]==aa), next(z for z in gruppe if z["id"]==bb)
                ausgabe_wiederholung.append(paar(a0,b0,raster[aa],raster[bb]))
        geordnet = sorted((d for d in gruppe if d["hz"] is not None and "aufnahmezeit" in d["exif"]),
                          key=lambda d: (d["exif"]["aufnahmezeit"],d["exif"].get("subsekunde_aufnahme",""),d["id"]))
        for a0,b0 in pairwise(geordnet):
            jahrestag = a0["exif"]["aufnahmezeit"].split()[0]
            if jahrestag != b0["exif"]["aufnahmezeit"].split()[0]:
                continue
            chronologie.append({"serie":serie,**paar(a0,b0,raster[a0["id"]],raster[b0["id"]])})
        p = [q["linienabstand_rel"] for q in paare if q["serie"]==serie and q["linienabstand_rel"] is not None]
        zusammen.append({"serie":serie,"fotos":len(gruppe),"frequenzen":sorted(hz_gruppen),"dichte_nachbarn":len(p),
                          "flaechenanteil_median":float(np.median([g["abdeckung_rel"] for g in gruppe])),
                          "mittlerer_linienabstand_median":float(np.median(p)) if p else None,
                          "wiederholungsbeobachtungen":ausgabe_wiederholung})
    del raster
    referenz = lese_json(g0/"bildpruefung.json")
    holdout = referenz["bilder"]
    verfahren = ["basis", *holdout[0]["stoerung"]]
    variante = {}
    with np.load(g0/"bildpruefung.npz") as archive:
        for v in verfahren:
            abdeckung = {z["hz"]: z["abdeckung_rel"] if v=="basis" else z["stoerung"][v]["abdeckung_rel"]
                         for z in holdout}
            nachbarn = []
            zusatz = "" if v=="basis" else f"{v}_"
            for a0,b0 in pairwise(holdout):
                def quelle(z):
                    pref=z["id"]+"_"+zusatz
                    return archive[pref+"linie"], archive[pref+"sicht"]
                l1,g1=quelle(a0)
                l2,g2=quelle(b0)
                dist = linienabstand(l1,l2,g1 & g2)
                nachbarn.append({"hz_a":a0["hz"],"hz_b":b0["hz"],"linienabstand_rel":dist[0] if dist else None})
            variante[v]={"abdeckung":abdeckung,"minimum_hz":min(abdeckung,key=abdeckung.get),
                         "nachbarn":nachbarn,"max_nachbar":max(nachbarn,key=lambda d:d["linienabstand_rel"] or 0)}
    ergebnis = {"schema":2,"v1_atlas_sha256":dateihashes(a_pfad)[0],"bildparameter":a["konfiguration"]["bild_parameter"],
                "max_nachbar_schritt_hz":max_schritt_hz,"radialringe":[0,.12,.25,.38,.5,.72],
                "serien":zusammen,"bilder":bilder,"chronologische_paare":len(chronologie),
                "frequenzpaare":len(paare),"zweitserie":{"name":referenz["serie"],"varianten":variante}}
    ziel.mkdir(parents=True,exist_ok=True)
    json_schreiben(ziel/"atlas.json",ergebnis)
    _csv(ziel/"frequenznachbarn.csv",paare)
    _csv(ziel/"aufnahmenachbarn.csv",chronologie)
    print(f"Atlas V2: {len(bilder)} Fotos, {len(zusammen)} Serien, {len(paare)} Frequenzpaare.",flush=True)
    return ergebnis
