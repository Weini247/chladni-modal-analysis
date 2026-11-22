
"""Prüfe V3-Geometrie, Entscheidungsregel und Kataloggrenzen ohne Fotoarchiv."""
from collections import namedtuple
from dataclasses import replace
from types import SimpleNamespace
import unittest

import numpy as np
from scipy import ndimage as ndi

from chladni.eigenmoden import Platte
from chladni.invers_v3 import _unif, kollisionsstatistik, tolerante_distanz
from chladni.mustervergleich import knotenraster
from chladni.plattenmechanik import Anschluss, spektrum, unterraumvergleich


class V3Wissenschaft(unittest.TestCase):
    def test_knotenmenge_skaleninvariant(self):
        y,x=np.indices((41,41),dtype=float)
        f=x-12.4-.017*y*y
        np.testing.assert_array_equal(knotenraster(f),knotenraster(-5*f))

    def test_freie_platte_materialskala_aendert_eigenraeume_nicht(self):
        p=Platte(.18,.003,69e9,.35,2700)
        s0=spektrum(p,"frei",12,5,Anschluss())
        s1=spektrum(replace(p,e_pa=p.e_pa*1.21),"frei",12,5,Anschluss())
        np.testing.assert_allclose(s1.frequenzen_hz/s0.frequenzen_hz,1.1,rtol=1e-6)
        q=unterraumvergleich(s0,s1)
        self.assertGreater(min(x["projektor_overlap"] for x in q),.999999)

    def test_kollision_und_eindeutige_familien(self):
        H=namedtuple("H","modell familie moden")
        m=np.eye(5,dtype=bool); other=np.fliplr(m)
        k=SimpleNamespace(hypothesen=[H("A",("1",),("1",)),H("B",("1",),("1",)),H("A",("1",),("1","2"))],
                          linien=np.array([m,m,other]),grund=np.ones_like(m))
        self.assertEqual(_unif(k),2)
        self.assertEqual(_unif(k,{"A"}),1)
        r=kollisionsstatistik(k)
        self.assertEqual(r["verschiedene_masken"],2)
        self.assertEqual(r["familienuebergreifende_masken"],1)

    def test_f1_fit_und_test_verwenden_verschiedene_flaechen(self):
        n=20
        sl=np.zeros((n,n),bool);sl[:10]=True
        lin=np.zeros_like(sl);lin[:,2]=True
        a=lin.copy();a[~sl]=False;a[10:,15]=True
        b=lin.copy();b[sl]=False;b[:10,15]=True
        paare=[]
        for region in (sl,~sl):
            paare.append((np.array([(x&region).ravel() for x in (a,b)],dtype=np.float32),
                          np.array([ndi.distance_transform_edt(~(x&region)).ravel()/n for x in (a,b)])))
        k=SimpleNamespace(bereiche=[sl,~sl],_paare=paare,c=SimpleNamespace(raster=n))
        fit,test=tolerante_distanz(k,lin,np.ones_like(lin),2/n)
        np.testing.assert_allclose(fit,[0,1])
        np.testing.assert_allclose(test,[1,0])
        self.assertIsNone(tolerante_distanz(k,lin,sl,2/n))
