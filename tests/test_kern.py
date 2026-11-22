from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from chladni.bildpipeline import (BildParameter, Geometrie, analysiere_bild, jaccard,
                                  linienabstand, plattenperspektive)
from chladni.frequenzen import Frequenzbeleg, bewertete_frequenz, lese_hz
from chladni.inventar import abgleich_archiv
from chladni.provenienz import dateihashes, quellpfad
from chladni.registrierung import verfeinere_ecken


class KernTests(unittest.TestCase):
    def test_sha_und_pfadgrenze(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            root = Path(tmp)
            bild = root / "a.txt"
            bild.write_bytes(b"abc")
            self.assertEqual(dateihashes(bild), ("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", "352441c2"))
            self.assertEqual(quellpfad(root, "a.txt"), bild.resolve())
            with self.assertRaises(ValueError):
                quellpfad(root, "../a.txt")

    def test_frequenzen_mit_einheit(self):
        self.assertAlmostEqual(lese_hz("04,125 kHz"), 4125)
        self.assertAlmostEqual(lese_hz("2361,06 Hz"), 2361.06)
        self.assertIsNone(lese_hz("04,125"))
        self.assertIsNone(lese_hz("0:15,10 kHz"))

    def test_quellenwiderspruch(self):
        a = Frequenzbeleg("Foto", "0.3863 kHz", 386.3, "visuell", "manuell_gelesen", "einzelbild")
        b = Frequenzbeleg("Name", "380", 380, "dateiname", "heuristisch", "einzelbild")
        c = Frequenzbeleg("Ordner", "380", 380, "ordner", "heuristisch", "ordner")
        d = Frequenzbeleg("OCR", "03.8 kHz", 3800, "ocr", "ocr_ungeprueft", "einzelbild", 40)
        e = Frequenzbeleg("Display", "0.6334 A", None, "visuell", "manuell_gelesen", "anderes_observable")
        self.assertEqual(bewertete_frequenz([a, b, c]), {"hz": None, "status": "widerspruch"})
        self.assertEqual(bewertete_frequenz([a, c]), {"hz": 386.3, "status": "manuell_gelesen"})
        self.assertEqual(bewertete_frequenz([c, d]), {"hz": None, "status": "zu_pruefen"})
        self.assertEqual(bewertete_frequenz([a, e]), {"hz": 386.3, "status": "manuell_gelesen"})

    def test_homographie_und_schraubenmaske(self):
        geom = Geometrie(((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)), (0.5, 0.5))
        bild = Image.new("RGB", (100, 100), "#2449c8")
        r = analysiere_bild(bild, geom, BildParameter(raster=100))
        self.assertTrue(np.allclose(r.schraube_xy, (0.5, 0.5)))
        self.assertFalse(r.gueltig[50, 50])
        self.assertTrue(r.sand[30, 30])
        self.assertFalse(r.sand[0, 0])
        with self.assertRaises(ValueError):
            Geometrie(tuple(reversed(geom.ecken)), geom.schraube)

    def test_registrierung_synthetisches_viereck(self):
        rgb = np.full((220, 300, 3), 215, dtype=np.uint8)
        rgb[51:174, 101:224] = [98, 73, 63]
        e = ((0.335, 0.23), (0.74, 0.23), (0.74, 0.79), (0.335, 0.79))
        geom, fit = verfeinere_ecken(Image.fromarray(rgb), Geometrie(e, (0.54, 0.51)))
        _, zentrum = plattenperspektive(Image.fromarray(rgb), geom, 100)
        self.assertLess(np.max(np.abs(np.asarray(zentrum)-0.5)), 0.012)
        self.assertLess(max(fit["fit_rms_rel"]), 0.008)

    def test_metrik_und_leerfall(self):
        a = np.zeros((20, 20), bool)
        b, v = a.copy(), ~a
        self.assertIsNone(jaccard(a, b, v))
        self.assertIsNone(linienabstand(a, b, v))
        a[:, 2], b[:, 5] = True, True
        self.assertEqual(linienabstand(a, b, v), (0.15, 0.15))
        self.assertEqual(jaccard(a, a, v), 1.0)

    def test_zip_abgleich_mit_trailing_space(self):
        dateien = [{"pfad": "A.zip", "archiv_member": [{"pfad": "Messung /a", "bytes": 3, "crc32": "a"}]},
                   {"pfad": "A/Messung/a", "bytes": 3, "crc32": "a"}]
        self.assertEqual(abgleich_archiv(dateien)[0]["groesse_crc_passend"], 1)
