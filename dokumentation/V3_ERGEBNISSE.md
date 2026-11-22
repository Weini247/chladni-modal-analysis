
# Chladni V3 · Befunde und Qualitätsaudit

## Unabhängiger Eingangsabgleich

Ausgang ist `9c202ed85e6b9a530fb8e65d806c84805cb56117`. V1 liegt auf `main` bei `fb85daa`. Die V2-Neuberechnung in getrennten Zielordnern ergab **28/28 bytegleiche Artefakte**, darunter sieben Figuren in je drei Formaten. Der V2-Laufaudit und der Starttest des ursprünglichen Tk-Explorers bestanden. Die V2-Testgruppe bestand 26/26 Prüfungen. Der Archivstand umfasst 297 Quellen, 284 dekodierte Bilder, 168 vollständige Aufnahmen, 24 Reihen und 146 Frequenznachbarpaare.

In einem direkten V1-Eingangslauf wurden acht Pilotregistrierungen und Masken aus Originaldaten neu berechnet. Die betroffenen archivierten Zahlen und Segmentierungsraster stimmten exakt überein. Die 168 Frequenzentscheidungen wurden aus den Belegen reproduziert. Darunter sind 163 manuelle Ablesungen, vier unbekannte Angaben und ein Konflikt. Der größte relative Navier-Eigenwertfehler betrug 3,89×10⁻¹⁰ bei der festgelegten Schranke 2×10⁻⁷.

| Prüfung | Aussage und Grenze |
| --- | --- |
| Navier, freie Literaturplatte | Analytische und extern tabellierte Referenzen prüfen ausgewählte Eigenwerte unter idealisierten Randbedingungen. Der maximale absolute Fehler der dimensionslosen Frequenzparameter der Literaturplatte beträgt 0,00386. Die Solverresiduen prüfen algebraische Konsistenz und Orthogonalität. Konvergenz bei steigendem Ansatzgrad wird separat beurteilt. |
| Entartung und Spektralschnitt | Der Rechenweg erweitert den Ausschnitt bei einem abgeschnittenen Cluster. Hauptwinkel und Projektorüberlapp vergleichen fast entartete Unterräume. Ein Eigenvektor innerhalb eines solchen Raums hängt von der Basiswahl ab. |
| Bildvergleich G0 | Die registrierten Rechtecke und Referenzmasken prüfen Wiederholbarkeit. Die Maskenreferenz stammt aus einem maschinellen Farbverfahren und teilt Annahmen mit dem untersuchten Verfahren. Sensorfehler und wahre Sandpixel sind dadurch nicht unabhängig kalibriert. |
| Frequenz und Unsicherheit | Frequenzstatus dokumentiert die Quelle und mögliche Konflikte einer Ablesung. Die Auflösung der Anzeige und die Stabilität der Anregung sind getrennte experimentelle Fragen. Algorithmische Bereiche beschreiben Änderungen am Auswerteweg. |
| Synthetische Inversion | V2 fand 56/56 bekannte Familien unter den ersten sechs, 6/28 Mischfälle auf Rang 1 und eine falsche Familie unter zehn angenommenen Fällen. Die Formannahmen des Generators und des Katalogs sind verwandt. Disjunkte Bildstreifen begrenzen räumliche Überanpassung innerhalb einer Aufnahme und ersetzen keine unabhängigen Experimente. |
| Start, Export und Hashes | Automatisierte Smoke- und Integritätstests belegen Ausführbarkeit, Stabilität und die Dateiintegrität des geprüften Archivs. |

## G1 · Bildgeometrie und Frequenzreihen

Die vorab festgelegten 22 Einstellungen erzeugen je 22 Auswertungen für dieselben 22 Aufnahmen. Der Test umfasst Farbtrennung, Licht, Kontrast, lokale Abschattung und Reflexion, Perspektive, Schraubenzentrum und Maskenradius, Linienbreite, Morphologie sowie drei Skelettmethoden. Der symmetrische mittlere Linienabstand und die 95. Distanzperzentile werden innerhalb des gemeinsam sichtbaren Gebiets in Anteilen der Plattenseite gemessen. Die Maßzahl des Flächenanteils bezieht sich auf die sichtbaren Pixel. Frequenzschritte berücksichtigen vorhandene Anzeigen und bewahren Mehrfachaufnahmen. Die Aufnahmefolge steht separat in `bildstudie.json`.

