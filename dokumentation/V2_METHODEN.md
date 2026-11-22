# V2 · Methoden, Konventionen und Grenzen

## Lage und Bildobservablen

Alle Bildkoordinaten sind \(x/a,y/a\), positiv nach rechts und nach unten. Die Serienanalyse verwendet die Schnittmenge der gültigen Bildpixel. Sandbedeckung ist der Anteil der sichtbaren Fläche mit Blauüberschuss oberhalb der expliziten V1-Schwelle. Die Flächenschwelle quantifiziert das beobachtete Farbmuster. Eine Rückrechnung auf Sandmasse oder Auslenkung ist ohne photometrisches bzw. partikelmechanisches Modell offen.

Die Ausgangsregistrierung verwendet vier Plattenecken, Kontrollpunkte und eine Schraubenmaske. Für die Zweitserie markiert eine separate, maschinell-visuelle Sichtung die Ecken und den Schraubenpunkt in einem 1000×750-Pixel-Bildrahmen. Das Gitter in 25 Innenpunkten quantifiziert die Differenz der Homographien in \(a\). Hue \(0{,}49\dots0{,}72\) und Sättigung ≥ 0,34 definieren klare blaue Pixel, Sättigung ≤ 0,12 oder andere Farbwinkel klares Metall. Diffuse, dunkle und mehrdeutige Übergänge können unklassifiziert bleiben. Die alternative Vollmaske nutzt eine schwächere Schwelle (0,24) mit Medianfilter. Beide sind maschinelle Farbkriterien auf denselben physikalischen Fotos.

Die Dichte wird in 4×4 gleich großen Plattenzellen und radial in normierten Ringen angegeben. Die topologischen Kennzahlen beziehen sich auf binäre Rasterkomponenten, Endpixel, Verzweigungscluster und eingeschlossene Hintergrundregionen. Skelett- und Topologiewerte sind vom Raster, der Dicke diffuser Ablagerungen und den Ausschlussmasken abhängig. Die acht D4-Werte sind Jaccard-Überlappungen mit der jeweils transformierten Maske im gemeinsamen Sichtbereich. Sie liefern Bildsymmetrieindikatoren.

Frequenznachbarschaften verbinden benachbarte vorhandene Ablesungen derselben Reihe bei Abstand bis 2 Hz. Tatsächliche Aufnahmezeit, Abstände und Wiederholungen stehen in getrennten Tabellen. Insbesondere folgen die Bilder der Zweitserie nicht in aufsteigender Frequenzordnung. Wegen dieser Reihenfolge und unbekannter Sandvorgeschichte lässt sich der Sprung im Linienmaß nicht direkt als Hysterese oder Resonanz deuten.

## Plattenmodelle und Einheiten

Die mechanische Basis ist die Kirchhoff–Love-Biegeenergie homogener isotroper Platten. Die ausführliche Herleitung und V1-Ergebnisse bleiben in [Physik](PHYSIK.md). Die Modelle bleiben getrennt:

- **M0** nutzt historische Kosinusprodukte als Bildbaseline mit symmetrisch eindeutigen Indexpaaren \(n\le m\). Ihre Randsteigung verschwindet und die Außenmomente haben im Allgemeinen einen endlichen Wert.
- **M1** nutzt einfach gelagerte Navier-Ränder. Die exakten Sinusformen und Frequenzen \(\Omega=\pi^2(n^2+m^2)\) dienen zum Benchmarking.
- **M2** umfasst freie Ränder, ideal zentrisch unterbundene Translation, eine verteilte vertikale Federfläche und eine Federfläche mit Rotationswiderstand und verteiltem Mitträger. Positiv definite Kontaktmatrizen ermöglichen die reziproke Lösung \(M v=\mu K v\), \(\lambda=\mu^{-1}\), mit Rücknormierung auf \(v^\mathsf{T} M v=1\). Bei freien Rändern und der Punktbedingung werden erwartete Starrkörpermoden separat behandelt.
- **M3** bleibt BLOCKED für die Rekonstruktion erzwungener GP2-Antworten. Kräfte, Kontaktimpedanz und Dämpfung sind ungemessen. Die zeitliche Animation zeigt eine normierte Eigenform mit \(\cos(\omega t)\) als Illustration.

