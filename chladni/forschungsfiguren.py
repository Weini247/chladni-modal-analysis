"""Statische V2-Abbildungen aus den Rechenartefakten, ohne GUI-Abhängigkeit."""
from __future__ import annotations

from pathlib import Path
import numpy as np
from PIL import Image

from .abbildungen import FARBE, NEBEN, ORANGE, speichere, stil
from .auswertung import lese_json
import matplotlib.pyplot as plt

MODELL = {"frei":"Frei", "zentralpunkt":"Zentralpunkt", "federflaeche":"Federfläche",
          "anschluss":"Feder, Rotation und Masse", "historisch":"Historischer Kosinus"}
FARBEN = [FARBE, ORANGE, "#466943", "#804a7b"]


def aus_v1(v1: Path,bild: str,datei: str) -> np.ndarray:
    with Image.open(v1/bild/datei) as im:
        return np.asarray(im.convert("RGB"))


def _titel(fig,titel,unter):
    fig.text(.068,.936,titel,weight="bold",size=22)
    fig.text(.068,.879,unter,c=NEBEN,size=10.8)


def _sweep(v1,z,atlas,g0):
    qs=atlas["zweitserie"]["varianten"]
    a=qs["basis"]
    ids={d["hz"]:d["id"] for d in g0["bilder"]}
    hz=sorted(ids)
    x=np.asarray(hz)
    fig=plt.figure(figsize=(13.2,8.2))
    grid=fig.add_gridspec(3,7,left=.09,right=.966,bottom=.121,top=.79,hspace=.55,wspace=.15,
                          height_ratios=(1.1,.98,1.05))
    _titel(fig,"Sandmuster zwischen 2090 und 2096 Hz",
           "Zweite Messserie · sieben neu abgelesene Originalaufnahmen · quadratische Metallplatte")
    for j,f in enumerate(hz):
        ax=fig.add_subplot(grid[0,j])
        ax.imshow(aus_v1(v1,ids[f],"platte.png"))
        ax.set_axis_off()
        ax.set_title(f"{f} Hz",loc="left",weight="bold",size=10)
        ax.text(.0,-.12,ids[f],transform=ax.transAxes,color=NEBEN,size=8)
    ax=fig.add_subplot(grid[1,:])
    y=np.array([[100*v["abdeckung"][str(f)] for f in hz] for v in qs.values()])
    ax.vlines(x,y.min(0),y.max(0),color=FARBE,alpha=.35,lw=4,label="Spanne der Varianten")
    ax.plot(x,y[0],marker="o",ms=5,ls="none",color=FARBE,label="Basis")
    ax.set(xticks=x, ylabel="Sandfläche [%]")
    ax.grid(axis="y",alpha=.23)
    ax.legend(frameon=False,loc="upper left",ncol=2)
    ax2=fig.add_subplot(grid[2,:])
    y=np.array([[100*d["linienabstand_rel"] for d in v["nachbarn"]] for v in qs.values()])
    mitte=x[:-1]+.5
    for j,x0 in enumerate(mitte):
        farbe=ORANGE if x0==2093.5 else FARBE
        ax2.vlines(x0,y.min(0)[j],y.max(0)[j],color=farbe,lw=4,alpha=.38)
        ax2.scatter(x0,y[0,j],color=farbe,s=36,zorder=3)
    ax2.set(xlabel="Benachbarte Anzeigeablesungen [Hz]",ylabel="Mittlerer Linienabstand\n[% der Plattenseite]")
    ax2.set_xticks(mitte,[f"{f}–{g}" for f,g in zip(hz[:-1],hz[1:],strict=True)])
    ax2.grid(axis="y",alpha=.23)
    fig.text(.09,.045,"Balken je Einzelaufnahme oder Fotopaar. Spannen aus Schwelle, Licht, "
             "Farbtemperatur, Kontrast und Registrierung.",size=9,c=NEBEN)
    speichere(fig,z/"zweitserie")