| Reihe | Aufnahmen | Größter benachbarter Wechsel | Position des Sandflächenminimums |
| --- | ---: | --- | --- |
| 2090–2096 Hz | 7 | **2093→2094 Hz in 22/22 Einstellungen**, 2,11 % der Plattenseite im Basislauf, Bereich 1,85–4,69 % | 2093 Hz in 12/22, 2092 Hz in 10/22 |
| 4122–4128 Hz | 8 | 4123→4124 Hz in 20/22, 4125→4126 Hz in 2/22 | 4125 Hz in 22/22 |
| 3720–3726 Hz | 7 | 3722→3723 Hz in 18/22, 3723→3724 Hz in 4/22 | 3726 Hz in 17/22, 3724 Hz in 5/22 |

Bei gleicher Anzeige liegen getrennte Aufnahmen für 4124 und 3722 Hz vor. Ihre Abstände im Basislauf betragen 0,24 % beziehungsweise 0,61 % der Plattenseite. Unabhängige Neustarts der Versuchsanordnung sind dabei nicht belegt. In der Reihe 2090–2096 Hz liegt keine gleichfrequente Wiederholungsaufnahme vor. Ein Abdeckungsminimum oder ein bildgeometrischer Sprung lokalisiert die Bildänderung. Eine mechanische Resonanz erfordert eine Frequenzgangmessung. Die Unsicherheitsbereiche der Tabelle gelten für die Auswertung derselben Bilder.

Die Annotationstichprobe enthält neun vorab ausgewählte Bilder. Pro Reihe gehen die erste, mittlere und letzte unterschiedliche Frequenz ein. Mehrfachaufnahmen werden nach Foto-ID aufgelöst. Im Browser lassen sich Ecken korrigieren und Sand, blankes Metall, Unklarheit und Linienkandidaten markieren. Revisionen enthalten Bearbeiter-ID, Herkunft, Elternrevision, Quell-Hash und Koordinatensystem. Der Vergleich projiziert B über das gemeinsame Originalbild auf A. IoU, Präzision und Recall verwenden nur gemeinsam eindeutig beschriftete Pixel, Linienabstände nur den nicht als unklar markierten Bereich. Herkunft und Verblindung werden selbst angegeben. Menschlich unabhängig bestätigte Referenz und daraus abgeleitete Segmentierungsgenauigkeit bleiben **BLOCKED**.

## G2 · Modell–Experiment-Lücke

Die V2-Entscheidung verlangt einen Prüfabstand ≤2,00 % der Plattenseite und einen Mindestabstand von 0,15 % zur nächsten ausgewiesenen Familie. Die Prüfdistanz wird in Streifen berechnet, die bei der Rangbildung zurückgehalten werden. Dadurch bleibt jede Foto-Inversion räumlich geprüft, bei gemeinsamen Aufnahme- und Modellannahmen. V3 verwendet dieselben Grenzen. Bei verändertem Katalog sind sie eine deskriptive Schwellenprobe. Die F1-Variante erhält keine Akzeptanzgrenze.

Der volle Katalog enthält **2.694 Hypothesen in 119 Familien**. Für alle sieben Kontrollaufnahmen liegt die erste Familie im Basislauf zwischen **2,986 und 3,296 %** der Plattenseite, Median **3,150 %**. Damit scheitern alle am Distanzkriterium. Die Kandidatenklasse wechselt bei 42 der 154 bildbezogenen Auswertungen der Kontrollreihe gegenüber der jeweiligen Basis. Keine der 154 Auswertungen erfüllt die Akzeptanzregel. Die kleinste Kontroll-Prüfdistanz über diese Einstellungen beträgt **2,923 %**. Diese Auswertungen behalten sieben unabhängige Foto-IDs als Bezugsgröße. Zwei weitere Serien liefern Transferdiagnostik für 15 Fotos. Auch dabei greift die Regel in keiner der 330 Auswertungen. Wahre experimentelle Familien sind für alle drei Serien unbekannt.

