"""Kantenverfeinerung nach manueller Lokalisierung des Plattenvierecks."""
from dataclasses import replace

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates

from .bildpipeline import Geometrie


def verfeinere_ecken(bild: Image.Image, seed: Geometrie) -> tuple[Geometrie, dict]:
    """Verfolge den stärksten Helligkeitsgradienten nahe jeder manuell vorgegebenen Kante."""
    klein = bild.copy()
    klein.thumbnail((900, 900))
    groesse = np.array(klein.size)
    ecken = np.asarray(seed.ecken) * groesse
    hell = gaussian_filter(np.asarray(klein.convert("L"), dtype=float) / 255, 1.25)
    linien, kontraste, rms = [], [], []
    aufloesung = float(min(groesse))
    fenster = aufloesung * 0.038
    offsets = np.linspace(-fenster, fenster, 63)
    t = np.linspace(0.09, 0.91, 70)
    for p, q in zip(ecken, np.roll(ecken, -1, axis=0), strict=True):
        laenge = np.linalg.norm(q-p)
        tangente = (q-p)/laenge
        normale = np.array([-tangente[1], tangente[0]])
        raster = p + t[:, None, None] * (q-p) + offsets[None, :, None] * normale
        profile = map_coordinates(hell, [raster[..., 1], raster[..., 0]], order=1, mode="nearest")
        # In den Rohbildern ist die Platte überwiegend dunkler als der Tisch.
        gradient = -np.gradient(profile, offsets, axis=1)
        prior = np.exp(-0.5 * (offsets / (0.73*fenster))**2)
        peak = np.argmax(gradient * prior, axis=1)
        staerke = gradient[np.arange(len(t)), peak]
        versatz = offsets[peak]
        gueltig = (staerke >= max(0.004, np.quantile(staerke, 0.45))) & (np.abs(versatz) < 0.96*fenster)
        if np.count_nonzero(gueltig) < 18:
            raise ValueError("Kantenkontrast unzureichend. Ecken manuell nachprüfen.")
        for _ in range(3):
            koeff = np.polyfit(t[gueltig], versatz[gueltig], 1, w=np.sqrt(staerke[gueltig]))
            fehler = versatz - np.polyval(koeff, t)
            gueltig &= np.abs(fehler) < max(2.0, 2.4*np.median(np.abs(fehler[gueltig])))
            if np.count_nonzero(gueltig) < 14:
                raise ValueError("Keine konsistente Plattenkante im Suchfenster.")
        mitte = (p+q)/2 + np.polyval(koeff, 0.5)*normale
        richtung = tangente + koeff[0]/laenge*normale
        neue_normale = np.array([-richtung[1], richtung[0]]) / np.linalg.norm(richtung)
        linien.append((neue_normale, float(mitte @ neue_normale)))
        kontraste.append(float(np.median(staerke[gueltig])))
        rms.append(float(np.sqrt(np.mean(fehler[gueltig]**2)) / aufloesung))
    kreuze = np.asarray([np.linalg.solve([a[0], b[0]], [a[1], b[1]])
                         for a, b in zip(linien[-1:] + linien[:-1], linien, strict=True)])
    verschiebung = float(np.max(np.linalg.norm(kreuze-ecken, axis=1)) / aufloesung)
    if verschiebung > 0.067:
        raise ValueError("Verfeinerte Ecken zu weit von der manuellen Vorgabe entfernt.")
    geom = replace(seed, ecken=tuple(map(tuple, kreuze / groesse)))
    return geom, {"gradient_median": kontraste, "fit_rms_rel": rms,
                  "max_korrektur_rel_kurzseite": verschiebung}
