"""Lokaler V3-Browserstart mit expliziten Dateirouten."""
from __future__ import annotations

from argparse import ArgumentParser
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .auswertung import PROJEKT, lese_json
from .labor_daten import LaborDaten, felddaten
from .v3_pfade import Eingaben, V1, V2, V3

STATISCH=PROJEKT/"oberflaeche_v3"
FIGUREN={"sweeps","gap","mechanik","synthetik"}


class LaborServer(ThreadingHTTPServer):
    def __init__(self,port: int,daten: LaborDaten):
        self.daten=daten
        super().__init__(("127.0.0.1",port),LaborAnfrage)


class LaborAnfrage(BaseHTTPRequestHandler):
    server: LaborServer

    def log_message(self,format,*args):
        if str(args[1] if len(args)>1 else "").startswith("5"):
            super().log_message(format,*args)

    def _antwort(self,daten: bytes,mime: str,status=200):
        self.send_response(status)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",str(len(daten)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Content-Security-Policy","default-src 'self'; img-src 'self' data: blob:; "
                         "style-src 'self'; frame-ancestors 'none'; object-src 'none'")
        self.end_headers()
        self.wfile.write(daten)

    def _json(self,obj,status=200):
        self._antwort(json.dumps(obj,ensure_ascii=False,allow_nan=False).encode(),
                      "application/json; charset=utf-8",status)

    def _datei(self,p: Path):
        mime=mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        if p.suffix==".js":
            mime="text/javascript"
        if p.suffix in {".js",".css",".html"}:
            mime+="; charset=utf-8"
        self._antwort(p.read_bytes(),mime)

    def _vertraut(self):
        return self.headers.get("Host","").lower() in {
            f"127.0.0.1:{self.server.server_port}",f"localhost:{self.server.server_port}"}

    def do_GET(self):
        self._sicher(self._get)

    def do_POST(self):
        self._sicher(self._post)

    def _sicher(self,aktion):
        if not self._vertraut():
            self._json({"fehler":"Diese Anwendung ist für den lokalen Loopback-Host bestimmt."},403)
            return
        try:
            aktion()
        except (KeyError,FileNotFoundError) as e:
            self._json({"fehler":f"Daten oder Route fehlen ({Path(e.filename).name if isinstance(e,FileNotFoundError) and e.filename else str(e)})."},404)
        except (TypeError,AttributeError,ValueError,ArithmeticError) as e:
            self._json({"fehler":str(e)},400)
        except (BrokenPipeError,ConnectionResetError):
            return
        except OSError as e:
            self._json({"fehler":"Lokaler Ein-/Ausgabefehler. Details stehen im Terminal."},503)
            print(e,flush=True)

    def _get(self):
        url=urlsplit(self.path)
        route=url.path.strip("/").split("/")
        ds=self.server.daten
        if url.path=="/":
            return self._datei(STATISCH/"index.html")
        if len(route)==1 and route[0] in {"labor.css","labor.js","grafik.js","annotation.js"}:
            return self._datei(STATISCH/route[0])
        if route==["api","gesund"]:
            return self._json({"schema":3,"status":"lokal"})
        if route==["api","atlas"]:
            return self._json(ds.atlas)
        if route==["api","studie"]:
            return self._json(lese_json(ds.e.ziel/"bildstudie.json"))
        if route==["api","gap"]:
            return self._json(lese_json(ds.e.ziel/"gap.json"))
        if route==["api","mechanik"]:
            return self._json(lese_json(ds.e.v2/"mechanik.json"))
        if route==["api","audit"]:
            return self._json(lese_json(ds.e.ziel/"v2-audit.json"))
        if route==["api","lauf"]:
            return self._json(lese_json(ds.e.ziel/"laufmanifest.json"))
        if len(route)==3 and route[:2]==["api","inverse"]:
            return self._json(ds.inverse(route[2]))
        if len(route)==3 and route[:2]==["api","annotation"]:
            return self._json(ds.annotation.liste(ds.fotos[route[2]]["id"]))
        if len(route)==3 and route[0]=="foto":
            return self._antwort(*ds.foto(route[1],route[2]))
        if len(route)==3 and route[:2]==["api","vergleich"]:
            p=parse_qs(url.query)
            return self._json(ds.annotation_vergleich(ds.fotos[route[2]]["id"],p["a"][0],p["b"][0]))
        if len(route)==2 and route[0]=="figur":
            f=Path(route[1])
            if f.stem in FIGUREN and f.suffix in {".png",".svg",".pdf"}:
                return self._datei(ds.e.ziel/"figuren"/f.name)
        raise KeyError(url.path)

    def _post(self):
        origin=self.headers.get("Origin")
        host=self.headers.get("Host")
        if self.headers.get("X-Chladni-Local")!="1" or (origin and origin!=f"http://{host}"):
            return self._json({"fehler":"Lokale Browseranfrage erforderlich."},403)
        n=int(self.headers.get("Content-Length","0"))
        if not 0<n<=1_000_000:
            raise ValueError("Ungültige Größe für die lokale Anfrage.")
        d=json.loads(self.rfile.read(n))
        if not isinstance(d,dict):
            raise ValueError("JSON-Objekt erforderlich.")
        route=urlsplit(self.path).path.strip("/").split("/")
        ds=self.server.daten
        if route==["api","moden"]:
            return self._json(felddaten(d))
        if len(route)==3 and route[:2]==["api","inverse"]:
            a=ds.rechnung(route[2],d)
            a["sandlinien_png"]="data:image/png;base64,"+base64.b64encode(a["sandlinien_png"]).decode("ascii")
            return self._json(a)
        if len(route)==3 and route[:2]==["api","annotation"]:
            return self._json(ds.neue_annotation(route[2],d),201)
        if len(route)==3 and route[:2]==["api","entzerren"]:
            return self._antwort(ds.anmerkungsbild(route[2],d),"image/png")
        raise KeyError(self.path)


def main():
    ap=ArgumentParser(description=__doc__)
    ap.add_argument("--rohdaten",type=Path,default=PROJEKT.parent)
    ap.add_argument("--v1",type=Path,default=V1)
    ap.add_argument("--v2",type=Path,default=V2)
    ap.add_argument("--ziel",type=Path,default=V3)
    ap.add_argument("--port",type=int,default=8897)
    a=ap.parse_args()
    if not (a.v1/"atlas.json").is_file() or not (a.v2/"atlas.json").is_file():
        ap.error("Der lokale Explorer benötigt die privaten V1-/V2-Atlasdaten. "
                 "Ohne GP2-Archiv: python -m werkzeuge.v3_modellpaket")
    daten=LaborDaten(Eingaben(a.rohdaten,a.v1,a.v2,a.ziel))
    with LaborServer(a.port,daten) as s:
        print(f"Local: http://127.0.0.1:{s.server_port}",flush=True)
        try:
            s.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__=="__main__":
    main()
