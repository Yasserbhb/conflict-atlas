import pathlib
import sys

# make `conflict_updater` importable when pytest runs from anywhere
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
