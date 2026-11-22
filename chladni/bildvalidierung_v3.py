"""Gepaarte Bildstörungen, Sweep-Vergleich und verblindete Stichprobe."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from itertools import combinations, pairwise, product
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.morphology import medial_axis, skeletonize, thin

from .auswertung import lese_json
from .bildpipeline import BildParameter, Geometrie, jaccard, linienabstand, plattenperspektive
from .bildpipeline import sandscore, segmentiere, sichtmaske
from .inventar import lade_bild, registriere_heif
from .provenienz import dateihashes, json_schreiben
from .v3_pfade import Eingaben


@dataclass(frozen=True)
class Beobachtung:
    sand: np.ndarray
    linien: np.ndarray
    sicht: np.ndarray

    @property
    def bedeckung(self) -> float:
        if not self.sicht.any():
            raise ValueError("Keine sichtbare Plattenfläche.")
        return float((self.sand & self.sicht).sum()/self.sicht.sum())


def _bildwert(rgb, p, sicht):
    sand, linien = segmentiere(sandscore(rgb, "blau", p), sicht, p)
    return Beobachtung(sand, linien, sicht)


def bildvarianten(im: Image.Image, g: Geometrie, p: BildParameter, c: dict):
    """Erzeuge jede technische Störung einzeln, in normierten Plattenkoordinaten."""
    rgb, mitte = plattenperspektive(im, g, p.raster)
    sicht = sichtmaske(p.raster, mitte, p, g.verdeckt)
    basis = _bildwert(rgb, p, sicht)
    yield "basis", basis
    for name, sign in (("weniger", -1), ("mehr", 1)):
        pp = replace(p, schwelle=p.schwelle + sign*c["schwelle_delta"])
        yield f"schwelle_{name}", _bildwert(rgb, pp, sicht)
    a = rgb.astype(np.float32)/255
    u = (np.arange(p.raster)+.5)/p.raster
    x,y = np.meshgrid(u,u)
    schatten = 1 - c["schatten"] / (1 + np.exp((x+.23*y-.57)*32))
    reflex = c["glanz"]*np.exp(-((x-.68)**2+(y-.36)**2)/.035)
    farbe = c["farbe_delta"]
    photometrie = {
        "belichtung_dunkel": a*(1-c["belichtung_delta"]),
        "belichtung_hell": a*(1+c["belichtung_delta"]),
        "kontrast_schwach": .5+(a-.5)*(1-c["kontrast_delta"]),
        "kontrast_stark": .5+(a-.5)*(1+c["kontrast_delta"]),
        "farbstich_warm": a*np.array([1+farbe,1,1-farbe]),
        "farbstich_kalt": a*np.array([1-farbe,1,1+farbe]),
        "schatten_lokal": a*schatten[...,None],
        "reflex_lokal": a+(1-a)*reflex[...,None],
    }
    for name, rgb0 in photometrie.items():
        yield name, _bildwert(np.uint8(np.rint(255*np.clip(rgb0,0,1))),p,sicht)
    for name, sign in (("links", -1), ("rechts", 1)):
        e=np.asarray(g.ecken).copy()
        e[0] += sign*c["eckversatz_rel"]*np.array([1.,-.6])
        e[2] += sign*c["eckversatz_rel"]*np.array([.2,1.])
        rgb0, m=plattenperspektive(im,replace(g,ecken=tuple(map(tuple,e))),p.raster)
        yield f"ecken_{name}", _bildwert(rgb0,p,sichtmaske(p.raster,m,p,g.verdeckt))
    for name, sign in (("links",-1),("rechts",1)):
        m=(mitte[0]+sign*c["zentrum_delta_rel"],mitte[1])
        yield f"zentrum_{name}", _bildwert(rgb,p,sichtmaske(p.raster,m,p,g.verdeckt))
    pp=replace(p,schraubenradius_rel=p.schraubenradius_rel+c["schraubenradius_delta"])
    yield "schraubenmaske_groesser", _bildwert(rgb,pp,sichtmaske(p.raster,mitte,pp,g.verdeckt))
    radius=c["morph_radius_px"]
    struktur=ndi.iterate_structure(ndi.generate_binary_structure(2,1), radius)
    masken={
        "morph_oeffnen":ndi.binary_opening(basis.sand,structure=struktur),
        "morph_schliessen":ndi.binary_closing(basis.sand,structure=struktur),
        "linien_duenn":ndi.binary_erosion(basis.sand,structure=struktur),
        "linien_breit":ndi.binary_dilation(basis.sand,structure=struktur),
    }
    for name, maske in masken.items():
        maske &= sicht
        yield name, Beobachtung(maske,skeletonize(maske),sicht)
    yield "skelett_thin", Beobachtung(basis.sand,thin(basis.sand),sicht)
    yield "skelett_medial", Beobachtung(basis.sand,medial_axis(basis.sand,rng=2026),sicht)


def bildvergleich(a: Beobachtung,b: Beobachtung) -> dict:
    sichtbar=a.sicht & b.sicht
    d=linienabstand(a.linien,b.linien,sichtbar)
    return {"abstand_rel":d[0] if d else None, "abstand_q95_rel":d[1] if d else None,
            "iou":jaccard(a.sand,b.sand,sichtbar),"gemeinsame_flaeche_rel":float(sichtbar.mean())}


def bewerte_frequenzen(fotos: list[dict], varianten: dict, name: str) -> dict:
    gruppen=defaultdict(list)
    for q in fotos:
        if q["hz"] is not None:
            gruppen[q["hz"]].append(q)
    paare=[]
    for a,b in pairwise(sorted(gruppen)):
        werte=[]
        ids=[]
        for f,g in product(gruppen[a],gruppen[b]):
            o=bildvergleich(varianten[f["id"]][name],varianten[g["id"]][name])
            ids.append({"a":f["id"],"b":g["id"],**o})
            if o["abstand_rel"] is not None:
                werte.append(o["abstand_rel"])
        paare.append({"von":a,"bis":b,"abstand_rel":float(np.median(werte)) if werte else None,
                      "auswertbare_paare":len(werte),"paare":ids})
    geordnet=sorted((p for p in paare if p["abstand_rel"] is not None),key=lambda d:-d["abstand_rel"])
    flaeche={f:float(np.median([varianten[q["id"]][name].bedeckung for q in gruppen[f]]))
             for f in sorted(gruppen)}
    sieger=geordnet[0] if geordnet else None
    abstand=(sieger["abstand_rel"]-geordnet[1]["abstand_rel"]) if len(geordnet)>1 else None
    return {"paare":paare,"staerkstes_paar":[sieger["von"],sieger["bis"]] if sieger else None,
            "siegerabstand_rel":abstand,"flaeche_rel":flaeche,
            "min_hz":min(flaeche,key=flaeche.get) if flaeche else None}


def stichprobe(fotos: list[dict]) -> list[dict]:
    gruppen=defaultdict(dict)
    for q in sorted(fotos,key=lambda d:d["id"]):
        if q["hz"] is not None:
            gruppen[q["serie"]].setdefault(q["hz"],q)
    auswahl=[]
    for serie,f in sorted(gruppen.items()):
        hz=sorted(f)
        for j in sorted({0,(len(hz)-1)//2,len(hz)-1}):
            z=f[hz[j]]
            auswahl.append({k:z[k] for k in ("id","serie","hz","pfad","sha256")})
    return auswahl


def bildstudie(e: Eingaben,cfg: dict) -> dict:
    registriere_heif()
    a=lese_json(e.v1/"atlas.json")
    bp=BildParameter(**{**a["konfiguration"]["bild_parameter"],"raster":cfg["bild"]["raster"]})
    aus=e.ziel/"bildvarianten"
    aus.mkdir(parents=True,exist_ok=True)
    fotos=[q for q in a["bilder"] if q["serie"] in cfg["serien"]]
    foto_diagnose, resultate = [], {}
    for q in fotos:
        im=lade_bild(e.original(q))
        vv=dict(bildvarianten(im,Geometrie(**q["geometrie"]),bp,cfg["bild"]))
        np.savez_compressed(aus/f"{q['id']}.npz",namen=list(vv),
            linien=np.stack([v.linien for v in vv.values()]), sicht=np.stack([v.sicht for v in vv.values()]))
        resultate[q["id"]]=vv
        foto_diagnose.append({"id":q["id"],"serie":q["serie"],"hz":q["hz"],"sha256":q["sha256"],
                              "varianten":{k:{**bildvergleich(vv["basis"],d),"bedeckung_rel":d.bedeckung}
                                            for k,d in vv.items()}})
        print(f"Bild V3 · {q['id']} · {len(vv)} Einstellungen",flush=True)
    sweeps={}
    for name in cfg["serien"]:
        g=[q for q in fotos if q["serie"]==name]
        varianten={k:bewerte_frequenzen(g,resultate,k) for k in next(iter(resultate.values()))}
        wdh=[{"id_a":x["id"],"id_b":y["id"],"hz":x["hz"],
              **bildvergleich(resultate[x["id"]]["basis"],resultate[y["id"]]["basis"])}
             for x,y in combinations(g,2) if x["hz"] is not None and x["hz"]==y["hz"]]
        chrono=sorted((q for q in g if q["exif"].get("aufnahmezeit")),
                     key=lambda q:(q["exif"]["aufnahmezeit"],q["exif"].get("subsekunde_aufnahme",""),q["id"]))
        sequenz=[{"id":q["id"],"hz":q["hz"],"zeit":q["exif"]["aufnahmezeit"]} for q in chrono]
        sweeps[name]={"varianten":varianten,"wiederholungen":wdh,"zeitfolge":sequenz,
                      "sieger_haeufigkeiten":dict(Counter(str(x["staerkstes_paar"]) for x in varianten.values()))}
    result={"schema":3,"v1_sha256":dateihashes(e.v1/"atlas.json")[0],
            "fotos":foto_diagnose,"sweeps":sweeps,
            "annotation":{"status_unabhaengige_menschliche_referenz":"BLOCKED",
                          "stichprobe":stichprobe(fotos),"automatische_masken_sind_ground_truth":False}}
    json_schreiben(e.ziel/"bildstudie.json",result)
    return result
