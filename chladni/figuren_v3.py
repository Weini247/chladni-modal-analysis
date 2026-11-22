
"""Publikationsfiguren aus den protokollierten V3-Daten und eine reine Modellgrafik."""
from __future__ import annotations

from pathlib import Path

from .abbildungen import speichere, stil
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

from .auswertung import PROJEKT, lese_json
from .eigenmoden import Platte
from .plattenmechanik import Anschluss, spektrum
from .v3_pfade import Eingaben

TEAL, BLUE, GOLD, INK = "#167a78", "#285892", "#a95822", "#17313e"
PALE = "#c6d4d9"
SERIES = {"Bilder 2030":"2,090–2,096 Hz", "Bilder 4120":"4,122–4,128 Hz", "Bilder 3720":"3,720–3,726 Hz"}
STRESS = {"ideal":"Ideal", "breit_diffus":"Diffuse band", "unterbrochen":"Interrupted", "registrierung":"Shifted"}


def _kopf(fig, titel: str, untertitel: str) -> None:
    fig.text(.075,.945,titel,fontsize=19,fontweight="bold",color=INK,va="top")
    fig.text(.075,.87,untertitel,fontsize=9.5,color="#4e6270",va="top")


def _achsen(ax, achse="y") -> None:
    ax.set_axisbelow(True)
    ax.grid(axis=achse,color=PALE,linewidth=.65)
    ax.tick_params(length=0,pad=7)


def _sweeps(studie: dict, ziel: Path) -> None:
    fig, achsen = plt.subplots(1,3,figsize=(11,4.2),sharey=True)
    fig.subplots_adjust(top=.70,bottom=.24,left=.075,right=.985,wspace=.18)
    _kopf(fig,"Where the extracted pattern changes",
          "Experimental archive  |  Baseline skeleton distance and full range across 22 extraction settings")
    for ax, (serie,titel) in zip(achsen,SERIES.items(),strict=True):
        s=studie["sweeps"][serie]
        paar=s["varianten"]["basis"]["paare"]
        ticks=[f"{p['von']:.0f}→{p['bis']:.0f}" for p in paar]
        for i,p in enumerate(paar):
            v=[100*v["paare"][i]["abstand_rel"] for v in s["varianten"].values()
               if v["paare"][i]["abstand_rel"] is not None]
            if not v:
                continue
            ax.vlines(i,min(v),max(v),color=BLUE,linewidth=2)
            ax.scatter(i,100*p["abstand_rel"],s=25,color=TEAL,zorder=2)
        for j,r in enumerate(s["wiederholungen"]):
            ax.scatter(-.65-.16*j,100*r["abstand_rel"],s=38,marker="D",color=GOLD,zorder=2)
        ax.set_xticks(range(len(paar)),ticks,rotation=58,ha="right",fontsize=8)
        ax.set_xlim(-1,len(paar)-.5)
        ax.set_title(titel,loc="left",fontsize=12,fontweight="bold",pad=10)
        _achsen(ax)
    achsen[0].set_ylabel("Mean skeleton distance [% of plate side]")
    fig.text(.075,.045,"● Baseline    │ Extraction range    ◆ Separate exposure at the same frequency",fontsize=9)
    speichere(fig,ziel/"sweeps")


