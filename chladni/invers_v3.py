"""Vorab registrierte Ablationen für die Modell–Experiment-Diskrepanz."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy.stats import binomtest
from skimage.morphology import skeletonize

from .auswertung import lese_json
from .eigenmoden import Platte
from .inverse_modelle import InversParameter, Katalog, grobraster, kennzeichne
from .mustervergleich import knotenraster, transformiere
from .plattenmechanik import Anschluss, spektrum, unterraumvergleich
from .provenienz import dateihashes, json_schreiben
from .v3_pfade import Eingaben

TREFFER = "KANDIDAT_IM_BEOBACHTUNGSMODELL"


def rangliste(k: Katalog, d, freq: float | None, *, modelle=None, einzeln=False,
              strafe=None, limit=6) -> list[dict]:
    """Rang nach Fitfläche, mit höchstens einer Hypothese je Modellfamilie."""
    if d is None:
        return []
    fit, test = d
    strafe = k.c.regularisierung_rel if strafe is None else strafe
    gewichte = np.array([strafe*(len(h.moden)-1) for h in k.hypothesen])
    order = np.argsort(fit+gewichte,kind="stable")
    gesehen, ret = set(), []
    for i in order:
        h=k.hypothesen[i]
        key=(h.modell,h.familie)
        if key in gesehen or (einzeln and len(h.moden)>1) or (modelle is not None and h.modell not in modelle):
            continue
        gesehen.add(key)
        lo,hi=min(h.eigenfrequenzen_hz),max(h.eigenfrequenzen_hz)
        ret.append({"index":int(i),"modell":h.modell,"familie":list(h.familie),"moden":list(h.moden),
                    "koeffizienten":list(h.koeffizienten),"d4":h.orientierung_d4,
                    "fit_rel":float(fit[i]),"test_rel":float(test[i]),
                    "freq_abstand_hz":max(lo-freq,freq-hi,0.) if freq is not None else None,
                    "frequenzspanne_hz":[lo,hi]})
        if len(ret)==limit:
            break
    return ret


def tolerante_distanz(k: Katalog, lin: np.ndarray, sicht: np.ndarray, tau: float):
    """1−F1 aus beidseitiger Linienüberdeckung innerhalb tau auf jeder Fläche."""
    werte=[]
    for region,(linien,distanz) in zip(k.bereiche,k._paare,strict=True):
        sichtbar = sicht & region
        obs = sichtbar & lin
        n = obs.sum()
        if n < 6:
            return None
        s = sichtbar.ravel().astype(np.float32)
        recall = (distanz<=tau)@obs.ravel().astype(np.float32)/n
        treffen = ndi.distance_transform_edt(~obs).ravel() <= tau*k.c.raster
        m = linien@s
        precision = np.divide(linien@(treffen*s),m,out=np.zeros_like(m),where=m>0)
        nenner = recall+precision
        f1=np.divide(2*recall*precision,nenner,out=np.zeros_like(nenner),where=nenner>0)
        werte.append(1-f1)
    return tuple(werte)


def beurteile(rang: list[dict], schwellen: dict) -> dict:
    status, luecke=kennzeichne(rang,schwellen)
    top=rang[0] if rang else None
    return {"status":status,"luecke_rel":luecke,
            "prueffehler_rel":top["test_rel"] if top else None,
            "familie":[top["modell"],top["familie"]] if top else None,
            "rang":rang}


def _kurz(rang, schwellen) -> dict:
    o=beurteile(rang,schwellen)
    del o["rang"]
    return o


def _unif(k: Katalog, auswahl=None, einzeln=False) -> int:
    return len({(h.modell,h.familie) for h in k.hypothesen
                if (auswahl is None or h.modell in auswahl) and (not einzeln or len(h.moden)==1)})


def kollisionsstatistik(k: Katalog) -> dict:
    gruppen=defaultdict(set)
    for h,lin in zip(k.hypothesen,k.linien,strict=True):
        gruppen[np.packbits(k.grund & lin).tobytes()].add((h.modell,h.familie))
    kollision=[g for g in gruppen.values() if len(g)>1]
    beispiel=sorted(kollision,key=lambda g:(-len(g),sorted(g)))[:3]
    return {"verschiedene_masken":len(gruppen),"familienuebergreifende_masken":len(kollision),
            "beispiele":[sorted(g) for g in beispiel]}


def _zielmuster(k: Katalog, p: Platte, anschluss: Anschluss, cfg: dict):
    """Renderfelder aus Grad 24. Referenzlabels sind projizierte Grad-20-Cluster."""
    rng=np.random.default_rng(cfg["seed"])
    n=2*k.c.raster
    x=(np.arange(n)+.5)/n
    xx,yy=np.meshgrid(x,x)
    pool={"einzel":[], "paar":[]}
    erlaubte={ (h.modell,h.familie) for h in k.hypothesen }
    for name,m in k.modelle.items():
        hi=spektrum(p,name,cfg["referenzgrad"],k.c.moden,anschluss)
        paare=unterraumvergleich(m,hi)
        mapping={i-1:tuple(map(str,z["a"])) for z in paare
                 if not z["dimensionswechsel"] and z["projektor_overlap"]>=.98 for i in z["b"]}
        ids=[i for i in sorted(mapping) if i>=3]
        pool["einzel"] += [(name,hi,i,None,mapping[i]) for i in ids]
        for i,j in combinations(ids,2):
            fam=tuple(sorted(set(mapping[i]+mapping[j]),key=int))
            if (name,fam) in erlaubte and hi.frequenzen_hz[j]/hi.frequenzen_hz[i]-1<=k.c.nahe_frequenzen_rel:
                pool["paar"].append((name,hi,i,j,fam))
    for art, kandidaten in pool.items():
        m=cfg["anzahl_pro_art"]
        if len(kandidaten)<m:
            raise ValueError(f"Zu wenige unabhängige Referenzfälle für {art}.")
        for i0,j0 in enumerate(rng.choice(len(kandidaten),m,replace=False)):
            name, hi, a,b,fam=kandidaten[j0]
            w=hi.feld(a,x,x)
            if b is not None:
                phi=rng.uniform(.2,2.94)
                w=np.cos(phi)*w+np.sin(phi)*hi.feld(b,x,x)
            orient=int(rng.integers(8))
            yield f"{art}-{i0+1:02d}",art,(name,list(fam)),knotenraster(transformiere(w,orient))
    for i in range(cfg["anzahl_pro_art"]):
        w=np.ones_like(xx)
        for _ in range(3):
            cx,cy=rng.uniform(.2,.8,2)
            a,b=rng.uniform(.08,.34,2)
            t=rng.uniform(0,np.pi)
            u=(xx-cx)*np.cos(t)+(yy-cy)*np.sin(t)
            v=-(xx-cx)*np.sin(t)+(yy-cy)*np.cos(t)
            w *= (u/a)**2+(v/b)**2-1
        yield f"null-{i+1:02d}","null",None,knotenraster(w)


def _varianten(linie,breite,rng):
    n=len(linie)
    x,y=np.meshgrid(np.arange(n),np.arange(n))
    full=np.ones(linie.shape,bool)
    yield "ideal",linie,full
    breit=ndi.binary_dilation(linie,iterations=breite)
    # Ortsabhängig breite Ablagerung plus vereinzelte Körner. Beobachtungsproxy.
    breit |= (ndi.distance_transform_edt(~linie)<breite*1.8) & (x<.48*n) & (y>.28*n)
    breit |= rng.random(linie.shape)<.004
    yield "breit_diffus",skeletonize(breit),full
    loch=(x-.54*n)**2+(y-.43*n)**2<(.12*n)**2
    yield "unterbrochen",linie & ~loch,full
    dx=2.5*np.sin(2*np.pi*y/n)
    dy=2*np.sin(2*np.pi*x/n)
    bewegung=ndi.map_coordinates(breit,[y+dy,x+dx],order=0,mode="constant")
    yield "registrierung",skeletonize(bewegung),full


def _synthetisch(k,p,anschluss,cfg):
    rng=np.random.default_rng(cfg["seed"]+1)
    result=[]
    tau=cfg["toleranz_raster_px"]/k.c.raster
    for id,art,wahr,linie in _zielmuster(k,p,anschluss,cfg):
        for name,l,sicht in _varianten(linie,cfg["band_raster_px"],rng):
            y,g=grobraster(l,sicht,k.c.raster)
            d=k.distanzen(y,g)
            reihen={
                "v2_distanz":rangliste(k,d,None),
                "rein_einzel":rangliste(k,d,None,einzeln=True),
                "tolerantes_f1":rangliste(k,tolerante_distanz(k,y,g,tau),None),
            }
            for verfahren,rg in reihen.items():
                top=[(r["modell"],r["familie"]) for r in rg]
                passt=wahr in top
                hatklasse=wahr is not None and any(
                    (h.modell,list(h.familie))==wahr and (verfahren!="rein_einzel" or len(h.moden)==1)
                    for h in k.hypothesen)
                status=kennzeichne(rg,cfg["schwellen"])[0] if verfahren=="v2_distanz" else None
                result.append({"id":id,"art":art,"stoerung":name,"verfahren":verfahren,"wahr":wahr,
                               "klasse_im_katalog":hatklasse,"top1":bool(top and top[0]==wahr),
                               "top6":passt,"bewertbar":bool(top),"status":status})
    zusammen=[]
    gruppen=defaultdict(list)
    for q in result:
        gruppen[(q["art"],q["stoerung"],q["verfahren"])].append(q)
    for (art,name,v),zz in sorted(gruppen.items()):
        klassen=_unif(k,einzeln=v=="rein_einzel")
        n=len(zz)
        known=sum(q["klasse_im_katalog"] and q["bewertbar"] for q in zz)
        akzeptiert=[q for q in zz if q["status"]==TREFFER]
        ci=binomtest(len(akzeptiert),n).proportion_ci(.95,method="wilson") if v=="v2_distanz" else None
        zusammen.append({"art":art,"stoerung":name,"verfahren":v,"n":n,"klassen":klassen,
                         "bewertbar":sum(q["bewertbar"] for q in zz),
                         "top1":sum(q["top1"] for q in zz),"top6":sum(q["top6"] for q in zz),
                         "zufall_top1_erwartet":known/klassen,"zufall_top6_erwartet":known*min(6,klassen)/klassen,
                         "akzeptiert":len(akzeptiert) if ci else None,
                         "falschakzeptiert":sum(not q["top1"] for q in akzeptiert) if ci else None,
                         "akzeptanz_wilson_95":[ci.low,ci.high] if ci else None})
    return {"faelle":result,"summen":zusammen}


def _messen(k: Katalog, foto: dict, linien, sichtbar, cfg, modelle=None, einzeln=False) -> dict:
    lin,sicht=grobraster(linien,sichtbar,k.c.raster)
    d=k.distanzen(lin,sicht)
    return _kurz(rangliste(k,d,foto["hz"],modelle=modelle,einzeln=einzeln),cfg["schwellen"])


def gap_studie(e: Eingaben, cfg: dict) -> dict:
    v2=lese_json(e.v2/"laufmanifest.json")["konfiguration"]
    p,k=Platte(**v2["platte"]),Anschluss(**v2["anschluss"])
    c=InversParameter(**v2["invers"])
    g=cfg["gap"]
    alt=lese_json(e.v2/"invers.json")
    if alt["synthetische_schwellen"]!=g["schwellen"]:
        raise ValueError("Die V2-Schwellen wurden in der V3-Konfiguration verändert.")
    katalog=Katalog(p,k,c)
    print(f"Gap: {len(katalog.hypothesen)} Hypothesen, {_unif(katalog)} Modellfamilien.",flush=True)
    syn=_synthetisch(katalog,p,k,g)
    fotos=[q for q in lese_json(e.v1/"atlas.json")["bilder"] if q["serie"] in cfg["serien"]]
    vv={q["id"]:{} for q in fotos}
    katalogfaelle=defaultdict(list)
    i_v2={q["id"]:q for q in alt["ergebnisse"]}
    for q in fotos:
        with np.load(e.ziel/"bildvarianten"/f"{q['id']}.npz") as z:
            linien,sicht=z["linien"],z["sicht"]
            for j,name in enumerate(z["namen"]):
                vv[q["id"]][str(name)] = _messen(katalog,q,linien[j],sicht[j],g)
        with np.load(e.v1/q["id"]/"raster.npz") as z:
            lin,s=grobraster(z["linien"],z["sicht"],c.raster)
        d=katalog.distanzen(lin,s)
        rg=rangliste(katalog,d,q["hz"])
        v2r=i_v2[q["id"]]["rang"]
        if [r["index"] for r in rg] != [r["index"] for r in v2r]:
            raise ArithmeticError(f"V2-Rang mit gleichem Kandidatenraum nicht reproduziert: {q['id']}")
        if q["serie"]!=cfg["kontrollserie"]:
            continue
        for name in ("historisch","frei","zentralpunkt","federflaeche","anschluss"):
            zz=rangliste(katalog,d,q["hz"],modelle={name})
            katalogfaelle[name].append({"id":q["id"],**_kurz(zz,g["schwellen"])})
        for name,einzeln in (("alle",False),("nur_einzel",True)):
            zz=rangliste(katalog,d,q["hz"],einzeln=einzeln)
            katalogfaelle[name].append({"id":q["id"],**_kurz(zz,g["schwellen"])})
        f1=rangliste(katalog,tolerante_distanz(katalog,lin,s,g["toleranz_raster_px"]/c.raster),q["hz"])
        katalogfaelle["tolerantes_f1"].append({"id":q["id"],"status":"UNZUGEORDNETE_METRIK",
            "familie":[f1[0]["modell"],f1[0]["familie"]] if f1 else None,
            "prueffehler_rel":f1[0]["test_rel"] if f1 else None})
    ident=kollisionsstatistik(katalog)
    anz=len(katalog.hypothesen)
    klassen=_unif(katalog)
    freie=katalog.modelle["frei"]
    material=spektrum(replace(p,e_pa=p.e_pa*1.21),"frei",c.grad,c.moden,k)
    check=unterraumvergleich(freie,material)
    invariant={"e_faktor":1.21,"min_projektor":min(a["projektor_overlap"] for a in check),
               "median_faktor":float(np.median([1+a["frequenz_delta_rel"] for a in check]))}
    del katalog
    veraenderungen=[
        ("anschluss_grad24",k,replace(c,grad=24)),
        *[(f"anschluss_steifigkeit_{s:g}",replace(k,vertikal_n_m=k.vertikal_n_m*s),c) for s in g["kontakt_faktoren"]],
        ("anschluss_radius_groesser",replace(k,radius_m=k.radius_m*g["radius_faktor"]),c),
    ]
    for name,annahme,param in veraenderungen:
        sk=Katalog(p,annahme,param)
        for q in fotos:
            if q["serie"]!=cfg["kontrollserie"]:
                continue
            with np.load(e.v1/q["id"]/"raster.npz") as z:
                zz=_messen(sk,q,z["linien"],z["sicht"],g,modelle={"anschluss"})
            katalogfaelle[name].append({"id":q["id"],"klassen":_unif(sk,{"anschluss"}),**zz})
        del sk
        print(f"Gap: Modellvariante {name} ausgewertet.",flush=True)
    aggregat=[]
    for name,ff in katalogfaelle.items():
        werte=[x["prueffehler_rel"] for x in ff if x["prueffehler_rel"] is not None]
        aggregat.append({"name":name,"n":len(ff),"bewertbar":len(werte),
                         "median_prueffehler_rel":float(np.median(werte)) if werte else None,
                         "treffer":sum(x["status"]==TREFFER for x in ff) if name!="tolerantes_f1" else None,
                         "faelle":ff})
    ergebnis={"schema":3,"sha256_v2":dateihashes(e.v2/"invers.json")[0],"schwellen":g["schwellen"],
              "katalog":{"hypothesen":anz,"klassen":klassen},"bildvarianten":vv,
              "serien":{s:[q["id"] for q in fotos if q["serie"]==s] for s in cfg["serien"]},
              "kontrollserie":cfg["kontrollserie"],"ablationsstudien":aggregat,
              "identifizierbarkeit":ident,"materialinvarianz_frei":invariant,"synthetisch":syn}
    json_schreiben(e.ziel/"gap.json",ergebnis)
    return ergebnis
