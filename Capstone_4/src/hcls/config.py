"""Configuration loading. The project root is the folder that holds config.yaml."""

from __future__ import annotations

import datetime as dt
import functools
from pathlib import Path

import yaml


def project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config.yaml").exists():
            return parent
    raise FileNotFoundError("config.yaml not found above " + str(here))


@functools.lru_cache(maxsize=1)
def load_config() -> dict:
    with open(project_root() / "config.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def as_of_date() -> dt.date:
    return dt.date.fromisoformat(str(load_config()["as_of_date"]))


def path(key: str) -> Path:
    """Absolute path for a key under `paths:` in config.yaml."""
    return project_root() / load_config()["paths"][key]


def outputs_dir(*parts: str) -> Path:
    p = path("outputs").joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def docs_dir(*parts: str) -> Path:
    p = project_root().joinpath("docs", *parts)
    p.mkdir(parents=True, exist_ok=True)
    return p
