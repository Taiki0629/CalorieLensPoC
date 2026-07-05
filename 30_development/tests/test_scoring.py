"""採点（CAL-9）の単体テスト: APE・母集団・欠損・ラベル・再現性。"""

from __future__ import annotations

from pathlib import Path

from calorielens import scoring


def _log(dish, model, step, trial, kcal, *, status="ok", cost=1.0, latency=1000):
    return {
        "dish": dish,
        "model": model,
        "step": step,
        "trial": trial,
        "status": status,
        "parsed": {"total_kcal": kcal, "dish_name": "料理1"} if kcal is not None else None,
        "cost_jpy": cost,
        "latency_ms": latency,
    }


def test_compute_ape():
    assert scoring.compute_ape(880, 800) == 10.0
    assert scoring.compute_ape(800, 800) == 0.0
    assert scoring.compute_ape(880, None) is None  # truth 未確定
    assert scoring.compute_ape(None, 800) is None
    assert scoring.compute_ape(880, 0) is None


def test_aggregate_ape_and_populations(demo_cfg):
    logs = [
        _log("d1", "m1", "S1", 1, 880, cost=1.0, latency=1000),
        _log("d1", "m1", "S1", 2, 720, cost=2.0, latency=2000),
        _log("d1", "m1", "S1", 3, 800, cost=3.0, latency=3000),
        # 失敗だが課金ありの行（cost は母集団に含む・APEには入らない）
        _log("d1", "m1", "S1", 4, None, status="parse_error", cost=9.0, latency=500),
    ]
    rows = scoring.aggregate(logs, demo_cfg)
    r = next(x for x in rows if x["step"] == "S1")
    assert r["n_total"] == 4 and r["n_ok"] == 3
    assert r["success_rate"] == 3 / 4
    assert abs(r["ape_mean"] - (10 + 10 + 0) / 3) < 1e-9  # APE は ok 3行のみ
    # cost/latency は失敗含む全行（母集団定義 M4）
    assert abs(r["cost_jpy_mean"] - (1 + 2 + 3 + 9) / 4) < 1e-9
    assert abs(r["latency_ms_mean"] - (1000 + 2000 + 3000 + 500) / 4) < 1e-9


def test_missing_truth_yields_empty_ape(demo_cfg):
    demo_cfg["dishes"][0]["truth"]["total_kcal"] = "要確認"
    logs = [_log("d1", "m1", "S1", 1, 880)]
    rows = scoring.aggregate(logs, demo_cfg)
    assert rows[0]["ape_mean"] == ""  # 空文字 sentinel


def test_std_empty_when_single(demo_cfg):
    logs = [_log("d1", "m1", "S1", 1, 880)]
    rows = scoring.aggregate(logs, demo_cfg)
    assert rows[0]["ape_std"] == ""  # n_ok=1 は std 不能→空


def test_name_accuracy_from_labels(demo_cfg):
    logs = [
        _log("d1", "m1", "S1", 1, 800),
        _log("d1", "m1", "S1", 2, 800),
        _log("d1", "m1", "S1", 3, 800),
    ]
    labels = {
        ("d1", "m1", "S1", 1): "正解",
        ("d1", "m1", "S1", 2): "正解",
        ("d1", "m1", "S1", 3): "誤り",
    }
    rows = scoring.aggregate(logs, demo_cfg, labels)
    assert abs(rows[0]["name_accuracy"] - 2 / 3) < 1e-9


def test_load_labels_skips_comments(tmp_path: Path):
    p = tmp_path / "labels.csv"
    p.write_text(
        "# コメント行\ndish,model,step,trial,label\nd1,m1,S1,1,正解\nd1,m1,S1,2,\n",
        encoding="utf-8",
    )
    labels = scoring.load_labels(p)
    assert labels == {("d1", "m1", "S1", 1): "正解"}  # 空 label はスキップ


def test_reproducible_csv_bytes(demo_cfg, tmp_path: Path):
    logs = [_log("d1", "m1", "S1", t, 800 + t) for t in range(1, 4)]
    rows = scoring.aggregate(logs, demo_cfg)
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    scoring.write_csv(rows, a, scoring.SCORE_FIELDS)
    scoring.write_csv(scoring.aggregate(logs, demo_cfg), b, scoring.SCORE_FIELDS)
    assert a.read_bytes() == b.read_bytes()  # 再実行で byte 同一（AC5）
