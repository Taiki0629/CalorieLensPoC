"""config.yaml と .env のロード（設計 §4・§9）。api_key の値は保持せず環境から都度解決する。"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import find_dotenv, load_dotenv


def load_env() -> None:
    """リポジトリルートの .env を読み込む（見つからなければ何もしない）。"""
    path = find_dotenv(usecwd=True)
    if path:
        load_dotenv(path)


def default_config_path() -> Path:
    """このパッケージから見た 30_development/config.yaml。"""
    return Path(__file__).resolve().parents[2] / "config.yaml"


def load_config(path: str | Path | None = None) -> dict:
    """config.yaml をロードし、相対パス解決用に `_root`（config.yaml のあるディレクトリ）を付す。"""
    path = Path(path) if path is not None else default_config_path()
    with path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["_root"] = path.parent
    return cfg


def resolve_provider(cfg: dict, provider: str) -> dict:
    """provider の base_url と api_key を .env から解決する。返り値の api_key はメモリ上のみ。

    base_url_env を持つ provider（例 ai&）は、その env 未設定なら base_url が None のままとなり、
    `base_url_required=True` で呼び出し側が明示エラーにできる（OpenAI へ誤送信するのを防ぐ）。
    """
    load_env()
    p = dict(cfg["providers"][provider])
    base_url_env = p.get("base_url_env")
    base_url = p.get("base_url")
    if base_url is None and base_url_env:
        base_url = os.environ.get(base_url_env)
    return {
        "base_url": base_url,
        "api_key": os.environ.get(p["api_key_env"]),
        "api_key_env": p["api_key_env"],
        "base_url_required": bool(base_url_env),
    }


def enabled_models(cfg: dict) -> list[dict]:
    """enabled:true のモデルのみ（CAL-3 で確定するまでは空）。"""
    return [m for m in cfg.get("models", []) if m.get("enabled")]