def _referenz(z,g0,npz):
    bild=g0["bilder"]
    fig,axs=plt.subplots(3,4,figsize=(11,8))
    fig.subplots_adjust(left=.055,right=.974,top=.79,bottom=.105,hspace=.18,wspace=.11)
    _titel(fig,"Plattenregistrierung und Referenzmasken",
           "2090–2096 Hz · Vergleich mit einem maschinellen Farbkriterium in zwölf Beispielansichten")
    for i,w in enumerate((bild[0],bild[3],bild[-1])):
        id=w["id"]
        c=np.zeros((*npz[id+"_fg"].shape,3),dtype=np.uint8)
        c[npz[id+"_fg"]]=[231,171,67]
        c[npz[id+"_bg"]]=[97,153,174]
        quelle=[npz[id+"_rgb"],c,npz[id+"_v1_ref"],npz[id+"_hsv"]]
        for j,(a,ax) in enumerate(zip(quelle,axs[i],strict=True)):
            ax.imshow(a,cmap="gray",vmin=0,vmax=1)
            ax.set_axis_off()
            if i==0:
                ax.set_title(["Rohfarb-Entzerrung","Klare HSV-Pixel","V1-Sandmaske","Alternative Vollmaske"][j],
                             loc="left",size=9,weight="bold")
            if j==0:
                ax.text(.0,-.08,f"{w['hz']} Hz",transform=ax.transAxes,size=8,color=NEBEN)
    fig.text(.055,.04,"Teilreferenz: Gold = klare Sandfarbe, Blau = klares Metall, Schwarz = ungelabelt. "
             "Automatischer Farbabgleich im selben Plattenraum.",size=8.5,c=NEBEN)
    speichere(fig,z/"bildreferenz")


def _serien(z,atlas):
    fig,axs=plt.subplots(2,2,figsize=(11,7))
    fig.subplots_adjust(left=.09,right=.96,top=.77,bottom=.13,hspace=.52,wspace=.28)
    _titel(fig,"Sandbedeckung in vier dichten Frequenzreihen",
           "Punkte sind Einzelaufnahmen. Der Offset bezieht sich auf die Medianfrequenz der jeweiligen Reihe.")
    for ax,serie in zip(axs.flat,("Bilder 958","Bilder 2030","Bilder 3720","Bilder 4120"),strict=True):
        fotos=sorted((q for q in atlas["bilder"] if q["serie"]==serie and q["hz"] is not None),
                      key=lambda q:q["hz"])
        hz=np.asarray([q["hz"] for q in fotos])
        f0=np.median(np.unique(hz))
        ax.scatter(hz-f0,100*np.asarray([q["abdeckung_rel"] for q in fotos]),c=FARBE,s=24)
        ax.set(title=f"{serie} · Bezug {f0:g} Hz", xlabel="Frequenzoffset [Hz]",ylabel="Sandfläche [%]")
        ax.grid(axis="y",alpha=.23)
    fig.text(.09,.047,"Die Serien unterscheiden sich in Motiv, Aufnahmefolge und Sandvorgeschichte.",
             c=NEBEN,size=9)
    speichere(fig,z/"serienvergleich")


def _mechanik(z,m):
    fig,axs=plt.subplots(1,3,figsize=(13.4,5.25))
    fig.subplots_adjust(left=.067,right=.975,top=.747,bottom=.22,wspace=.36)
    _titel(fig,"Konvergenz freier und zentral gehaltener Plattenmodelle",
           "Rayleigh–Ritz · 30 positive Frequenzen je Randmodell mit vervollständigten Randclustern")
    for (name,row),farbe in zip(m["modelle"].items(),FARBEN,strict=True):
        stufen=row["unterraeume"]
        x=[a["grad_b"] for a in stufen]
        d=[max(abs(v["frequenz_delta_rel"]) for v in a["vergleich"]) for a in stufen]
        o=[max(1-v["projektor_overlap"] for v in a["vergleich"]) for a in stufen]
        axs[0].semilogy(x,np.maximum(d,1e-13),"o-",c=farbe,label=MODELL[name])
        axs[1].semilogy(x,np.maximum(o,1e-15),"o-",c=farbe)
        axs[2].semilogy([r["grad"] for r in row["stufen"]],
                        [r["rel_residuum_max"] for r in row["stufen"]],"o-",c=farbe)
    for ax,title,yl in zip(axs,["Eigenfrequenzen","Eigenräume","Diskrete Eigengleichung"],
                           ["Max. relative Änderung","Max. 1 − Projektorüberlappung","Max. relatives Residuum"],strict=True):
        ax.set_title(title,loc="left",size=10,weight="bold")
        ax.set(xlabel="Polynomgrad je Achse",ylabel=yl)
        ax.grid(alpha=.2)
    fig.legend(*axs[0].get_legend_handles_labels(),loc="lower center",ncols=4,frameon=False)
    speichere(fig,z/"mechanik_konvergenz")
    fig,ax=plt.subplots(figsize=(10.8,5.25))
    fig.subplots_adjust(left=.27,right=.97,top=.72,bottom=.16)
    _titel(fig,"Spektrale Sensitivität des zentralen Anschlussmodells",
           "Szenarien um eine illustrativ gewählte Auflage · Paarung nach Eigenraumüberlappung")
    v=m["sensitivitaet"]
    for i,s in enumerate(v):
        x=100*np.array([r["frequenz_delta_rel"] for r in s["vergleich"] if r["projektor_overlap"]>.70])
        ax.scatter(x,np.full_like(x,i),s=20,alpha=.62,color=FARBE)
    ax.set_yticks(range(len(v)),[s["name"].replace("_"," ") for s in v])
    ax.set(xlabel="Relative Frequenzänderung [%]")
    ax.axvline(0,color=NEBEN,lw=.9)
    ax.grid(axis="x",alpha=.19)
    ax.invert_yaxis()
    fig.text(.068,.04,"Dargestellt sind zugeordnete Eigenräume mit Projektorüberlappung größer als 0,70.",
             color=NEBEN,size=8.7)
    speichere(fig,z/"mechanik_sensitivitaet")


