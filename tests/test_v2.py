"""Funktionale Regressionen der V2-Schnittstellen."""
import unittest

import numpy as np

from chladni.eigenmoden import Platte
from chladni.forschungsatlas import raumdichte
from chladni.inverse_modelle import (InversParameter, beobachtungsbereiche, grobraster,
                                     kennzeichne)
from chladni.inverse_studie import kalibriere
from chladni.plattenmechanik import Anschluss, spektrum


class V2KernTests(unittest.TestCase):
    def test_dichte_zaehlt_nur_sichtbare_pixel(self):
        g=np.ones((4,4),bool)
        s=np.zeros_like(g)
        s[0,0]=True
        s[2,2]=True
        g[0,1]=False
        g[2:,2:]=False
        self.assertEqual(raumdichte(s,g,2),[[1/3,0.],[0.,None]])

    def test_grobraster_verwirft_verdeckte_bloecke(self):
        a=np.zeros((8,8),bool)
        a[:,2]=True
        g=np.ones_like(a)
        g[0,3]=False
        l,mask=grobraster(a,g,4)
        self.assertFalse(mask[0,1])
        self.assertEqual(list(np.nonzero(l[:,1])[0]),[1,2,3])

    def test_bildbereiche_sind_disjunkt(self):
        grund,fit,hold=beobachtungsbereiche(64)
        self.assertFalse(np.any(fit&hold))
        self.assertTrue(np.all(grund[fit|hold]))
        self.assertFalse(grund[32,32])
        self.assertTrue(fit.any() and hold.any())

    def test_rang_kann_abstinent_sein(self):
        g={"max_test_rel":.031,"min_abstand_rel":.003}
        r=lambda v: {"test_rel":v}
        self.assertEqual(kennzeichne([],g)[0],"ZU_WENIG_LINIENEVIDENZ")
        self.assertEqual(kennzeichne([r(.04),r(.05)],g)[0],"KEIN_BELASTBARER_TREFFER")
        self.assertEqual(kennzeichne([r(.02),r(.022)],g)[0],"NICHT_EINDEUTIG_IDENTIFIZIERBAR")
        self.assertEqual(kennzeichne([r(.02),r(.025)],g)[0],"KANDIDAT_IM_BEOBACHTUNGSMODELL")

    def test_kalibration_begrenzt_akzeptierte_nullfaelle(self):
        rang=lambda a,b: [{"test_rel":a},{"test_rel":b}]
        a=[{"art":"null","rang":rang(.043,.065),"richtiger_erster":False} for _ in range(8)]
        a += [{"art":"einzel","rang":rang(.031,.06),"richtiger_erster":True} for _ in range(4)]
        grenze=kalibriere(a)
        self.assertGreaterEqual(grenze["max_test_rel"],.031)
        self.assertLess(grenze["max_test_rel"],.043)

    def test_spektralschnitt_wird_um_entartung_erweitert(self):
        m=spektrum(Platte(),"navier",12,2)
        self.assertEqual(len(m.lambda_),3)
        self.assertAlmostEqual(float(m.frequenzen_hz[-1]/m.frequenzen_hz[-2]),1.0,places=8)

    def test_ungueltige_studienparameter_fehlschlagen(self):
        with self.assertRaises(ValueError):
            Anschluss(rotation_nm=-1)
        with self.assertRaises(ValueError):
            InversParameter(seed_test=52145)
        with self.assertRaises(ValueError):
            spektrum(Platte(),"frei",1,10)
