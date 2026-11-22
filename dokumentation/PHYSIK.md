# Historischer Stand, Plattenmodell und Konventionen

## GP2-Audit

Die Projektpläne (Januar/Februar 2024) sehen ein Experiment mit quadratischer Platte, zentralem Schwingungserreger, variablem Funktionsgenerator und blauem Sand vor. Die späteren Pläne skizzieren ±25 Hz in 2-Hz-Schritten und einen vorgesehenen 100-g-Sandauftrag. Durchführung, Sandmenge und Sweep-Protokoll sind damit nicht belegt. Die Einzelbilder und das Poster zeigen tatsächlich teilweise 1-Hz-Schritte. Daneben gibt es ein eigenständiges Saitenexperiment.

Die Gruppenposter (PDF-Versionen 2 und 3 sowie zwei PPTX-Stände) zeigen Serienaufnahmen, Frequenzdifferenzen und eine nahezu lineare Regression. Das Poster macht kenntlich, dass die gezeigte Simulation und die gezeigten Experimente verschiedene Muster darstellen. Die Textnotiz erwähnt Haftreibung, diffuse Linien, eine möglicherweise verbogene Platte und schlecht reproduzierbare starke Schwingungen. Bilddokumentation und enge Frequenzintervalle sind die tragfähigen Ausgangspunkte. Zur Reproduktion der historischen numerischen Übereinstimmung fehlen die Einzelzuordnung aller Indizes, die Fitprozedur und die originalen Tabellen bzw. Skripte. Die genannte Abweichung von etwa ±0,5 % ist eine historische Angabe. Durch nachträgliches Fitten der Dicke und Zuordnung nach Frequenz könnten Residuen klein werden, selbst wenn eine Randbedingung geometrisch ungeeignet ist.

| Größe | Herkunft und Status |
|---|---|
| Kantenlänge 0,18 m, Masse etwa 0,26 kg | Historische Angaben aus dem Arbeitsbrief. Keine unabhängige Ablesung aufgefunden. Das Poster verwendet Ortsachsen ungefähr bis ±0,09 m. |
| E = 69 GPa, ν = 0,35 | Historische Modellwerte aus dem Arbeitsbrief |
| ρ = 2700 kg/m³ | Rechenwert für ein Al-ähnliches Szenario. Legierung unbekannt. |
| h = 3 mm | Illustrativer Rechenwert aus 0,26 kg/(2700 kg/m³ · (0,18 m)²) ≈ 2,97 mm, gerundet. Historische Fitdicke unbekannt. |
| r = 6 mm, k = 2·10⁵ N/m | Illustrative Annahmen für die Federfläche. Schrauben- und Kontaktabmessungen sowie Impedanz unbekannt. |

## Gleichung, Einheiten und Modellhierarchie

Für eine homogene, isotrope dünne Platte gilt in SI

\[
D\nabla^4w+\rho h\,\partial_t^2w=q, \qquad D=\frac{Eh^3}{12(1-\nu^2)}.
\]

Physische Fläche \([0,a]^2\), Rechenkoordinaten \(x/a,y/a\in[0,1]\). In den Fotoansichten liegt der Ursprung oben links. \(x\) wächst nach rechts, \(y\) nach unten. Die Orientierung bezeichnet einen Bildrahmen. Sie bestimmt keine Materialachse. Für die Rangliste werden die acht Operationen der Quadratgruppe \(D_4\) explizit betrachtet. Frequenzen sind \(f=\omega/(2\pi)\) in Hz. Der Solver verwendet \(\Omega=\omega a^2\sqrt{\rho h/D}\) und \(\lambda=\Omega^2\).

- **M0, historische Produkte.** \(w=\cos(n\pi x/a)\cos(m\pi y/a)\), \(\omega=\sqrt{D/(\rho h)}(\pi/a)^2(n^2+m^2)\). Der Operator im Inneren erfüllt damit die Eigenwertgleichung. Die Formen haben an den entsprechend ausgerichteten Kanten \(\partial_nw=0\) sowie die zugehörige verschwindende effektive Querkraft, während \(M_{nn}=-D(w_{nn}+\nu w_{tt})\) im Allgemeinen von null verschieden bleibt. Das ist eine Steigungsbedingung und bildet die freien Außenkanten nicht ab. Am normierten Mittelpunkt tritt \(w(1/2,1/2)=0\) nur für bestimmte Paritäten auf. Basisraster und Ursprung beeinflussen die historische Modenauswahl. Der Code rekonstruiert den separierbaren Teil, der historische Fitablauf bleibt offen.
- **M1, Navier-Platte.** Vier einfach gelagerte Kanten \(w=M_{nn}=0\). Exakte Sinusprodukte mit \(n,m\ge1\), \(\Omega=\pi^2(n^2+m^2)\), bieten eine unabhängige Referenz für den numerischen Ritzraum. Der Ritzraum multipliziert Polynome mit \(4x(1-x)\) je Achse und nutzt die natürlichen Momentenbedingungen der Variationsformulierung.
- **M2, freie Kanten.** Tensorbasis orthonormierter verschobener Legendre-Polynome in \(H^2\). Die Biegeenergie verwendet \(w_{xx}v_{xx}+w_{yy}v_{yy}+\nu(w_{xx}v_{yy}+w_{yy}v_{xx})+2(1-\nu)w_{xy}v_{xy}\). Gauss–Legendre integriert die polynomialen Produkte. Außenkanten frei über natürliche Momenten-, Schub- und Eckbedingungen der schwachen Form. Freie Platte mit drei Starrkörpermoden. Eine zentrale translatorische Punktbedingung reduziert den Ansatzraum auf \(w(1/2,1/2)=0\) per Nullraumbasis und lässt zwei Starrkörperrotationen übrig. Die Federfläche ergänzt alternativ \(k a^2/D\) mal das Flächenmittel von \(wv\) auf der Kontaktkreisscheibe. Die Koppelsteifigkeit hebt die drei Starrkörperfreiheiten zu weichen Moden an. Diese Hypothesen decken freie Kanten und plausible Grenzfälle ab. Eine starr geklemmte endliche Fläche oder mitbewegte Aktuatormasse erfordert ein eigenes Modell.
- **M3, erzwungene Antwort.** In einem freien linearen Modell koppelt eine ideale zentrische Kraft proportional zu \(\phi_j(1/2,1/2)\), für eine symmetrische Kontaktfläche proportional zum entsprechenden Integral. Bei Punktfixierung ist gleichzeitige zentrische Punktkraft im homogenen Ansatzraum wirkungslos. Basisanregung benötigt eine inhomogene Bewegung am Anschluss oder ein gekoppeltes Modell. M3 ist bis zu gesicherten Angaben zu Anregung, Masse, Dämpfung und Kontakt zurückgestellt.