def _gap(g: dict,ziel: Path) -> None:
    names={"historisch":"Historical cosine","frei":"Free edges","zentralpunkt":"Point constraint",
           "federflaeche":"Spring patch","anschluss":"Distributed contact","alle":"Full catalogue",
           "nur_einzel":"Single modes only","anschluss_grad24":"Contact, degree 24",
           "anschluss_steifigkeit_0.5":"Contact, half stiffness","anschluss_steifigkeit_2":"Contact, double stiffness",
           "anschluss_radius_groesser":"Contact, radius × 1.5"}
    rows=[r for r in g["ablationsstudien"] if r["name"] in names]
    fig,ax=plt.subplots(figsize=(9.15,5.8))
    fig.subplots_adjust(top=.77,bottom=.18,left=.255,right=.96)
    _kopf(fig,"The control set remains outside the fit limit",
          "3,720–3,726 Hz archive  |  Seven real exposures in each catalogue ablation")
    limit=100*g["schwellen"]["max_test_rel"]
    ax.axvspan(0,limit,color="#d9ece8",alpha=.65)
    ax.axvline(limit,color=TEAL,linewidth=1.4,linestyle="--")
    for i,r in enumerate(rows):
        v=[100*p["prueffehler_rel"] for p in r["faelle"] if p["prueffehler_rel"] is not None]
        y=i+np.linspace(-.12,.12,len(v))
        ax.scatter(v,y,s=20,facecolor="none",edgecolor=BLUE,linewidth=.9,zorder=3)
        ax.scatter(np.median(v),i,marker="|",s=125,color=GOLD,zorder=4)
    ax.set_yticks(range(len(rows)),[names[r["name"]] for r in rows])
    ax.invert_yaxis()
    ax.set_xlim(0,None)
    ax.set_xlabel("Leading family's distance on withheld stripes [% of plate side]")
    _achsen(ax,"x")
    fig.text(.075,.055,"○ Exposure     │ Median     Dashed line marks the fixed 2% limit. A separate family-gap rule also applies.",fontsize=9)
    speichere(fig,ziel/"gap")


def _mechanik(m: dict,ziel: Path) -> None:
    names={"frei":"Free edges","zentralpunkt":"Point constraint","federflaeche":"Spring patch","anschluss":"Distributed contact"}
    fig, (a,b)=plt.subplots(1,2,figsize=(10.5,4.65))
    fig.subplots_adjust(top=.74,bottom=.23,left=.095,right=.965,wspace=.36)
    _kopf(fig,"Resolution of the numerical plate models",
          "Rayleigh–Ritz degree sequence  |  Residuals and frequency changes in matched mode clusters")
    for (k,v),c,mk in zip(m["modelle"].items(),[TEAL,BLUE,GOLD,"#795991"],["o","s","^","D"],strict=True):
        a.semilogy([q["grad"] for q in v["stufen"]],[q["rel_residuum_max"] for q in v["stufen"]],
                   marker=mk,ms=4,color=c,label=names[k])
        for z in v["unterraeume"]:
            d=[abs(q["frequenz_delta_rel"]) for q in z["vergleich"] if not q["dimensionswechsel"]]
            if d:
                b.scatter(z["grad_b"],100*max(d),color=c,marker=mk,s=32,zorder=3)
    for ax in (a,b):
        _achsen(ax)
        ax.set_xlabel("Ritz degree")
        ax.set_xticks(sorted({q["grad"] for v in m["modelle"].values() for q in v["stufen"]}))
    a.set_ylabel("Max. relative eigenproblem residual")
    b.set_ylabel("Max. mean-frequency change [%]")
    b.set_yscale("log")
    a.legend(loc="upper center",bbox_to_anchor=(1.14,-.2),ncol=4,frameon=False,fontsize=8.7)
    speichere(fig,ziel/"mechanik")


