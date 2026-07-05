"""統合テスト: 合成ログ→採点→CSV→（文字列で読み戻し）→図。

cmd_visualize と同じ「CSV から全て文字列で読む」経路を通し、_num/_fmt の吸収と図生成を検証する
（この経路が未テストだったためパス解決バグがすり抜けた反省を回収）。
"""

from __future__ import annotations

import csv
from pathlib import Path

from calorielens import mockgen, scoring, visualize


def test_end_to_end_from_csv_strings(demo_cfg, tmp_path: Path):
    root = Path(demo_cfg["_root"])
    records = mockgen.generate(demo_cfg, seed=1)
    mockgen.write_logs(records, root / demo_cfg["paths"]["logs_dir"])

    logs = scoring.load_logs(root / demo_cfg["paths"]["logs_dir"])
    rows = scoring.aggregate(logs, demo_cfg)
    summary = scoring.summarize(rows)
    results = root / demo_cfg["paths"]["results_dir"]
    scoring.write_csv(rows, results / "scores.csv", scoring.SCORE_FIELDS)
    scoring.write_csv(summary, results / "summary.csv", scoring.SUMMARY_FIELDS)

    def _read(name):
        with (results / name).open(encoding="utf-8") as f:
            return list(csv.DictReader(f))

    score_str = _read("scores.csv")
    summary_str = _read("summary.csv")
    # CSV 由来なので全て文字列
    assert score_str and all(isinstance(v, str) for v in score_str[0].values())

    models = sorted({r["model"] for r in score_str})
    colors = visualize.model_colors(models)
    markers = visualize.model_markers(models)
    figs = tmp_path / "figs"
    p1 = visualize.line_ape_vs_steps(score_str, figs / "line.png", colors=colors, markers=markers)
    p2 = visualize.scatter_cost_ape(score_str, figs / "scatter.png", colors=colors, markers=markers)
    p3 = visualize.ranking_table(summary_str, figs / "rank.png")
    daily = demo_cfg["cost_scenario"]["daily_requests"]
    p4 = visualize.daily_cost_table(score_str, daily, figs / "daily.png")
    for p in (p1, p2, p3, p4):
        assert p.exists() and p.stat().st_size > 0

    # 文字列 CSV からでも頭打ち（S1 の APE > S4）が読める
    ape = {r["step"]: visualize._num(r["ape_mean"]) for r in score_str if r["model"] == "m1"}
    assert ape["S1"] > ape["S4"]
