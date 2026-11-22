"""Dimensionloser Rayleigh–Ritz-Solver für isotrope quadratische Kirchhoff–Love-Platten."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import numpy as np
from numpy.polynomial.legendre import Legendre, leggauss, legvander
from numpy.typing import NDArray
from scipy.linalg import eigh, null_space

Matrix = NDArray[np.float64]
Rand = Literal["navier", "frei", "zentralpunkt", "federflaeche"]


@dataclass(frozen=True)
class Platte:
    seite_m: float = 0.18
    dicke_m: float = 0.003  # Illustrativer Rechenwert
    e_pa: float = 69e9
    nu: float = 0.35
    rho_kg_m3: float = 2700.0

    def __post_init__(self) -> None:
        groessen = (self.seite_m, self.dicke_m, self.e_pa, self.rho_kg_m3)
        if not all(np.isfinite(v) and v > 0 for v in groessen) or not -1 < self.nu < 0.5:
            raise ValueError("Ungültige Plattenparameter für isotrope Elastizität.")

    @property
    def biegesteifigkeit_nm(self) -> float:
        return self.e_pa * self.dicke_m**3 / (12 * (1 - self.nu**2))

    @property
    def hz_skala(self) -> float:
        return float(np.sqrt(self.biegesteifigkeit_nm / (self.rho_kg_m3 * self.dicke_m))
                     / (2 * np.pi * self.seite_m**2))


@dataclass(frozen=True)
class ModenErgebnis:
    rand: Rand
    grad: int
    lambda_: Matrix
    frequenzen_hz: Matrix
    koeffizienten: Matrix
    masse: Matrix
    steifigkeit: Matrix
    freiheitsbasis: Matrix
    starrmoden: int

    def feld(self, index: int, x: Matrix, y: Matrix) -> Matrix:
        bx = basiswerte(x, self.grad, self.rand == "navier")
        by = basiswerte(y, self.grad, self.rand == "navier")
        return by @ self.koeffizienten[:, index].reshape(self.grad + 1, self.grad + 1) @ bx.T


def basiswerte(x: Matrix, grad: int, navier: bool) -> Matrix:
    werte = legvander(2 * x - 1, grad) * np.sqrt(2 * np.arange(grad + 1) + 1)
    return werte * (4 * x * (1 - x))[:, None] if navier else werte


@lru_cache(maxsize=12)
def plattenmatrizen(grad: int, nu: float, navier: bool) -> tuple[Matrix, Matrix]:
    """K_ij = ∫ (u_xx v_xx + u_yy v_yy + ν Kreuzterme + 2(1−ν) u_xy v_xy)."""
    x, w = leggauss(grad + 4)
    polynome = [Legendre.basis(i) * np.sqrt(2 * i + 1) for i in range(grad + 1)]
    if navier:
        randfaktor = Legendre([2 / 3, 0, -2 / 3])  # 1 − x² in Legendre-Koordinaten
        polynome = [p * randfaktor for p in polynome]
    v, d, dd = [np.stack([2**i * p.deriv(i)(x) for p in polynome], axis=1) for i in range(3)]
    m, a, b, c = (v.T @ (w[:, None] * v) / 2,
                  d.T @ (w[:, None] * d) / 2,
                  dd.T @ (w[:, None] * dd) / 2,
                  dd.T @ (w[:, None] * v) / 2)
    masse = np.kron(m, m)
    steif = (np.kron(m, b) + np.kron(b, m) + nu * (np.kron(c, c.T) + np.kron(c.T, c))
             + 2 * (1 - nu) * np.kron(a, a))
    return masse, (steif + steif.T) / 2


def kontaktmatrix(grad: int, radius_rel: float) -> Matrix:
    """Ungedämpfte vertikale Federwirkung, gleichmäßig über eine Kreisscheibe verteilt."""
    r, w = leggauss(grad + 2)
    r = (r + 1) / 2
    theta = np.linspace(0, 2 * np.pi, 4 * grad + 4, endpoint=False)
    x = 0.5 + radius_rel * (r[:, None] * np.cos(theta)).ravel()
    y = 0.5 + radius_rel * (r[:, None] * np.sin(theta)).ravel()
    b = (basiswerte(y, grad, False)[:, :, None] * basiswerte(x, grad, False)[:, None, :])
    b = b.reshape(len(x), -1)
    gewicht = np.repeat(w * r / len(theta), len(theta))
    return b.T @ (gewicht[:, None] * b)


def berechne_eigenmoden(platte: Platte, rand: Rand, grad: int = 12, anzahl: int = 16,
                       radius_m: float = 0.006, feder_n_m: float = 2e5) -> ModenErgebnis:
    if rand not in {"navier", "frei", "zentralpunkt", "federflaeche"} or not 2 <= grad <= 24:
        raise ValueError("Randmodell oder maximaler Polynomgrad außerhalb des unterstützten Bereichs.")
    if anzahl < 1:
        raise ValueError("Mindestens eine elastische Mode anfordern.")
    masse, steif = plattenmatrizen(grad, platte.nu, rand == "navier")
    z = np.eye(len(masse))
    starrmoden = 0
    if rand == "zentralpunkt":
        mitte = basiswerte(np.array([0.5]), grad, False)
        z = null_space(np.kron(mitte, mitte))
        starrmoden = 2
    elif rand == "frei":
        starrmoden = 3
    elif rand == "federflaeche":
        if not 0 < radius_m < platte.seite_m / 2 or not 0 < feder_n_m < np.inf:
            raise ValueError("Kontaktradius und Federsteifigkeit müssen positiv und endlich sein.")
        steif = steif + (feder_n_m * platte.seite_m**2 / platte.biegesteifigkeit_nm
                         * kontaktmatrix(grad, radius_m / platte.seite_m))
    if len(z.T) < starrmoden + anzahl:
        raise ValueError("Die Basis enthält weniger Freiheitsgrade als angeforderte Moden.")
    k, m = (z.T @ steif @ z, z.T @ masse @ z) if rand == "zentralpunkt" else (steif, masse)
    werte, v = eigh(k, m, subset_by_index=(0, starrmoden + anzahl - 1))
    if np.any(werte[starrmoden:] <= 0):
        raise ArithmeticError("Das Modell lieferte nichtpositive elastische Eigenwerte.")
    if starrmoden and np.max(np.abs(werte[:starrmoden])) > 1e-9 * np.linalg.norm(k, np.inf):
        raise ArithmeticError("Erwarteter Starrkörper-Nullraum fehlt.")
    positiv = werte[starrmoden:]
    return ModenErgebnis(rand, grad, positiv, np.sqrt(positiv) * platte.hz_skala,
                         z @ v[:, starrmoden:], masse, steif, z, starrmoden)


def navier_analytisch(anzahl: int) -> list[tuple[float, int, int]]:
    return sorted((np.pi**4 * (n*n + m*m)**2, n, m)
                  for n in range(1, anzahl + 1) for m in range(1, anzahl + 1))[:anzahl]


def historischer_kosinus(platte: Platte, n: int, m: int, x: Matrix, y: Matrix) -> tuple[float, Matrix]:
    if min(n, m) < 0 or n == m == 0:
        raise ValueError("Historischer Ansatz erfordert nichtnegative Indizes und mindestens eine Welle.")
    return (platte.hz_skala * np.pi**2 * (n*n + m*m),
            np.outer(np.cos(m * np.pi * y), np.cos(n * np.pi * x)))
