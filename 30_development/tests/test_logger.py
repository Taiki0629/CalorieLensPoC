"""JSONL ログ出力の単体テスト（AC4・AC5 秘密情報非混入）。"""

from __future__ import annotations

import json
from pathlib import Path

from calorielens.logger import LOG_FIELDS, append_jsonl, build_log_record


def test_build_record_whitelists_fields():
    rec = build_log_record(
        {"status": "ok", "api_key": "SECRET", "authorization": "Bearer x", "extra": 1}
    )
    assert set(rec.keys()) == set(LOG_FIELDS)
    assert "api_key" not in rec and "authorization" not in rec and "extra" not in rec
    assert rec["status"] == "ok"


def test_secret_not_written(tmp_path: Path):
    rec = build_log_record({"status": "ok", "model": "m", "api_key": "SUPER_SECRET_KEY"})
    path = tmp_path / "log.jsonl"
    append_jsonl(path, rec)
    text = path.read_text(encoding="utf-8")
    assert "SUPER_SECRET_KEY" not in text


def test_append_jsonl_one_line_per_record(tmp_path: Path):
    path = tmp_path / "log.jsonl"
    append_jsonl(path, build_log_record({"status": "ok"}))
    append_jsonl(path, build_log_record({"status": "parse_error"}))
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["status"] == "ok"
    assert json.loads(lines[1])["status"] == "parse_error"
