"""V2-Eigencluster, Anschlussparameter, Unterräume und Konvergenzstudien."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from functools import lru_cache
from pathlib import Path

import numpy as np
from numpy.polynomial.legendre import Legendre, leggauss
from scipy.linalg import eigh
from scipy.optimize import linear_sum_assignment

from .eigenmoden import (ModenErgebnis, Platte, berechne_eigenmoden, kontaktmatrix,
                         plattenmatrizen)
from .mustervergleich import familien
from .provenienz import json_schreiben

NAHE_FREQ_REL = 0.005


@dataclass(frozen=True)
class Anschluss:
    radius_m: float = 0.006
    vertikal_n_m: float = 200000
    rotation_nm: float = 1.5
    verteilte_masse_kg: float = 0.018

    def __post_init__(self):
        z = (self.radius_m,self.vertikal_n_m,self.rotation_nm,self.verteilte_masse_kg)
        if not all(np.isfinite(x) and x>=0 for x in z) or self.radius_m==0 or self.vertikal_n_m==0:
            raise ValueError("Kontakt braucht Radius, vertikale Steifigkeit und nichtnegative Zusatzparameter.")


@lru_cache(maxsize=8)
def rotationsmatrix(grad: int, radius_rel: float) -> np.ndarray:
    """Flächenmittel der Gradienten-Energie auf demselben kreisförmigen Kontakt."""
    t,w=leggauss(grad+2)
    r=(t+1)/2
    nt=4*grad+4
    theta=np.linspace(0,2*np.pi,nt,endpoint=False)
    x=(2*radius_rel*r[:,None]*np.cos(theta)).ravel()
    y=(2*radius_rel*r[:,None]*np.sin(theta)).ravel()
    pol=[Legendre.basis(i)*np.sqrt(2*i+1) for i in range(grad+1)]
    wert=lambda x,d: np.stack([2**d*p.deriv(d)(x) for p in pol],axis=1)
    dx=(wert(y,0)[:,:,None]*wert(x,1)[:,None,:]).reshape(len(x),-1)
    dy=(wert(y,1)[:,:,None]*wert(x,0)[:,None,:]).reshape(len(x),-1)
    gew=np.repeat(w*r/nt,nt)[:,None]
    return dx.T @ (gew*dx) + dy.T @ (gew*dy)


def aufgesetzte_masse(platte: Platte, anschluss: Anschluss, grad: int, anzahl: int) -> ModenErgebnis:
    if not 2 <= grad <= 24 or not 1 <= anzahl <= (grad+1)**2:
        raise ValueError("Modenzahl oder Grad außerhalb des unterstützten Raums.")
    radius=anschluss.radius_m/platte.seite_m
    if not 0 < radius < 0.5:
        raise ValueError("Die Kontaktfläche muss im Platteninneren liegen.")
    m,k=plattenmatrizen(grad,platte.nu,False)
    c=kontaktmatrix(grad,radius)
    d=platte.biegesteifigkeit_nm
    k=k+(anschluss.vertikal_n_m*platte.seite_m**2/d)*c
    if anschluss.rotation_nm:
        k=k+(anschluss.rotation_nm/d)*rotationsmatrix(grad,radius)
    m=m+(anschluss.verteilte_masse_kg/(platte.rho_kg_m3*platte.dicke_m*platte.seite_m**2))*c
    # Beide Kontaktmatrizen sind positiv definit. Im reziproken Problem liegen die
    # kleinsten physikalischen Eigenwerte am gut aufgelösten Ende des Spektrums.
    mu,dual=eigh((m+m.T)/2,(k+k.T)/2,subset_by_index=(len(k)-anzahl,len(k)-1))
    if np.any(mu<=0):
        raise ArithmeticError("Anschlussmodell lieferte einen nichtpositiven Eigenwert.")
    mu=mu[::-1]
    lam=1/mu
    vek=dual[:,::-1]/np.sqrt(mu)
    # Feldbasis ist dieselbe freie Legendre-Basis wie bei der V1-Federfläche.
    return ModenErgebnis("federflaeche",grad,lam,np.sqrt(lam)*platte.hz_skala,vek,m,k,np.eye(len(m)),0)


def spektrum(p: Platte, name: str, grad: int, mindestens: int,
             kontakt: Anschluss = Anschluss(), nahe_freq: float = NAHE_FREQ_REL) -> ModenErgebnis:
    """Lese mindestens eine Wächter-Mode und erweitere über den gesamten Randcluster."""
    if type(mindestens) is not int or mindestens<1 or not 2 <= grad <= 24 or not 0 <= nahe_freq < 0.1:
        raise ValueError("Erwarte positive Modenzahl und sinnvolle Frequenzlücke.")
    freiheitsgrade=(grad+1)**2-{"frei":3,"zentralpunkt":3}.get(name,0)
    if mindestens>freiheitsgrade:
        raise ValueError("Modenzahl außerhalb des diskreten Raumes.")
    n=min(freiheitsgrade,mindestens+4)
    while True:
        if name in {"anschluss","federflaeche"}:
            anschluss=kontakt if name=="anschluss" else replace(kontakt,rotation_nm=0,verteilte_masse_kg=0)
            ergebnis=aufgesetzte_masse(p,anschluss,grad,n)
        else:
            ergebnis=berechne_eigenmoden(p,name,grad,n,kontakt.radius_m,kontakt.vertikal_n_m)
        end=next(g[-1]+1 for g in familien(ergebnis.frequenzen_hz,nahe_freq) if mindestens-1 in g)
        if end<n or n==freiheitsgrade:
            return replace(ergebnis,lambda_=ergebnis.lambda_[:end],frequenzen_hz=ergebnis.frequenzen_hz[:end],
                           koeffizienten=ergebnis.koeffizienten[:,:end])
        n=min(freiheitsgrade,n+8)


def _feldbasen(m: ModenErgebnis, n: int, g: list[tuple[int,...]]) -> list[np.ndarray]:
    x=(np.arange(n)+0.5)/n
    return [np.linalg.qr(np.stack([m.feld(i,x,x).ravel() for i in familie],1),mode="reduced")[0] for familie in g]


def unterraumvergleich(a: ModenErgebnis,b: ModenErgebnis,n: int=55) -> list[dict]:
    ga,gb=(familien(m.frequenzen_hz,NAHE_FREQ_REL) for m in (a,b))
    qa,qb=_feldbasen(a,n,ga),_feldbasen(b,n,gb)
    # Normalisierte Projektorüberlappung. Unterschiedliche Dimensionen erhalten einen Abzug.
    u=np.array([[np.linalg.norm(x.T@y,"fro")**2/max(x.shape[1],y.shape[1]) for y in qb] for x in qa])
    ia,ib=linear_sum_assignment(-u)
    k=[]
    for i,j in zip(ia,ib,strict=True):
        s=np.linalg.svd(qa[i].T@qb[j],compute_uv=False)
        a_hz,b_hz=float(np.mean(a.frequenzen_hz[list(ga[i])])),float(np.mean(b.frequenzen_hz[list(gb[j])]))
        k.append({"a":[x+1 for x in ga[i]],"b":[x+1 for x in gb[j]],"hz_a":a_hz,"hz_b":b_hz,
                  "frequenz_delta_rel": b_hz/a_hz-1,
                  "projektor_overlap":float(np.clip(u[i,j],0,1)),
                  "max_hauptwinkel_grad":float(np.rad2deg(np.arccos(np.clip(s.min(),0,1)))),
                  "dimensionswechsel":len(ga[i])!=len(gb[j])})
    return k


def residuale(m: ModenErgebnis) -> dict:
    v=m.koeffizienten
    mv=m.masse@v
    r=m.freiheitsbasis.T@(m.steifigkeit@v-mv*m.lambda_)
    norm=np.linalg.norm(r,axis=0)/(np.linalg.norm(mv,axis=0)*m.lambda_)
    orth=v.T@mv-np.eye(v.shape[1])
    return {"rel_residuum_max":float(norm.max()),"m_orthogon_abs_max":float(np.abs(orth).max()),
            "rel_residuen":norm.tolist()}


def modellstudie(ziel: Path,p: Platte,k: Anschluss) -> dict:
    ziel.mkdir(parents=True,exist_ok=True)
    namen=("frei","zentralpunkt","federflaeche","anschluss")
    grade=(12,16,20,24)
    modeller={name:[spektrum(p,name,g,30,k) for g in grade] for name in namen}
    bericht={}
    for name,serie in modeller.items():
        bericht[name]={"stufen":[{"grad":m.grad,"hz":m.frequenzen_hz.tolist(),**residuale(m)} for m in serie],
                       "unterraeume":[{"grad_a":a.grad,"grad_b":b.grad,"vergleich":unterraumvergleich(a,b)}
                                      for a,b in zip(serie[:-1],serie[1:],strict=True)]}
    benchmark=np.array([13.47,19.60,24.27,34.80,34.80])
    rechnung=np.sqrt(spektrum(replace(p,nu=.3),"frei",20,5).lambda_[:5])
    # Huang et al. Tab. 1, zwei Dezimalstellen. Toleranz: eine halbe letzte Dezimalstelle.
    frei_fehler=np.abs(rechnung-benchmark)
    basis=modeller["anschluss"][-1]
    variationen=[
        ("kontakt_weich",p,replace(k,vertikal_n_m=k.vertikal_n_m/2,rotation_nm=k.rotation_nm/2)),
        ("kontakt_hart",p,replace(k,vertikal_n_m=k.vertikal_n_m*2,rotation_nm=k.rotation_nm*2)),
        ("keine_zusatzmasse",p,replace(k,verteilte_masse_kg=0)),
        ("radius_groesser",p,replace(k,radius_m=k.radius_m*1.5)),
        ("E_plus_10_prozent",replace(p,e_pa=p.e_pa*1.1),k),
        ("dicke_plus_10_prozent",replace(p,dicke_m=p.dicke_m*1.1),k),
        ("dichte_plus_10_prozent",replace(p,rho_kg_m3=p.rho_kg_m3*1.1),k),
        ("poisson_0_30",replace(p,nu=.30),k)]
    sensitivitaet=[{"name":name,"platte":asdict(pp),"kontakt":asdict(kk),
                   "vergleich":unterraumvergleich(basis,spektrum(pp,"anschluss",24,30,kk))}
                   for name,pp,kk in variationen]
    modellpaar=[{"modell_a":"frei","modell_b":name,"vergleich":unterraumvergleich(modeller["frei"][-1],seq[-1])}
                 for name,seq in modeller.items() if name!="frei"]
    out={"schema":2,"platte":asdict(p),"anschluss":asdict(k),"nahe_freq_rel":NAHE_FREQ_REL,
         "benchmark":{"quelle":"Huang, Leissa & Liao 2008, Tab. 1, P=10×10",
                      "werte":benchmark.tolist(),"rechnung":rechnung.tolist(),
                      "abs_fehler_max":float(frei_fehler.max()),"bestanden":bool(frei_fehler.max()<.005)},
         "modelle":bericht,"sensitivitaet":sensitivitaet,"modellwechsel":modellpaar}
    json_schreiben(ziel/"mechanik.json",out)
    print(f"Mechanik V2: {len(namen)} Modelle × {len(grade)} Grade, Literatur-Maximum {frei_fehler.max():.5f}.",flush=True)
    return out
