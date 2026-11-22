# V3 · Reproduktion

## Öffentlicher Snapshot ohne GP2-Daten

Python 3.12 in einer eigenen virtuellen Umgebung verwenden. Die Befehle aus der Projektwurzel ausführen.

```sh
python -m pip install -r requirements-lock.txt
python -m chladni.checks --scope all
python -m chladni.forschung_v3 showcase
python -m werkzeuge.v3_modellpaket
```

Die Tests umfassen analytische Eigenwerte, Residuen, Unterraumvergleiche, synthetische Bildverarbeitung und Inversion. Das Modellpaket verwendet die V2-Modellparameter sowie den festgelegten V3-Seed und die gleichen Kriterien für die synthetische Benchmark-Auswertung. Es schreibt `mechanik.json`, `synthetik.json` und beide Abbildungen in PNG, SVG und PDF unter `ausgaben/privat/modellpaket`. Mit `--ziel` lässt sich ein anderer Ausgabeordner wählen. Die Titelgrafik ist eine numerische Simulation.

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
