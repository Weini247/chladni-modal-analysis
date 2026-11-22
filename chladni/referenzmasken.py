"""Vergleich beider Segmentierungen mit teilannotierten GP2-Referenzmasken."""
import argparse
from dataclasses import replace
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw

from .abbildungen import speichere, stil
from .auswertung import PROJEKT, lese_json
from .bildpipeline import BildParameter, jaccard, sandscore, segmentiere
from .provenienz import dateihashes, json_schreiben


def maske(polygone: list, n: int) -> np.ndarray:
    raster = Image.new("1", (n,n))
    draw = ImageDraw.Draw(raster)
    for p in polygone:
        draw.polygon([tuple(x) for x in p], fill=1)
    return np.asarray(raster)


def bilanz(positiv: np.ndarray, negativ: np.ndarray, result: np.ndarray) -> dict:
    tp, fn, fp, tn = (int(a.sum()) for a in (positiv & result, positiv & ~result,
                                              negativ & result, negativ & ~result))
    return {"TP": tp, "FN": fn, "FP": fp, "TN": tn,
            "iou": jaccard(positiv, result, positiv | negativ),
            "sensitivitaet": tp/(tp+fn) if tp+fn else None,
            "spezifitaet": tn/(tn+fp) if tn+fp else None}


def pruefe(ziel: Path, labels: Path) -> None:
    atlas = lese_json(ziel / "atlas.json")
    p = BildParameter(**atlas["konfiguration"]["bild_parameter"])
    if p.raster != 512:
        raise ValueError("Die vorhandenen Referenzannotationen wurden auf 512×512 px erstellt.")
    lokal = replace(p, schwelle=atlas["konfiguration"]["lokal_schwelle"])
    regionen = lese_json(labels)
    ergebnisse = []
    with plt.rc_context(stil()):
        fig, axs = plt.subplots(len(regionen), 4, figsize=(10.1, 9.4), layout="constrained")
        fig.suptitle("Teilannotierte Referenzregionen", fontweight="bold", fontsize=19, x=0.06, ha="left")
        for i, z in enumerate(regionen):
            ordner = ziel / z["id"]
            with Image.open(ordner / "platte.png") as raw:
                rgb = np.array(raw)
            with np.load(ordner / "raster.npz") as a:
                sichtbar, global_ = a["sicht"], a["sand"]
            sand = maske(z["sand"], p.raster) & sichtbar
            metall = maske(z["metall"], p.raster) & sichtbar
            if (sand & metall).any():
                raise ValueError("Sand- und Metallmarkierung überlappen.")
            vorhersage, _ = segmentiere(sandscore(rgb, "lokal", lokal), sichtbar, lokal)
            ergebnisse.append({"id": z["id"], "name": z["name"], "roi": z["roi"],
                                "platte_sha256": dateihashes(ordner / "platte.png")[0],
                                "blau": bilanz(sand, metall, global_),
                                "lokal": bilanz(sand, metall, vorhersage)})
            ref = np.zeros_like(rgb)
            ref[sand] = [232, 178, 74]
            ref[metall] = [114, 183, 202]
            l,t,r,b = z["roi"]
            for j, (inhalt, titel) in enumerate(((rgb, "Entzerrte Aufnahme"), (ref, "Manuelle Teilmaske"),
                (global_, "Blauüberschuss"), (vorhersage, "Lokaler Kontrast"))):
                ax = axs[i,j]
                ax.imshow(inhalt[t:b,l:r], cmap="gray", vmin=0, vmax=1, interpolation="nearest")
                ax.set_axis_off()
                if i == 0:
                    ax.set_title(titel, fontsize=11, loc="left")
                if j == 0:
                    ax.text(0, -0.10, z["id"]+" · "+z["name"], transform=ax.transAxes, fontsize=8.4)
        fig.supxlabel("Gelb: Sandkern   •   Blau: Metall   •   Schwarz in Teilmaske: ohne Annotation",
                      fontsize=9, x=0.06, ha="left")
        speichere(fig, ziel / "referenzmasken")
    summen = {}
    for name in ("blau", "lokal"):
        tp, fn, fp, tn = (sum(z[name][f] for z in ergebnisse) for f in ("TP","FN","FP","TN"))
        summen[name] = {"annotierte_pixel": tp+fn+fp+tn, "iou": tp/(tp+fp+fn),
                        "sensitivitaet": tp/(tp+fn), "spezifitaet": tn/(tn+fp)}
    json_schreiben(ziel / "referenzmasken.json", {"labels_sha256": dateihashes(labels)[0],
                                               "regionen": ergebnisse, "summen": summen})
    print(summen)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ausgabe", default=PROJEKT / "ausgaben/privat/analyse", type=Path)
    parser.add_argument("--labels", default=PROJEKT / "konfiguration/referenzmasken.json", type=Path)
    args = parser.parse_args()
    pruefe(args.ausgabe, args.labels)
