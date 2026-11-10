"""Load the search profile (profile.yaml or profile.example.yaml)."""
from pathlib import Path

import yaml


def load_profile(path) -> dict:
    with open(Path(path), encoding="utf-8") as f:
        return yaml.safe_load(f)
