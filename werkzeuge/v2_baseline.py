"""Führe unveränderte V1-Rechenwege für den Hauptbefund ohne Ergebniscache aus."""
from argparse import ArgumentParser
from collections import Counter
from dataclasses import replace
from pathlib import Path
import platform

import numpy as np

from chladni.auswertung import PROJEKT, lade_registrierungen, lese_json, varianten
from chladni.bildpipeline import BildParameter, analysiere_bild, diagnostik, linienabstand
from chladni.eigenmoden import Platte, berechne_eigenmoden
from chladni.frequenzen import bewertete_frequenz
from chladni.inventar import lade_bild, registriere_heif, sichtbare_dateien
from chladni.provenienz import dateihashes, json_schreiben, quellpfad
from chladni.registrierung import verfeinere_ecken

p = ArgumentParser(description=__doc__)
p.add_argument("rohdaten", type=Path)
p.add_argument("--ziel", type=Path, default=PROJEKT/"ausgaben/privat/v2/g0")
args = p.parse_args()
ziel = args.ziel.resolve()
if not ziel.is_relative_to(PROJEKT / "ausgaben/privat/v2") or args.rohdaten.resolve().is_relative_to(PROJEKT):
    p.error("Ziel im privaten V2-Bereich und separate Quellenwurzel angeben.")
ziel.mkdir(parents=True, exist_ok=True)
registriere_heif()
inv_pfad = PROJEKT/"ausgaben/privat/inventar/dateninventar.json"
a_pfad = PROJEKT/"ausgaben/privat/analyse/atlas.json"
inv = lese_json(inv_pfad)
alte = lese_json(a_pfad)
inv_index = {d["pfad"]: d for d in inv["dateien"]}
wurzel = args.rohdaten.resolve()
dateien = sichtbare_dateien(wurzel, PROJEKT)
aktuell = {p.relative_to(wurzel).as_posix(): p for p in dateien}
missing = sorted(inv_index.keys() - aktuell.keys())
extras = sorted(aktuell.keys() - inv_index.keys())
hashfehler = [q for q,d in inv_index.items() if q in aktuell and dateihashes(aktuell[q])[0] != d["sha256"]]
cfg = lese_json(PROJEKT/"konfiguration/pilot.json")
bildp = BildParameter(**cfg["bild_parameter"])
registriert = lade_registrierungen(PROJEKT/"konfiguration/registrierungen.csv", inv_index)
v1 = {z["id"]: z for z in alte["bilder"]}
abweichung = []
gruppe = {}
for d in registriert:
    z = v1[d["id"]]
    f = bewertete_frequenz(d["belege"])
    if (f["hz"], f["status"]) != (z["hz"], z["frequenzstatus"]):
        abweichung.append(d["id"])
    if d["serie"] != cfg["serie_pilot"]:
        continue
    im = lade_bild(quellpfad(args.rohdaten,d["pfad"]))
    geom = d["geom"] if d["eckmethode"] == "manuell" else verfeinere_ecken(im,d["geom"])[0]
    gruppe[d["id"]] = analysiere_bild(im,geom,bildp)
ref = gruppe[cfg["sweep_referenz"]]
max_abs = 0.0
for key,r in gruppe.items():
    a = diagnostik(r)
    z = v1[key]
    ab = linienabstand(r.linien,ref.linien,r.gueltig & ref.gueltig)
    with np.load(PROJEKT/f"ausgaben/privat/analyse/{key}/raster.npz") as gespeichert:
        if not (np.array_equal(r.sand,gespeichert["sand"]) and np.array_equal(r.linien,gespeichert["linien"])):
            raise AssertionError(f"V1-Masken unterscheiden sich bei {key}.")
    for feld in ("abdeckung_rel","breite_edt_median_rel","sichtbare_flaeche_rel"):
        max_abs = max(max_abs,abs(a[feld]-z[feld]))
    max_abs = max(max_abs,abs(ab[0]-z["abstand_referenz_rel"]),abs(ab[1]-z["abstand_referenz_q95_rel"]))
p_mod = Platte(**cfg["platte"])
m = berechne_eigenmoden(p_mod,"navier",13,10)
analytisch = np.sort([(np.pi**2*(n*n+k*k))**2 for n in range(1,7) for k in range(1,7)])[:10]
max_eig = float(np.max(np.abs(m.lambda_/analytisch-1)))
luecken = []
for rand in cfg["modellvergleich"]:
    full = berechne_eigenmoden(p_mod,rand,cfg["grad"],cfg["moden"]+1)
    delta = float(full.lambda_[-1] / full.lambda_[-2] - 1)
    luecken.append({"modell":rand,"letzte_relative_eigenwertluecke":delta,
                   "cluster_abgeschnitten":delta <= 1e-6})
befund = {"python":platform.python_version(),"inventar_sha256":dateihashes(inv_pfad)[0],
          "atlas_v1_sha256":dateihashes(a_pfad)[0],"quellen":len(aktuell),
          "hashfehler":hashfehler,"fehlende_quellen":missing,"unbekannte_quellen":extras,
          "freq_konsistenz_abweichungen":abweichung,
          "freq_status":dict(Counter(d["frequenzstatus"] for d in alte["bilder"])),
          "bilder":sum(d["status"]=="bild_dekodiert" for d in inv["dateien"]),
          "sweep_frisch_neuberechnet":len(gruppe),"sweep_abs_abweichung_max":max_abs,
          "navier_rel_eig_max":max_eig,"spektralschnitt":luecken}
json_schreiben(ziel/"baseline.json",befund)
print(befund)
raise SystemExit(bool(missing or extras or hashfehler or abweichung or max_abs > 1e-12 or max_eig > 2e-7))
