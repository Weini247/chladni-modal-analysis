"""Getrennte synthetische Kalibration und Prüfung sowie reales Screening."""
from __future__ import annotations

from dataclasses import asdict, replace
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy.stats import binomtest
from skimage.morphology import skeletonize

from .auswertung import lese_json
from .bildpipeline import BildParameter, segmentiere
from .eigenmoden import Platte
from .inverse_modelle import InversParameter, Katalog, grobraster, kennzeichne
from .mustervergleich import familien, knotenraster, transformiere
from .plattenmechanik import Anschluss
from .provenienz import dateihashes, json_schreiben

AKZEPTIERT="KANDIDAT_IM_BEOBACHTUNGSMODELL"


def _syn(k: Katalog,seed: int,n: int) -> list[dict]:
    rng=np.random.default_rng(seed)
    N=k.c.raster*2
    x=(np.arange(N)+.5)/N
    xx,yy=np.meshgrid(x,x)
    out=[]
    for art in ("einzel","paar","null"):
        for i in range(n):
            wahr=None
            if art!="null":
                name=("frei","anschluss", "zentralpunkt","federflaeche")[i%4]
                m=k.modelle[name]
                fs=m.frequenzen_hz
                g=familien(fs,.005)
                idg={j:tuple(str(q+1) for q in p) for p in g for j in p}
                if art=="einzel":
                    j=int(rng.integers(3,len(fs)))
                    feld=m.feld(j,x,x)
                    wahr=(name,list(idg[j]))
                else:
                    paare=[(a,b) for a,b in combinations(range(3,len(fs)),2) if fs[b]/fs[a]-1<=k.c.nahe_frequenzen_rel]
                    j,l=paare[int(rng.integers(len(paare)))]
                    theta=rng.uniform(.22,2.95)
                    feld=np.cos(theta)*m.feld(j,x,x)+np.sin(theta)*m.feld(l,x,x)
                    wahr=(name,list(dict.fromkeys(idg[j]+idg[l])))
                echt=knotenraster(transformiere(feld,int(rng.integers(8))))
            else:
                f=np.ones((N,N))
                for _ in range(int(rng.integers(2,5))):
                    x0,y0=rng.uniform(.18,.82,2)
                    a,b=rng.uniform(.09,.37,2)
                    theta=rng.uniform(0,np.pi)
                    u=(xx-x0)*np.cos(theta)+(yy-y0)*np.sin(theta)
                    v=-(xx-x0)*np.sin(theta)+(yy-y0)*np.cos(theta)
                    f*=((u/a)**2+(v/b)**2-1)
                echt=knotenraster(f)
            breit=int(rng.integers(1,4))
            foto=ndi.binary_dilation(echt,iterations=breit)
            gw=rng.uniform(.14,.86,2)
            sicht=((xx-gw[0])**2+(yy-gw[1])**2)>rng.uniform(.075,.13)**2
            if i%2:
                loch=rng.uniform(.19,.81,2)
                foto &= ((xx-loch[0])**2+(yy-loch[1])**2)>.105**2
            foto ^= rng.random(foto.shape)<.0035
            if i%3==0:
                aa,bb=rng.uniform(.2,.8,2)
                foto|=(np.abs(yy-aa)<.012) & (np.abs(xx-bb)<.08)
            lin,mask=grobraster(skeletonize(foto & sicht),sicht,k.c.raster)
            d=k.distanzen(lin,mask)
            rang=k.ranke(d,k.c.regularisierung_rel)
            einzeln=k.ranke(d,0.,nur_einzel=True)
            def richtig(row):
                return bool(wahr and row and row["modell"]==wahr[0] and row["familie"]==wahr[1])
            out.append({"art":art,"id":f"{art}-{i:02d}","wahr":wahr,"verbreiterung_px":breit,
                        "richtiger_erster":bool(rang and richtig(rang[0])),
                        "richtige_familie_top6":any(richtig(r) for r in rang),
                        "richtiger_einzel_baseline":bool(einzeln and richtig(einzeln[0])),
                        "rang":rang[:6]})
    return out


def kalibriere(daten: list[dict]) -> dict:
    moeglich=[]
    for s in range(12,73,4):
        for luecke in (0.,.0015,.003,.0045,.006):
            grenze={"max_test_rel":s/1000,"min_abstand_rel":luecke}
            accept=[z for z in daten if kennzeichne(z["rang"],grenze)[0]==AKZEPTIERT]
            falsch_null=sum(z["art"]=="null" for z in accept)
            wahr=sum(z["richtiger_erster"] for z in accept)
            falsch_modell=len(accept)-wahr-falsch_null
            if falsch_null<=1 and falsch_modell<=1:
                moeglich.append(((wahr,-falsch_null,-falsch_modell,-s,luecke),grenze))
    if not moeglich:
        return {"max_test_rel":0.0,"min_abstand_rel":0.006}
    return max(moeglich,key=lambda paar:paar[0])[1]


