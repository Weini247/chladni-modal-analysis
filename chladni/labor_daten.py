"""Testbare Schnittstellen zwischen Rechenmodulen und lokalem Browserlabor."""
from __future__ import annotations

from dataclasses import replace
from functools import cached_property, lru_cache
from io import BytesIO
from threading import Lock

import numpy as np
from PIL import Image

from .annotationen import AnnotationsSpeicher, vergleich
from .auswertung import lese_json
from .bildpipeline import BildParameter, Geometrie, analysiere_bild, plattenperspektive
from .eigenmoden import Platte, historischer_kosinus
from .inventar import lade_bild, registriere_heif
from .inverse_modelle import InversParameter, Katalog, grobraster
from .invers_v3 import beurteile, rangliste
from .plattenmechanik import Anschluss, residuale, spektrum, unterraumvergleich
from .v3_pfade import Eingaben


@lru_cache(maxsize=4)
def _moden(platte, kontakt, modell, grad, anzahl):
    return spektrum(platte,modell,grad,anzahl,kontakt)


def _png(a) -> bytes:
    s=BytesIO()
    Image.fromarray(a).save(s,format="PNG")
    return s.getvalue()


def _maske(s,v) -> bytes:
    rgb=np.empty((*s.shape,3),dtype=np.uint8)
    rgb[:]=[18,27,34]
    rgb[~v]=[8,13,18]
    rgb[s & v]=[112,230,209]
    return _png(rgb)


def _overlay(rgb,linien):
    data=np.copy(rgb)
    data[linien]=[251,203,114]
    return _png(data)


def _zahl(d,k,grenze):
    w=float(d[k])
    if not np.isfinite(w) or not grenze[0]<=w<=grenze[1]:
        raise ValueError(f"{k} liegt außerhalb des unterstützten Bereichs {grenze}.")
    return w


def _ganz(d,k,grenze):
    w=_zahl(d,k,grenze)
    if int(w)!=w:
        raise ValueError(f"{k} muss ganzzahlig sein.")
    return int(w)


class LaborDaten:
    def __init__(self,e: Eingaben):
        self.e=e
        self.annotation=AnnotationsSpeicher(e.ziel/"annotationen")
        self.sperre=Lock()
        registriere_heif()

    @cached_property
    def alt(self):
        return lese_json(self.e.v1/"atlas.json")

    @cached_property
    def fotos(self):
        return {q["id"]:q for q in self.alt["bilder"]}

    @cached_property
    def v2(self):
        return lese_json(self.e.v2/"laufmanifest.json")["konfiguration"]

    @cached_property
    def cfg(self):
        return lese_json(self.e.konfig)

    @cached_property
    def atlas(self):
        a=lese_json(self.e.v2/"atlas.json")
        daten=[]
        for q in a["bilder"]:
            daten.append({**q,"exif":{k:v for k,v in q["exif"].items()
                                      if k in {"aufnahmezeit","subsekunde_aufnahme"}},
                          "bildvarianten":q["serie"] in self.cfg["serien"]})
        return {"bilder":daten,"serien":a["serien"],"frequenzpaare":a["frequenzpaare"],
                "chronologische_paare":a["chronologische_paare"],
                "versuchsserien":self.cfg["serien"],"kontrollserie":self.cfg["kontrollserie"]}

    @cached_property
    def archiv_inverse(self):
        a=lese_json(self.e.v2/"invers.json")
        return {d["id"]:d for d in a["ergebnisse"]}

    @cached_property
    def felder(self):
        with np.load(self.e.v2/"inverse_felder.npz") as d:
            return {int(i):f for i,f in zip(d["indices"],d["felder"],strict=True)}

    @cached_property
    def katalog(self):
        c=InversParameter(**self.v2["invers"])
        return Katalog(Platte(**self.v2["platte"]),Anschluss(**self.v2["anschluss"]),c)

    def foto(self,id,kategorie) -> tuple[bytes,str]:
        q=self.fotos[id]
        namensliste={"original":"original-vorschau.jpg","platte":"platte.png","linien":"linien.png"}
        if kategorie in namensliste:
            f=self.e.v1/q["id"]/namensliste[kategorie]
            return f.read_bytes(),"image/jpeg" if f.suffix==".jpg" else "image/png"
        if kategorie=="maske":
            with np.load(self.e.v1/q["id"]/"raster.npz") as d:
                return _maske(d["sand"],d["sicht"]),"image/png"
        raise KeyError(kategorie)

    def _felder(self,rg,q):
        return [{"index":r["index"],"n":len(q[r["index"]]),
                 "werte":np.around(q[r["index"]],4).ravel().tolist()} for r in rg]

    def inverse(self,id):
        q=self.archiv_inverse[id]
        return {"ergebnis":q,"felder":self._felder(q["rang"],self.felder),
                "schwellen":self.cfg["gap"]["schwellen"],"quelle":"gesicherter_v2_katalog"}

    def rechnung(self,id,d):
        q=self.fotos[id]
        s=_zahl(d,"schwelle",(.05,.18))
        p=replace(BildParameter(**self.alt["konfiguration"]["bild_parameter"]),schwelle=s)
        im=lade_bild(self.e.original(q))
        r=analysiere_bild(im,Geometrie(**q["geometrie"]),p)
        with self.sperre:
            k=self.katalog
            lin,mask=grobraster(r.linien,r.gueltig,k.c.raster)
            rang=rangliste(k,k.distanzen(lin,mask),q["hz"])
            schwellen=self.cfg["gap"]["schwellen"]
            ergebnis=beurteile(rang,schwellen)
            return {"ergebnis":ergebnis,"felder":self._felder(rang,k.feld),"schwellen":schwellen,
                    "quelle":"neue_extraktion","schwelle":s,
                    "sandlinien_png":_overlay(r.rgb,r.linien),
                    "sandflaeche_rel":float(r.sand.sum()/r.gueltig.sum())}

    def anmerkungsbild(self,id,d):
        q=self.fotos[id]
        geom=Geometrie(**d)
        ein=lade_bild(self.e.original(q))
        rgb,_=plattenperspektive(ein,geom,600)
        return _png(rgb)

    def neue_annotation(self,id,d):
        q=self.fotos[id]
        self.e.original(q)
        return self.annotation.speichere(q,d)

    def annotation_vergleich(self,id,a,b):
        return vergleich(self.annotation.lese(id,a),self.annotation.lese(id,b))


