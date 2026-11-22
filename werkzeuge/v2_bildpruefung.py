"""Prüfe V1 gegen separat markierte Geometrie und eine maschinelle HSV-Teilreferenz."""
from __future__ import annotations
from argparse import ArgumentParser
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.color import rgb2hsv
from skimage.morphology import skeletonize
from skimage.transform import ProjectiveTransform

from chladni.auswertung import PROJEKT, lese_json
from chladni.bildpipeline import BildParameter, Geometrie, analysiere_bild, diagnostik, jaccard, linienabstand
from chladni.inventar import lade_bild, registriere_heif
from chladni.provenienz import dateihashes, json_schreiben, quellpfad


def hue_referenz(rgb: np.ndarray, region: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    hsv = rgb2hsv(rgb)
    h, s, v = np.moveaxis(hsv, -1, 0)
    blau = (h >= 0.49) & (h <= 0.72)
    fg = region & blau & (s >= 0.34) & (v >= 0.21)
    bg = region & (v >= 0.15) & ((s <= 0.12) | ((h <= 0.39) | (h >= 0.83)))
    full = ndi.median_filter(region & blau & (s >= 0.24) & (v >= 0.19), size=3) & region
    return fg, bg, full


def test_metriken(vorhersage: np.ndarray, positiv: np.ndarray, negativ: np.ndarray) -> dict:
    tp, fp, fn, tn = (int(m.sum()) for m in (vorhersage & positiv, vorhersage & negativ,
                                             ~vorhersage & positiv, ~vorhersage & negativ))
    return {"iou": tp / (tp+fp+fn), "praezision": tp / (tp+fp), "recall": tp / (tp+fn),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def homographie(g: Geometrie) -> ProjectiveTransform:
    h = ProjectiveTransform.from_estimate(np.asarray(g.ecken), np.array([[0,0],[1,0],[1,1],[0,1]]))
    if not h:
        raise ArithmeticError("Homographie der Referenzschätzung ist singulär.")
    return h


def bildeinfluesse(im: Image.Image):
    a = np.asarray(im, dtype=np.float32) / 255
    for name, f in (("dunkler", 0.85), ("heller", 1.15),
                    ("waermer", [1.08,1,0.92]), ("kaelter", [0.92,1,1.08])):
        yield name, Image.fromarray(np.uint8(np.clip(a*f,0,1)*255+0.5))
    for name, f in (("kontrast_minus",0.8), ("kontrast_plus",1.2)):
        yield name, Image.fromarray(np.uint8(np.clip(0.5+(a-0.5)*f,0,1)*255+0.5))


def stoerungen(im: Image.Image, geom: Geometrie, p: BildParameter):
    for name, s in (("schwelle_minus", -0.02), ("schwelle_plus", 0.02)):
        yield name, analysiere_bild(im,geom,replace(p,schwelle=p.schwelle+s))
    muster = np.array([[-1,-1],[1,-1],[1,1],[-1,1]])
    e = np.asarray(geom.ecken)
    for richtung in (-1,1):
        g = replace(geom,ecken=tuple(map(tuple,e+richtung*0.004*muster)))
        yield f"ecken_{richtung:+d}", analysiere_bild(im,g,p)
        for achse in (0,1):
            pos = np.array(geom.schraube)
            pos[achse] += richtung*0.012
            yield f"schraube_{achse}_{richtung:+d}", analysiere_bild(im,replace(geom,schraube=tuple(pos)),p)
    # Störungen im Rohfarbraum vor der Homographie. 1500 px reichen für den 512px-Plattenausschnitt.
    kopie = im.copy()
    kopie.thumbnail((1500,1500),Image.Resampling.LANCZOS)
    basis_rgb = analysiere_bild(kopie,geom,p)
    for name, mod in bildeinfluesse(kopie):
        yield name, analysiere_bild(mod,geom,p)
    yield "skalierungs_kontrolle", basis_rgb


def analyse(rohdaten: Path, ziel: Path) -> dict:
    alt = PROJEKT/"ausgaben/privat/analyse/atlas.json"
    atlas = lese_json(alt)
    p = BildParameter(**atlas["konfiguration"]["bild_parameter"])
    vorlage = PROJEKT/"konfiguration/v2_bildreferenz.json"
    ref = lese_json(vorlage)
    gruppen = {z["id"]:z for z in atlas["bilder"] if z["serie"] == ref["serie"]}
    if gruppen.keys() != ref["eckmarkierungen"].keys():
        raise ValueError("Referenz muss alle Aufnahmen der zurückgehaltenen Serie enthalten.")
    ziel.mkdir(exist_ok=True,parents=True)
    rasterspeicher, werte = {}, []
    x = np.linspace(0.1,0.9,5)
    netz = np.stack(np.meshgrid(x,x),axis=-1).reshape(-1,2)
    registriere_heif()
    for id,r in ref["eckmarkierungen"].items():
        z = gruppen[id]
        if z["hz"] != r["hz_gelesen"]:
            raise ValueError(f"Displayablesung widerspricht V1 bei {id}.")
        quelle = quellpfad(rohdaten,z["pfad"])
        if dateihashes(quelle)[0] != z["sha256"]:
            raise ValueError(f"Falsches Original: {id}")
        im = lade_bild(quelle)
        geom = Geometrie(**z["geometrie"])
        e = np.asarray(r["ecken"]) / ref["markierungsraster_px"]
        s = np.asarray(r["schraube"]) / ref["markierungsraster_px"]
        manuell = Geometrie(tuple(map(tuple,e)),tuple(s))
        vorhersage = analysiere_bild(im,geom,p)
        alternativ = analysiere_bild(im,manuell,p)
        h1,h2 = homographie(geom),homographie(manuell)
        delta = np.linalg.norm(h1(h2.inverse(netz))-netz,axis=1)
        # Masken im manuell entzerrten Raster. V1-Maske projiziert in diesen Rahmen.
        pixel = (np.arange(p.raster)+0.5)/p.raster
        p_xy=np.stack(np.meshgrid(pixel,pixel),axis=-1).reshape(-1,2)
        xy = ((h1(h2.inverse(p_xy))*p.raster)-0.5).T[::-1]
        def umrastern(a: np.ndarray) -> np.ndarray:
            return ndi.map_coordinates(a,xy,order=0,mode="constant",cval=0).reshape(a.shape)
        sicht = alternativ.gueltig & umrastern(vorhersage.gueltig)
        fg,bg,hsv_full = hue_referenz(alternativ.rgb,sicht)
        sand = umrastern(vorhersage.sand)
        linien = umrastern(vorhersage.linien)
        m = test_metriken(sand,fg,bg)
        m["sicht_annotiert"] = float((fg|bg).sum()/sicht.sum())
        m["iou_vollmasken"] = jaccard(sand,hsv_full,sicht)
        m["linienabstand_vollmasken_rel"] = linienabstand(linien,skeletonize(hsv_full),sicht)
        m["gitter_mittel_rel"] = float(delta.mean())
        m["gitter_max_rel"] = float(delta.max())
        m["schraubendifferenz_rel"] = float(np.linalg.norm(h1(s[None,:])[0] - vorhersage.schraube_xy))
        stoerungswerte = {}
        for name, variant in stoerungen(im,geom,p):
            g = vorhersage.gueltig & variant.gueltig
            stoerungswerte[name] = {"iou_basis": jaccard(vorhersage.sand,variant.sand,g),
                                    "linienabstand_basis": linienabstand(vorhersage.linien,variant.linien,g),
                                    "abdeckung_rel":diagnostik(variant)["abdeckung_rel"]}
            rasterspeicher[f"{id}_{name}_linie"] = variant.linien
            rasterspeicher[f"{id}_{name}_sicht"] = variant.gueltig
        rasterspeicher.update({f"{id}_sand":vorhersage.sand, f"{id}_linie":vorhersage.linien,
                               f"{id}_sicht":vorhersage.gueltig,f"{id}_rgb":alternativ.rgb,
                               f"{id}_fg":fg,f"{id}_bg":bg,f"{id}_v1_ref":sand, f"{id}_hsv":hsv_full})
        werte.append({"id":id,"hz":r["hz_gelesen"],"pfad":z["pfad"],"sha256":z["sha256"],
                      "geometrie_v1":z["geometrie"],"abdeckung_rel":diagnostik(vorhersage)["abdeckung_rel"],
                      "referenz":m,"stoerung":stoerungswerte})
        print(f"{id} · {r['hz_gelesen']} Hz · Masken-IoU {m['iou']:.3f} · Gitter {m['gitter_mittel_rel']:.4f}",flush=True)
    np.savez_compressed(ziel/"bildpruefung.npz",**rasterspeicher)
    zusammen = {name:float(np.median([z["referenz"][name] for z in werte]))
                for name in ("iou","praezision","recall","sicht_annotiert","iou_vollmasken")}
    zusammen["gitter_mittel_rel_max"] = max(z["referenz"]["gitter_mittel_rel"] for z in werte)
    test = (zusammen["iou"] >= 0.75 and zusammen["praezision"] >= 0.8 and zusammen["recall"] >= 0.8
            and zusammen["gitter_mittel_rel_max"] <= 0.025)
    result = {"serie":ref["serie"],"qualitaetskriterien_erfuellt":test,"referenztyp":"maschinell_hsv_teilmaske",
              "annotationen_sha256":dateihashes(vorlage)[0],"atlas_v1_sha256":dateihashes(alt)[0],
              "zusammenfassung":zusammen,"bilder":sorted(werte,key=lambda a:a["hz"])}
    json_schreiben(ziel/"bildpruefung.json",result)
    return zusammen


if __name__=="__main__":
    ap=ArgumentParser(description=__doc__)
    ap.add_argument("rohdaten",type=Path)
    ap.add_argument("--ziel",type=Path,default=PROJEKT/"ausgaben/privat/v2/g0")
    a=ap.parse_args()
    if not a.ziel.resolve().is_relative_to(PROJEKT/"ausgaben/privat/v2") or a.rohdaten.resolve().is_relative_to(PROJEKT):
        ap.error("V2-Ziel und separate Quellenwurzel erforderlich.")
    print(analyse(a.rohdaten,a.ziel))
