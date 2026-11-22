"""Reproduzierbare Matplotlib-Abbildungen aus berechneten Artefakten."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from .bildpipeline import BildErgebnis
from .eigenmoden import Platte, berechne_eigenmoden

FARBE = "#155f81"
ORANGE = "#a64a18"
TEXT = "#182d3d"
NEBEN = "#4e6270"


def stil() -> dict:
    return {"font.family": "DejaVu Sans", "font.size": 10, "text.color": TEXT,
            "axes.labelcolor": TEXT, "axes.edgecolor": "#9cabb2", "axes.spines.top": False,
            "axes.spines.right": False, "xtick.color": NEBEN, "ytick.color": NEBEN,
            "figure.facecolor": "#f6f7f6", "axes.facecolor": "#f6f7f6", "svg.hashsalt": "chladni-1"}


def speichere(fig, pfad: Path) -> None:
    for fmt in ("png", "svg", "pdf"):
        meta = {"Creator": "GP2 Chladni", "Date": None} if fmt == "svg" else {"Creator": "GP2 Chladni"}
        if fmt == "pdf":
            meta["CreationDate"] = None
        fig.savefig(pfad.with_suffix("." + fmt), dpi=190, metadata=meta)
    plt.close(fig)


def ueberlagerung(rgb: np.ndarray, linien: np.ndarray, gueltig: np.ndarray) -> np.ndarray:
    overlay = rgb.copy()
    overlay[~gueltig] = (0.45 * overlay[~gueltig] + np.array([26, 33, 42])).astype(np.uint8)
    overlay[linien] = (255, 218, 126)
    return overlay


def bildtafel(original: Image.Image, bild: BildErgebnis, titel: str, untertitel: str,
                messung: dict, pfad: Path, modellfeld: np.ndarray | None = None,
                modelltext: str = "") -> None:
    with plt.rc_context(stil()):
        n = 5 if modellfeld is not None else 4
        fig, axes = plt.subplots(1, n, figsize=(3.0*n, 4.06))
        fig.subplots_adjust(left=0.035, right=0.975, top=0.72, bottom=0.22, wspace=0.25)
        vorschau = original.copy()
        vorschau.thumbnail((820, 700))
        axes[0].imshow(vorschau)
        axes[0].set_axis_off()
        axes[0].set_title("Originalaufnahme", loc="left", fontsize=10.5)
        farbe = np.ma.masked_where(~bild.gueltig, bild.sandscore)
        auswahl = [(bild.rgb, None, "Entzerrte Platte"),
                   (farbe, "cividis", "Blauüberschuss / Score"),
                   (ueberlagerung(bild.rgb, bild.linien, bild.gueltig), None, "Sandlinien-Kandidaten")]
        for ax, (a, cmap, name) in zip(axes[1:], auswahl):
            im = ax.imshow(a, cmap=cmap, extent=[0, 1, 1, 0],
                           **({"vmin": 0, "vmax": 0.46} if cmap else {}))
            ax.set_title(name, loc="left", fontsize=10.5)
            ax.set_xticks([0, 0.5, 1])
            ax.set_yticks([0, 0.5, 1])
            ax.set_xlabel("x/a")
            if cmap:
                cb = fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.045, pad=0.24, ticks=[0, 0.2, 0.4])
                cb.ax.tick_params(labelsize=7)
        if modellfeld is not None:
            ax = axes[-1]
            v = np.max(np.abs(modellfeld))
            ax.imshow(modellfeld/v, cmap="RdBu_r", vmin=-1, vmax=1, extent=[0, 1, 1, 0])
            xy = (np.arange(len(modellfeld)) + 0.5) / len(modellfeld)
            ax.contour(xy, xy, modellfeld, levels=[0], colors="#182d3d", linewidths=0.8)
            ax.set_xticks([0, 0.5, 1])
            ax.set_yticks([0, 0.5, 1])
            ax.set_xlabel("x/a")
            ax.set_title(modelltext, loc="left", fontsize=9.5)
        axes[1].set_ylabel("y/a")
        fig.text(0.035, 0.92, titel, fontsize=22, weight="bold")
        fig.text(0.035, 0.84, untertitel, color=NEBEN, fontsize=10)
        fig.text(0.035, 0.072, (f"Sandfläche {100*messung['abdeckung_rel']:.1f} %  ·  "
                 f"{messung['skelett_komponenten_8']} Skelettkomponenten  ·  "
                 "Gelb: Skelett der Sandmaske  ·  Abgedunkelt: Ausschlussregionen"), color=NEBEN)
        speichere(fig, pfad)


def sweep_abbildung(zeilen: list[dict], bilder: dict, ziel: Path) -> None:
    zeilen = sorted((z for z in zeilen if z["hz"] is not None), key=lambda z: (z["hz"], z["id"]))
    if not zeilen:
        return
    n = len(zeilen)
    with plt.rc_context(stil()):
        fig = plt.figure(figsize=(13.0, 8.1))
        g = fig.add_gridspec(3, n, height_ratios=[1.09, 1, 1],
                            left=0.075, right=0.965, top=0.79, bottom=0.14, hspace=0.55, wspace=0.14)
        fig.text(0.075, 0.919, "Sandablagerung im 1-Hz-Sweep", fontsize=26, weight="bold")
        fig.text(0.075, 0.869, "GP2 Düsseldorf   /   Registrierte Originalaufnahmen 4122–4128 Hz",
                 fontsize=11, color=NEBEN)
        for i, z in enumerate(zeilen):
            ax = fig.add_subplot(g[0, i])
            ax.imshow(bilder[z["id"]])
            ax.set_title(f"{z['hz']:.0f} Hz", fontsize=10, weight="bold", pad=6)
            ax.set_axis_off()
            ax.text(0.5, -0.10, z["id"], transform=ax.transAxes, ha="center", color=NEBEN, fontsize=8)
        for i, (feld, ylabel, farbe) in enumerate((
                ("abdeckung_rel", "Sandfläche [%]", FARBE),
                ("abstand_referenz_rel", "Linienabstand zu 4125 Hz [% von a]", ORANGE))):
            ax = fig.add_subplot(g[i+1, :])
            for z in zeilen:
                wert = z[feld]
                streuung = z.get(feld + "_bereich")
                if wert is None:
                    continue
                if streuung is not None:
                    ax.vlines(z["hz"], 100*min(streuung), 100*max(streuung), color=farbe, alpha=0.55, lw=1.8)
                ax.plot(z["hz"], wert*100, "o", color=farbe, markersize=5, markeredgecolor="white", markeredgewidth=0.6)
            ax.set_ylabel(ylabel)
            ax.set_xticks(sorted({z["hz"] for z in zeilen}))
            ax.grid(axis="y", color="#d5dfe1", lw=0.7)
            if i == 1:
                ax.set_xlabel("Fotografierte Anregungsfrequenz [Hz]")
        fig.text(0.075, 0.056, "Balken zeigen die Spannweite der Schwellen- und Eckvarianten. "
                 "Zwei Aufnahmen bei 4124 Hz. Jeder Punkt ist ein Foto.", fontsize=9, color=NEBEN)
        speichere(fig, ziel)


def spektrum_abbildung(ziel: Path) -> None:
    p = Platte(nu=0.30)
    mit = ["frei", "zentralpunkt", "federflaeche"]
    namen = ["Freie Platte", "Punktbedingung", "Federfläche"]
    with plt.rc_context(stil()):
        fig, ax = plt.subplots(figsize=(9.4, 4.65))
        fig.subplots_adjust(left=0.21, right=0.965, top=0.73, bottom=0.21)
        for i, (rand, name) in enumerate(zip(mit, namen, strict=True)):
            eig = berechne_eigenmoden(p, rand, grad=16, anzahl=12)
            ax.eventplot(np.sqrt(eig.lambda_), lineoffsets=i, linelengths=0.54, lw=2.1,
                         colors=[FARBE if i != 2 else ORANGE])
        ax.set_yticks(range(3), namen)
        ax.invert_yaxis()
        ax.set_ylim(2.55, -0.55)
        ax.set_axisbelow(True)
        ax.grid(axis="x", color="#d5dfe1", lw=0.7)
        ax.set_xlabel(r"Dimensionslose Frequenz $\Omega=\omega\,a^2\sqrt{\rho h/D}$")
        fig.text(0.075, 0.90, "Eigenfrequenzen und zentrale Befestigung", fontsize=20, weight="bold")
        fig.text(0.075, 0.81, "Rayleigh–Ritz, Polynomgrad 16 je Achse, isotrope Platte, ν = 0,30",
                 fontsize=10, color=NEBEN)
        fig.text(0.075, 0.054, "Parametrischer Modellvergleich. Kontaktparameter illustrativ. "
                 "Entartete Frequenzen liegen übereinander.", fontsize=8.5, color=NEBEN)
        speichere(fig, ziel)