def _synthetik(g: dict,ziel: Path) -> None:
    fig, achsen=plt.subplots(1,2,figsize=(10.6,4.4),sharey=True)
    fig.subplots_adjust(top=.72,bottom=.23,left=.075,right=.975,wspace=.12)
    _kopf(fig,"Top-six recovery stays high as rank one varies",
          "Seeded synthetic fields  |  16 single modes and 16 mode pairs at each observation setting")
    for ax,art,titel in zip(achsen,("einzel","paar"),("Single modes","Mode pairs"),strict=True):
        rows={r["stoerung"]:r for r in g["synthetisch"]["summen"]
              if r["art"]==art and r["verfahren"]=="v2_distanz"}
        for i,key in enumerate(STRESS):
            d=rows[key]
            ax.bar(i-.17,d["top1"],width=.31,color=BLUE,label="Top 1" if i==0 else None)
            ax.bar(i+.17,d["top6"],width=.31,color=TEAL,label="Top 6" if i==0 else None)
            ax.scatter(i+.17,d["zufall_top6_erwartet"],s=24,marker="D",color=GOLD,zorder=4,
                       label="Uniform Top 6 expectation" if i==0 else None)
        ax.set_xticks(range(len(STRESS)),STRESS.values(),fontsize=9)
        ax.set_yticks([0,4,8,12,16])
        ax.set_ylim(0,17)
        ax.set_title(titel,loc="left",fontsize=12,fontweight="bold",pad=8)
        _achsen(ax)
    achsen[0].set_ylabel("Fields containing the known family")
    achsen[0].legend(loc="upper center",bbox_to_anchor=(1.02,-.16),ncol=3,frameon=False,fontsize=9)
    speichere(fig,ziel/"synthetik")


def hero(ziel: Path, platte: dict, kontakt: dict) -> None:
    """Öffentlichkeitsfähiges Motiv ausschließlich aus dem freien Eigenproblem."""
    p=Platte(**platte)
    r=spektrum(p,"frei",20,13,Anschluss(**kontakt))
    axis=np.linspace(0,1,155)
    i=11
    field=r.feld(i,axis,axis)
    field=field/np.max(np.abs(field))
    figure=plt.figure(figsize=(10.2,3.75),facecolor="#0e1721")
    cmap=LinearSegmentedColormap.from_list("signed_mode",["#365996","#dce9eb","#bc7954"])
    ax=figure.add_axes([.54,.03,.44,.93])
    ax.set_axis_off()
    ax.imshow(field,cmap=cmap,vmin=-1,vmax=1,extent=(0,1,1,0),interpolation="bilinear")
    ax.contour(axis,axis,field,levels=[0],colors=["#1d3946"],linewidths=[1.06])
    figure.text(.067,.82,"COMPUTATIONAL PLATE MECHANICS",fontsize=9,color="#77dfcb",fontweight="bold")
    figure.text(.06,.65,"Chladni\nModal Analysis",fontsize=32,color="#f0f6fa",fontweight="bold",va="top",linespacing=1.03)
    figure.text(.067,.241,"A GP2 experiment revisited through\nimage analysis and inverse modeling.",fontsize=11,color="#b2c3d2",va="top")
    figure.text(.067,.07,f"SIMULATION   ·   FREE SQUARE PLATE   ·   MODE {i+1}",fontsize=8,color="#77dfcb")
    ziel.parent.mkdir(parents=True,exist_ok=True)
    figure.savefig(ziel,dpi=150,facecolor=figure.get_facecolor(),metadata={"Creator":"GP2 Chladni V3"})
    plt.close(figure)


def abbildungen(e: Eingaben) -> None:
    private=e.ziel/"figuren"
    private.mkdir(parents=True,exist_ok=True)
    studie=lese_json(e.ziel/"bildstudie.json")
    gap=lese_json(e.ziel/"gap.json")
    m=lese_json(e.v2/"mechanik.json")
    config={"svg.hashsalt":"chladni-v3","axes.labelsize":9,"figure.facecolor":"#f7f9f8","axes.facecolor":"#f7f9f8"}
    with plt.rc_context(stil() | config):
        _sweeps(studie,private)
        _gap(gap,private)
        _mechanik(m,private)
        _synthetik(gap,private)
        hero(private/"hero.png",m["platte"],m["anschluss"])


def showcase() -> None:
    """Erzeuge nur die numerische Titelgrafik im versionierbaren Ausgabepfad."""
    m=lese_json(PROJEKT/"konfiguration/v2.json")
    with plt.rc_context(stil()):
        hero(PROJEKT/"ausgaben/modelle/v3-hero.png",m["platte"],m["anschluss"])
