"""可視化（CAL-10）の単体テスト: 数値正規化・色割当・ソート・日次コスト・図生成。"""

from __future__ import annotations

from pathlib import Path

from calorielens import visualize


def test_num_normalization():
    assert visualize._num("") is None
    assert visualize._num(None) is None
    assert visualize._num("12.5") == 12.5
    assert visualize._num(3) == 3.0
    assert visualize._num("x") is None


def test_model_colors_fixed_by_entity():
    # ソートした実体順に固定割当（順位ではなく実体に追従）
    c = visualize.model_colors(["zeta", "alpha"])
    assert c["alpha"] == visualize.CATEGORICAL[0]
    assert c["zeta"] == visualize.CATEGORICAL[1]
    # モデル集合が同じなら色は不変
    assert visualize.model_colors(["alpha", "zeta"]) == c


def test_ranking_sort_ape_then_cost():
    summary = [
        {
            "model": "b",
            "ape_mean": 10.0,
            "cost_jpy_mean": 0.5,
            "name_accuracy": "",
            "latency_ms_mean": "",
        },
        {
            "model": "a",
            "ape_mean": 5.0,
            "cost_jpy_mean": 1.0,
            "name_accuracy": "",
            "latency_ms_mean": "",
        },
        {
            "model": "c",
            "ape_mean": "",
            "cost_jpy_mean": 0.1,
            "name_accuracy": "",
            "latency_ms_mean": "",
        },
    ]
    order = [r["model"] for r in visualize.ranking_rows(summary)]
    assert order == ["a", "b", "c"]  # APE 昇順、空 APE は末尾


def test_daily_cost_rows():
    rows = [{"model": "m", "step": "S1", "cost_jpy_mean": 0.5}]
    out = visualize.daily_cost_rows(rows, 10000)
    assert out[0]["daily_jpy"] == 0.5 * 10000
    # 欠損コストは空
    rows2 = [{"model": "m", "step": "S1", "cost_jpy_mean": ""}]
    assert visualize.daily_cost_rows(rows2, 10000)[0]["daily_jpy"] == ""


def _score_rows():
    return [
        {
            "dish": "d1",
            "model": "m1",
            "step": s,
            "ape_mean": a,
            "cost_jpy_mean": 0.9,
            "name_accuracy": 0.7,
            "latency_ms_mean": 1200,
        }
        for s, a in [("S1", 20.0), ("S2", 10.0), ("S3", 7.0), ("S4", 7.5)]
    ]


def test_line_and_scatter_generate_files(tmp_path: Path):
    rows = _score_rows()
    p1 = visualize.line_ape_vs_steps(rows, tmp_path / "line.png", demo=True)
    p2 = visualize.scatter_cost_ape(rows, tmp_path / "scatter.png")
    assert p1.exists() and p1.stat().st_size > 0
    assert p2.exists() and p2.stat().st_size > 0


def test_tables_generate_files(tmp_path: Path):
    summary = [
        {
            "model": "m1",
            "ape_mean": 11.0,
            "cost_jpy_mean": 0.9,
            "name_accuracy": 0.7,
            "latency_ms_mean": 1200,
        }
    ]
    p1 = visualize.ranking_table(summary, tmp_path / "rank.png")
    p2 = visualize.daily_cost_table(_score_rows(), 10000, tmp_path / "daily.png")
    assert p1.exists() and p1.stat().st_size > 0
    assert p2.exists() and p2.stat().st_size > 0
