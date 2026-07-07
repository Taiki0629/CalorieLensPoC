"""CAL-3 証跡保存＋seed受理の実証（永続証跡は 90_resources/CAL-3_evidence へ）。
1) 両provider /models の生レスポンスを取得日時付きで保存（AC1）。
2) 採用4モデルすべてに seed 付きテキスト最小リクエストを投げ、seed が拒否されない
   （送っても安全）ことを実APIで確認し、結果を JSON で永続保存。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
from openai import OpenAI

from calorielens import config

def _repo_root(start: Path) -> Path:
    """配置場所に依存せずリポジトリルート（CLAUDE.md のある階層）を探す。"""
    for p in [start, *start.parents]:
        if (p / "CLAUDE.md").exists():
            return p
    return start.parents[1]


ROOT = _repo_root(Path(__file__).resolve())
EV = ROOT / "90_resources/CAL-3_evidence"
EV.mkdir(parents=True, exist_ok=True)
NOW = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

SEED_TARGETS = [
    ("openai", "gpt-5.4"),
    ("openai", "gpt-5.4-mini"),
    ("aiand", "google/gemma-4-31b-it"),
    ("aiand", "moonshotai/kimi-k2.6"),
]


def save_models(provider: str) -> None:
    cfg = config.load_config()
    rp = config.resolve_provider(cfg, provider)
    base = rp["base_url"] or "https://api.openai.com/v1"
    r = httpx.get(
        f"{base}/models",
        headers={"Authorization": f"Bearer {rp['api_key']}"},
        timeout=30,
    )
    out = EV / f"{provider}_models.json"
    out.write_text(
        json.dumps(
            {"fetched_at": NOW, "base_url": base, "status": r.status_code, "body": r.json()},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"saved {out.name} ({r.status_code}, {len(r.json().get('data', []))} models)")


def seed_ok(provider: str, model: str) -> dict:
    cfg = config.load_config()
    rp = config.resolve_provider(cfg, provider)
    client = OpenAI(api_key=rp["api_key"], base_url=rp["base_url"])
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "1と言って"}],
            seed=12345,
        )
        rec = {"provider": provider, "model": model, "seed_accepted": True,
               "text": resp.choices[0].message.content}
    except Exception as e:  # noqa: BLE001
        rec = {"provider": provider, "model": model, "seed_accepted": False,
               "error_type": type(e).__name__, "error": str(e)[:200]}
    tag = "OK " if rec["seed_accepted"] else "NG "
    print(f"seed {tag} {provider}/{model}: {rec.get('text', rec.get('error'))!r}")
    return rec


if __name__ == "__main__":
    for p in ("openai", "aiand"):
        save_models(p)
    print()
    seeds = [seed_ok(prov, model) for prov, model in SEED_TARGETS]
    out = EV / "seed_probe_result.json"
    out.write_text(
        json.dumps({"tested_at": NOW, "seed": 12345, "results": seeds},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nsaved -> {out}")
