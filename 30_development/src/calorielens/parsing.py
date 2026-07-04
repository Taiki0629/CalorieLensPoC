"""生応答→JSON抽出→スキーマ検証（設計 §6）。不正時は理由付きで失敗を返す。"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from .schema import Estimate

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _as_dict(s: str) -> dict | None:
    try:
        obj = json.loads(s.strip())
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def extract_json(text: str) -> dict | None:
    """生応答から JSON オブジェクトを取り出す。コードフェンス→全体→先頭オブジェクトの順で試す。"""
    if not text:
        return None
    # 1) ```json ... ``` フェンス
    m = _FENCE.search(text)
    if m:
        obj = _as_dict(m.group(1))
        if obj is not None:
            return obj
    # 2) 全体がそのまま JSON
    obj = _as_dict(text)
    if obj is not None:
        return obj
    # 3) 最初の '{' から raw_decode で先頭 1 オブジェクトのみ取る（後続の地の文に強い）
    start = text.find("{")
    if start != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError:
            obj = None
        if isinstance(obj, dict):
            return obj
    return None


def parse_estimate(text: str) -> tuple[Estimate | None, str | None]:
    """(Estimate, None) 成功 / (None, 失敗理由) を返す。"""
    obj = extract_json(text)
    if obj is None:
        return None, "no JSON object found in response"
    try:
        return Estimate.model_validate(obj), None
    except ValidationError as ex:
        return None, f"schema validation failed: {ex.errors(include_url=False)[:3]}"
