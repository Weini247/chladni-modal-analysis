"""Zentraler Runner. Fehlt eine Prüfung oder wird eine übersprungen, schlägt der Lauf fehl."""
import argparse
from pathlib import Path
import unittest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("all", "unit", "wissenschaft"), default="all")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    suite = unittest.TestSuite()
    for scope, ordner, muster, anzahl in (("unit", "tests", "test*.py", 20),
                                         ("wissenschaft", "wissenschaft", "val*.py", 16)):
        if args.scope not in ("all", scope):
            continue
        gruppe = unittest.defaultTestLoader.discover(str(root/ordner), pattern=muster, top_level_dir=str(root))
        if gruppe.countTestCases() != anzahl:
            print(f"{scope}: {gruppe.countTestCases()} Prüfungen gefunden, {anzahl} erwartet.")
            return 2
        suite.addTests(gruppe)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return int(not result.wasSuccessful() or bool(result.skipped))


if __name__ == "__main__":
    raise SystemExit(main())