Für die isotrope Platte gelten \(D=Eh^3/[12(1-\nu^2)]\), \(\Omega=\omega a^2\sqrt{\rho h/D}\), \(\lambda=\Omega^2\) und \(f=\omega/(2\pi)\). Für die Kontaktkreisscheibe \(A_c\) steht \(\langle\cdot\rangle_c\) für Flächenmittel. V2 ergänzt im normierten Ritzproblem die Formen
\[
 K_c(u,v)=\frac{k a^2}{D}\langle u v\rangle_c+
          \frac{k_\theta}{D}\langle\nabla u\cdot\nabla v\rangle_c,\qquad
 M_c(u,v)=\frac{m_c}{\rho h a^2}\langle u v\rangle_c.
\]
Hier ist \(k\) in N/m, \(k_\theta\) in N·m, \(m_c\) in kg, \(\nabla\) bezogen auf dimensionslose Plattenkoordinaten und \(r_c\) in Metern angegeben. Die verteilte Masse folgt lokal dem Plattenfeld. Ein starres Anbauteil mit eigenen Freiheitsgraden oder dynamischer Impedanz wäre ein anderes Problem. Die Parameter \(h=3\) mm, \(r_c=6\) mm, \(k=200000\) N/m, \(k_\theta=1,5\) N·m und \(m_c=18\) g definieren eine illustrative Rechnung. Das Messarchiv liefert keinen unabhängigen Fit für diese Parameter.

Für freie Ränder bestimmt eine absolute Frequenzskala im Wesentlichen die Kombination \(h\sqrt{E/\{\rho(1-\nu^2)\}}/a^2\). Eine Fotoserie mit Anregungswerten ohne Eigenmodenlabels und Antwortmessungen trennt diese Parameter und die Kontaktterme nicht. Die Studie variiert Einflussgrößen einzeln und interpretiert Ergebnisse als Szenarien.

Schnitte des Spektrums berücksichtigen Wächtermoden und vervollständigen Gruppen am Rand. Gruppen der Frequenzen innerhalb 0,5 % vom ersten Gruppenwert werden über die orthonormalisierten Felder auf einem festen Vergleichsraster gepaart. Die Zuordnung maximiert die Projektorüberlappung über die Kandidaten, wobei ein Dimensionswechsel die Überlappung absenkt. Hauptwinkel werden aus Singulärwerten berechnet. Rasterüberlappungen ersetzen keine Normabschätzung des kontinuierlichen Biharmonischen Operators. Die Tabellen zeigen je Modell die ersten 30 positiven Frequenzen einschließlich eines gegebenenfalls verlängerten Endclusters.