def felddaten(d: dict) -> dict:
    """Normierte Felder für Abbildung, Nulllinien und relative Phasenanimation."""
    modell=d["modell"]
    if modell not in {"navier","frei","zentralpunkt","federflaeche","anschluss","historisch"}:
        raise ValueError("Unbekanntes Plattenmodell.")
    p=Platte(_zahl(d,"seite_m",(.06,.5)),_zahl(d,"dicke_mm",(.4,10))/1000,
             _zahl(d,"e_gpa",(15,300))*1e9,_zahl(d,"nu",(-.1,.48)),_zahl(d,"rho",(800,11000)))
    if p.dicke_m/p.seite_m>.10:
        raise ValueError("Das Verhältnis Dicke/Seitenlänge liegt außerhalb der Plattenannahme (≤0,10).")
    k=Anschluss(_zahl(d,"radius_mm",(1,24))/1000,_zahl(d,"k_n_m",(2000,2e6)),
                _zahl(d,"rotation_nm",(0,20)),_zahl(d,"masse_g",(0,120))/1000)
    grad=_ganz(d,"grad",(8,24))
    i=_ganz(d,"mode",(1,30))
    j=_ganz(d,"mode2",(0,30))
    mix=_zahl(d,"mischung_deg",(-90,90)) if j else 0.
    n=49
    x=(np.arange(n)+.5)/n
    diagnose=None
    konvergenz=None
    if modell=="historisch":
        ordnung=sorted((a*a+b*b,a,b) for a in range(9) for b in range(a,9) if a or b)
        def feld(index):
            _,a,b=ordnung[index-1]
            return historischer_kosinus(p,a,b,x,x)
    else:
        m=_moden(p,k,modell,grad,30)
        diagnose=residuale(m)
        if d.get("konvergenz") is True:
            g2=grad+4 if grad<=20 else grad-4
            andere=_moden(p,k,modell,g2,30)
            vergleich=unterraumvergleich(m,andere)
            konvergenz={"grad_referenz":g2,"unterraeume":vergleich}
        def feld(index):
            return float(m.frequenzen_hz[index-1]),m.feld(index-1,x,x)
    f1,w1=feld(i)
    f2,w2=feld(j) if j else (0.,np.zeros_like(w1))
    theta=np.deg2rad(mix)
    a,b=np.cos(theta)*w1,np.sin(theta)*w2
    skala=np.max(abs(a)+abs(b))
    if not np.isfinite(skala) or skala<=0:
        raise ArithmeticError("Normierung des Modenfelds fehlgeschlagen.")
    return {"modell":modell,"grad":grad,"mode":i,"mode2":j,"mischung_deg":mix,"n":n,
            "frequenzen_hz":[f1,f2] if j else [f1],
            "felder":[np.around(a/skala,5).ravel().tolist(),np.around(b/skala,5).ravel().tolist()],
            "referenz":"illustratives_eigenwertproblem","numerische_diagnose":diagnose,
            "gradvergleich":konvergenz}
