"""1リクエスト実行とスイープ（設計 §4）。status で分類し1ログ行を返す。課金一括はガード。"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from .client import build_messages, call_chat, make_client
from .config import resolve_provider
from .cost import compute_cost_jpy, price_ref
from .images import image_ref, resolve_step_images
from .logger import build_log_record
from .parsing import parse_estimate
from .prompts import get_prompt


def _classify_exception(ex: Exception) -> str:
    """API 例外を vision 非対応か一般 API エラーに分類する。"""
    text = str(ex).lower()
    if "vision" in text or ("image" in text and "support" in text):
        return "vision_unsupported"
    return "api_error"


def _find(items: list[dict], key: str, value: str) -> dict:
    for it in items:
        if it.get(key) == value:
            return it
    raise KeyError(f"{key}={value} not found")


def _accumulate(total: dict, usage: dict | None) -> None:
    """usage を total に積算する（全試行の課金を漏らさず合算するため。設計 §7 重大指摘対応）。"""
    if not usage:
        return
    for k in ("input_tokens", "output_tokens", "total_tokens"):
        v = usage.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            total[k] += v


def run_one(
    cfg: dict,
    dish_id: str,
    step: str,
    model_cfg: dict,
    trial: int,
    run_id: str,
    *,
    client: object | None = None,
    now: datetime | None = None,
) -> dict:
    """1条件を1回実行し、1ログ行（dict）を返す。client を渡すと実APIを叩かずモックできる。"""
    root = Path(cfg["_root"])
    derived = root / cfg["paths"]["derived_dir"]
    exp = cfg["experiment"]
    provider = model_cfg["provider"]
    prov = resolve_provider(cfg, provider)

    dish = _find(cfg["dishes"], "id", dish_id)
    img_paths = resolve_step_images(dish["steps"], step, derived)
    refs = [image_ref(p, base=root) for p in img_paths]  # 相対パスで記録（設計 §8）
    prompt = get_prompt(exp["prompt_version"])
    messages = build_messages(prompt, img_paths)

    ts = (now or datetime.now(UTC)).isoformat()
    rec: dict = {
        "timestamp": ts,
        "run_id": run_id,
        "provider": provider,
        "base_url": prov["base_url"],
        "model": model_cfg["id"],
        "dish": dish_id,
        "step": step,
        "n_images": len(img_paths),
        "trial": trial,
        "temperature": exp["temperature"],
        "seed": exp.get("seed"),
        "prompt_version": exp["prompt_version"],
        "image_refs": refs,
        "response_raw": None,
        "parsed": None,
        "usage": None,
        "attempts": 0,
        "latency_ms": None,
        "cost_jpy": None,
        "price_ref": price_ref(model_cfg, cfg["pricing"]["fx"]),
        "status": "api_error",  # fail-closed。成功時のみ ok へ昇格
        "error": None,
    }

    if client is None:
        if not prov["api_key"]:
            rec["error"] = f"API key not set ({prov['api_key_env']})"
            return build_log_record(rec)
        if prov["base_url_required"] and not prov["base_url"]:
            rec["error"] = f"base_url not set for provider '{provider}'"
            return build_log_record(rec)
        client = make_client({"base_url": prov["base_url"]}, prov["api_key"])

    # seed はモデル単位で opt-in（未対応 endpoint への無条件送信で全 api_error 化するのを防ぐ）。
    # send_seed が厳密に True のときだけ送る（`要確認` 等の文字列は送らない）
    send_seed = exp.get("seed") if model_cfg.get("send_seed") is True else None
    max_retries = exp.get("max_json_retries", 2)
    total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    attempts = 0
    last_err: str | None = None
    cur_messages = messages

    for _ in range(max_retries + 1):
        try:
            raw, usage, latency = call_chat(
                client,
                model_cfg["id"],
                cur_messages,
                temperature=exp["temperature"],
                seed=send_seed,
            )
        except Exception as ex:  # noqa: BLE001 — 全例外を status に分類し落とさない（設計 §6）
            rec["attempts"] = attempts
            rec["status"] = _classify_exception(ex)
            rec["error"] = f"{type(ex).__name__}: {ex}"
            _finalize_cost(rec, total_usage, attempts, model_cfg, cfg)
            return build_log_record(rec)

        attempts += 1
        _accumulate(total_usage, usage)
        rec["response_raw"] = raw
        rec["latency_ms"] = latency

        est, err = parse_estimate(raw or "")
        if est is not None:
            rec["parsed"] = est.model_dump()
            rec["status"] = "ok"
            rec["error"] = None
            break
        last_err = err
        # リトライは画像を再送せず、直前の応答を「JSONのみ」で整形させる（再送コストを回避）
        cur_messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": raw or ""},
            {
                "role": "user",
                "content": "上の内容を、指定のJSONオブジェクトのみで出力し直してください。",
            },
        ]
    else:
        rec["status"] = "parse_error"
        rec["error"] = last_err

    rec["attempts"] = attempts
    _finalize_cost(rec, total_usage, attempts, model_cfg, cfg)
    return build_log_record(rec)


def _finalize_cost(rec: dict, total_usage: dict, attempts: int, model_cfg: dict, cfg: dict) -> None:
    """全試行を合算した usage と、それに基づく cost_jpy を確定する。"""
    usage = total_usage if (attempts and any(total_usage.values())) else None
    rec["usage"] = usage
    rec["cost_jpy"] = compute_cost_jpy(usage, model_cfg, cfg["pricing"]["fx"])


def iter_conditions(
    cfg: dict,
    *,
    dishes: list[str] | None = None,
    steps: list[str] | None = None,
    models: list[dict] | None = None,
) -> Iterator[tuple[str, str, dict, int]]:
    """(dish_id, step, model_cfg, trial) を列挙する。"""
    dish_ids = dishes or [d["id"] for d in cfg["dishes"]]
    model_cfgs = models if models is not None else [m for m in cfg["models"] if m.get("enabled")]
    trials = cfg["experiment"]["trials"]
    for dish_id in dish_ids:
        dish = _find(cfg["dishes"], "id", dish_id)
        step_keys = steps or list(dish["steps"].keys())
        for step in step_keys:
            for model_cfg in model_cfgs:
                for trial in range(1, trials + 1):
                    yield dish_id, step, model_cfg, trial


def count_conditions(cfg: dict, **kwargs) -> int:
    """スイープの総リクエスト数（課金一括実行の見積りに使う）。"""
    return sum(1 for _ in iter_conditions(cfg, **kwargs))