## Inverse Fragestellung

Der Ranglistenabstand mittelt die mittleren gerichteten euklidischen Abstände auf gemeinsamen sichtbaren Plattenpixeln. Er kann falsche Zusatzlinien bestrafen. Winkel werden in numerisch zweidimensionalen Eigenräumen mit 15° Schritt abgetastet. Vorzeichen, Gesamtamplitude und mehrere invariante Geometrien sind aus Nullstellen nicht identifizierbar. Überlagerungen verschiedener Frequenzen oder nicht in Phase schwingender Anteile erfordern ein dynamisches Modell. Der Abstand in Hz wird separat gespeichert. Die Arbeit behandelt fotografierte Anregungsfrequenz, Antwortmaximum und ungestörte Eigenfrequenz als unterschiedliche Größen.

Ohne unabhängige Kenntnis von \(E,\rho,h,a\) bestimmen Eigenfrequenzen für feste Randannahmen vor allem die Kombination \(\sqrt{E/[\rho(1-\nu^2)]}\,h/a^2\). Normierte Spektralverhältnisse helfen für \(\nu\) oder Randparameter, wenn Modenzuordnungen belastbar sind. Die beobachtete Sandverteilung hängt unter anderem von Beschleunigung, Reibung, Sandmenge und Anregungsvorgeschichte ab. Die Segmentierung liefert einen geometrischen Beobachtungskanal.

## Literatur

1. A. W. Leissa (1969), *Vibration of Plates*, NASA SP-160, Kap. 4. Benchmark-Konventionen und Referenz für freie und einfach gelagerte Platten. [NASA-Original](https://ntrs.nasa.gov/citations/19700009156)
2. S. J. D. D’Alessio (2021), *Forced free vibrations of a square plate*. Freie Außenkanten und zentrale Anregung als anderes physikalisches Problem als homogene Zentralfixierung. [Springer, DOI 10.1007/s42452-020-04062-6](https://link.springer.com/article/10.1007/s42452-020-04062-6)
3. P. H. Tuan et al. (2015), *Exploring the resonant vibration of thin plates*. Experimenteller Antwortvergleich mit zentrischem Oszillator und Prüfung von Zusatzmasse im dortigen Aufbau. [DOI 10.1121/1.4916704](https://doi.org/10.1121/1.4916704)
4. P. H. Tuan et al. (2015), *Resolving the formation of modern Chladni figures*. Experimenteller Vergleich mit definiertem Resonanzspektrum. [DOI 10.1209/0295-5075/111/64004](https://doi.org/10.1209/0295-5075/111/64004)
5. P. H. Tuan et al. (2018), *Point-driven modern Chladni figures with symmetry breaking*. Experiment und Modell zu Symmetriebruch und zentraler Anregung. [Scientific Reports](https://www.nature.com/articles/s41598-018-29244-6)
6. Y.-C. Tseng et al. (2021), *Exploiting Modern Chladni Plates to Analogously Manifest the Point Interaction*. Position der Anregung und Punktwechselwirkung in einem eigenen experimentellen System. [Applied Sciences](https://www.mdpi.com/2076-3417/11/21/10094)
7. P. H. Tuan et al. (2014), *Exploring the distinction between experimental resonant modes and theoretical eigenmodes*. Modenzerlegung für erzwungene Plattenantworten. [Physical Review E](https://journals.aps.org/pre/abstract/10.1103/PhysRevE.89.022911)

Analytische Ergebnisse sind bekannte Plattentheorie. Der numerische Benchmark reproduziert diese Theorie. Die quantitative Nachauswertung basiert auf dem lokalen GP2-Bestand. Die Auswahl der Literatur dient dem Modellkontext. Eine Originalitätsprüfung bleibt offen.
