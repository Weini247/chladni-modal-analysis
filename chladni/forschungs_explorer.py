"""Erweiterter lokaler Explorer für Atlas, Eigenmoden, Inversion und Forschungsdaten."""
from __future__ import annotations

from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
import numpy as np
from PIL import Image

from .auswertung import PROJEKT, lese_json
from .eigenmoden import Platte
from .explorer import (AKZENT, BLAU, MARINE, MODELLNAMEN, PAPIER, SUB, WEISS, Explorer,
                       bild_subplot, text)
from .forschungsfiguren import MODELL
from .plattenmechanik import Anschluss, spektrum


class ForschungsExplorer(Explorer):
    def __init__(self,root: tk.Tk,v1: Path,v2: Path,rohdaten: Path):
        self.v2=v2
        self.zweit=lese_json(v2/"atlas.json")
        self.qc={r["id"]:r for r in self.zweit["bilder"]}
        self.mechanik=lese_json(v2/"mechanik.json")
        self.inversion=lese_json(v2/"invers.json")
        self.synthetik=lese_json(v2/"inverse_validierung.json")
        with np.load(v2/"inverse_felder.npz") as a:
            self.felder_invers={int(i):f for i,f in zip(a["indices"],a["felder"],strict=True)}
        self.timer=None
        super().__init__(root,v1,rohdaten)
        self.root.title("Chladni Research Explorer · V2")
        self.tab_inverse=tk.Frame(self.tabs,bg=PAPIER)
        self.tab_dash=tk.Frame(self.tabs,bg=PAPIER)
        self.tabs.insert(2,self.tab_inverse,text="Inverse Rekonstruktion")
        self.tabs.insert(3,self.tab_dash,text="Forschungsdaten")
        self.baue_inverse()
        self.baue_dashboard()
        self.tabs.bind("<<NotebookTabChanged>>",lambda _: self.stop_play())

    def baue_atlas(self):
        super().baue_atlas()
        self.ansicht.configure(values=(*self.ansicht["values"],"Galerie",
                                     "Sandmaske und räumliche Dichte"))
        toolbar=NavigationToolbar2Tk(self.ac,self.ac.get_tk_widget().master,pack_toolbar=False)
        toolbar.update()
        toolbar.pack(side="bottom",fill="x",padx=11)

    def zeige_atlas(self):
        name=self.ansicht.get()
        ix=self.aufnahme.current()
        if name not in {"Galerie","Sandmaske und räumliche Dichte"} or not 0<=ix<len(self.gruppe):
            return super().zeige_atlas()
        z=self.gruppe[ix]
        self.af.clear()
        self.kopf.configure(text=self.fototitel(z))
        qualitaet=self.qc[z["id"]]
        if name=="Galerie":
            subset=self.gruppe[max(0,min(ix-4,len(self.gruppe)-9)):][:9]
            for i,d in enumerate(subset):
                ax=self.af.add_subplot((len(subset)+2)//3,3,i+1)
                bild_subplot(ax,self.lade(d,"platte.png"),self.fototitel(d),False)
            self.info.configure(text=f"{len(subset)} Fotos der gefilterten Auswahl · Reihenfolge nach Anzeige")
        else:
            with np.load(self.ausgabe/z["id"]/"raster.npz") as f:
                maske=np.ma.masked_where(~f["sicht"],f["sand"])
            ax=self.af.add_subplot(131)
            bild_subplot(ax,self.lade(z,"platte.png"),"Registrierte Aufnahme")
            ax=self.af.add_subplot(132)
            ax.imshow(maske,cmap="cividis",vmin=0,vmax=1,extent=(0,1,1,0))
            ax.set(title="Segmentierte Sandfläche",xlabel="x/a",ylabel="y/a")
            ax=self.af.add_subplot(133)
            im=ax.imshow(np.array(qualitaet["dichte_4x4"],dtype=float)*100,cmap="cividis",vmin=0,vmax=100,
                         extent=(0,1,1,0))
            ax.set(title="Bedeckung pro Quadrantengitter",xlabel="x/a",ylabel="y/a")
            self.af.colorbar(im,ax=ax,shrink=.7,label="Sandfläche [%]")
            self.info.configure(text=(f"{z['serie']} · {100*z['abdeckung_rel']:.2f} % Bedeckung · "
                f"{qualitaet['skelett_komponenten_8']} Skelettkomponenten · "
                f"{qualitaet['eingeschlossene_hintergrundregionen_4']} eingeschlossene Pixelregionen"))
        self.ac.draw_idle()

    def baue_modelle(self):
        super().baue_modelle()
        # Zusatzmodell wird bewusst über die getestete Rechenschicht geladen.
        self.rand.configure(values=(*self.rand["values"],MODELL["anschluss"]))
        panel=self.rand.master
        bar=tk.Frame(panel,bg=PAPIER)
        bar.pack(fill="x",pady=(2,0))
        ttk.Button(bar,text="Phase animieren",command=self.play).pack(side="left")
        ttk.Button(bar,text="Stopp",command=self.stop_play).pack(side="left",padx=3)
        self.konv_info=text(panel,"",8,SUB,wraplength=249,justify="left")
        self.konv_info.pack(anchor="w",pady=(5,0))
        self.konvergenztext()

    def zeige_modell(self):
        self.stop_play()
        if self.rand.get()!=MODELL["anschluss"]:
            super().zeige_modell()
        else:
            self.zeige_anschluss()
        if hasattr(self,"konv_info"):
            self.konvergenztext()

    def zeige_anschluss(self):
        try:
            v={k:float(e.get().replace(",", ".")) for k,e in self.felder.items()}
            n=int(v["mode"])
            if n!=v["mode"] or not 1<=n<=20:
                raise ValueError("Mode zwischen 1 und 20 eingeben.")
            p=Platte(v["a"],v["h"]/1000,v["e"]*1e9,v["nu"],v["rho"])
            k=Anschluss(v["r"]/1000,v["k"],self.mechanik["anschluss"]["rotation_nm"],
                         self.mechanik["anschluss"]["verteilte_masse_kg"])
            if not 0<=v["winkel"]<180 or not 0<=v["f"]<np.inf:
                raise ValueError("Winkel und Anregungsmarke außerhalb der unterstützten Skala.")
            key=(p,k)
            if not hasattr(self,"anschluss_cache") or self.anschluss_cache[0]!=key:
                self.anschluss_cache=(key,spektrum(p,"anschluss",18,22,k))
            m=self.anschluss_cache[1]
            from .mustervergleich import familien
            cluster=next(g for g in familien(m.frequenzen_hz,.005) if n-1 in g)
            x=(np.arange(160)+.5)/160
            w=m.feld(n-1,x,x)
            if v["winkel"]:
                if len(cluster)!=2:
                    raise ValueError("Ein Mischwinkel erfordert zwei Moden im Eigencluster.")
                theta=np.deg2rad(v["winkel"])
                w=np.cos(theta)*m.feld(cluster[0],x,x)+np.sin(theta)*m.feld(cluster[1],x,x)
            w=w/np.max(abs(w))
        except (ValueError,ArithmeticError,np.linalg.LinAlgError) as exc:
            self.modinfo.configure(text=str(exc))
            return
        self.mf.clear()
        if self.darstellung.get()=="3D-Oberfläche":
            ax=self.mf.add_subplot(projection="3d")
            xx,yy=np.meshgrid(x,x)
            ax.plot_surface(xx,yy,w,cmap="RdBu_r",vmin=-1,vmax=1,rcount=55,ccount=55,linewidth=0)
            ax.set(zlabel="w / max|w|",xlabel="x/a",ylabel="y/a")
            ax.invert_yaxis()
        else:
            ax=self.mf.add_subplot()
            if self.darstellung.get()=="Feld und Nulllinien":
                im=ax.imshow(w,cmap="RdBu_r",vmin=-1,vmax=1,extent=(0,1,1,0))
                self.mf.colorbar(im,ax=ax,shrink=.75,label="Normierte Auslenkung")
            ax.contour(x,x,w,levels=[0],colors=[MARINE],linewidths=.95)
            ax.set(xlabel="x/a",ylabel="y/a",xlim=(0,1),ylim=(1,0),aspect="equal")
        self.modkopf.configure(text=f"Elastischer Anschluss   /   Mode {n}")
        nah=np.argmin(np.abs(m.frequenzen_hz-v["f"]))
        self.modinfo.configure(text=(f"{m.frequenzen_hz[n-1]:.2f} Hz · Zusatzmasse "
             f"{1000*k.verteilte_masse_kg:g} g · Rotation {k.rotation_nm:g} N m · "
             f"Nächste Mode zur Anregungsmarke {nah+1}. Illustrative Parameter."))
        self.mc.draw_idle()

    def konvergenztext(self):
        name={v:k for k,v in MODELLNAMEN.items()}.get(self.rand.get(),"anschluss")
        info=self.mechanik["modelle"].get(name)
        if info:
            letzten=info["unterraeume"][-1]["vergleich"]
            delta=max(abs(a["frequenz_delta_rel"]) for a in letzten)*100
            self.konv_info.configure(text=f"Studienparameter · Grad 20→24\nMax. Änderung {delta:.3g} % bei zugeordneten Eigenräumen.")
        else:
            self.konv_info.configure(text="Analytischer Navier-Benchmark · siehe Forschungsdaten")

    def play(self):
        self.stop_play()
        if not self.mf.axes or not self.mf.axes[0].images:
            self.modinfo.configure(text="Die Phasenanimation benötigt die 2D-Feldansicht.")
            return
        self.anim_im=self.mf.axes[0].images[0]
        self.anim_base=np.array(self.anim_im.get_array())
        self.anim_phase=0
        self.modinfo.configure(text="Eigenmode mit verlangsamt abgespielter Phase cos(ωt). Die Farbskala ist normiert.")
        self.tick()

    def tick(self):
        self.anim_im.set_data(self.anim_base*np.cos(self.anim_phase))
        self.anim_phase+=2*np.pi/42
        self.mc.draw_idle()
        self.timer=self.root.after(65,self.tick)

    def stop_play(self):
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer=None
            self.anim_im.set_data(self.anim_base)
            self.mc.draw_idle()

    def baue_inverse(self):
        panel,body,self.ivf,self.ivc=self.layout(self.tab_inverse)
        self.inverszeilen={z["id"]:z for z in self.inversion["ergebnisse"]}
        serien=["Alle"]+sorted({z["serie"] for z in self.inverszeilen.values()})
        start=serien.index(self.inversion["kontrollserie"]) if self.inversion["kontrollserie"] in serien else 0
        self.i_serie=self.kombi(panel,"Messserie",serien,self.filter_invers,start)
        self.i_bild=self.kombi(panel,"Experimentelles Foto",["—"],lambda _:self.zeige_kandidaten())
        self.i_typ=self.kombi(panel,"Katalog",["Einzel- und Mischkandidaten","Nur Einzelmoden"],
                              lambda _:self.zeige_kandidaten())
        self.i_status=text(panel,"",9,SUB,wraplength=242,justify="left")
        self.i_status.pack(anchor="w",pady=(12,7))
        self.i_tree=ttk.Treeview(panel,columns=("modell","familie","test"),show="headings",height=7)
        for key,label,b in (("modell","Modell",82),("familie","Familie",80),("test","Prüfwert",70)):
            self.i_tree.heading(key,text=label)
            self.i_tree.column(key,width=b,anchor="w",stretch=True)
        self.i_tree.pack(fill="x",pady=4)
        self.i_tree.bind("<<TreeviewSelect>>",lambda _:self.zeige_inverse())
        ttk.Button(panel,text="Details und Alternativen",command=self.inversdetails).pack(fill="x",pady=(8,3))
        ttk.Button(panel,text="Abbildung exportieren",command=lambda:self.export(self.ivf)).pack(fill="x")
        self.ikopf=text(body,"Inverse Rekonstruktion",19,bg=WEISS,fett=True)
        self.ikopf.pack(anchor="w",padx=18,pady=(13,2))
        self.i_info=text(body,"",9,SUB,WEISS,wraplength=800,justify="left")
        self.i_info.pack(anchor="w",padx=18)
        self.ivc.get_tk_widget().pack(fill="both",expand=True,padx=11,pady=4)
        toolbar=NavigationToolbar2Tk(self.ivc,body,pack_toolbar=False)
        toolbar.update()
        toolbar.pack(side="bottom",fill="x",padx=11)
        self.filter_invers()

    def filter_invers(self,_event=None):
        serie=self.i_serie.get()
        self.i_gruppe=sorted((z for z in self.inverszeilen.values() if serie in {"Alle",z["serie"]}),
                             key=lambda z:(z["hz"] is None,z["hz"] or 0,z["id"]))
        self.i_bild.configure(values=[f"{z['hz']:g} Hz · {z['id']}" if z["hz"] is not None
                                     else f"Frequenz offen · {z['id']}" for z in self.i_gruppe])
        self.i_bild.current(0)
        self.zeige_kandidaten()

    def zeige_kandidaten(self):
        z=self.i_gruppe[self.i_bild.current()]
        getrennt=self.i_typ.current()==1
        self.i_rang=z["rang_nur_einzel" if getrennt else "rang"]
        children=self.i_tree.get_children()
        if children:
            self.i_tree.delete(*children)
        short={"frei":"Frei","zentralpunkt":"Zentralpunkt","federflaeche":"Federfläche",
               "anschluss":"Anschluss","historisch":"Kosinus"}
        for i,r in enumerate(self.i_rang):
            self.i_tree.insert("","end",iid=str(i),values=(short[r["modell"]],"/".join(r["familie"]),
                                                          f"{100*r['test_rel']:.2f} % a"))
        if self.i_rang:
            self.i_tree.selection_set("0")
        self.zeige_inverse()

    def zeige_inverse(self):
        z=self.i_gruppe[self.i_bild.current()]
        self.ivf.clear()
        self.ikopf.configure(text=self.i_bild.get())
        status=z["status"].replace("_"," ").capitalize()
        self.i_status.configure(text=status+"\nAkzeptanzschwelle aus synthetischen Kontrollen.")
        self.i_info.configure(text="Bildrang aus getrennten Flächen. Frequenzabstand wird separat berichtet.")
        for i,(typ,titel) in enumerate((("original-vorschau.jpg","Experiment · Original"),
                                        ("linien.png","Experiment · Sandlinien"))):
            bild_subplot(self.ivf.add_subplot(2,2,i+1),self.lade(z,typ),titel,i==1)
        mark=self.i_tree.selection()
        if mark and int(mark[0])<len(self.i_rang):
            k=self.i_rang[int(mark[0])]
            f=self.felder_invers[k["index"]]
            x=(np.arange(len(f))+.5)/len(f)
            ax=self.ivf.add_subplot(223)
            im=ax.imshow(f,cmap="RdBu_r",extent=(0,1,1,0),vmin=-1,vmax=1)
            ax.contour(x,x,f,levels=[0],colors=[MARINE],linewidths=.9)
            ax.set(title="Modell · normiertes Feld",xlabel="x/a",ylabel="y/a")
            self.ivf.colorbar(im,ax=ax,shrink=.75)
            ov=self.ivf.add_subplot(224)
            bild_subplot(ov,self.lade(z,"platte.png"),"Modellnullen über Experiment")
            ov.contour(x,x,f,levels=[0],colors=[AKZENT],linewidths=1.05)
            freq=f" · Δf {k['freq_abstand_hz']:.0f} Hz" if k["freq_abstand_hz"] is not None else ""
            self.i_info.configure(text=(f"{MODELL[k['modell']]} · Train {100*k['fit_rel']:.2f} % a · "
                f"Prüffläche {100*k['test_rel']:.2f} % a{freq} · Geometrischer Kandidat"))
        self.ivc.draw_idle()

    def inversdetails(self):
        import json
        z=self.i_gruppe[self.i_bild.current()]
        window=tk.Toplevel(self.root)
        window.title("Ränge und Sensitivität · "+z["id"])
        window.geometry("820x590")
        box=tk.Text(window,padx=16,pady=18,wrap="word",font=("Consolas",10))
        box.pack(fill="both",expand=True)
        box.insert("end",json.dumps(z,ensure_ascii=False,indent=2))
        box.configure(state="disabled")

    def baue_dashboard(self):
        panel,body,self.dvf,self.dvc=self.layout(self.tab_dash)
        self.dashboard_figuren={"Zweite Messserie":"zweitserie","Bildvalidierung":"bildreferenz",
             "Vergleich der Messreihen":"serienvergleich",
             "Konvergenz und Residuen":"mechanik_konvergenz","Parametersensitivität":"mechanik_sensitivitaet",
             "Inversion · Kontrollbild":"inverse_kontrollaufnahme","Inversion · Synthetik":"inverse_validierung"}
        self.dash_view=self.kombi(panel,"Wissenschaftliche Abbildung",list(self.dashboard_figuren),self.zeige_dashboard)
        ttk.Button(panel,text="Abbildung exportieren",command=lambda:self.export(self.dvf)).pack(fill="x",pady=13)
        cnt=Counter(z["status"] for z in self.inversion["ergebnisse"])
        test=self.synthetik["test"]["null"]
        text(panel,f"{len(self.qc)} registrierte Vollfotos\n{len(self.zweit['serien'])} Messreihen\n"
                   f"{self.zweit['frequenzpaare']} Frequenznachbarn\n\n"
                   f"Geometrisch mehrdeutig {cnt['NICHT_EINDEUTIG_IDENTIFIZIERBAR']}\n"
                   f"Akzeptierte Nullfälle {test['akzeptiert']} von {test['n']}",
             10,SUB,justify="left",wraplength=244).pack(anchor="w",pady=7)
        self.dvf.set_facecolor(WEISS)
        self.dvc.get_tk_widget().pack(fill="both",expand=True,padx=11,pady=8)
        self.zeige_dashboard()

    def zeige_dashboard(self,_event=None):
        self.dvf.clear()
        ax=self.dvf.add_subplot()
        pfad=self.v2/"figuren"/(self.dashboard_figuren[self.dash_view.get()]+".png")
        with Image.open(pfad) as im:
            ax.imshow(np.asarray(im))
        ax.set_axis_off()
        self.dvc.draw_idle()


def main():
    ap=ArgumentParser(description=__doc__)
    ap.add_argument("--v1",type=Path,default=PROJEKT/"ausgaben/privat/analyse")
    ap.add_argument("--v2",type=Path,default=PROJEKT/"ausgaben/privat/v2")
    ap.add_argument("--rohdaten",type=Path,default=PROJEKT.parent)
    ap.add_argument("--smoke",action="store_true")
    args=ap.parse_args()
    root=tk.Tk()
    if args.smoke:
        root.withdraw()
    app=ForschungsExplorer(root,args.v1,args.v2,args.rohdaten)
    if args.smoke:
        for s in ("Galerie","Sandmaske und räumliche Dichte","Experiment und Modell"):
            app.ansicht.set(s)
            app.zeige_atlas()
            app.ac.draw()
        for s in app.dashboard_figuren:
            app.dash_view.set(s)
            app.zeige_dashboard()
            app.dvc.draw()
        for i in range(2):
            app.i_typ.current(i)
            app.zeige_kandidaten()
            app.ivc.draw()
        app.rand.set(MODELL["anschluss"])
        app.zeige_modell()
        app.mc.draw()
        app.play()
        app.stop_play()
        app.darstellung.set("3D-Oberfläche")
        app.zeige_modell()
        app.mc.draw()
        root.update_idletasks()
        root.destroy()
        print(f"V2-Explorer geprüft: {len(app.qc)} Atlaseinträge und {len(app.inverszeilen)} Inversionseinträge.")
    else:
        root.mainloop()


if __name__=="__main__":
    main()