Der Literaturvergleich reproduziert die erste Fünfergruppe von Huang, Leissa und Liao, Tab. 1, bei \(\nu=0{,}30\). Die Tabellenwerte haben zwei Nachkommastellen, daher beträgt die Vergleichstoleranz 0,005 dimensionslos. [Primärquelle der freien Platte](https://ir.lib.nycu.edu.tw/bitstream/11536/8502/1/000259156600003.pdf)

## Inverse Rekonstruktion

Das Beobachtungsmodell vergleicht Kandidaten von Sandlinien mit den projizierten Nullstellen einer normierten reellen Modellform. Es beinhaltet keine allgemeine Sandtransportgleichung. Die Bibliothek enthält M0 und vier M2-Modelle. Theorien werden unter den acht D4-Transformationen der quadratischen Platte betrachtet. M0 dient als Einzelmodenbaseline. M2 erlaubt zusätzlich zwei Moden derselben mechanischen Variante, wenn ihre berechneten Frequenzen höchstens 2,5 % auseinanderliegen. Normierte Koeffizienten \((\cos\theta,\sin\theta)\) werden auf einem 20°-Gitter untersucht. Vorzeichen und Betrag der Auslenkung sind aus den Sandlinien nicht bestimmt. Bei mehreren Moden ist \(\theta\) basisabhängig und kein gemessener Phasenwinkel.

Auf einem 64×64-Raster werden Bildbereiche durch disjunkte schräge Streifen in Anpassungs- und Prüfflächen aufgeteilt. Der Anpassungsbereich ordnet Modelle und wählt Orientierung sowie Winkel je Familie. Der Prüfabschnitt bewertet die eingefrorenen Kandidaten. Die beiden gerichteten Linienabstände sind bei 0,08 \(a\) gekappt, symmetrisch gemittelt und schraubenfrei. Im gerichteten Abstand Bild→Modell bleibt das analytische Linienfeld im jeweiligen Streifen verfügbar. Modell→Bild normiert nur theoretische Punkte im sichtbaren Ausschnitt. Die Abstände sind damit eine explizite, asymmetrisch beobachtete Zensierung im symmetrisch gemittelten Score. Lokale Verdeckungen, bei denen theoretische Linien knapp hinter einer Maske liegen, bleiben eine Grenze. Die Zusatzstrafe für eine zweite Komponente beträgt 0,0025 \(a\), weniger als ein Rasterpixel. Null, Standardwert und Verdopplung prüfen die Regularisierung. Segmentschwellen ±0,02 werden zusätzlich in der zurückgehaltenen realen Kontrollserie variiert.

Der beste Kandidat wird nur relativ zu den Kataloghypothesen beurteilt. Die Regel begrenzt den Prüfabstand und verlangt Abstand zu den Alternativen unter den sechs nach Anpassungsfehler besten Familien. Familien werden anhand von Modellname und Frequenzcluster definiert. Symmetrieäquivalenzen sind bei der Orientierungssuche eingebaut. Die Frequenzkompatibilität ist ein separat gespeicherter Abstand der Fotoanzeige vom theoretischen Frequenzintervall. Sie verändert die geometrische Rangfolge nicht. Ein Vergleich mit dynamischer Antwort ist später separat möglich. [Primärquelle zum Unterschied zwischen Eigen- und Antwortformen](https://journals.aps.org/pre/abstract/10.1103/PhysRevE.89.022911)

### Fehlakzeptanz und Gültigkeitsbereich

Kalibrations- und Prüfensemble verwenden getrennte Seeds und je 28 Einzelmoden-, 28 Mischungs- und 28 Nichtmodellfälle. Muster werden auf doppelter Rasterauflösung generiert, unter anderem mit beliebigen D4-Orientierungen, variierenden Mischungswinkeln, verbreiterten Linien, Pixelstörungen, fehlenden Stücken, Verdeckung und Zusatzsegmenten. Die Nichtmodellfälle verwenden zusammengesetzte Ellipsenkonturen. Die Kataloggröße gilt auch bei der Kalibration und ist damit in die empirische Mehrfachsuche einbezogen. Die Datensätze sind unabhängig generierte Renderings derselben Modellfamilien. Sie decken keine beliebigen Bildartefakte und keinen Verteilungswechsel zum echten Versuchsaufbau ab.

Der Kalibrationslauf durchsucht ein diskretes Schwellenraster und verlangt maximal eine Fehlakzeptanz pro Nichtmodellklasse und maximal eine falsch akzeptierte Modellfamilie insgesamt. Der unabhängige Lauf berichtet Ränge, Akzeptanz, richtige Zuordnung und Wilson-Spannen der Akzeptanzquote. Mehrere Varianten desselben Basismodus können statistisch ähnlich sein. Wilson-Spannen sind deskriptiv für die erzeugte Kontrollstichprobe. Die Aussage einer bestätigten experimentellen Eigenfamilie bleibt OPEN. Ein Kandidat im geometrischen Beobachtungsmodell kann im wissenschaftlichen Vergleich dennoch nützlich sein.
