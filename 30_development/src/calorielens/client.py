"""OpenAI 互換クライアント（設計 §4）。base_url 切替・messages 構築・usage 正規化。

全モデルで同一手法（プロンプト＋抽出パース）で比較する方針のため、response_format（json_schema/
json_object）は使わない（比較の公平性のため。設計 §5）。対応可否は AC1 追いPRの実確認事項。
"""

from __future__ import annotations

import time
from pathlib import Path

from openai import OpenAI

from .images import to_data_url


def make_client(provider: dict, api_key: str) -> OpenAI:
    """provider["base_url"]（None なら OpenAI 既定）と api_key でクライアントを作る。"""
    kwargs: dict = {"api_key": api_key}
    base_url = provider.get("base_url")
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def build_messages(prompt: str, image_paths: list[Path]) -> list[dict]:
    """テキスト＋複数画像（1〜4枚以上）を1メッセージに積む（AC2）。"""
    content: list[dict] = [{"type": "text", "text": prompt}]
    for p in image_paths:
        content.append({"type": "image_url", "image_url": {"url": to_data_url(p)}})
    return [{"role": "user", "content": content}]


def map_usage(usage: object) -> dict | None:
    """SDK の usage を {input_tokens, output_tokens, total_tokens} に正規化する。

    OpenAI 互換の chat.completions は prompt_tokens/completion_tokens を返す。ai& 側の形状は
    実確認前（設計 §2.1）のため、両方の名前を許容し、取得できなければ None。
    """
    if usage is None:
        return None

    def get(*names: str):
        for n in names:
            v = getattr(usage, n, None)
            if v is None and isinstance(usage, dict):
                v = usage.get(n)
            if v is not None:
                return v
        return None

    input_tokens = get("input_tokens", "prompt_tokens")
    output_tokens = get("output_tokens", "completion_tokens")
    total_tokens = get("total_tokens")
    if input_tokens is None and output_tokens is None and total_tokens is None:
        return None
    if total_tokens is None:
        total_tokens = (input_tokens or 0) + (output_tokens or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def call_chat(
    client: object,
    model: str,
    messages: list[dict],
    *,
    temperature: float = 0,
    seed: int | None = None,
) -> tuple[str | None, dict | None, int]:
    """chat.completions を叩き (生テキスト, usage, latency_ms) を返す。例外は呼び出し側で捕捉。"""
    kwargs: dict = {"model": model, "messages": messages, "temperature": temperature}
    if seed is not None:
        kwargs["seed"] = seed
    started = time.monotonic()
    resp = client.chat.completions.create(**kwargs)
    latency_ms = int((time.monotonic() - started) * 1000)
    raw = resp.choices[0].message.content
    usage = map_usage(getattr(resp, "usage", None))
    return raw, usage, latency_ms
