"""合成ログ生成（mockgen）の単体テスト: スキーマ適合・頭打ち・cost充填・決定性。"""

from __future__ import annotations

from calorielens import mockgen, scoring
from calorielens.logger import LOG_FIELDS


def test_records_conform_to_log_schema(demo_cfg):
    recs = mockgen.generate(demo_cfg, seed=1)
    assert recs
    for r in recs:
        assert set(r.keys()) == set(LOG_FIELDS)
        assert str(r["run_id"]).startswith("demo-")


def test_has_failure_and_cost_filled(demo_cfg):
    recs = mockgen.generate(demo_cfg, seed=1)
    assert any(r["status"] == "parse_error" for r in recs)  # 失敗も再現
    assert all(r["cost_jpy"] is not None for r in recs)  # デモ単価で cost 充填


def test_plateau_ape_decreases(demo_cfg):
    recs = mockgen.generate(demo_cfg, seed=1)
    rows = scoring.aggregate(recs, demo_cfg)
    by_step = {r["step"]: r["ape_mean"] for r in rows if r["model"] == "m1"}
    # S1 の APE が S4 より大きい（枚数を足すと精度が上がる＝頭打ち曲線）
    assert by_step["S1"] > by_step["S4"]


def test_deterministic(demo_cfg):
    a = mockgen.generate(demo_cfg, seed=42)
    b = mockgen.generate(demo_cfg, seed=42)
    assert a == b  # seed 固定で決定的
