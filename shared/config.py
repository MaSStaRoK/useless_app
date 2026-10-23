"""Application configuration."""

import json
import os
import sys
from pathlib import Path


def _config_paths() -> tuple[Path, ...]:
    if getattr(sys, "frozen", False):
        return (
            Path(sys.executable).resolve().parent / "config.json",
            Path(getattr(sys, "_MEIPASS")) / "config.json",
        )
    return (Path(__file__).resolve().parents[1] / "config.json",)


def load_config() -> str:
    values = {}
    for path in _config_paths():
        try:
            values = json.loads(path.read_text(encoding="utf-8"))
            break
        except (OSError, json.JSONDecodeError):
            continue
    repository = os.environ.get("GITHUB_UPDATE_REPOSITORY", values.get("github_repository", ""))
    return str(repository).strip()
