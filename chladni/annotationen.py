"""Unveränderliche lokale Annotationen und registrierter Vergleich."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import re
from uuid import uuid4

import numpy as np
from PIL import Image, ImageDraw
from skimage.transform import ProjectiveTransform

from .auswertung import lese_json
from .bildpipeline import Geometrie, jaccard, linienabstand
from .provenienz import json_schreiben

ID = re.compile(r"[A-Za-z0-9_-]{1,70}")
REV = re.compile(r"[0-9a-f]{32}")
EINHEIT = np.array([[0.,0.],[1.,0.],[1.,1.],[0.,1.]])
POLYGONE = {"sand","metall","unklar"}
FORMEN = POLYGONE | {"linie"}


def _punkte(daten, min_anzahl: int):
    a = np.asarray(daten,dtype=float)
    if (a.ndim!=2 or a.shape[1]!=2 or not min_anzahl<=len(a)<=2000
            or not np.isfinite(a).all() or np.any(a<0) or np.any(a>1)):
        raise ValueError("Ungültige normalisierte Stützpunkte.")
    return a.tolist()


def _revision(key: str) -> str:
    if not isinstance(key,str) or not REV.fullmatch(key):
        raise ValueError("Ungültige Revisions-ID.")
    return key


class AnnotationsSpeicher:
    def __init__(self,wurzel: Path):
        self.wurzel = wurzel

    def _ordner(self,bild: str) -> Path:
        if not isinstance(bild,str) or not ID.fullmatch(bild):
            raise ValueError("Ungültige Bild-ID.")
        pfad=(self.wurzel/bild).resolve()
        if not pfad.is_relative_to(self.wurzel.resolve()):
            raise ValueError("Annotation außerhalb des Projektspeichers.")
        return pfad

    def lese(self,bild: str, revision: str) -> dict:
        return lese_json(self._ordner(bild)/f"{_revision(revision)}.json")

    def liste(self,bild: str) -> list[dict]:
        return sorted((lese_json(p) for p in self._ordner(bild).glob("*.json")
                       if REV.fullmatch(p.stem)),key=lambda d:d["erzeugt_utc"],reverse=True)

    def speichere(self,bild: dict,nutzlast: dict) -> dict:
        autor = (nutzlast.get("autor") or "").strip()
        quelle=nutzlast.get("herkunft")
        parent=nutzlast.get("vorgaenger")
        if not 1<=len(autor)<=80 or quelle not in {"manuell_selbstangabe","assistiert","synthetischer_test"}:
            raise ValueError("Bearbeiter und Herkunft der Annotation sind erforderlich.")
        g=nutzlast.get("geometrie") or {}
        verdeckt=tuple(tuple(map(tuple,_punkte(p,3))) for p in g.get("verdeckt",[]))
        geom=Geometrie(tuple(map(tuple,_punkte(g.get("ecken",[]),4))),
                       tuple(_punkte([g.get("schraube",[])],1)[0]),verdeckt)
        formen=nutzlast.get("formen",[])
        if not isinstance(formen,list) or len(formen)>150:
            raise ValueError("Bis zu 150 Linien und Polygone je Annotation.")
        daten=[]
        for item in formen:
            art=item.get("typ")
            if art not in FORMEN:
                raise ValueError("Unbekannter Annotationstyp.")
            punkte=_punkte(item.get("punkte"),2 if art=="linie" else 3)
            if len({tuple(p) for p in punkte}) < (2 if art=="linie" else 3):
                raise ValueError("Die Markierung benötigt verschiedene Stützpunkte.")
            daten.append({"typ":art,"punkte":punkte})
        version=1
        if parent:
            alt=self.lese(bild["id"],parent)
            if alt["bild_sha256"]!=bild["sha256"]:
                raise ValueError("Vorgänger bezieht sich auf eine andere Quelldatei.")
            version=alt["version"]+1
        key=uuid4().hex
        record={"schema":3,"revision":key,"version":version,"vorgaenger":parent,
                "autor":autor,"herkunft":quelle,"erzeugt_utc":datetime.now(timezone.utc).isoformat(),
                "bild_id":bild["id"],"bild_sha256":bild["sha256"],"bild_pfad":bild["pfad"],
                "geometrie":asdict(geom),"formen":daten,
                "notiz":str(nutzlast.get("notiz",""))[:1000],
                "blindmodus":bool(nutzlast.get("blindmodus")),
                "unabhaengigkeit":"nicht_extern_bestaetigt"}
        json_schreiben(self._ordner(bild["id"])/f"{key}.json",record)
        return record


def _homographie(d: dict) -> ProjectiveTransform:
    ziel=np.asarray(d["geometrie"]["ecken"],dtype=float)
    h=ProjectiveTransform.from_estimate(EINHEIT,ziel)
    if not h:
        raise ValueError("Homographie der Annotation ist singulär.")
    return h


def _raster(d: dict,h,n: int) -> dict[str,np.ndarray]:
    raster={k:Image.new("1",(n,n)) for k in FORMEN}
    gd={k:ImageDraw.Draw(v) for k,v in raster.items()}
    for item in d["formen"]:
        art=item["typ"]
        punkte=[tuple(p) for p in (h(np.asarray(item["punkte"]))*n)]
        if art=="linie":
            gd[art].line(punkte,fill=1,width=1)
        else:
            gd[art].polygon(punkte,fill=1)
    return {k:np.asarray(a) for k,a in raster.items()}


def vergleich(a: dict,b: dict,n: int=384) -> dict:
    """Vergleich in der Plattenebene von a. B wird über das Original rückprojiziert."""
    if a["bild_id"]!=b["bild_id"] or a["bild_sha256"]!=b["bild_sha256"]:
        raise ValueError("Nur Revisionen derselben Quelldatei vergleichen.")
    def ident(x):
        return x

    if np.array_equal(a["geometrie"]["ecken"],b["geometrie"]["ecken"]):
        projektion=ident
    else:
        ha,hb=_homographie(a),_homographie(b)
        def projektion(x):
            return ha.inverse(hb(x))

    links=_raster(a,ident,n)
    rechts=_raster(b,projektion,n)
    klar=~(links["unklar"] | rechts["unklar"])
    amb=(links["sand"]&links["metall"]) | (rechts["sand"]&rechts["metall"])
    aktiv=klar & ~amb & (links["sand"]|links["metall"]) & (rechts["sand"]|rechts["metall"])
    tp=int((aktiv & links["sand"] & rechts["sand"]).sum())
    pred=int((aktiv & rechts["sand"]).sum())
    ref=int((aktiv & links["sand"]).sum())
    q=np.linspace(.1,.9,5)
    gitter=np.stack(np.meshgrid(q,q),axis=-1).reshape(-1,2)
    d=np.linalg.norm(projektion(gitter)-gitter,axis=1)
    dist=linienabstand(links["linie"],rechts["linie"],klar)
    return {"revisionen":[a["revision"],b["revision"]],
            "abgedeckter_annotierter_bereich_rel":float(aktiv.mean()),
            "iou":jaccard(links["sand"],rechts["sand"],aktiv),
            "praezision_b_gegen_a":tp/pred if pred else None,
            "recall_b_gegen_a":tp/ref if ref else None,
            "linienabstand_rel":dist[0] if dist else None,
            "linienabstand_q95_rel":dist[1] if dist else None,
            "gitter_mittel_rel":float(d.mean()),
            "unabhaengigkeit":"nicht_extern_bestaetigt"}