def _inverse(v1,z,invers,syn,felder):
    real=[r for r in invers["ergebnisse"] if r["serie"]==invers["kontrollserie"] and r["rang"]]
    d=min(real,key=lambda q:abs((q["hz"] or 0)-3723))
    k=d["rang"][0]
    lookup={i:j for j,i in enumerate(felder["indices"])}
    feld=felder["felder"][lookup[k["index"]]]
    fig,axs=plt.subplots(1,3,figsize=(11,4.8))
    fig.subplots_adjust(left=.064,right=.974,top=.76,bottom=.19,wspace=.21)
    ergebnistext = {"KEIN_BELASTBARER_TREFFER":"Kein belastbarer Treffer",
                    "NICHT_EINDEUTIG_IDENTIFIZIERBAR":"Mehrere plausible Kandidaten",
                    "KANDIDAT_IM_BEOBACHTUNGSMODELL":"Kandidat im Beobachtungsmodell"}
    _titel(fig,"Modenkandidaten der Kontrollserie",
           f"{d['id']} · Anzeige {d['hz']:g} Hz · {ergebnistext[d['status']]}")
    for j,(typ,name) in enumerate((("original-vorschau.jpg","Experiment · Original"),
                                   ("linien.png","Experiment · Sandlinien"),
                                   ("platte.png","Modellkontur über dem Experiment"))):
        ax=axs[j]
        ax.imshow(aus_v1(v1,d["id"],typ),**({"extent":(0,1,1,0)} if j else {}))
        ax.set_axis_off()
        ax.set_title(name,loc="left",weight="bold",size=10)
        if j==2:
            x=(np.arange(len(feld))+.5)/len(feld)
            ax.contour(x,x,feld,levels=[0],colors=["#ffcd66"],linewidths=1.25)
    fig.text(.064,.069,f"{MODELL[k['modell']]} · Familie {'/'.join(k['familie'])} · "
             f"Abstand im zurückgehaltenen Bildbereich {100*k['test_rel']:.2f} % der Plattenseite.",
             color=NEBEN,size=9)
    speichere(fig,z/"inverse_kontrollaufnahme")
    fig,ax=plt.subplots(figsize=(9,4.85))
    fig.subplots_adjust(left=.09,right=.966,top=.73,bottom=.18)
    _titel(fig,"Synthetischer Inversionstest",
           "Vom Kalibrationslauf getrennte Zufallsstichprobe · Zahlen je Musterklasse")
    x=np.arange(3)
    cats=("einzel","paar","null")
    w=.22
    for i,(key,title,c) in enumerate((("top1","Richtige Familie auf Rang 1",FARBE),
                                      ("top6","Richtige Familie unter sechs", "#50866f"),
                                      ("akzeptiert","Als Kandidat ausgegeben",ORANGE))):
        werte=[syn["test"][r][key] for r in cats]
        b=ax.bar(x+(i-1)*w,werte,w,label=title,color=c)
        ax.bar_label(b,fontsize=8,padding=2)
    n=syn["test"]["null"]["n"]
    ax.set(ylim=(0,n+4),ylabel=f"Fälle von je {n}")
    ax.set_xticks(x,["Einzelmode","Zwei Moden","Ellipse/Artefakt"])
    ax.grid(axis="y",alpha=.22)
    ax.set_axisbelow(True)
    ax.legend(loc="upper right",frameon=False,fontsize=8)
    speichere(fig,z/"inverse_validierung")


def abbildungen(v1: Path,ziel: Path,g0: Path) -> None:
    z=ziel/"figuren"
    z.mkdir(exist_ok=True,parents=True)
    a=lese_json(ziel/"atlas.json")
    m=lese_json(ziel/"mechanik.json")
    i=lese_json(ziel/"invers.json")
    s=lese_json(ziel/"inverse_validierung.json")
    g=lese_json(g0/"bildpruefung.json")
    with plt.rc_context(stil()):
        _sweep(v1,z,a,g)
        _serien(z,a)
        with np.load(g0/"bildpruefung.npz") as r:
            _referenz(z,g,r)
        _mechanik(z,m)
        with np.load(ziel/"inverse_felder.npz") as f:
            _inverse(v1,z,i,s,f)
    print(f"V2: sieben Abbildungen in PNG, SVG und PDF unter {z}.")
