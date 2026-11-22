
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from chladni.annotationen import AnnotationsSpeicher, vergleich
from chladni.auswertung import PROJEKT
from chladni.bildvalidierung_v3 import stichprobe
from chladni.invers_v3 import beurteile
from chladni.labor_daten import felddaten


def modusparameter() -> dict:
    return dict(modell="navier",seite_m=.18,dicke_mm=3,e_gpa=69,nu=.35,rho=2700,radius_mm=6,
                k_n_m=200000,rotation_nm=1.5,masse_g=18,grad=10,mode=1,mode2=2,mischung_deg=35)


def annotationsdaten() -> dict:
    return {"autor":"Synthetischer Prüfdatensatz","herkunft":"synthetischer_test","vorgaenger":None,
            "blindmodus":False,"geometrie":{"ecken":[[.1,.1],[.9,.1],[.9,.9],[.1,.9]],"schraube":[.5,.5]},
            "formen":[{"typ":"sand","punkte":[[.2,.2],[.4,.2],[.4,.4],[.2,.4]]},
                      {"typ":"metall","punkte":[[.6,.6],[.8,.6],[.8,.8]]},
                      {"typ":"linie","punkte":[[.3,.23],[.3,.37]]}]}


class V3Einheit(unittest.TestCase):
    def test_moden_api_feld_und_normierung(self):
        r=felddaten(dict(modusparameter(),konvergenz=True))
        self.assertEqual(r["modell"],"navier")
        self.assertGreater(r["frequenzen_hz"][1],r["frequenzen_hz"][0])
        f=np.array(r["felder"])
        self.assertEqual(f.shape,(2,r["n"]**2))
        self.assertTrue(np.isfinite(f).all())
        self.assertAlmostEqual(np.max(np.sum(abs(f),axis=0)),1,places=4)
        self.assertEqual(r["gradvergleich"]["grad_referenz"],14)
        self.assertTrue(r["gradvergleich"]["unterraeume"])

    def test_parameterfehler(self):
        d=modusparameter()
        with self.assertRaises(ValueError):
            felddaten(dict(d,mode=2.5))
        with self.assertRaisesRegex(ValueError,"Plattenannahme"):
            felddaten(dict(d,seite_m=.06,dicke_mm=10))

    def test_einfrieren_der_schwellen(self):
        schwellen={"max_test_rel":.02,"min_abstand_rel":.0015}
        a={"fit_rel":.01,"test_rel":.03,"modell":"frei","familie":["1"]}
        b={**a,"fit_rel":.02,"test_rel":.04,"familie":["2"]}
        self.assertEqual(beurteile([a,b],schwellen)["status"],"KEIN_BELASTBARER_TREFFER")
        self.assertEqual(beurteile([],schwellen)["status"],"ZU_WENIG_LINIENEVIDENZ")

    def test_stichprobe_frequenzen_dedupliziert(self):
        fotos=[{"id":f"IMG_{i}","serie":"Test","hz":f,"pfad":f"{i}.jpg","sha256":"synthetisch"}
               for i,f in enumerate((1,1,2,3,4,5))]
        rows=stichprobe(fotos)
        self.assertEqual([x["hz"] for x in rows],[1,3,5])
        self.assertEqual(rows[0]["id"],"IMG_0")

    def test_revisionen_sind_immutable_und_quellgebunden(self):
        a={"id":"SYNTH","pfad":"synthetisch.jpg","sha256":"a"*64}
        with TemporaryDirectory(dir=PROJEKT) as temp:
            storage=AnnotationsSpeicher(Path(temp))
            d=annotationsdaten()
            r0=storage.speichere(a,d)
            r1=storage.speichere(a,dict(d,vorgaenger=r0["revision"]))
            self.assertEqual([x["version"] for x in storage.liste(a["id"])],[2,1])
            self.assertEqual(storage.lese(a["id"],r0["revision"]),json.loads(json.dumps(r0)))
            x=vergleich(r0,r1)
            self.assertGreater(x["abgedeckter_annotierter_bereich_rel"],.04)
            self.assertEqual(x["iou"],1)
            self.assertEqual(x["linienabstand_rel"],0)
            self.assertEqual(x["gitter_mittel_rel"],0)
            self.assertEqual(x["unabhaengigkeit"],"nicht_extern_bestaetigt")
            with self.assertRaisesRegex(ValueError,"andere Quelldatei"):
                storage.speichere(dict(a,sha256="x"*64),dict(d,vorgaenger=r0["revision"]))
            with self.assertRaises(ValueError):
                storage.liste("../SYNTH")

    def test_unklare_labels_liefern_keine_uebereinstimmung(self):
        d=annotationsdaten()
        record={**d,"bild_id":"SYNTH","bild_sha256":"a"*64,"revision":"a"*32}
        unklar={"typ":"unklar","punkte":[[0,0],[1,0],[1,1],[0,1]]}
        r=vergleich(record,dict(record,formen=d["formen"]+[unklar]))
        self.assertEqual(r["abgedeckter_annotierter_bereich_rel"],0)
        self.assertIsNone(r["iou"])
        self.assertIsNone(r["linienabstand_rel"])