| Hypothese | Quantitativer Befund | Offener Anteil |
| --- | --- | --- |
| **H1 Randbedingungen** | Frei, Punktzwang, Federfläche und verteilter Anschluss ergeben 0/7. Die Mediane reichen von 3,66 bis 4,19 % für diese vier Kataloge. Das historische Kosinusmodell liegt bei 3,15 %. | Erzwungene, gedämpfte Antwort und reale Kopplung wurden nicht gemessen. Der geometrische Rang kalibriert keinen Anschluss. |
| **H2 Modellparameter** | Anschlussgrad 24, vertikale Steifigkeit ×0,5/×2 und Radius ×1,5 ergeben 0/7 bei Medianen von 3,68–4,19 %. Bei der freien Platte ergibt E×1,21 einen Frequenzfaktor 1,10 bei Projektorüberlapp über 0,999999999999. Im bereits geprüften V2-Anschlussmodell verändert 10 % mehr Dicke die gemittelten Clusterfrequenzen um bis zu 10,86 %. Ohne Zusatzmasse sinkt der kleinste Überlapp passend dimensionierter Cluster auf 0,781. | Die Materialinvarianz gilt für die homogene freie Platte bei fester Poissonzahl. Die Anschlussrechnungen sind parametrische Szenarien und liefern keine Messwerte für reale Kontaktgrößen. |
| **H3 Sanddynamik** | Diffuse synthetische Paare reduzieren Top 6 von 16/16 auf 15/16 und Top 1 von 7/16 auf 5/16. Die registrierungsverschobene diffuse Variante reduziert die Annahmen beim Paar von vier auf zwei. | Die Störungen bilden plausible Beobachtungsfehler ab. Es fehlen Messungen von Partikeltransport, Anregung und Oberflächenbeschleunigung. |
| **H4 Bildverarbeitung** | 42 Familienwechsel in 154 kontrollierten Reextraktionen bei 0/154 Akzeptanzen und ≥2,923 % Prüfdistanz. | Größere, kombinierte oder systematische Bildfehler sowie mechanische Effekte außerhalb der Proxies wurden nicht getestet. |
| **H5 Modenüberlagerung** | Beim idealen synthetischen Paar steigert der volle Ansatz den Top-6-Treffer von 12/16 auf 16/16 gegenüber Einzelhypothesen. Im realen Satz liefern beide 0/7 bei 3,15 % Median. | Frequenznahe Paare mit statischen reellen Gewichten testen einen Teil möglicher stationärer Überlagerungen. Ein erzwungenes komplexes Feld kann mehr Anteile enthalten. |
| **H6 Metrik und Kandidatenraum** | F1 aus wechselseitiger Linienüberdeckung bei zwei Pixeln Toleranz im 64er-Raster erreicht bei idealen Paaren Top 6 von 16/16 und Top 1 von 3/16 gegenüber 7/16 für V2-Distanz. Die Rangwirkung hängt von der Beobachtungsstörung ab. 62 Rastermasken sind exakt familienübergreifend identisch. | Für F1 gibt es keine externe Kalibrierung. Fehlende Familien und uneindeutige Geometrie können auch bei guter Pixelmessung bestehen. |

### Synthetische Trennschärfe und Abstention

Mit Seed 922671 werden 16 Einzel- und 16 Paarfelder aus Grad 24, Orientierung und Paarwinkel variiert, mit 16 Negativkonturen ergänzt. Die Grad-24-Labels werden über Projektorüberlapp ≥0,98 auf zulässige Grad-20-Familien abgebildet. Daraus folgt eine Prüfung von Störung und Numerik **innerhalb** der modellierten Familien. Die enthaltenen Familien repräsentieren keine Stichprobe realer Apparaturen. Diffuse Bandbreite plus Streukörner, Unterbrechungen und Versatz nutzen dieselben Grundfelder. Die Versatzvariante verwendet das diffuse Band.

