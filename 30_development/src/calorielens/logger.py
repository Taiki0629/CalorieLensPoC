"""JSONL ログ出力（設計 §7・§9）。1リクエスト=1行。秘密情報・base64 は記録しない。"""

from __future__ import annotations

import json
from pathlib import Path

# 出力を許すフィールド（ホワイトリスト）。ここに無いキー（api_key 等）は落とす＝秘密情報の混入防止。
LOG_FIELDS: tuple[str, ...] = (
    "timestamp",
    "run_id",
    "provider",
    "base_url",
    "model",
    "dish",
    "step",
    "n_images",
    "trial",
    "temperature",
    "seed",
    "prompt_version",
    "image_refs",
    "response_raw",
    "parsed",
    "usage",
    "attempts",
    "latency_ms",
    "cost_jpy",
    "price_ref",
    "status",
    "error",
)


def build_log_record(fields: dict) -> dict:
    """LOG_FIELDS のみで1レコードを構成する（順序固定・想定外キーは除外）。"""
    return {k: fields.get(k) for k in LOG_FIELDS}


def append_jsonl(path: str | Path, record: dict) -> None:
    """1レコードを JSONL として追記する。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
