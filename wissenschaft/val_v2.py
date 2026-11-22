"""Zusätzliche physikalische und räumliche Validierungen der V2."""
from dataclasses import replace
import unittest

import numpy as np

from chladni.eigenmoden import Platte, berechne_eigenmoden
from chladni.inverse_modelle import InversParameter, Katalog
from chladni.plattenmechanik import Anschluss, residuale, rotationsmatrix, spektrum, unterraumvergleich


class V2Wissenschaft(unittest.TestCase):
    def test_tabellierte_freie_platte(self):
        v=np.sqrt(spektrum(Platte(nu=.3),"frei",20,5).lambda_[:5])
        np.testing.assert_allclose(v,[13.47,19.60,24.27,34.80,34.80],rtol=0,atol=.005)

    def test_neuer_anschluss_hat_federflaeche_als_grenzfall(self):
        p=Platte()
        k=Anschluss(rotation_nm=0,verteilte_masse_kg=0)
        a=berechne_eigenmoden(p,"federflaeche",12,10,k.radius_m,k.vertikal_n_m)
        b=spektrum(p,"anschluss",12,10,k)
        np.testing.assert_allclose(a.lambda_,b.lambda_[:10],rtol=2e-6)
        r=residuale(spektrum(p,"anschluss",24,30))
        self.assertLess(r["rel_residuum_max"],1e-6)
        self.assertLess(r["m_orthogon_abs_max"],1e-10)

    def test_steiferer_anschluss_und_massenzunahme(self):
        p=Platte()
        k=Anschluss()
        g=spektrum(p,"anschluss",12,12,k)
        r=spektrum(p,"anschluss",12,12,replace(k,rotation_nm=2*k.rotation_nm))
        m=spektrum(p,"anschluss",12,12,replace(k,verteilte_masse_kg=2*k.verteilte_masse_kg))
        self.assertTrue(np.all(r.lambda_[:12]/g.lambda_[:12]>1-2e-7))
        self.assertTrue(np.all(m.lambda_[:12]/g.lambda_[:12]<1+2e-7))
        rmat=rotationsmatrix(8,k.radius_m/p.seite_m)
        self.assertLess(abs(np.linalg.eigvalsh(rmat)[0])/np.linalg.norm(rmat,2),1e-12)

    def test_hauptwinkel_sind_invariant_unter_basiswechsel(self):
        m=spektrum(Platte(),"navier",12,3)
        v=m.koeffizienten.copy()
        t=.47
        v[:,1:3]=v[:,1:3]@np.array([[np.cos(t),-np.sin(t)],[np.sin(t),np.cos(t)]])
        ret=unterraumvergleich(m,replace(m,koeffizienten=v))
        self.assertGreater(min(z["projektor_overlap"] for z in ret),1-1e-10)
        self.assertLess(max(z["max_hauptwinkel_grad"] for z in ret),1e-4)

    def test_geaenderte_prueflaeche_wirkt_nicht_auf_angepassten_rangwert(self):
        k=Katalog(Platte(),Anschluss(),InversParameter(raster=32,grad=8,moden=12,
                                                       winkel_schritt_grad=45,anzahl_klasse=4))
        a=next(s for s in k.linien if (s & k.bereiche[0]).sum()>8 and (s & k.bereiche[1]).sum()>8)
        b=a.copy()
        b[k.bereiche[1]]=~b[k.bereiche[1]]
        x,y=k.distanzen(a,k.grund), k.distanzen(b,k.grund)
        np.testing.assert_array_equal(x[0],y[0])
        self.assertGreater(np.max(abs(x[1]-y[1])),.001)
