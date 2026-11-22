"""Erzeuge die zwei freigegebenen README-Tafeln aus lokalen V1/V2-Ausgaben."""
from __future__ import annotations

from argparse import ArgumentParser
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation

from chladni.abbildungen import plt, stil
from chladni.auswertung import lese_json

BG, INK, MUTED = "#f7f9f8", "#17313e", "#4e6270"
MODEL_LINE = "#ff9d80"


def _bilddaten(pfad: Path) -> tuple[np.ndarray, np.ma.MaskedArray, np.ndarray, np.ndarray]:
    with Image.open(pfad/"platte.png") as bild:
        rgb = np.asarray(bild.convert("RGB"))
    with np.load(pfad/"raster.npz") as raster:
        sichtbar = raster["sicht"]
        score = np.ma.masked_where(~sichtbar, raster["score"])
        spur = binary_dilation(raster["linien"] & sichtbar) & sichtbar
    hintergrund = np.rint(.38*rgb + .62*np.array([19,27,36])).astype(np.uint8)
    overlay = hintergrund.copy()
    overlay[spur] = (255,218,126)
    return rgb, score, hintergrund, overlay


def _layout(spalten: int, groesse: tuple[float,float], titel: str, untertitel: str):
    fig, ax = plt.subplots(1,spalten,figsize=groesse)
    fig.subplots_adjust(left=.042,right=.966,top=.72,bottom=.18,wspace=.12)
    fig.text(.042,.945,titel,fontsize=22,weight="bold",va="top",color=INK)
    fig.text(.042,.836,untertitel,fontsize=11,va="top",color=MUTED)
    return fig, ax


def _ansicht(ax, titel: str, raster, **kwargs):
    flaeche = ax.imshow(raster,**kwargs)
    ax.set_axis_off()
    ax.set_title(titel,fontsize=10.8,weight="bold",loc="left",pad=7,color=INK)
    return flaeche


def _farbskala(fig, ax, flaeche, ticks, titel: str):
    bar = fig.colorbar(flaeche,ax=ax,orientation="horizontal",fraction=.06,pad=.105,ticks=ticks)
    bar.ax.tick_params(labelsize=8,length=2)
    bar.ax.set_xlabel(titel,fontsize=8,labelpad=1)


def _png(fig, ziel: Path) -> None:
    buf = BytesIO()
    fig.savefig(buf,format="png",dpi=150,facecolor=BG)
    buf.seek(0)
    # Speichere nur RGB-Pixel, ohne Metadaten aus den Quelldateien.
    with Image.open(buf) as bild:
        Image.fromarray(np.asarray(bild.convert("RGB"))).save(ziel,optimize=True)
    plt.close(fig)


def _experiment(privat: Path, ziel: Path) -> None:
    frame = privat/"analyse/IMG_1601"
    rgb, score, _, overlay = _bilddaten(frame)
    with Image.open(frame/"original-vorschau.jpg") as foto:
        aufbau = foto.convert("RGB")
    fig, ax = _layout(5,(13.5,3.85),"Chladni pattern at 4,122 Hz",
                      "GP2 laboratory experiment  |  Blue sand on a centrally mounted plate")
    _ansicht(ax[0],"Original setup photo",aufbau)
    _ansicht(ax[1],"Registered plate",rgb)
    cmap = plt.get_cmap("cividis").with_extremes(bad="#e4e9ed")
    scorebild = _ansicht(ax[2],"Blue-excess score",score,cmap=cmap,vmin=0,vmax=.46)
    _ansicht(ax[3],"Sand-trace overlay",overlay)
    feld = np.load(frame/"modellfeld.npy")
    normiert = feld/np.max(np.abs(feld))
    modell = _ansicht(ax[4],"Free plate · #26/27",normiert,cmap="RdBu_r",vmin=-1,vmax=1,extent=(0,1,1,0))
    xy = (np.arange(len(feld))+.5)/len(feld)
    ax[4].contour(xy,xy,feld,levels=[0],colors=[INK],linewidths=.9)
    _farbskala(fig,ax[4],modell,[-1,0,1],"Normalized model displacement")
    _farbskala(fig,ax[2],scorebild,[0,.2,.4],"Image score (dimensionless)")
    fig.text(.042,.051,"Yellow lines show the extracted sand traces, thickened for display. "
             "The last panel shows the calculated field.",fontsize=9.5,color=MUTED)
    _png(fig,ziel/"experiment-4122.png")


def _kontrolle(privat: Path, ziel: Path) -> None:
    inversion = lese_json(privat/"v2/invers.json")
    aufnahme = next(z for z in inversion["ergebnisse"] if z["id"]=="IMG_1583")
    kandidat = aufnahme["rang"][0]
    if kandidat["modell"] != "historisch" or len(kandidat["moden"]) != 1:
        raise ValueError("Die Kontrolltafel erwartet das archivierte Kosinusprodukt als führenden Kandidaten.")
    m,n = map(int,kandidat["moden"][0].split(","))
    # Spiegelungen ändern das Vorzeichen, aber nicht die symmetrischen Nullstellen.
    # Eine ungerade Anzahl Vierteldrehungen vertauscht die beiden Achsen.
    nx,ny = (n,m) if kandidat["d4"] % 2 else (m,n)
    rgb, _, hintergrund, overlay = _bilddaten(privat/"analyse"/aufnahme["id"])
    distanz = 100*kandidat["test_rel"]
    grenze = 100*inversion["synthetische_schwellen"]["max_test_rel"]
    if aufnahme["status"] != "KEIN_BELASTBARER_TREFFER" or distanz <= grenze:
        raise ValueError("Die Kontrolltafel erwartet den archivierten Abstand oberhalb der Prüfschwelle.")
    fig, ax = _layout(3,(11,4.3),"Control exposure at 3,723 Hz",
                      "Experimental control  |  Leading model candidate rejected")
    _ansicht(ax[0],"Registered plate",rgb)
    _ansicht(ax[1],"Sand-trace overlay",overlay)
    _ansicht(ax[2],"Model zero lines",hintergrund,extent=(0,1,1,0))
    ax[2].vlines((np.arange(nx)+.5)/nx,0,1,colors=MODEL_LINE,linewidth=1.4)
    ax[2].hlines((np.arange(ny)+.5)/ny,0,1,colors=MODEL_LINE,linewidth=1.4)
    ax[2].set(xlim=(0,1),ylim=(1,0))
    fig.text(.042,.099,f"Cosine product {m},{n}   |   Withheld distance {distanz:.2f}% of plate side   |   "
             f"Distance limit {grenze:.2f}%",fontsize=10,color=MUTED)
    fig.text(.042,.046,"Yellow: extracted traces, thickened for display.  Coral: analytic zero lines.",
             fontsize=9.2,color=MUTED)
    _png(fig,ziel/"control-3723.png")


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--privat",type=Path,required=True,help="Lokaler Ausgabeordner mit analyse/ und v2/.")
    parser.add_argument("--ziel",type=Path,required=True,help="Ausgabeordner für die zwei PNG-Tafeln.")
    args = parser.parse_args()
    args.ziel.mkdir(parents=True,exist_ok=True)
    with plt.rc_context(stil() | {"figure.facecolor":BG,"axes.facecolor":BG}):
        _experiment(args.privat,args.ziel)
        _kontrolle(args.privat,args.ziel)


if __name__ == "__main__":
    main()
