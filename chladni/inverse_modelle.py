"""Begrenztes Knotenlinien-Beobachtungsmodell und räumlich getrennte Rangliste."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import skeletonize

from .eigenmoden import Platte, historischer_kosinus
from .mustervergleich import familien, knotenraster, transformiere
from .plattenmechanik import Anschluss, spektrum


@dataclass(frozen=True)
class InversParameter:
    raster: int = 64
    grad: int = 20
    moden: int = 30
    winkel_schritt_grad: int = 20
    abstand_kappung_rel: float = .08
    regularisierung_rel: float = .0025
    nahe_frequenzen_rel: float = .025
    seed_kalibration: int = 52145
    seed_test: int = 79139
    anzahl_klasse: int = 28

    def __post_init__(self):
        if (not 32 <= self.raster <= 160 or not 4 <= self.grad <= 24 or self.moden<8 or
                not 5 <= self.winkel_schritt_grad <= 45 or not 0<self.abstand_kappung_rel<.25 or
                not 0<=self.regularisierung_rel<.025 or not .005<=self.nahe_frequenzen_rel<.1 or
                self.seed_kalibration==self.seed_test or self.anzahl_klasse<4):
            raise ValueError("Ungültige Konfiguration des inversen Versuchs.")


@dataclass(frozen=True)
class Hypothese:
    modell: str
    familie: tuple[str, ...]
    moden: tuple[str, ...]
    koeffizienten: tuple[float, ...]
    orientierung_d4: int
    eigenfrequenzen_hz: tuple[float, ...]
    index: int


def beobachtungsbereiche(raster: int) -> tuple[np.ndarray,np.ndarray,np.ndarray]:
    x=(np.arange(raster)+0.5)/raster
    xx,yy=np.meshgrid(x,x)
    grund=(np.hypot(xx-.5,yy-.5)>.112) & (xx>.035) & (xx<.965) & (yy>.035) & (yy<.965)
    u=(xx+.38*yy)/1.38
    fit=grund & (((u>=.06)&(u<=.26))|((u>=.52)&(u<=.74)))
    test=grund & (((u>=.31)&(u<=.47))|((u>=.79)&(u<=.94)))
    return grund,fit,test


def grobraster(linien: np.ndarray, sicht: np.ndarray, n: int) -> tuple[np.ndarray,np.ndarray]:
    if linien.shape!=sicht.shape or linien.ndim!=2 or linien.shape[0]!=linien.shape[1]:
        raise ValueError("Linien und Sicht müssen im selben quadratischen Raster liegen.")
    m=linien.shape[0]
    if m%n==0:
        k=m//n
        l=linien.reshape(n,k,n,k).any(axis=(1,3))
        g=sicht.reshape(n,k,n,k).all(axis=(1,3))
    else:
        y=(np.arange(n)+.5)*m/n-.5
        yy,xx=np.meshgrid(y,y,indexing="ij")
        g=ndi.map_coordinates(sicht,[yy,xx],order=0)
        l=ndi.map_coordinates(ndi.maximum_filter(linien,size=max(1,round(m/n))),[yy,xx],order=0)
    return skeletonize(l & g),g


class Katalog:
    def __init__(self,p: Platte,k: Anschluss,config: InversParameter):
        self.c=config
        self.modelle={name:spektrum(p,name,config.grad,config.moden,k) for name in
                      ("frei","zentralpunkt","federflaeche","anschluss")}
        x=(np.arange(config.raster)+.5)/config.raster
        self.hypothesen: list[Hypothese]=[]
        self.felder: list[np.ndarray]=[]
        historische=sorted((n*n+m*m,n,m) for n in range(10) for m in range(n,10) if n or m)
        for _,n,m in historische[:config.moden]:
            hz,f=historischer_kosinus(p,n,m,x,x)
            name=f"{n},{m}"
            self._orientiere("historisch",(name,),(name,),(1.,),(hz,),f)
        for name,m in self.modelle.items():
            frequenzen=m.frequenzen_hz
            feld=[m.feld(i,x,x) for i in range(len(frequenzen))]
            cluster=familien(frequenzen,.005)
            gruppen={i:tuple(str(j+1) for j in g) for g in cluster for i in g}
            for i,f in enumerate(feld):
                self._orientiere(name,gruppen[i],(str(i+1),),(1.,),(float(frequenzen[i]),),f)
            for i,j in combinations(range(len(frequenzen)),2):
                if frequenzen[j]/frequenzen[i]-1>config.nahe_frequenzen_rel:
                    continue
                familie=tuple(dict.fromkeys(gruppen[i]+gruppen[j]))
                for winkel in range(config.winkel_schritt_grad,180,config.winkel_schritt_grad):
                    a=np.deg2rad(winkel)
                    c,s=float(np.cos(a)),float(np.sin(a))
                    if abs(c)<1e-8 or abs(s)<1e-8:
                        continue
                    self._orientiere(name,familie,(str(i+1),str(j+1)),(c,s),
                                     (float(frequenzen[i]),float(frequenzen[j])),c*feld[i]+s*feld[j])
        self.feld=np.stack(self.felder)
        del self.felder
        self.linien=np.stack([knotenraster(f) for f in self.feld])
        self.grund,*self.bereiche=beobachtungsbereiche(config.raster)
        self._paare=[]
        for b in self.bereiche:
            f=self.linien & b
            maske=f.reshape(len(self.linien),-1).astype(np.float32)
            dist=np.stack([self._dt(k).ravel() for k in f]).astype(np.float32)
            self._paare.append((maske,dist))

    def _orientiere(self,modell,familie,moden,coeff,hz,w):
        gesehen=set()
        for code in range(8):
            q=transformiere(w,code)
            key=np.packbits(knotenraster(q)).tobytes()
            if key not in gesehen:
                idx=len(self.hypothesen)
                self.hypothesen.append(Hypothese(modell,familie,moden,coeff,code,hz,idx))
                self.felder.append(np.asarray(q/np.max(np.abs(q)),dtype=np.float32))
                gesehen.add(key)

    def _dt(self,linie):
        if np.any(linie):
            return np.minimum(ndi.distance_transform_edt(~linie)/self.c.raster,self.c.abstand_kappung_rel)
        return np.full(linie.shape,self.c.abstand_kappung_rel)

    def distanzen(self,linien: np.ndarray,sicht: np.ndarray) -> tuple[np.ndarray,np.ndarray] | None:
        if linien.shape!=self.grund.shape or sicht.shape!=self.grund.shape:
            raise ValueError("Für jedes Ranking ist dasselbe Raster wie für den Katalog nötig.")
        werte=[]
        for b,(s,d) in zip(self.bereiche,self._paare,strict=True):
            sichtbar=sicht & b
            beobachtet=linien & sichtbar
            if beobachtet.sum()<6:
                return None
            ab=d@beobachtet.ravel().astype(np.float32)/beobachtet.sum()
            n=s@sichtbar.ravel().astype(np.float32)
            ba=np.divide(s@(self._dt(beobachtet)*sichtbar).ravel().astype(np.float32),n,
                         out=np.full(len(n),self.c.abstand_kappung_rel,dtype=np.float32),where=n>0)
            werte.append((ab+ba)/2)
        return werte[0],werte[1]

    def ranke(self,distanzen,regularisierung: float,freq_hz: float|None=None,limit: int=6,
              nur_einzel: bool=False) -> list[dict]:
        if distanzen is None:
            return []
        fit,test=distanzen
        straf=np.array([regularisierung*(len(h.moden)-1) for h in self.hypothesen])
        order=np.argsort(fit+straf,kind="stable")
        ergebnis=[]
        gesehen=set()
        for i in order:
            h=self.hypothesen[i]
            key=(h.modell,h.familie)
            if key in gesehen or nur_einzel and len(h.moden)>1:
                continue
            gesehen.add(key)
            da=min(h.eigenfrequenzen_hz)
            db=max(h.eigenfrequenzen_hz)
            df=max(da-freq_hz,freq_hz-db,0.) if freq_hz is not None else None
            ergebnis.append({"index":int(i),"modell":h.modell,"familie":list(h.familie),"moden":list(h.moden),
                              "koeffizienten":list(h.koeffizienten),"d4":h.orientierung_d4,
                              "frequenzspanne_hz":[da,db],"freq_abstand_hz":df,
                              "fit_rel":float(fit[i]),"test_rel":float(test[i]),
                              "fit_regularisiert_rel":float(fit[i]+straf[i])})
            if len(ergebnis)==limit:
                break
        return ergebnis


def kennzeichne(rang: list[dict],grenzen: dict) -> tuple[str,float|None]:
    if len(rang)<2:
        return "ZU_WENIG_LINIENEVIDENZ",None
    abstand=min(k["test_rel"] for k in rang[1:])-rang[0]["test_rel"]
    if rang[0]["test_rel"]>grenzen["max_test_rel"]:
        return "KEIN_BELASTBARER_TREFFER",abstand
    if abstand<grenzen["min_abstand_rel"]:
        return "NICHT_EINDEUTIG_IDENTIFIZIERBAR",abstand
    return "KANDIDAT_IM_BEOBACHTUNGSMODELL",abstand
