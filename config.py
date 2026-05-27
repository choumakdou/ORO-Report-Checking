"""config.py — Settings and API key management for ORO QC Checker."""
import json
import os
import sys


def get_base_dir() -> str:
    """Return the directory containing the executable (or script)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_config_path() -> str:
    return os.path.join(get_base_dir(), "config.json")


DEFAULTS = {
    "api_key": "",
    "model": "gpt-4o-mini",
    "output_dir": "",          # empty = same dir as exe
    "auto_open_report": True,
}


def load_config() -> dict:
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Merge with defaults so new keys are always present
            merged = {**DEFAULTS, **data}
            return merged
        except Exception:
            pass
    return dict(DEFAULTS)


def save_config(cfg: dict) -> None:
    with open(get_config_path(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get_api_key() -> str:
    return load_config().get("api_key", "")


def set_api_key(key: str) -> None:
    cfg = load_config()
    cfg["api_key"] = key.strip()
    save_config(cfg)


def get_model() -> str:
    return load_config().get("model", "gpt-4o-mini")


def get_output_dir() -> str:
    cfg = load_config()
    d = cfg.get("output_dir", "")
    if not d:
        d = get_base_dir()
    return d
