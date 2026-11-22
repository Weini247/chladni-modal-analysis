"""Getrennter M0/M2-Vergleich auf der experimentellen Kontrollserie."""
from argparse import ArgumentParser
from pathlib import Path
from collections import defaultdict
import numpy as np

from chladni.auswertung import PROJEKT, lese_json
from chladni.eigenmoden import Platte
from chladni.inverse_modelle import InversParameter, Katalog, grobraster
from chladni.plattenmechanik import Anschluss
from chladni.provenienz import dateihashes, json_schreiben


def main():
    p=ArgumentParser(description=__doc__)
    p.add_argument("--v1",type=Path,default=PROJEKT/"ausgaben/privat/analyse")
    p.add_argument("--ziel",type=Path,default=PROJEKT/"ausgaben/privat/v2")
    p.add_argument("--konfig",type=Path,default=PROJEKT/"konfiguration/v2.json")
    a=p.parse_args()
    if not a.ziel.resolve().is_relative_to(PROJEKT/"ausgaben/privat/v2"):
        p.error("Ziel innerhalb der privaten V2-Ausgaben erforderlich.")
    cfg=lese_json(a.konfig)
    k=Katalog(Platte(**cfg["platte"]),Anschluss(**cfg["anschluss"]),InversParameter(**cfg["invers"]))
    modelle=defaultdict(list)
    for i,h in enumerate(k.hypothesen):
        modelle[h.modell].append(i)
    atlas=lese_json(a.v1/"atlas.json")
    serie=cfg["experimente"]["invers_real_holdout"]
    out=[]
    for q in atlas["bilder"]:
        if q["serie"]!=serie:
            continue
        raster=a.v1/q["id"]/"raster.npz"
        with np.load(raster) as f:
            lin,vis=grobraster(f["linien"],f["sicht"],k.c.raster)
        d=k.distanzen(lin,vis)
        if d is None:
            continue
        fit,hold=d
        scores=[]
        for n,ind in modelle.items():
            for art in (("einzel","mischung") if n!="historisch" else ("einzel",)):
                eligible=[i for i in ind if (art=="mischung" or len(k.hypothesen[i].moden)==1)]
                idx=min(eligible,key=lambda i:fit[i]+k.c.regularisierung_rel*(len(k.hypothesen[i].moden)-1))
                h=k.hypothesen[idx]
                df=max(min(h.eigenfrequenzen_hz)-q["hz"],q["hz"]-max(h.eigenfrequenzen_hz),0)
                scores.append({"modell":n,"katalog":art,"familie":h.familie,"moden":h.moden,
                               "fit_rel":float(fit[idx]),"pruefung_rel":float(hold[idx]),"abstand_hz":df})
        out.append({"id":q["id"],"hz":q["hz"],"sha256":q["sha256"],"messungen":scores})
    result={"serie":serie,"konfiguration_sha256":dateihashes(a.konfig)[0],"fotos":out,
            "mediane":[{"modell":n,"katalog":m,
                       "test_rel":float(np.median([r["pruefung_rel"] for q in out for r in q["messungen"]
                                                      if r["modell"]==n and r["katalog"]==m]))}
                       for n,m in sorted({(r["modell"],r["katalog"]) for q in out for r in q["messungen"]})]}
    json_schreiben(a.ziel/"m0_m2_vergleich.json",result)
    print(result["mediane"])


if __name__=="__main__":
    main()
