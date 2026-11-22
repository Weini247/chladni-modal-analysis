# V3 · Reproduktion

## Öffentlicher Snapshot ohne GP2-Daten

Python 3.12 in einer eigenen virtuellen Umgebung verwenden. Die Befehle aus der Projektwurzel ausführen.

```sh
python -m pip install -r requirements-lock.txt
python -m chladni.checks --scope all
python -m werkzeuge.v3_modellpaket
```

Die Tests umfassen analytische Eigenwerte, Residuen, Unterraumvergleiche, synthetische Bildverarbeitung und Inversion. Das Modellpaket verwendet die V2-Modellparameter sowie den festgelegten V3-Seed und die gleichen Kriterien für die synthetische Benchmark-Auswertung. Es schreibt `mechanik.json`, `synthetik.json` und beide Abbildungen in PNG, SVG und PDF unter `ausgaben/privat/modellpaket`. Mit `--ziel` lässt sich ein anderer Ausgabeordner wählen. Ein separater Simulationsbanner ist weiterhin mit `python -m chladni.forschung_v3 showcase` erzeugbar.

Die Berechnungen wurden mit einem BLAS-Thread geprüft. Reproduzierbarkeit auf Dateiebene bezieht sich auf dieselben Python-, Bibliotheks- und Font-Versionen auf derselben Plattform. Numerische Toleranzen sind in den Tests dokumentiert.

## Vollständiger Experimentlauf mit privaten Eingaben

Der lokale Rohdatenbestand umfasst die GP2-Aufnahmen und das dazugehörige SHA-256-Inventar. Der veröffentlichte Code enthält die Rechenwege. Für ihre Ausführung sind die getrennt gehaltenen Originaldateien, die lokalen Registrierungs- und Referenzkonfigurationen sowie die vorbereiteten V1- und V2-Eingangsartefakte einschließlich unabhängiger V2-Auditkopien nötig. Das Archiv und diese Begleitdaten gehören gemeinsam zur lokalen Forschungsumgebung. Die [Aggregatbefunde](V3_ERGEBNISSE.md) berichten die Ergebnisse der geprüften lokalen Läufe.

```powershell
$roh = (Read-Host 'Pfad zum lokalen GP2-Archiv')
$env:OPENBLAS_NUM_THREADS = '1'
python -m chladni.forschung_v3 alle --rohdaten $roh
python -m chladni.forschung_v3 alle --rohdaten $roh --ziel ausgaben/privat/v3/nachrechnung
python -m werkzeuge.v3_laufaudit --rohdaten $roh
$env:CHLADNI_ROHDATEN = $roh
python -m werkzeuge.v3_httpcheck
.\start-v3.ps1 --rohdaten $roh --port 8897
```

Die letzte Zeile startet den optionalen Explorer auf Loopback. Die Analyseprovenienz bindet das Inventar, die V1- und V2-Artefakte, Konfigurationen, Module und Ausgaben im Laufmanifest über SHA-256. Annotationen liegen in einem getrennten Revisionsspeicher. Unabhängige menschliche Referenzannotationen stehen aus.

[Methoden und Befunde](V3_ERGEBNISSE.md) · [Versuchsprotokoll](V3_PROTOKOLL.md) · [Oberfläche und Formate](V3_DESIGN.md)

## Quellen der vier README-Abbildungen

| Abbildung | Quelle | Ausgabe |
| --- | --- | --- |
| `mechanik.png` | `modellstudie` aus `chladni/plattenmechanik.py` mit `konfiguration/v2.json` | Relative Eigenproblemresiduen und Frequenzänderungen bei Verfeinerung in vier Modellen |
| `synthetik.png` | Synthetischer Benchmark aus `chladni/invers_v3.py`, Modellkatalog aus `konfiguration/v2.json`, Seed und Prüfkriterien aus `konfiguration/v3.json` | Top-1- und Top-6-Treffer je Beobachtungssetting mit gleichverteilter Top-6-Referenz |
| `sweeps.png` | Lokales `ausgaben/privat/v3/bildstudie.json`, erstellt mit `python -m chladni.forschung_v3 bilder` und `konfiguration/v3.json` | Basiswert und Minimum–Maximum über 22 Auswertungseinstellungen pro Frequenzschritt |
| `gap.png` | Lokales `ausgaben/privat/v3/gap.json`, erstellt mit `python -m chladni.forschung_v3 gap`, der archivierten V2-Modellkonfiguration und den eingefrorenen Grenzen aus `konfiguration/v3.json` | Minimum, Median und Maximum der zurückgehaltenen Prüfdistanzen über sieben Aufnahmen je Katalogvariante |

Die beiden numerischen PNGs unter `assets/figures/` stammen aus `python -m werkzeuge.v3_modellpaket`. Die beiden experimentellen PNGs verwenden den vorhandenen Export aus `chladni/figuren_v3.py` mit aggregierter Darstellung. Aus einem vorbereiteten lokalen Analysebestand erzeugt `python -m chladni.forschung_v3 figuren` die PNGs unter `ausgaben/privat/v3/figuren/`. Die Rohbilder, Einzelwerte und Annotationsdaten verbleiben im privaten Bestand. Exportiert wurden nur die gerenderten Aggregatgrafiken.

Die IDs der zugrunde liegenden lokalen Artefakte sind per SHA-256 im V3-Laufmanifest belegt.

- `bildstudie.json` · `99afbf7bc839cc674b32c9ee21a051a85aab471e2fa4996623c5412112e5d607`
- `gap.json` · `29aed9ecc88e282b2dabd18ef26df976bdcb8c0530f4f65aded9ef137f27f098`

## Bildtafeln aus zwei freigegebenen Aufnahmen

- **4122 Hz** · Die Quelle ist die lokale Aufnahme `IMG_1601`. Die Tafel kombiniert einen Aufbauausschnitt aus der Originalvorschau, die perspektivisch registrierte Platte und die gespeicherten Raster `score`, `sicht` und `linien`. Die Heatmap zeigt den dimensionslosen Blauüberschuss-Score mit fester Farbskala von 0 bis 0,46. Gelb markiert das Skelett der segmentierten Sandmaske.
- **3723 Hz** · Die Quelle ist die lokale Kontrollaufnahme `IMG_1583`. Die Modellkontur nutzt die Nullhöhe des führenden V2-Kandidaten aus `invers.json` und `inverse_felder.npz`. Die Prüfdistanz auf den zurückgehaltenen Streifen beträgt gerundet 2,99 % der Plattenseite. Die geometrische Schwelle beträgt 2,00 %.

Die Veröffentlichung enthält die zwei fertigen PNG-Tafeln ohne eingebettete EXIF-Daten. Für eine Neuberechnung werden die privaten V1- und V2-Artefakte benötigt.
