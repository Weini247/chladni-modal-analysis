# V3 · Protokoll vor den Vergleichsläufen

V3 basiert auf `9c202ed85e6b9a530fb8e65d806c84805cb56117`. `main` und `forschung-v2` bleiben erhalten. Neue Ergebnisse liegen unter `ausgaben/privat/v3`. Die Originale werden ausschließlich gelesen.

## Arbeitspakete

1. V2 nachrechnen, Rohdaten und Branches vergleichen.
2. Drei Serien auf Bildrobustheit prüfen und eine Stichprobe für verblindete Annotationen festlegen.
3. Bild-, Such- und Modellannahmen getrennt variieren. V2-Akzeptanzschwellen einfrieren.
4. Lokalen Explorer mit Atlas, Modenlabor, Inversion, Annotation und Gap-Vergleich fertigstellen.
5. Figuren, englische README, Tests und Datenintegrität auditieren.

## Bildrobustheit

Alle Vollfotos aus Bilder 4120, 2030 und 3720. Frequenzpaarungen folgen direkt benachbarten verfügbaren Anzeigen. Mehrfachbeobachtungen werden paarweise ausgewertet und je Frequenzschritt mit dem Median der Abstände zusammengefasst. Die Zuordnung gleicher Frequenz und die Aufnahmefolge sind getrennte Datensätze. Primär sind der symmetrische mittlere Abstand der Skelette im gemeinsamen sichtbaren Plattenraum und der Flächenanteil. Robust ist der stärkste Übergang, wenn dieselbe Paarung unter allen Varianten maximal bleibt. Analysestörungen sind gepaarte Neuberechnungen derselben Originale. Unabhängige Aufnahmen bei gleicher Frequenz werden separat gezählt.

Die festen Varianten behandeln Schwelle, Licht, Kontrast, RGB-Farbe, einen örtlichen Schatten, eine örtliche Reflexion, eine asymmetrische Eckstörung, Schraubenzentrum und Maskengröße, Morphologie und zwei alternative Skelettalgorithmen. Die Operationsgrößen stehen in `konfiguration/v3.json`. Die Auflösung bleibt mit 512 Pixeln gleich.

Für die verblindete Stichprobe werden die erste, mittlere und letzte *verschiedene* Frequenz jeder Serie mit lexikografisch erster Foto-ID bei Wiederholungen gewählt. Historische oder automatisch erzeugte Masken werden beim Annotieren standardmäßig ausgeblendet. Menschlich unabhängige Bildvalidierung ist BLOCKED, bis entsprechende Annotationen vorliegen.

## Modell–Experiment-Vergleich

Primär sind Zahl und Prüfdistanzen der sieben 3720er-Originale beim eingefrorenen V2-Kriterium: Testdistanz ≤ 0,020 a und Abstand zur nächsten der fünf ausgewiesenen Alternativen ≥ 0,0015 a. Katalogwechsel verändern die Konkurrenzmenge. Dieselbe Grenze dient dort nur als deskriptive Schwellenprobe. Die Schwellen werden anhand realer Aufnahmen nicht neu geschätzt.

- **H1** Randbedingung. Freie Platte, Punktbedingung, Federfläche und Anschlussvarianten getrennt betrachten. Kandidatenzahlen explizit berichten.
- **H2** Parameter. Je ein Anschlussparameter wird variiert: vertikale Steifigkeit ×0,5 oder ×2, Radius ×1,5, Basisgrad 20→24. Für freie Kanten ist reine Materialskalierung bei konstanter Poissonzahl ein Invarianztest der Modellgeometrie.
- **H3/H4** Beobachtung. Ideal, verbreitert/diffus, unterbrochen und versetzt werden auf denselben synthetischen Feldern verglichen. Reale Varianten aus der Bildstudie begrenzen den Einfluss der Bildverarbeitung. Die synthetischen Störungen sind Beobachtungsproxies.
- **H5/H6** Inversion. Einzelmoden und Superpositionen sowie unabhängige Fit- und Prüfflächen. Alternative tolerante F1-Überdeckung in zwei Rasterpixeln, mit separat berichtetem Rang und ohne alte Akzeptanzgrenze. Die beiden anderen Serien liefern Transferdiagnostik ohne Modenlabels.
- **Neue synthetische Kontrolle.** Fester Seed, höherer Referenzgrad 24, Projektion des Referenzeigenraums auf den V2-Suchraum Grad 20. Top-k gegen zufällige eindeutige Familien des jeweils auswertbaren Katalogs. Zusätzliche Nichtmodellkonturen. Identische Rastermasken aus verschiedenen Modellfamilien zählen als direkt sichtbare Mehrdeutigkeit.

Offene mechanische Größen werden nicht aus den Fotos ergänzt. Anregungsantwort, Sandtransport und tatsächliche Kontaktparameter bleiben experimentell zu bestimmen.
