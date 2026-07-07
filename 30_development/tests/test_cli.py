"""CLI smoke サブコマンド（CAL-5 AC1 疎通）の単体テスト。実APIは叩かずモック注入。"""

from __future__ import annotations

from pathlib import Path

from calorielens.__main__ import cmd_run, cmd_smoke
from calorielens.runner import count_conditions

from .conftest import GOOD_JSON, FakeClient


def _model(mid: str) -> dict:
    return {
        "id": mid,
        "provider": "openai",
        "price_input_per_1m": 1.0,
        "price_output_per_1m": 2.0,
        "price_currency": "jpy",
        "price_ref": "r",
        "enabled": True,
    }


def test_cmd_smoke_one_per_enabled_model(cfg):
    # enabled 2 モデル → S1/trial1 のみで各1件（全step×全trialの本番一括にならない）。
    # 2品目を足して dishes=[先頭dish] の限定が load-bearing であること（2品でも2行）を固定する。
    cfg["models"] = [_model("m1"), _model("m2")]
    cfg["dishes"].append({"id": "dish2", "label": "2品目", "steps": {"S1": ["IMG_A.jpg"]}})
    rc = cmd_smoke(cfg, "t", client=FakeClient(content=GOOD_JSON))
    assert rc == 0
    log = Path(cfg["_root"]) / cfg["paths"]["logs_dir"] / "_smoke" / "t.jsonl"
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2  # enabled 各1件のみ（先頭dish・S1・trial1。2品目・S2は含まない）


def test_cmd_smoke_no_enabled_models(cfg):
    cfg["models"] = []
    assert cmd_smoke(cfg, "t") == 1  # enabled 無し → 実行前に 1 で返す（実APIを叩かない）


def test_run_dish_filter_scopes_conditions(cfg):
    # --dish で対象を1品に絞れる（他品の再実行を避ける）。cfg: trials=2, dish1 steps=S1,S2
    cfg["models"] = [_model("m1")]
    cfg["dishes"].append({"id": "dish2", "label": "2品目", "steps": {"S1": ["IMG_A.jpg"]}})
    assert count_conditions(cfg, models=cfg["models"]) == 6  # dish1(2step×2trial)+dish2(1×2)
    assert count_conditions(cfg, models=cfg["models"], dishes=["dish2"]) == 2  # dish2 のみ


def test_cmd_run_dish_still_guarded(cfg):
    # --dish を付けても課金ガードは無傷（--allow-paid 無し → 実APIを叩かず 2 で停止）
    cfg["models"] = [_model("m1")]
    assert cmd_run(cfg, "t", allow_paid=False, dishes=["test_dish"]) == 2
