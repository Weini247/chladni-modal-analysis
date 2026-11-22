"""Prüfe Studienmanifest, V1-Verknüpfungen und V2-Abbildungsformate."""
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree
import json

import numpy as np
from PIL import Image
import pymupdf

from chladni.auswertung import PROJEKT, lese_json
from chladni.provenienz import dateihashes, json_schreiben


def fordere(bedingung: bool, hinweis: str):
    if not bedingung:
        raise ValueError(hinweis)


def main():
    p=ArgumentParser(description=__doc__)
    p.add_argument("--ziel",type=Path,default=PROJEKT/"ausgaben/privat/v2")
    p.add_argument("--v1",type=Path,default=PROJEKT/"ausgaben/privat/analyse")
    a=p.parse_args()
    z=a.ziel.resolve()
    if not z.is_relative_to(PROJEKT/"ausgaben/privat/v2"):
        p.error("V2-Ziel außerhalb des privaten Projektbereichs.")
    manifest=lese_json(z/"laufmanifest.json")
    for name,sha in manifest["code_sha256"].items():
        fordere(dateihashes(PROJEKT/"chladni"/(name+".py"))[0]==sha,f"Codeabweichung {name}")
    for name,sha in manifest["artefakte"].items():
        fordere(dateihashes(z/name)[0]==sha,f"Abweichender Export {name}")
    v1sha=dateihashes(a.v1/"atlas.json")[0]
    fordere(v1sha==manifest["v1_sha256"],"V1-Atlas passt nicht zum V2-Manifest.")
    atlas=lese_json(z/"atlas.json")
    inv=lese_json(z/"invers.json")
    m=lese_json(z/"mechanik.json")
    v1=lese_json(a.v1/"atlas.json")
    eintraege=lambda r:{q["id"]:q["sha256"] for q in r}
    fordere(eintraege(atlas["bilder"])==eintraege(v1["bilder"])==eintraege(inv["ergebnisse"]),
            "Atlas und Inverse haben verschiedene Quellenidentitäten.")
    fordere(m["benchmark"]["bestanden"],"Unabhängiger Literaturvergleich fehlt.")
    with np.load(z/"inverse_felder.npz") as f:
        ids=set(f["indices"])
        fordere(len(f["felder"])==len(ids) and f["felder"].shape==f["knoten"].shape,
                "Kandidatenspeicher enthält doppelte IDs oder inkonsistente Felder.")
        fordere(all(b["index"] in ids for r in inv["ergebnisse"]
                    for rang in (r["rang"],r["rang_nur_einzel"]) for b in rang),
                "Rangliste verweist auf fehlendes Raster.")
    exports={}
    for p0 in sorted((z/"figuren").glob("*.png")):
        with Image.open(p0) as i:
            i.verify()
        ElementTree.parse(p0.with_suffix(".svg"))
        with pymupdf.open(p0.with_suffix(".pdf")) as doc:
            fordere(len(doc)==1 and doc[0].get_text(),"PDF ohne Exportinhalt: "+p0.stem)
        for ende in (".png",".pdf",".svg"):
            f=p0.with_suffix(ende)
            exports[f.name]=dateihashes(f)[0]
    fordere(len(exports)==21,"Erwarte sieben V2-Abbildungen in je drei Formaten.")
    diag={"atlasbilder":len(atlas["bilder"]),"serien":len(atlas["serien"]),
          "freq_paare":atlas["frequenzpaare"],"chronologische_paare":atlas["chronologische_paare"],
          "inversion":dict(Counter(r["status"] for r in inv["ergebnisse"])),
          "kandidatenfelder":len(ids),"figuren_sha256":exports,"v1_atlas_sha256":v1sha,
          "inverse_npz_sha256":dateihashes(z/"inverse_felder.npz")[0]}
    json_schreiben(z/"audit_v2.json",diag)
    print(json.dumps({k:v for k,v in diag.items() if k!="figuren_sha256"},ensure_ascii=False))


if __name__=="__main__":
    main()
