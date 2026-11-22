
"""End-to-End-HTTP-Prüfung auf einem dynamischen Loopback-Port."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from chladni.auswertung import PROJEKT
from chladni.labor_daten import LaborDaten
from chladni.labor_web import LaborServer
from chladni.v3_pfade import Eingaben, V3
from tests.test_v3 import annotationsdaten, modusparameter


def pruefe() -> None:
    roh=Path(os.environ.get("CHLADNI_ROHDATEN", PROJEKT.parent))
    with TemporaryDirectory(prefix="http-pruefung-",dir=V3) as temp:
        e=Eingaben(roh)
        daten=LaborDaten(e)
        daten.annotation.wurzel=Path(temp)
        with LaborServer(0,daten) as server:
            t=Thread(target=server.serve_forever,daemon=True)
            t.start()
            adr=f"http://127.0.0.1:{server.server_port}"
            klick=unittest.TestCase()

            def senden(pfad,data=None,*,mime="application/json",status=200,headers=None):
                h={} if data is None else {"Content-Type":"application/json","X-Chladni-Local":"1","Origin":adr}
                h.update(headers or {})
                req=Request(adr+pfad,data=None if data is None else json.dumps(data).encode(),headers=h)
                try:
                    response=urlopen(req,timeout=35)
                except HTTPError as fehler:
                    response=fehler
                with response:
                    klick.assertEqual(response.code,status)
                    klick.assertEqual(response.headers.get_content_type(),mime)
                    body=response.read()
                    return json.loads(body) if mime=="application/json" else body

            folgen=[]
            try:
                html=senden("/",mime="text/html").decode("utf-8-sig")
                for ansicht in ("atlas","modes","inverse","gap","annotation","validation"):
                    klick.assertIn('href="#'+ansicht+'"',html)
                for pfad,mime in (("/labor.css","text/css"),("/labor.js","text/javascript"),
                                  ("/grafik.js","text/javascript"),("/annotation.js","text/javascript")):
                    klick.assertGreater(len(senden(pfad,mime=mime)),500)
                klick.assertEqual(senden("/api/gesund")["schema"],3)
                folgen.append("Startseite und Ressourcen")
                a=senden("/api/atlas")
                klick.assertEqual((len(a["bilder"]),len(a["serien"])),(168,24))
                id="IMG_1583"
                bild=next(q for q in a["bilder"] if q["id"]==id)
                klick.assertTrue(senden(f"/foto/{id}/original",mime="image/jpeg").startswith(b"\xff\xd8"))
                for layer in ("platte","linien","maske"):
                    klick.assertTrue(senden(f"/foto/{id}/{layer}",mime="image/png").startswith(b"\x89PNG"))
                klick.assertEqual(len(senden("/api/studie")["fotos"]),22)
                klick.assertEqual(senden("/api/gap")["katalog"]["klassen"],119)
                klick.assertTrue(senden("/api/mechanik")["benchmark"]["bestanden"])
                klick.assertEqual(len(senden("/api/audit")["artefakte"]),28)
                klick.assertEqual(senden("/api/lauf")["rohdaten_nachher"]["dateien"],297)
                for fmt,mime,header in (("png","image/png",b"\x89PNG"),("svg","image/svg+xml",b"<?xml"),
                                        ("pdf","application/pdf",b"%PDF")):
                    klick.assertTrue(senden("/figur/gap."+fmt,mime=mime).startswith(header))
                folgen.append("Atlas, Qualität, Daten und Formate")
                mod=senden("/api/moden",dict(modusparameter(),konvergenz=True))
                klick.assertEqual(len(mod["felder"]),2)
                klick.assertTrue(mod["gradvergleich"]["unterraeume"])
                senden("/api/moden",dict(modusparameter(),mode=0),status=400)
                senden("/api/moden",modusparameter(),headers={"Origin":"https://example.invalid"},status=403)
                folgen.append("Modenberechnung und Fehlermeldung")
                inv=f"/api/inverse/{id}"
                archived=senden(inv)
                klick.assertEqual(archived["ergebnis"]["status"],"KEIN_BELASTBARER_TREFFER")
                klick.assertEqual(len(archived["felder"]),6)
                live=senden(inv,{"schwelle":.10})
                klick.assertEqual(live["quelle"],"neue_extraktion")
                klick.assertTrue(live["sandlinien_png"].startswith("data:image/png;base64,"))
                senden("/api/inverse/unknown",status=404)
                folgen.append("Reale Inversion mit neuer Extraktion und Abstention")
                qa=f"/api/annotation/{id}"
                d=dict(annotationsdaten(),geometrie=bild["geometrie"])
                klick.assertEqual(senden(qa),[])
                klick.assertTrue(senden(f"/api/entzerren/{id}",d["geometrie"],mime="image/png").startswith(b"\x89PNG"))
                r0=senden(qa,d,status=201)
                r1=senden(qa,dict(d,vorgaenger=r0["revision"]),status=201)
                result=senden(f"/api/vergleich/{id}?a={r0['revision']}&b={r1['revision']}")
                klick.assertEqual(len(senden(qa)),2)
                klick.assertEqual(r1["version"],2)
                klick.assertEqual(r1["bild_sha256"],bild["sha256"])
                klick.assertEqual(r1["herkunft"],"synthetischer_test")
                klick.assertGreater(result["iou"],.95)
                senden("/unbekannt",status=404)
                folgen.append("Annotation, Registrierung und Revisionsvergleich im Testspeicher")
            finally:
                server.shutdown()
                t.join(timeout=5)
    print("V3-HTTP-Prüfung:",", ".join(folgen))


if __name__=="__main__":
    pruefe()
