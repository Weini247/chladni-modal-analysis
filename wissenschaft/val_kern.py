"""Analytische und synthetische Validierungen. Toleranzen siehe VALIDIERUNG.md."""
from __future__ import annotations

import unittest

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

from chladni.bildpipeline import BildParameter, Geometrie, analysiere_bild, jaccard
from chladni.eigenmoden import Platte, basiswerte, berechne_eigenmoden, navier_analytisch
from chladni.mustervergleich import familien, knotenraster, rangliste


class WissenschaftlichePruefungen(unittest.TestCase):
    def test_val1_analytische_frequenzen_und_eigenraum(self):
        p = Platte()
        modell = berechne_eigenmoden(p, "navier", 13, 10)
        ref = navier_analytisch(10)
        np.testing.assert_allclose(modell.lambda_, [r[0] for r in ref], rtol=2e-7, atol=0)
        x = np.linspace(0, 1, 101)
        for gruppe in familien(modell.lambda_):
            num = np.stack([modell.feld(i, x, x).ravel() for i in gruppe], axis=1)
            exakt = np.stack([np.outer(np.sin(ref[i][2]*np.pi*x), np.sin(ref[i][1]*np.pi*x)).ravel()
                              for i in gruppe], axis=1)
            q, _ = np.linalg.qr(num)
            r, _ = np.linalg.qr(exakt)
            self.assertGreater(np.linalg.svd(r.T @ q, compute_uv=False).min(), 1-2e-7)

    def test_val2_ritz_konvergenz(self):
        p = Platte(nu=0.30)
        for rand, grenze in (("frei", 3e-5), ("zentralpunkt", 0.005), ("federflaeche", 3e-4)):
            serien = [berechne_eigenmoden(p, rand, grad, 10) for grad in [10, 14, 18, 22]]
            frequenz = np.array([s.frequenzen_hz for s in serien])
            self.assertLess(np.max(frequenz[1:] / frequenz[:-1]-1), 1e-5, rand)
            self.assertLess(np.max(np.abs(frequenz[-1]/frequenz[-2]-1)), grenze, rand)
            # Kontinuierliche Eigenräume auf einem Vergleichsraster. Gruppiert für Entartung.
            x = (np.arange(95)+0.5)/95
            for gruppe in familien(serien[-1].lambda_):
                q, _ = np.linalg.qr(np.stack([serien[-1].feld(i,x,x).ravel() for i in gruppe], 1))
                s, _ = np.linalg.qr(np.stack([serien[-2].feld(i,x,x).ravel() for i in gruppe], 1))
                self.assertGreater(np.linalg.svd(q.T @ s, compute_uv=False).min(), 0.999, rand)

    def test_val3_residuum_und_orthogonalitaet(self):
        for rand in ("navier", "frei", "zentralpunkt", "federflaeche"):
            m = berechne_eigenmoden(Platte(), rand, 12, 12)
            v = m.koeffizienten
            np.testing.assert_allclose(v.T @ m.masse @ v, np.eye(v.shape[1]), rtol=0, atol=1e-10)
            res = m.freiheitsbasis.T @ (m.steifigkeit @ v - (m.masse @ v)*m.lambda_)
            skala = m.lambda_ * np.linalg.norm(m.masse @ v, axis=0)
            self.assertLess(np.max(np.linalg.norm(res, axis=0) / skala), 1e-6, rand)
            if rand == "zentralpunkt":
                b = basiswerte(np.array([0.5]), m.grad, False)
                self.assertLess(np.max(np.abs(np.kron(b,b) @ v)), 1e-12)

    def test_val4_d4_und_entartung(self):
        x = (np.arange(111)+0.5)/111
        for rand in ("navier", "frei", "zentralpunkt", "federflaeche"):
            m = berechne_eigenmoden(Platte(), rand, 12, 10)
            gruppen = [g for g in familien(m.lambda_) if len(g) == 2]
            self.assertTrue(gruppen, rand)
            for g in gruppen:
                felder = [m.feld(i,x,x) for i in g]
                q, _ = np.linalg.qr(np.stack([f.ravel() for f in felder], 1))
                for op in (np.rot90, np.fliplr):
                    r, _ = np.linalg.qr(np.stack([op(f).ravel() for f in felder], 1))
                    self.assertGreater(np.linalg.svd(q.T @ r, compute_uv=False).min(), 1-1e-9)

    def test_val4_weiche_kontaktgrenze(self):
        p = Platte()
        frei = berechne_eigenmoden(p, "frei", 9, 4)
        kontakt = berechne_eigenmoden(p, "federflaeche", 9, 7, feder_n_m=2.5)
        np.testing.assert_allclose(kontakt.frequenzen_hz[3:], frei.frequenzen_hz, rtol=1e-5, atol=0)
        self.assertEqual(frei.starrmoden, 3)
        self.assertLess(kontakt.frequenzen_hz[2], frei.frequenzen_hz[0] * 0.01)

    def test_val5_val7_segmentierung_mit_kontrolliertem_rauschen(self):
        n = 128
        x, y = np.meshgrid(np.arange(n), np.arange(n))
        sand = (abs(x-y) <= 3) | (abs(x+y-n) <= 3)
        geom = Geometrie(((0,0),(1,0),(1,1),(0,1)), (0.5,0.5))
        rng = np.random.default_rng(249)
        for licht in (0.2, 0.4):
            rgb = np.full((n,n,3), 129.0)
            rgb[sand] += [-45, 5, 65]
            rgb += licht*x[...,None] + rng.normal(0, 9, rgb.shape)
            r = analysiere_bild(Image.fromarray(np.uint8(rgb.clip(0,255))), geom, BildParameter(raster=n))
            self.assertGreater(jaccard(r.sand, sand, r.gueltig), 0.97)

    def test_val6_reine_mode_und_doppelraum(self):
        n = 78
        x = (np.arange(n)+0.5)/n
        m = berechne_eigenmoden(Platte(), "navier", 10, 6)
        g = np.ones((n,n), bool)
        f = m.feld(3,x,x)
        kandidat = rangliste([m], knotenraster(f), g)[0]
        self.assertEqual(kandidat.moden, (4,))
        f = np.cos(np.pi/6)*m.feld(1,x,x)+np.sin(np.pi/6)*m.feld(2,x,x)
        linien = knotenraster(f)
        rng = np.random.default_rng(114)
        breiter = ndi.binary_dilation(linien, iterations=2)
        breiter ^= rng.random((n,n)) < 0.004
        from skimage.morphology import skeletonize
        kandidaten = rangliste([m], skeletonize(breiter), g)
        self.assertEqual(kandidaten[0].moden, (2,3))
        self.assertTrue(np.array_equal(knotenraster(f), knotenraster(-f)))