| Störung / V2-Distanz | Top 1, Einzel + Paar | Top 6, Einzel + Paar | Annahmen / 32 | Falsche Familien unter Annahmen |
| --- | ---: | ---: | ---: | ---: |
| Ideal | 12 | 32 | 5 | 1 |
| Diffuses Band | 10 | 31 | 5 | 1 |
| Unterbrechung | 12 | 32 | 5 | 1 |
| Versatz | 11 | 32 | 2 | 1 |

Für zufälliges Ranking mit gleichverteilten unterschiedlichen Familien beträgt die erwartete Treffermenge je Zustand 32/119 = 0,269 für Top 1 und 192/119 = 1,613 für Top 6. Der eingeschränkte Einzelkatalog besitzt 114 Klassen. Darin fehlen zwei wahre Paarlabels. Deshalb gehen dort 14 Paarfälle in die Zufallserwartung ein. Diese Referenz beschreibt den Katalog und kein Wahrscheinlichkeitsmodell für GP2. Die Negativkontrolle liefert 0/16 falsche Annahmen pro Beobachtungszustand. Das 95-%-Wilson-Intervall je Zustand reicht bis rund 19,4 %. Die vier Zustände teilen Grundfelder, weshalb gepoolte Konfidenzintervalle oder ein behaupteter kleiner experimenteller Fehleranteil unzulässig wären.

### Identifizierbarkeit

Für das statische Feld w ist Z(w) = {x | w(x)=0}. Für jedes c≠0 gilt Z(cw)=Z(w). Damit sind globales Vorzeichen und Amplitude aus Z unbestimmbar. Im harmonischen Feld
`w(x,t) = Σ Aⱼ φⱼ(x) cos(ωⱼt + θⱼ)` enthält eine stationäre Sandspur keinen Zeitstempel für die einzelnen Phasen. Bei einem entarteten Eigenraum sind orthogonale Basistransformationen möglich. Sie ändern die Komponentenkoeffizienten, wenn dasselbe Raumfeld beschrieben wird. Die Quadratgruppe D₄ bildet zusätzliche Äquivalenzen, wenn die absolute Orientierung fehlt. Rasterung, Schraubenausschluss und diffuse Linien können weitere Klassen zusammenführen. Über alle Hypothesen wurden 1.438 verschiedene sichtbare Rastermasken gefunden, davon 62 mit mindestens zwei Familien. Entsprechende Klassen bleiben aus dieser Darstellung prinzipiell mehrdeutig, auch bei idealer Beobachtung.

Ein Eigenwertproblem beschreibt freie Schwingungen eines angenommenen Modells. Das fotografierte Experiment wird angetrieben. Im Frequenzraum hängen Form und Phase der Antwort von einer Lastverteilung sowie Masse, Steifigkeit und Dämpfung ab. Die Verteilung von Sand hängt zusätzlich von der Körnerdynamik ab. Studien an erzwungenen Platten und beobachtete Antiknoten-Anhäufung unter bestimmten Beschleunigungsbedingungen begründen diese offenen Hypothesen. Sie belegen das Regime der GP2-Aufnahmen nicht. [Tuan et al.](https://journals.aps.org/pre/abstract/10.1103/PhysRevE.89.022911) · [van Gerner et al.](https://doi.org/10.1103/PhysRevE.82.012301)

## Bewertung

- **V3-G1 bestanden** für reproduzierbare Auswertung und Empfindlichkeitsbericht. Unabhängige menschliche Referenz **BLOCKED**.
- **V3-G2 bestanden** als quantitatives Negativresultat mit festgehaltenen offenen Hypothesen. Mechanische Modenzuordnung und experimentelle Kalibrierung bleiben offen.
- Die Abbildungsexporte und die anonyme, simulationsbasierte Titelgrafik sind lokal vorbereitet. Vor einer Veröffentlichung von Gruppenmaterial stehen Rechteklärung und individuelle Quellenattribution aus.