def _zaehlung(a: list[dict],grenze: dict) -> dict:
    o={}
    for typ in ("einzel","paar","null"):
        d=[r for r in a if r["art"]==typ]
        e=[r for r in d if kennzeichne(r["rang"],grenze)[0]==AKZEPTIERT]
        r=sum(z["richtiger_erster"] for z in d)
        interval=binomtest(len(e),len(d)).proportion_ci(.95,method="wilson")
        o[typ]={"n":len(d),"top1":r,"top6":sum(z["richtige_familie_top6"] for z in d),
                "top1_einzel_baseline":sum(z["richtiger_einzel_baseline"] for z in d),
                "akzeptiert":len(e),"akzeptiert_richtig":sum(z["richtiger_erster"] for z in e),
                "akzeptanz_wilson_95":[interval.low,interval.high]}
    return o


def _signatur(r: list[dict]):
    return (r[0]["modell"],tuple(r[0]["familie"])) if r else None


def _analysiere_foto(k: Katalog,z: dict,pfad: Path,grenzen: dict,pp: BildParameter,
                     holdout: str) -> dict:
    with np.load(pfad) as f:
        lin,sicht=grobraster(f["linien"],f["sicht"],k.c.raster)
        s=k.distanzen(lin,sicht)
        rang=k.ranke(s,k.c.regularisierung_rel,z["hz"])
        einzel=k.ranke(s,0,z["hz"],nur_einzel=True)
        status,abstand=kennzeichne(rang,grenzen)
        g=k.c.regularisierung_rel
        rang_varianten={f"strafe_{a:g}":_signatur(k.ranke(s,a,z["hz"])) for a in (0.,g,2*g)}
        if z["serie"]==holdout:
            for delta in (-.02,.02):
                _,q=segmentiere(f["score"],f["sicht"],replace(pp,schwelle=pp.schwelle+delta))
                l,mask=grobraster(q,f["sicht"],k.c.raster)
                rang_varianten[f"schwelle_{delta:+.02f}"]=_signatur(k.ranke(k.distanzen(l,mask),g,z["hz"]))
    if len(set(rang_varianten.values()))>1 and status==AKZEPTIERT:
        status="NICHT_EINDEUTIG_IDENTIFIZIERBAR"
    # Frequency is recorded as a separate corroboration metric, with no fitted parameters.
    f_rang=sorted((r for r in rang if r["freq_abstand_hz"] is not None),key=lambda r:r["freq_abstand_hz"])
    return {"id":z["id"],"serie":z["serie"],"hz":z["hz"],"sha256":z["sha256"],"status":status,
            "test_abstand_zum_naechsten_rel":abstand,"rang":rang,"rang_nur_einzel":einzel,
            "freq_reihung_unter_top6":[{"index":r["index"],"freq_abstand_hz":r["freq_abstand_hz"]} for r in f_rang],
            "rang_varianten":rang_varianten,"experimentell_kalibrierter_treffer":False}


def inversionsstudie(v1: Path,ziel: Path,p: Platte,k: Anschluss,cfg: dict) -> dict:
    ziel.mkdir(parents=True,exist_ok=True)
    c=InversParameter(**cfg["invers"])
    library=Katalog(p,k,c)
    print(f"Inversion V2: {len(library.hypothesen)} unterschiedliche Rasterhypothesen.",flush=True)
    cal=_syn(library,c.seed_kalibration,c.anzahl_klasse)
    test=_syn(library,c.seed_test,c.anzahl_klasse)
    grenze=kalibriere(cal)
    testzahlen=_zaehlung(test,grenze)
    print(f"Synthetische Prüfung: {testzahlen}",flush=True)
    atlas=lese_json(v1/"atlas.json")
    bp=BildParameter(**atlas["konfiguration"]["bild_parameter"])
    holdout=cfg["experimente"]["invers_real_holdout"]
    real=[_analysiere_foto(library,z,v1/z["id"]/"raster.npz",grenze,bp,holdout) for z in atlas["bilder"]]
    typen=("rang","rang_nur_einzel")
    ids=sorted({r["index"] for z in real for typ in typen for r in z[typ]})
    np.savez_compressed(ziel/"inverse_felder.npz",indices=np.array(ids,dtype=int),
                        felder=library.feld[ids],knoten=library.linien[ids],
                        fit=library.bereiche[0],test=library.bereiche[1])
    syn={"schema":2,"parameter":asdict(c),"schwellen":grenze,
         "kandidatenzahl":len(library.hypothesen),"kalibration":_zaehlung(cal,grenze),
         "test":testzahlen,"kalibrationsfaelle":cal,"testfaelle":test}
    json_schreiben(ziel/"inverse_validierung.json",syn)
    bericht={"schema":2,"v1_atlas_sha256":dateihashes(v1/"atlas.json")[0],
              "synthetische_schwellen":grenze,"kontrollserie":holdout,
              "kandidatenzahl":len(library.hypothesen),"ergebnisse":real}
    json_schreiben(ziel/"invers.json",bericht)
    print(f"Inversion V2: {len(real)} Originale mit Rangliste/Abstinenzstatus.",flush=True)
    return bericht
