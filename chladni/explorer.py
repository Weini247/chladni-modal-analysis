"""Lokaler Forschungs-Explorer mit experimentellem Atlas und Plattenmodellen."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
from PIL import Image

from .auswertung import PROJEKT, lese_json
from .eigenmoden import Platte, berechne_eigenmoden
from .mustervergleich import familien
from .provenienz import quellpfad

PAPIER = "#f0f4f4"
WEISS = "#ffffff"
MARINE = "#142a3b"
BLAU = "#146487"
SUB = "#4a6372"
AKZENT = "#e3a54d"
MODELLNAMEN = {"navier": "Navier · einfach gelagert", "frei": "Freie Ränder",
               "zentralpunkt": "Zentrale Punktbedingung", "federflaeche": "Federfläche"}
STUFEN = {"manuell_gelesen": "Sichtablesung", "widerspruch": "Quellenkonflikt",
          "unbekannt": "Frequenz unbekannt", "zu_pruefen": "Zu prüfen",
          "unplausibel": "Unplausibel", "nicht_ausgewertet": "Registrierung offen"}


def text(master, inhalt: str, groesse: int = 10, fg: str = MARINE, bg: str = PAPIER,
         fett: bool = False, **kwargs) -> tk.Label:
    return tk.Label(master, text=inhalt, fg=fg, bg=bg,
                    font=("Segoe UI", groesse, "bold" if fett else "normal"), **kwargs)


def bild_subplot(ax, bild, titel: str, achsen: bool = True) -> None:
    ax.set_title(titel, loc="left", color=MARINE, fontweight="bold", fontsize=10)
    if achsen:
        ax.imshow(bild, extent=[0, 1, 1, 0])
        ax.set_xlabel("x/a")
        ax.set_ylabel("y/a")
        ax.set_xticks([0, 0.5, 1])
        ax.set_yticks([0, 0.5, 1])
    else:
        ax.imshow(bild)
        ax.set_axis_off()


def normiertes_feld(feld: np.ndarray) -> np.ndarray:
    maximum = np.max(np.abs(feld))
    if maximum <= np.finfo(float).eps:
        raise ValueError("Die gewählten Koeffizienten ergeben ein Nullfeld.")
    return feld / maximum


class Explorer:
    def __init__(self, root: tk.Tk, ausgabe: Path, rohdaten: Path):
        self.root = root
        self.ausgabe = ausgabe
        self.rohdaten = rohdaten
        self.atlas = lese_json(ausgabe / "atlas.json")
        self.fotos = self.atlas["bilder"]
        self.konfig = self.atlas["konfiguration"]
        inv = lese_json(PROJEKT / self.konfig["inventar"])
        self.thumbs = (PROJEKT / self.konfig["inventar"]).parent / "vorschaubilder"
        self.archiv = [z for z in inv["dateien"] if z["status"] == "bild_dekodiert"]
        self.modell_cache = {}
        self.gruppe = []
        self.aktualisiert = False
        self.root.title("Chladni Explorer · GP2 Düsseldorf")
        self.root.geometry("1280x850")
        self.root.minsize(940, 675)
        self.root.configure(bg=PAPIER)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background=PAPIER, foreground=MARINE)
        style.configure("TNotebook", borderwidth=0)
        style.configure("TNotebook.Tab", background="#dce8eb", padding=(17, 10), font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", WEISS)], foreground=[("selected", BLAU)])
        style.configure("TButton", padding=(8, 6), background="#dce8eb")
        style.configure("TCombobox", padding=(5, 4))
        hero = tk.Frame(root, bg=MARINE)
        hero.pack(fill="x")
        text(hero, "Chladni Explorer", 26, WEISS, MARINE, True).pack(anchor="w", padx=27, pady=(13, 0))
        text(hero, f"GP2 Düsseldorf   /   {len(self.archiv)} Archivbilder   /   {len(self.fotos)} registrierte Aufnahmen",
             10, "#bed8e2", MARINE).pack(anchor="w", padx=29, pady=(2, 13))

        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=19, pady=(11, 13))
        self.tab_atlas = tk.Frame(self.tabs, bg=PAPIER)
        self.tab_model = tk.Frame(self.tabs, bg=PAPIER)
        self.tab_archiv = tk.Frame(self.tabs, bg=PAPIER)
        self.tabs.add(self.tab_atlas, text="Experimentatlas")
        self.tabs.add(self.tab_model, text="Eigenmoden")
        self.tabs.add(self.tab_archiv, text="Bildarchiv")
        self.baue_atlas()
        self.baue_modelle()
        self.baue_archiv()

    def layout(self, parent) -> tuple[tk.Frame, tk.Frame, Figure, FigureCanvasTkAgg]:
        panel = tk.Frame(parent, bg=PAPIER, width=260)
        panel.pack(side="left", fill="y", padx=(8, 13), pady=13)
        panel.pack_propagate(False)
        body = tk.Frame(parent, bg=WEISS)
        body.pack(side="left", fill="both", expand=True, padx=(1, 10), pady=13)
        fig = Figure(figsize=(8, 5), dpi=100, facecolor=WEISS, layout="constrained")
        chart = FigureCanvasTkAgg(fig, master=body)
        return panel, body, fig, chart

    def kombi(self, parent, beschriftung, werte, callback, index=0):
        text(parent, beschriftung, fg=SUB, fett=True).pack(anchor="w", pady=(10, 3))
        box = ttk.Combobox(parent, values=werte, state="readonly", width=29)
        box.pack(fill="x")
        box.current(index)
        if callback:
            box.bind("<<ComboboxSelected>>", callback)
        return box

    def baue_atlas(self) -> None:
        panel, body, self.af, self.ac = self.layout(self.tab_atlas)
        serie = self.konfig["serie_pilot"]
        serien = ["Alle"] + sorted({z["serie"] for z in self.fotos})
        self.serie = self.kombi(panel, "Messserie", serien, self.filter_atlas,
                                serien.index(serie) if serie in serien else 0)
        self.status = self.kombi(panel, "Frequenzbeleg", ["Alle", *sorted({STUFEN.get(z["frequenzstatus"],
                                 z["frequenzstatus"]) for z in self.fotos})], self.filter_atlas)
        familien = sorted({k["rand"] + " " + "/".join(map(str, k["moden"]))
                           for z in self.fotos for k in z.get("bildranking", [])[:1]})
        self.familie = self.kombi(panel, "Bester geometrischer Kandidat",
                                 ["Alle", *familien], self.filter_atlas)
        self.ansicht = self.kombi(panel, "Ansicht", ["Aufnahme und Sandlinien", "Experiment und Modell",
                                    "Vergleich zweier Aufnahmen", "Frequenz-Sweep",
                                    "Posterabgleich", "Symmetrieübersicht"],
                                    lambda _: self.zeige_atlas())
        text(panel, "Aufnahme", fg=SUB, fett=True).pack(anchor="w", pady=(13, 3))
        self.aufnahme = ttk.Combobox(panel, state="readonly", width=29)
        self.aufnahme.pack(fill="x")
        self.aufnahme.bind("<<ComboboxSelected>>", self.auswahl)
        self.regler = tk.Scale(panel, from_=0, to=0, orient="horizontal", showvalue=False,
                               command=self.regle, bg=PAPIER, highlightthickness=0, troughcolor="#c8dce3")
        self.regler.pack(fill="x", pady=(3, 0))
        self.zweiter = self.kombi(panel, "Vergleichsaufnahme", ["—"], lambda _: self.zeige_atlas())
        ttk.Button(panel, text="Abbildung exportieren", command=lambda: self.export(self.af)).pack(fill="x", pady=(16, 5))
        ttk.Button(panel, text="Provenienz und Frequenzbelege", command=self.zeige_provenienz).pack(fill="x", pady=2)
        ttk.Button(panel, text="Quelldatei öffnen", command=self.oeffne_quelle).pack(fill="x", pady=2)
        self.kopf = text(body, "Experimentatlas", 19, bg=WEISS, fett=True)
        self.kopf.pack(anchor="w", padx=19, pady=(15, 2))
        self.info = text(body, "", 10, SUB, WEISS, wraplength=820, justify="left")
        self.info.pack(anchor="w", padx=19, pady=(0, 2))
        self.ac.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=(6, 10))
        self.filter_atlas()

    def filter_atlas(self, _event=None) -> None:
        serie, status, familie = self.serie.get(), self.status.get(), self.familie.get()
        self.gruppe = []
        for z in self.fotos:
            f = STUFEN.get(z["frequenzstatus"], z["frequenzstatus"])
            if (serie != "Alle" and z["serie"] != serie) or (status != "Alle" and f != status):
                continue
            kandidaten = z.get("bildranking", [])
            k = kandidaten[0] if kandidaten else None
            if familie != "Alle" and (k is None or familie != k["rand"] + " " + "/".join(map(str, k["moden"]))):
                continue
            self.gruppe.append(z)
        self.gruppe.sort(key=lambda z: (z["hz"] is None, z["hz"] or 0, z["id"]))
        labels = [self.fototitel(z) for z in self.gruppe]
        self.aktualisiert = True
        for box in (self.aufnahme, self.zweiter):
            box.configure(values=labels)
            if labels:
                box.current(0 if box == self.aufnahme else len(labels)-1)
            else:
                box.set("")
        self.regler.configure(to=max(0, len(labels)-1))
        self.regler.set(0)
        self.aktualisiert = False
        self.zeige_atlas()

    @staticmethod
    def fototitel(z: dict) -> str:
        freq = f"{z['hz']:g} Hz" if z["hz"] is not None else STUFEN.get(z["frequenzstatus"], "Offen")
        return f"{freq}  ·  {z['id']}"

    def regle(self, wert) -> None:
        if not self.aktualisiert and self.gruppe:
            index = int(float(wert))
            if self.aufnahme.current() != index:
                self.aufnahme.current(index)
                self.zeige_atlas()

    def auswahl(self, _event=None) -> None:
        self.regler.set(self.aufnahme.current())
        self.zeige_atlas()

    def lade(self, z: dict, typ: str) -> np.ndarray:
        with Image.open(self.ausgabe / z["id"] / typ) as bild:
            return np.array(bild)

    def zeige_atlas(self) -> None:
        self.af.clear()
        index = self.aufnahme.current()
        if not 0 <= index < len(self.gruppe):
            self.kopf.configure(text="Keine passende Aufnahme")
            self.info.configure(text="")
            self.ac.draw_idle()
            return
        z = self.gruppe[index]
        self.kopf.configure(text=self.fototitel(z))
        f = z["spiegel_jaccard"]
        info = (f"{z['serie']}   /   Sandfläche {z['abdeckung_rel']*100:.1f} %   /   "
                f"Spiegel-Jaccard x {f['links_rechts']:.2f}, y {f['oben_unten']:.2f}")
        modus = self.ansicht.get()
        if modus in {"Frequenz-Sweep", "Posterabgleich"}:
            pfad = self.ausgabe / ("sweep-4122-4128.png" if modus == "Frequenz-Sweep" else "posterabgleich.png")
            if pfad.is_file():
                with Image.open(pfad) as bild:
                    bild_subplot(self.af.add_subplot(), np.array(bild), "", False)
                info = ("Abgelesene Einzelaufnahmen und deterministische Sensitivitätsspannen."
                        if modus == "Frequenz-Sweep" else
                        "Beste Bildtreffer der Posterpanels unter acht Originalaufnahmen.")
            else:
                info = "Abbildung fehlt. Die Reproduktionsbefehle stehen in der README."
        elif modus == "Symmetrieübersicht":
            ax = self.af.add_subplot()
            labels = ("links_rechts", "oben_unten", "diagonal", "90_grad")
            werte = [z["spiegel_jaccard"][k] for k in labels]
            punkte = [d["spiegel_jaccard"] for d in self.gruppe]
            for i, k in enumerate(labels):
                y = [d[k] for d in punkte if d[k] is not None]
                ax.scatter([i]*len(y), y, s=17, alpha=0.43, color=BLAU)
                if werte[i] is not None:
                    ax.scatter(i, werte[i], s=66, color=AKZENT, edgecolor=MARINE, zorder=3)
            ax.set_xticks(range(4), ["Links/rechts", "Oben/unten", "Diagonal", "Drehung 90°"])
            ax.set(ylim=(0, 1.03), ylabel="Jaccard-Index der Sandmaske")
            ax.grid(axis="y", alpha=0.25)
            info = "Orange markiert die ausgewählte Aufnahme. Die übrigen Werte stammen aus der gefilterten Gruppe."
        elif modus == "Vergleich zweier Aufnahmen":
            z2 = self.gruppe[max(0, self.zweiter.current())]
            for i, d in enumerate((z, z2), 1):
                bild_subplot(self.af.add_subplot(1, 2, i), self.lade(d, "linien.png"), self.fototitel(d))
        elif modus == "Experiment und Modell":
            bild_subplot(self.af.add_subplot(1, 2, 1), self.lade(z, "linien.png"), "Sandlinien-Kandidaten")
            if z.get("bildranking"):
                a = z["bildranking"][0]
                feld = normiertes_feld(np.load(self.ausgabe / z["id"] / "modellfeld.npy"))
                x = (np.arange(len(feld)) + 0.5) / len(feld)
                panel = self.af.add_subplot(1, 2, 2)
                bild_subplot(panel, self.lade(z, "platte.png"), "Modellnullen (orange) auf der Aufnahme")
                panel.contour(x, x, feld, levels=[0], colors=[AKZENT], linewidths=1.1)
                info = (f"{MODELLNAMEN[a['rand']]} · Eigenfamilie {a['moden']} · "
                        f"Linienabstand {a['bildabstand_rel']*100:.2f} % von a. "
                        f"Illustrative Modellfrequenz {a['hz']:.1f} Hz. Ranking nach Bildabstand.")
            else:
                info = "Für diese Aufnahme liegt kein berechneter Modellvergleich vor."
        else:
            for j, (typ, titel) in enumerate((("original-vorschau.jpg", "Originalaufnahme"),
                                              ("platte.png", "Entzerrte Platte"),
                                              ("linien.png", "Sandlinien-Kandidaten")), 1):
                bild_subplot(self.af.add_subplot(1, 3, j), self.lade(z, typ), titel, j != 1)
        self.info.configure(text=info)
        self.ac.draw_idle()

    def zeige_provenienz(self) -> None:
        index = self.aufnahme.current()
        if 0 <= index < len(self.gruppe):
            z = self.gruppe[index]
            popup = tk.Toplevel(self.root)
            popup.title(self.fototitel(z))
            popup.geometry("840x525")
            p = tk.Text(popup, wrap="word", padx=20, pady=13, bg=WEISS, fg=MARINE, font=("Consolas", 10))
            p.pack(fill="both", expand=True)
            auswahl = ("id", "pfad", "sha256", "exif", "frequenzstatus", "frequenzbelege",
                       "registrierung", "geometrie", "bildranking")
            p.insert("1.0", json.dumps({k: z[k] for k in auswahl}, indent=2, ensure_ascii=False))
            p.configure(state="disabled")

    def oeffne_quelle(self) -> None:
        index = self.aufnahme.current()
        if not 0 <= index < len(self.gruppe):
            return
        try:
            pfad = quellpfad(self.rohdaten, self.gruppe[index]["pfad"])
            if sys.platform == "win32":
                os.startfile(pfad)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(pfad)])
        except (OSError, ValueError) as exc:
            messagebox.showerror("Quelldatei", str(exc))

    def baue_modelle(self) -> None:
        panel, body, self.mf, self.mc = self.layout(self.tab_model)
        self.rand = self.kombi(panel, "Randmodell", list(MODELLNAMEN.values()), lambda _: self.zeige_modell(), 1)
        self.darstellung = self.kombi(panel, "Darstellung", ["Feld und Nulllinien", "3D-Oberfläche", "Nulllinien"],
                                     lambda _: self.zeige_modell())
        self.felder = {}
        eingaben = [("mode", "Mode ab 1", 4), ("a", "Seitenlänge [m]", 0.18),
                    ("h", "Dicke [mm]", 3.0), ("e", "Elastizitätsmodul [GPa]", 69),
                    ("nu", "Poissonzahl ν", 0.35), ("rho", "Dichte [kg/m³]", 2700),
                    ("r", "Kontaktradius [mm]", 6), ("k", "Kontaktsteifigkeit [N/m]", 200000),
                    ("winkel", "Mischwinkel im Eigenpaar [°]", 0), ("f", "Anregungsmarke [Hz]", 4125)]
        form = tk.Frame(panel, bg=PAPIER)
        form.pack(fill="x", pady=(12, 6))
        for i, (key, label, wert) in enumerate(eingaben):
            text(form, label, 9, SUB).grid(row=i, column=0, padx=(0, 5), pady=2, sticky="w")
            feld = ttk.Entry(form, width=10)
            feld.insert(0, str(wert))
            feld.grid(row=i, column=1, sticky="ew", pady=2)
            feld.bind("<Return>", lambda _: self.zeige_modell())
            self.felder[key] = feld
        ttk.Button(panel, text="Eigenmoden berechnen", command=self.zeige_modell).pack(fill="x", pady=4)
        ttk.Button(panel, text="Abbildung exportieren", command=lambda: self.export(self.mf)).pack(fill="x", pady=4)
        self.modkopf = text(body, "Numerisches Plattenmodell", 19, bg=WEISS, fett=True)
        self.modkopf.pack(anchor="w", padx=19, pady=(15, 2))
        self.modinfo = text(body, "", 10, SUB, WEISS, wraplength=775, justify="left")
        self.modinfo.pack(anchor="w", padx=19, pady=(0, 2))
        self.mc.get_tk_widget().pack(fill="both", expand=True, padx=14, pady=(9, 13))
        self.zeige_modell()

    def zeige_modell(self) -> None:
        try:
            v = {k: float(f.get().replace(",", ".")) for k, f in self.felder.items()}
            n = int(v["mode"])
            if v["mode"] != n or not 1 <= n <= 20:
                raise ValueError("Mode als ganze Zahl zwischen 1 und 20 eingeben.")
            if not 0 <= v["winkel"] < 180 or not 0 <= v["f"] < np.inf:
                raise ValueError("Mischwinkel in [0, 180) und eine nichtnegative Frequenz eingeben.")
            p = Platte(v["a"], v["h"] / 1000, v["e"] * 1e9, v["nu"], v["rho"])
            rand = next(k for k, name in MODELLNAMEN.items() if name == self.rand.get())
            key = (p, rand, v["r"], v["k"])
            if key not in self.modell_cache:
                self.modell_cache = {key: berechne_eigenmoden(p, rand, 14, 24, v["r"]/1000, v["k"])}
            m = self.modell_cache[key]
            gruppe = next(g for g in familien(m.lambda_) if n-1 in g)
            x = (np.arange(160) + 0.5) / 160
            if v["winkel"] and len(gruppe) != 2:
                raise ValueError("Ein Mischwinkel ist nur im zweidimensionalen Eigenraum definiert.")
            w = m.feld(n-1, x, x)
            if v["winkel"]:
                z = np.deg2rad(v["winkel"])
                w = np.cos(z)*m.feld(gruppe[0], x, x) + np.sin(z)*m.feld(gruppe[1], x, x)
            w = normiertes_feld(w)
        except (ValueError, ArithmeticError, np.linalg.LinAlgError) as exc:
            self.modinfo.configure(text=str(exc))
            return
        self.mf.clear()
        if self.darstellung.get() == "3D-Oberfläche":
            ax = self.mf.add_subplot(projection="3d")
            a, b = np.meshgrid(x, x)
            ax.plot_surface(a, b, w, cmap="RdBu_r", vmin=-1, vmax=1, linewidth=0,
                            antialiased=True, rcount=58, ccount=58)
            ax.set(xlabel="x/a", ylabel="y/a", zlabel="w / max|w|")
            ax.invert_yaxis()
        else:
            ax = self.mf.add_subplot()
            if self.darstellung.get() == "Feld und Nulllinien":
                im = ax.imshow(w, cmap="RdBu_r", vmin=-1, vmax=1, extent=[0,1,1,0])
                self.mf.colorbar(im, ax=ax, shrink=0.77, label="Normierte Auslenkung")
            ax.contour(x, x, w, levels=[0], colors=[MARINE], linewidths=0.95)
            ax.set(aspect="equal", xlim=(0,1), ylim=(1,0), xlabel="x/a", ylabel="y/a")
        best = np.argmin(np.abs(m.frequenzen_hz-v["f"]))
        self.modkopf.configure(text=f"{self.rand.get()}   /   Mode {n}")
        self.modinfo.configure(text=(f"Eigenfrequenz {m.frequenzen_hz[n-1]:.2f} Hz · Familie "
            f"{', '.join(str(i+1) for i in gruppe)} · Anregungsmarke {v['f']:g} Hz · "
            f"Nächste berechnete Mode {best+1} ({m.frequenzen_hz[best]:.2f} Hz)"))
        self.mc.draw_idle()

    def baue_archiv(self) -> None:
        panel, body, self.df, self.dc = self.layout(self.tab_archiv)
        gruppen = ["Alle"] + sorted({Path(z["pfad"]).parent.name for z in self.archiv})
        self.archiv_filter = self.kombi(panel, "Ordner", gruppen, self.filter_archiv)
        box = tk.Frame(panel, bg=PAPIER)
        box.pack(fill="both", expand=True, pady=(10, 0))
        scrollbar = ttk.Scrollbar(box)
        scrollbar.pack(side="right", fill="y")
        self.archiv_liste = tk.Listbox(box, bg=WEISS, fg=MARINE, relief="flat", yscrollcommand=scrollbar.set,
                                      exportselection=False, font=("Segoe UI", 10))
        self.archiv_liste.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self.archiv_liste.yview)
        self.archiv_liste.bind("<<ListboxSelect>>", self.zeige_archiv)
        self.archiv_info = text(body, "", 10, SUB, WEISS, wraplength=800, justify="left")
        self.archiv_info.pack(anchor="w", padx=19, pady=(15, 2))
        self.dc.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=10)
        self.filter_archiv()

    def filter_archiv(self, _event=None) -> None:
        auswahl = self.archiv_filter.get()
        self.archiv_gruppe = [z for z in self.archiv if auswahl in {"Alle", Path(z["pfad"]).parent.name}]
        self.archiv_liste.delete(0, "end")
        for z in self.archiv_gruppe:
            p = Path(z["pfad"])
            self.archiv_liste.insert("end", f"{p.parent.name} · {p.name}")
        if self.archiv_gruppe:
            self.archiv_liste.selection_set(0)
        self.zeige_archiv()

    def zeige_archiv(self, _event=None) -> None:
        index = self.archiv_liste.curselection()
        if index:
            z = self.archiv_gruppe[index[0]]
            self.df.clear()
            self.archiv_info.configure(text=(f"{z['pfad']}\n"
                f"{z['orientiert_breite_px']} × {z['orientiert_hoehe_px']} px  ·  SHA-256 {z['sha256']}"))
            with Image.open(self.thumbs / (z["sha256"] + ".jpg")) as bild:
                bild_subplot(self.df.add_subplot(), np.array(bild), Path(z["pfad"]).name, False)
            self.dc.draw_idle()

    @staticmethod
    def export(fig: Figure) -> None:
        pfad = filedialog.asksaveasfilename(defaultextension=".png", initialdir=PROJEKT / "ausgaben/privat",
                filetypes=[("PNG", "*.png"), ("SVG", "*.svg"), ("PDF", "*.pdf")])
        if pfad:
            ziel = Path(pfad).resolve()
            if not ziel.is_relative_to(PROJEKT / "ausgaben/privat"):
                messagebox.showerror("Export", "Speichere die Abbildung in ausgaben/privat/ des Forschungsprojekts.")
            else:
                fig.savefig(ziel, dpi=190, facecolor=fig.get_facecolor())


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ausgabe", type=Path, default=PROJEKT / "ausgaben/privat/analyse")
    p.add_argument("--rohdaten", type=Path, default=PROJEKT.parent)
    p.add_argument("--smoke", action="store_true", help="Fenster und drei Ansichten aufbauen und direkt schließen")
    args = p.parse_args()
    root = tk.Tk()
    if args.smoke:
        root.withdraw()
    app = Explorer(root, args.ausgabe, args.rohdaten)
    if args.smoke:
        for name in ("Experiment und Modell", "Vergleich zweier Aufnahmen", "Frequenz-Sweep",
                     "Symmetrieübersicht", "Posterabgleich"):
            app.ansicht.set(name)
            app.zeige_atlas()
            app.ac.draw()
        app.darstellung.set("3D-Oberfläche")
        app.zeige_modell()
        app.mc.draw()
        app.dc.draw()
        root.update_idletasks()
        root.destroy()
        print(f"Explorer bereit: {len(app.fotos)} analysierte Aufnahmen, {len(app.archiv)} Archivbilder.")
    else:
        root.mainloop()


if __name__ == "__main__":
    main()
