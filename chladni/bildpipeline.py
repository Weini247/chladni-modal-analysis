"""Entzerrung, klassische Sandsegmentierung und geometrische Diagnostik."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage.morphology import skeletonize

Punkt = tuple[float, float]
Binaer = NDArray[np.bool_]
Feld = NDArray[np.float64]
Methode = Literal["blau", "lokal"]


@dataclass(frozen=True)
class BildParameter:
    raster: int = 512
    schwelle: float = 0.105
    lokal_sigma_rel: float = 0.025
    komponentenflaeche_rel: float = 0.00009
    rand_rel: float = 0.018
    schraubenradius_rel: float = 0.047

    def __post_init__(self) -> None:
        if not 64 <= self.raster <= 2048:
            raise ValueError("Raster muss zwischen 64 und 2048 Pixeln liegen.")
        if not 0 < self.schwelle < 1 or not 0 < self.lokal_sigma_rel < 0.25:
            raise ValueError("Schwelle oder lokales Fenster außerhalb des gültigen Bereichs.")
        if not 0 < self.komponentenflaeche_rel < 0.1:
            raise ValueError("Komponentenfläche außerhalb des gültigen Bereichs.")
        if not 0 <= self.rand_rel < 0.5 or not 0 <= self.schraubenradius_rel < 0.5:
            raise ValueError("Maskenradien außerhalb des gültigen Bereichs.")


@dataclass(frozen=True)
class Geometrie:
    ecken: tuple[Punkt, Punkt, Punkt, Punkt]
    schraube: Punkt
    verdeckt: tuple[tuple[Punkt, ...], ...] = ()

    def __post_init__(self) -> None:
        e = np.asarray(self.ecken, dtype=float)
        s = np.asarray(self.schraube, dtype=float)
        if (e.shape != (4, 2) or s.shape != (2,) or not np.all(np.isfinite(e)) or
                not np.all((e >= 0) & (e <= 1)) or not np.all((s >= 0) & (s <= 1))):
            raise ValueError("Geometrie braucht normalisierte Bildkoordinaten in [0,1].")
        kanten = np.roll(e, -1, axis=0) - e
        naechste = np.roll(kanten, -1, axis=0)
        kreuz = kanten[:, 0] * naechste[:, 1] - kanten[:, 1] * naechste[:, 0]
        if not np.all(kreuz > 0.001):
            raise ValueError("Ecken konvex und im Uhrzeigersinn angeben, beginnend oben links.")
        for polygon in self.verdeckt:
            p = np.asarray(polygon, dtype=float)
            if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.all((0 <= p) & (p <= 1)):
                raise ValueError("Verdeckungen brauchen Polygone in normalisierten Plattenkoordinaten.")


@dataclass(frozen=True)
class BildErgebnis:
    rgb: NDArray[np.uint8]
    gueltig: Binaer
    sandscore: Feld
    sand: Binaer
    linien: Binaer
    schraube_xy: Punkt


def plattenperspektive(bild: Image.Image, geom: Geometrie, raster: int) -> tuple[NDArray[np.uint8], Punkt]:
    """Vierpunktabbildung. Ausgabe-x rechts, Ausgabe-y nach unten."""
    n = float(raster)
    von = [(0, 0), (n, 0), (n, n), (0, n)]
    nach = np.asarray(geom.ecken) * np.array([bild.width, bild.height])
    zeilen = []
    for (x, y), (u, v) in zip(von, nach, strict=True):
        zeilen.extend([[x, y, 1, 0, 0, 0, -u*x, -u*y], [0, 0, 0, x, y, 1, -v*x, -v*y]])
    h = np.linalg.solve(zeilen, nach.ravel())
    rgb = np.asarray(bild.convert("RGB").transform((raster, raster), Image.Transform.PERSPECTIVE,
                     h, Image.Resampling.BICUBIC))
    h_inv = np.linalg.inv(np.r_[h, 1].reshape(3, 3))
    s = h_inv @ np.r_[np.asarray(geom.schraube) * [bild.width, bild.height], 1]
    x, y = s[:2] / (s[2] * n)
    if not (0 < x < 1 and 0 < y < 1):
        raise ValueError("Schraubenmarkierung liegt außerhalb der entzerrten Platte.")
    return rgb, (float(x), float(y))


def sichtmaske(raster: int, schraube: Punkt, parameter: BildParameter,
               verdeckt: tuple[tuple[Punkt, ...], ...] = ()) -> Binaer:
    xy = (np.arange(raster) + 0.5) / raster
    x, y = np.meshgrid(xy, xy)
    rand = parameter.rand_rel
    gueltig = (x > rand) & (x < 1-rand) & (y > rand) & (y < 1-rand)
    gueltig &= np.hypot(x-schraube[0], y-schraube[1]) > parameter.schraubenradius_rel
    if verdeckt:
        maske = Image.new("1", (raster, raster))
        zeichnung = ImageDraw.Draw(maske)
        for polygon in verdeckt:
            zeichnung.polygon([(a*raster, b*raster) for a, b in polygon], fill=1)
        gueltig &= ~np.asarray(maske)
    return gueltig


def sandscore(rgb: NDArray[np.uint8], methode: Methode, parameter: BildParameter) -> Feld:
    r, g, b = np.moveaxis(rgb.astype(float) / 255, -1, 0)
    farbe = b - (r+g)/2
    if methode == "blau":
        return farbe
    if methode == "lokal":
        hintergrund = ndi.gaussian_filter(farbe, parameter.lokal_sigma_rel * parameter.raster)
        return farbe - hintergrund
    raise ValueError(f"Unbekannte Segmentierung: {methode}")


def segmentiere(score: Feld, gueltig: Binaer, parameter: BildParameter) -> tuple[Binaer, Binaer]:
    # Schwache Glättung der Farbdifferenz unterdrückt isoliertes Pixelrauschen.
    sand = (ndi.gaussian_filter(score, 0.5) >= parameter.schwelle) & gueltig
    sand = (ndi.binary_closing(sand, structure=np.ones((3, 3))) | sand) & gueltig
    labels, _ = ndi.label(sand, np.ones((3, 3)))
    groessen = np.bincount(labels.ravel())
    groessen[0] = 0
    sand = groessen[labels] >= max(1, np.ceil(parameter.komponentenflaeche_rel * sand.size))
    return sand, skeletonize(sand)


def analysiere_bild(bild: Image.Image, geom: Geometrie, parameter: BildParameter,
                    methode: Methode = "blau") -> BildErgebnis:
    rgb, schraube = plattenperspektive(bild, geom, parameter.raster)
    gueltig = sichtmaske(parameter.raster, schraube, parameter, geom.verdeckt)
    score = sandscore(rgb, methode, parameter)
    sand, linien = segmentiere(score, gueltig, parameter)
    return BildErgebnis(rgb, gueltig, score, sand, linien, schraube)


def jaccard(a: Binaer, b: Binaer, gueltig: Binaer) -> float | None:
    vereinigt = np.count_nonzero((a | b) & gueltig)
    return float(np.count_nonzero(a & b & gueltig) / vereinigt) if vereinigt else None


def linienabstand(a: Binaer, b: Binaer, gueltig: Binaer) -> tuple[float, float] | None:
    """Symmetrischer Mittelabstand und Mittel der gerichteten 95%-Quantile in Seitenlängen."""
    a, b = a & gueltig, b & gueltig
    if a.shape != b.shape or a.shape[0] != a.shape[1]:
        raise ValueError("Linienabstand setzt gemeinsame quadratische Plattenkoordinaten voraus.")
    if not a.any() or not b.any():
        return None
    ab, ba = ndi.distance_transform_edt(~b)[a], ndi.distance_transform_edt(~a)[b]
    return (float((ab.mean() + ba.mean()) / (2*a.shape[0])),
            float((np.quantile(ab, 0.95) + np.quantile(ba, 0.95)) / (2*a.shape[0])))


def diagnostik(ergebnis: BildErgebnis) -> dict:
    sand, linien, gueltig = ergebnis.sand, ergebnis.linien, ergebnis.gueltig
    acht = np.ones((3, 3), dtype=int)
    nachbarn = ndi.convolve(linien.astype(int), acht, mode="constant") - linien
    hintergrund, _ = ndi.label(~sand)
    am_rand = np.unique(hintergrund[~gueltig])
    loecher = set(np.unique(hintergrund)) - set(am_rand) - {0}
    dist = ndi.distance_transform_edt(sand)
    width = 2 * dist[linien] / sand.shape[0]
    symmetrien = {}
    for name, op in (("links_rechts", np.fliplr), ("oben_unten", np.flipud),
                     ("diagonal", np.transpose), ("90_grad", np.rot90)):
        symmetrien[name] = jaccard(sand, op(sand), gueltig & op(gueltig))
    return {"abdeckung_rel": float(sand.sum() / gueltig.sum()) if gueltig.any() else None,
            "sichtbare_flaeche_rel": float(gueltig.mean()),
            "breite_edt_median_rel": float(np.median(width)) if width.size else None,
            "skelettpixel": int(linien.sum()), "sand_komponenten_8": int(ndi.label(sand, acht)[1]),
            "skelett_komponenten_8": int(ndi.label(linien, acht)[1]),
            "endpunkte_8": int(np.count_nonzero(linien & (nachbarn == 1))),
            "verzweigungscluster_8": int(ndi.label(linien & (nachbarn >= 3), acht)[1]),
            "eingeschlossene_hintergrundregionen_4": len(loecher), "spiegel_jaccard": symmetrien,
            "schraube_xy": list(ergebnis.schraube_xy)}
