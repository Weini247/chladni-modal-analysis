
# V3 · Oberfläche und visuelle Sprache

Der Research Explorer bietet eine browserbasierte Alternative zum V2-Tk-Explorer. Browser übernehmen responsive Layouts und Tastatursteuerung. Canvas zeichnet die tatsächlich berechneten Eigenfelder, Nullkonturen und registrierten Annotationen. Die lokale HTTP-Schnittstelle verwendet die bestehenden Python-Module für Bildaufbereitung, Katalogbewertung und Physik. Die Wahl vermeidet eine zweite wissenschaftliche Implementierung und erlaubt größere Bildflächen sowie gemeinsame Navigation.

| Ebene | Zuständigkeit |
| --- | --- |
| Rechenkern | `bildpipeline.py`, `plattenmechanik.py` und `inverse_modelle.py` liefern registrierte Bilder, Raster, Eigenfelder und Vergleichsdistanzen. |
| Studien | `bildvalidierung_v3.py` und `invers_v3.py` werten jeweils eigene versionierte Störungen aus. `annotationen.py` speichert und vergleicht manuelle Regionen. |
| Daten und Dienst | `labor_daten.py` hält API-Datensätze und Berechnungen. `labor_web.py` stellt sie an 127.0.0.1 bereit und beschränkt Routen und Anfragen. |
| Browser | `labor.js` steuert Ansichten und Zustände. `grafik.js` enthält die Canvas-Zeichenlogik, `annotation.js` den Zeicheneditor und `labor.css` das visuelle System. |
| Export | `figuren_v3.py` erzeugt die gemeinsamen Exportdateien. Die Validierungsansicht verlinkt dieselben PNG-, SVG- und PDF-Dateien. |

## Farben, Schriften und Bewegung

Dunkelgrau `#0c1016` bildet den Hintergrund, die nächsthöhere Ebene verwendet `#131a23`. Türkis `#70e3cf` hebt interaktive Elemente und Modellkonturen in Overlays hervor. Violett markiert modellbasierte Inhalte, Ocker Prüf- und Abstentionshinweise. Farbe wird durch Text, Linienformen und Symbole ergänzt. Auslenkungsfelder verwenden eine vorzeichenbezogene Blau–Neutral–Rost-Skala mit Null in der Mitte. Die Linienüberlagerung verwendet Ocker für extrahierte Beobachtungsspuren und Türkis für Modellkonturen. Im statischen Export unterscheiden zusätzlich Symbolformen und Linienstile die Reihen. Helle Hintergründe und DejaVu Sans unterstützen den Druck.

Die Browsertypografie nutzt Segoe UI mit System-Fallback und Cascadia Mono oder Consolas für Zahlen und Provenienz. Die Grundschriftgröße ist 1 rem. Hauptinhalte nutzen 72 px Außenabstand auf breiten und 28 px auf kleinen Displays, den verfügbaren Platz begrenzt eine gemeinsame Inhaltsbreite. Die Desktopansichten gruppieren Bedienung und große Bildfläche. Auf kleinen Displays folgen Bedienelemente und Auswertung untereinander.

## Interaktionen und Zustände

- Der Atlas navigiert diskret durch echte Aufnahmen. Doppelte Frequenzen behalten eigene ID und Bilddaten. Der Vergleich zeigt einzelne Punkte und verbindet Frequenzlücken nicht durch interpolierte Messwerte.
- Die 3D-Ansicht zeigt eine projizierte Oberfläche aus dem normierten Raster, mit Rotation über Maus, Touch oder Pfeiltasten. Die Animation startet auf Wunsch, läuft in Zeitlupe und benutzt Frequenzverhältnisse der gewählten Moden. Ein festes Normierungsmaß vermeidet künstliches Nachskalieren in jeder Phase. Der optionale Gradvergleich zeigt, wie sich Eigenfrequenzen und Unterräume bei denselben Eingabeparametern und einem anderen Ritz-Grad ändern.
- Die Inversion zeigt zunächst den archivierten Befund. Eine separate Ausführung berechnet eine geänderte Extraktion aus dem quellgeprüften Foto. Der Rangselektor hebt das zugehörige Feld und Overlay hervor. Fit, Prüfdistanz, Familie und Abstention werden gemeinsam angezeigt.
- Die Annotation beginnt auf dem Bild ohne algorithmische Labels. Eine neue Revisions-ID ergänzt die Chronik. Vergebene Labels und Status bleiben auditiert, auch wenn eine Revision aus einer älteren hervorgeht.
- Fehlende Dateien, ungültige Rechnungen und abgelehnte Fits haben ihre eigenen Textzustände. Browser-Steuerelemente nutzen sichtbare Fokusränder. Animation der Seiteninteraktionen respektiert die Browser-Einstellung für reduzierte Bewegung.

## Freigabe

Die lokale Startseite zeigt ein registriertes Experimentbild. Das öffentliche README-Motiv nutzt ausschließlich eine gekennzeichnete numerische Simulation. Fotografische Ableitungen, genaue Quellenpfade und Annotationsrevisionen bleiben im privaten Datenbereich. Vor der Weitergabe experimentbezogener Inhalte sind Rechte und individuelle Attribution zu klären.
