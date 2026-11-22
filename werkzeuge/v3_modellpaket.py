"""Erzeuge numerische Validierungsfiguren ohne Zugriff auf das GP2-Archiv."""
from argparse import ArgumentParser
from pathlib import Path

import matplotlib.pyplot as plt

from chladni.abbildungen import stil
from chladni.auswertung import PROJEKT, lese_json
from chladni.eigenmoden import Platte
from chladni.figuren_v3 import _mechanik, _synthetik
from chladni.invers_v3 import _synthetisch
from chladni.inverse_modelle import InversParameter, Katalog
from chladni.plattenmechanik import Anschluss, modellstudie
from chladni.provenienz import json_schreiben


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--ziel", type=Path, default=PROJEKT/"ausgaben/privat/modellpaket")
    args = parser.parse_args()
    settings = lese_json(PROJEKT/"konfiguration/v2.json")
    criteria = lese_json(PROJEKT/"konfiguration/v3.json")["gap"]
    plate = Platte(**settings["platte"])
    contact = Anschluss(**settings["anschluss"])
    args.ziel.mkdir(parents=True, exist_ok=True)
    mechanics = modellstudie(args.ziel, plate, contact)
    if not mechanics["benchmark"]["bestanden"]:
        raise SystemExit("Freie-Platte-Benchmark fehlgeschlagen.")
    catalogue = Katalog(plate, contact, InversParameter(**settings["invers"]))
    synthetic = {"synthetisch": _synthetisch(catalogue, plate, contact, criteria)}
    json_schreiben(args.ziel/"synthetik.json", synthetic)
    with plt.rc_context(stil() | {"svg.hashsalt": "chladni-v3",
                                "axes.labelsize": 9,
                                "figure.facecolor": "#f7f9f8",
                                "axes.facecolor": "#f7f9f8"}):
        _mechanik(mechanics, args.ziel)
        _synthetik(synthetic, args.ziel)
    print(f"Numerische Ergebnisse und Abbildungen: {args.ziel}")


if __name__ == "__main__":
    main()
