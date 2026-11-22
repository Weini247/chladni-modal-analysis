"""Bildbasierte Rangliste und beschränkte Suche in zweidimensionalen Eigenräumen."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage as ndi

from .bildpipeline import Binaer, Feld
from .eigenmoden import ModenErgebnis


@dataclass(frozen=True)
class Kandidat:
    rand: str
    moden: tuple[int, ...]
    hz: float
    winkel_grad: int | None
    d4: int
    bildabstand_rel: float
    abstand_hz: float | None


def knotenraster(feld: Feld) -> Binaer:
    # Jede Vorzeichen wechselnde Rasterkante markiert je den nächstgelegenen Pixel.
    linie = np.zeros(feld.shape, bool)
    for achse in (0, 1):
        w = np.moveaxis(feld, achse, 0)
        n = np.moveaxis(linie, achse, 0)
        kreuzt = np.signbit(w[:-1]) != np.signbit(w[1:])
        links = np.abs(w[:-1]) <= np.abs(w[1:])
        n[:-1] |= kreuzt & links
        n[1:] |= kreuzt & ~links
    linie |= (feld == 0) & (ndi.maximum_filter(feld, size=3) > 0) & (ndi.minimum_filter(feld, size=3) < 0)
    return linie


def transformiere(a: Binaer | Feld, code: int) -> Binaer | Feld:
    return np.rot90(a if code < 4 else np.fliplr(a), code % 4)


def familien(lam: Feld, toleranz: float = 1e-6) -> list[tuple[int, ...]]:
    gruppen: list[list[int]] = []
    for i, wert in enumerate(lam):
        if gruppen and abs(wert / lam[gruppen[-1][0]] - 1) <= toleranz:
            gruppen[-1].append(i)
        else:
            gruppen.append([i])
    return [tuple(gruppe) for gruppe in gruppen]


def kandidat_felder(felder: list[Feld], winkel_schritt: int = 15):
    if len(felder) == 1:
        yield None, felder[0]
    elif len(felder) == 2:
        for winkel in range(0, 180, winkel_schritt):
            a = np.deg2rad(winkel)
            yield winkel, np.cos(a)*felder[0] + np.sin(a)*felder[1]
    else:
        raise ValueError("Die beschränkte Suche verarbeitet nur ein- oder zweidimensionale Eigenräume.")


def rangliste(paket: list[ModenErgebnis], linien: Binaer, gueltig: Binaer,
              anregung_hz: float | None = None, winkel_schritt: int = 15) -> list[Kandidat]:
    n = linien.shape[0]
    if linien.shape != (n, n) or gueltig.shape != linien.shape or not 1 <= winkel_schritt <= 90:
        raise ValueError("Ein gemeinsames quadratisches Raster und sinnvoller Winkelschritt sind nötig.")
    linien = linien & gueltig
    if not linien.any():
        return []
    dist_emp = ndi.distance_transform_edt(~linien)
    x = (np.arange(n) + 0.5) / n
    ergebnis = []
    for modell in paket:
        for gruppe in familien(modell.lambda_):
            felder = [modell.feld(i, x, x) for i in gruppe]
            frequenz = float(np.mean(modell.frequenzen_hz[list(gruppe)]))
            bester = None
            for winkel, feld in kandidat_felder(felder, winkel_schritt):
                linie = knotenraster(feld)
                gesehen = set()
                for code in range(8):
                    th = transformiere(linie, code) & gueltig
                    bild_id = np.packbits(th).tobytes()
                    if bild_id in gesehen or not th.any():
                        continue
                    gesehen.add(bild_id)
                    ab = ndi.distance_transform_edt(~th)[linien].mean()
                    ba = dist_emp[th].mean()
                    kandidat = Kandidat(modell.rand, tuple(i+1 for i in gruppe), frequenz,
                                        winkel, code, float((ab + ba)/(2*n)),
                                        abs(frequenz-anregung_hz) if anregung_hz is not None else None)
                    if bester is None or kandidat.bildabstand_rel < bester.bildabstand_rel:
                        bester = kandidat
            if bester:
                ergebnis.append(bester)
    return sorted(ergebnis, key=lambda k: (k.bildabstand_rel, k.rand, k.moden))


def rekonstruiere(modell: ModenErgebnis, kandidat: Kandidat, raster: int) -> Feld:
    x = (np.arange(raster) + 0.5) / raster
    felder = [modell.feld(i-1, x, x) for i in kandidat.moden]
    if kandidat.winkel_grad is None:
        feld = felder[0]
    else:
        a = np.deg2rad(kandidat.winkel_grad)
        feld = np.cos(a)*felder[0] + np.sin(a)*felder[1]
    return transformiere(feld, kandidat.d4)
