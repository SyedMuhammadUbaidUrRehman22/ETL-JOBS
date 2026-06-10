"""
config.py — YAML configuration loader.

Responsibilities:
- Read config.yaml
- Validate required top-level sections
- Provide config as a dictionary
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


REQUIRED_SECTIONS = [
    "database",
    "scraping",
    "filters",
    "sources",
    "output",
]


class ConfigError(Exception):
    """Raised when config loading or validation fails."""


def load_config(config_path: str = "config.yaml") -> dict[str, Any]:
    """
    Load YAML config from disk.

    Args:
        config_path: Path to config.yaml.

    Returns:
        Config dictionary.

    Raises:
        ConfigError: If file is missing, invalid, or incomplete.
    """
    path = Path(config_path)

    if not path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        with path.open("r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML config: {config_path}") from exc

    if not isinstance(config, dict):
        raise ConfigError("Config file must contain a YAML dictionary/object")

    missing_sections = [
        section for section in REQUIRED_SECTIONS if section not in config
    ]

    if missing_sections:
        raise ConfigError(
            f"Config missing required sections: {', '.join(missing_sections)}"
        )

    return config


def get_enabled_sources(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    Return only enabled source configs.
    """
    sources = config.get("sources", {})

    return {
        source_name: source_config
        for source_name, source_config in sources.items()
        if source_config.get("enabled") is True
    }