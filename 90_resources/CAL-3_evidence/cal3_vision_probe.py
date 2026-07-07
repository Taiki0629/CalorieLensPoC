"""CAL-3 AC3: vision 実証（使い捨てアドホック・共通実装は使わない）。
gpt-5.4(OpenAI) と google/gemma-4-31b-it(ai&) にテスト画像1枚を送り、
画像入力が受理され正常応答が返るかを実APIで確認する。
生応答は永続証跡 90_resources/CAL-3_evidence/vision_probe_result.json に保存（記録＝証跡）。
"""

from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

from calorielens import config

def _repo_root(start: Path) -> Path:
    """配置場所に依存せずリポジトリルート（CLAUDE.md のある階層）を探す。"""
    for p in [start, *start.parents]:
        if (p / "CLAUDE.md").exists():
            return p
    return start.parents[1]


ROOT = _repo_root(Path(__file__).resolve())
IMG = ROOT / "30_development/data/derived/IMG_0420.jpg"
# 永続証跡（コミット対象）。記録＝この保存ファイルを一致させる（CAL-3 §0）
OUT = ROOT / "90_resources/CAL-3_evidence/vision_probe_result.json"
PROMPT = "この画像に写っている料理は何ですか。料理名だけを日本語で短く答えてください。"

TARGETS = [
    ("openai", "gpt-5.4"),
    ("openai", "gpt-5.4-mini"),
    ("aiand", "google/gemma-4-31b-it"),
    ("aiand", "moonshotai/kimi-k2.6"),
]


def data_uri(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/jpeg;base64,{b64}"


def call(provider: str, model: str, uri: str) -> dict:
    cfg = config.load_config()
    rp = config.resolve_provider(cfg, provider)
    client = OpenAI(api_key=rp["api_key"], base_url=rp["base_url"])
    msg = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": uri}},
            ],
        }
    ]
    t0 = time.monotonic()
    try:
        resp = client.chat.completions.create(model=model, messages=msg)
        dt = (time.monotonic() - t0) * 1000
        return {
            "provider": provider,
            "model": model,
            "status": "ok",
            "latency_ms": round(dt),
            "text": resp.choices[0].message.content,
            "usage": resp.usage.model_dump() if resp.usage else None,
        }
    except Exception as e:  # noqa: BLE001
        dt = (time.monotonic() - t0) * 1000
        return {
            "provider": provider,
            "model": model,
            "status": "error",
            "latency_ms": round(dt),
            "error_type": type(e).__name__,
            "error": str(e)[:500],
        }


def main() -> None:
    uri = data_uri(IMG)
    print(f"image={IMG.name} bytes={IMG.stat().st_size}")
    results = []
    for provider, model in TARGETS:
        print(f"\n--- {provider} / {model} ---")
        r = call(provider, model, uri)
        results.append(r)
        print(f"status={r['status']} latency={r['latency_ms']}ms")
        if r["status"] == "ok":
            print(f"text  = {r['text']!r}")
            print(f"usage = {r['usage']}")
        else:
            print(f"{r['error_type']}: {r['error']}")
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    payload = {"tested_at": now, "image": IMG.name, "prompt": PROMPT, "results": results}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
