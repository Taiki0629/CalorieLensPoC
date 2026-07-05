"""デモ用 合成ログ生成（CAL-9/10 設計 §5）。実結果と混ざらないよう run_id=demo-*・demo dir 出力。

step が進むほど誤差が縮み途中で頭打ちする APE を再現し、cost_jpy を充填（デモ単価）。一部を
parse_error にして success_rate/課金計上も再現する。seed 固定で決定的（実 API は一切叩かない）。
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from pathlib import Path

from .cost import compute_cost_jpy
from .logger import build_log_record

# step が進むと誤差が縮み S3〜S4 で頭打ちする（アングル積み増し実験の想定形）
_STEP_ERR = {"S1": 0.35, "S2": 0.18, "S3": 0.12, "S4": 0.11, "S5": 0.105, "S6": 0.10}


def _fake_refs(dish: dict, step: str) -> list[dict]:
    refs = []
    for name in dish["steps"][step]:
        sha = hashlib.sha256(name.encode("utf-8")).hexdigest()
        refs.append({"path": f"data/derived/{name}", "sha256": sha})
    return refs


def generate(cfg: dict, *, seed: int = 12345, run_id: str = "demo-001") -> list[dict]:
    """デモ config から合成ログ（build_log_record 済み dict のリスト）を生成する。"""
    rng = random.Random(seed)
    fx = cfg["pricing"]["fx"]
    models = [m for m in cfg["models"] if m.get("enabled")]
    trials = cfg["experiment"]["trials"]
    ts = "2026-07-05T00:00:00+00:00"
    records: list[dict] = []

    for dish in cfg["dishes"]:
        truth = dish["truth"]["total_kcal"]
        for mi, model in enumerate(models):
            model_bias = 0.02 + 0.04 * mi  # モデルごとの系統誤差（頭打ちの下限）
            for step in dish["steps"]:
                err = _STEP_ERR.get(step, 0.1)
                for trial in range(1, trials + 1):
                    input_tokens = 1000 + rng.randint(0, 200)
                    output_tokens = 40 + rng.randint(0, 20)
                    usage = {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens,
                    }
                    base = {
                        "timestamp": ts,
                        "run_id": run_id,
                        "provider": model["provider"],
                        "base_url": None,
                        "model": model["id"],
                        "dish": dish["id"],
                        "step": step,
                        "n_images": len(dish["steps"][step]),
                        "trial": trial,
                        "temperature": 0,
                        "seed": None,
                        "prompt_version": "v1",
                        "image_refs": _fake_refs(dish, step),
                        "response_raw": None,
                        "parsed": None,
                        "usage": usage,
                        "attempts": 1,
                        "latency_ms": 800 + rng.randint(0, 1200),
                        "cost_jpy": compute_cost_jpy(usage, model, fx),
                        "price_ref": model.get("price_ref"),
                        "status": "ok",
                        "error": None,
                    }
                    # 最終モデルの S1 trial1 は parse_error（失敗＋課金計上のデモ）
                    if mi == len(models) - 1 and step == "S1" and trial == 1:
                        usage3 = {k: v * 3 for k, v in usage.items()}
                        base["usage"] = usage3
                        base["attempts"] = 3
                        base["cost_jpy"] = compute_cost_jpy(usage3, model, fx)
                        base["status"] = "parse_error"
                        base["response_raw"] = "壊れたJSON（demo）"
                        base["error"] = "demo parse_error"
                    else:
                        signed = (rng.random() - 0.5) * 2 * err + model_bias
                        est = round(truth * (1 + signed), 1)
                        base["response_raw"] = json.dumps({"total_kcal": est}, ensure_ascii=False)
                        base["parsed"] = {
                            "dish_name": dish["label"],
                            "total_kcal": est,
                            "protein_g": round(truth * 0.025, 1),
                            "fat_g": round(truth * 0.03, 1),
                            "carb_g": round(truth * 0.14, 1),
                            "confidence": round(0.4 + 0.4 * rng.random(), 2),
                        }
                    records.append(build_log_record(base))
    return records


def write_logs(records: list[dict], out_dir: str | Path, run_id: str = "demo-001") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{run_id}.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


def write_demo_labels(records: list[dict], path: str | Path, *, seed: int = 7) -> Path:
    """合成ログの ok 行に対しデモ用ラベル（大半 正解・一部 惜しい）を決定的に付ける。"""
    rng = random.Random(seed)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write("# デモ用 合成ラベル（実判定ではない）。判定基準: CAL-9-CAL-10-design §3.4\n")
        w = csv.DictWriter(f, fieldnames=["dish", "model", "step", "trial", "label"])
        w.writeheader()
        for r in records:
            if r.get("status") != "ok":
                continue
            label = "正解" if rng.random() > 0.2 else "惜しい"
            w.writerow(
                {
                    "dish": r["dish"],
                    "model": r["model"],
                    "step": r["step"],
                    "trial": r["trial"],
                    "label": label,
                }
            )
    return path
