"""採点（CAL-9・設計 §3）: JSONLログ→APE・料理名正解率・latency・コストを集計。数値手打ち禁止。

欠損の扱い（設計 §3.1/§3.2）:
- APE は status==ok かつ parsed.total_kcal が数値の行のみ。truth 未確定なら空。
- parse_error/api_error/vision_unsupported は APE から除外し success_rate に計上（補完しない）。
- cost_jpy_mean は cost_jpy 非null の全行（失敗分含む・CAL-5§6）。latency も非null 全行の平均。
- 欠損数値セルは空文字 "" で書く（再実行の byte 同一のため）。
"""

from __future__ import annotations

import csv
import json
import statistics
from collections.abc import Iterable
from pathlib import Path

SCORE_FIELDS = (
    "dish",
    "model",
    "step",
    "n_total",
    "n_ok",
    "success_rate",
    "ape_mean",
    "ape_std",
    "kcal_mean",
    "name_accuracy",
    "latency_ms_mean",
    "cost_jpy_mean",
)
SUMMARY_FIELDS = (
    "model",
    "ape_mean",
    "name_accuracy",
    "latency_ms_mean",
    "cost_jpy_mean",
)


def _is_num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _step_num(step: str) -> int:
    """`S1`→1 等。CSV 行順を数値順に揃える（S10 が S2 より前に来ないように）。"""
    try:
        return int(step[1:])
    except (ValueError, IndexError):
        return 0


def load_logs(logs_dir: str | Path) -> list[dict]:
    """指定ディレクトリ直下の *.jsonl を読み込む（サブディレクトリは辿らない）。"""
    logs_dir = Path(logs_dir)
    rows: list[dict] = []
    for p in sorted(logs_dir.glob("*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def compute_ape(est_kcal: object, truth_kcal: object) -> float | None:
    """APE = |est − truth| / truth × 100。数値でない/ truth=0/未確定 なら None。"""
    if not (_is_num(est_kcal) and _is_num(truth_kcal)) or truth_kcal == 0:
        return None
    return abs(est_kcal - truth_kcal) / truth_kcal * 100


def _iter_data_rows(f: Iterable[str]) -> Iterable[str]:
    for line in f:
        if not line.lstrip().startswith("#"):
            yield line


def load_labels(path: str | Path) -> dict:
    """料理名ラベル CSV を {(dish,model,step,trial): label} で返す（先頭 # 行はコメント）。"""
    path = Path(path)
    labels: dict = {}
    if not path.exists():
        return labels
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(_iter_data_rows(f))
        for r in reader:
            try:
                lab = (r.get("label") or "").strip()
                if lab:
                    labels[(r["dish"], r["model"], r["step"], int(r["trial"]))] = lab
            except (KeyError, TypeError, ValueError):
                continue  # 手編集 CSV の壊れた行はスキップ
    return labels


def _mean(values: list[float]) -> float | str:
    return statistics.fmean(values) if values else ""


def aggregate(logs: list[dict], cfg: dict, labels: dict | None = None) -> list[dict]:
    """(dish, model, step) 粒度で集計する。安定ソート・欠損は空文字。"""
    labels = labels or {}
    truth_by_dish = {d["id"]: (d.get("truth") or {}).get("total_kcal") for d in cfg["dishes"]}

    groups: dict[tuple, list[dict]] = {}
    for r in logs:
        groups.setdefault((r["dish"], r["model"], r["step"]), []).append(r)

    rows: list[dict] = []
    for (dish, model, step), items in sorted(
        groups.items(), key=lambda kv: (kv[0][0], kv[0][1], _step_num(kv[0][2]))
    ):
        n_total = len(items)
        ok = [
            r
            for r in items
            if r.get("status") == "ok" and _is_num((r.get("parsed") or {}).get("total_kcal"))
        ]
        n_ok = len(ok)
        truth = truth_by_dish.get(dish)
        apes = [a for r in ok if (a := compute_ape(r["parsed"]["total_kcal"], truth)) is not None]
        kcals = [r["parsed"]["total_kcal"] for r in ok]
        latencies = [r["latency_ms"] for r in items if _is_num(r.get("latency_ms"))]
        costs = [r["cost_jpy"] for r in items if _is_num(r.get("cost_jpy"))]
        labeled = [
            lab
            for r in items
            if (lab := labels.get((dish, model, step, r.get("trial")))) is not None
        ]
        name_acc = (sum(1 for x in labeled if x == "正解") / len(labeled)) if labeled else ""

        rows.append(
            {
                "dish": dish,
                "model": model,
                "step": step,
                "n_total": n_total,
                "n_ok": n_ok,
                "success_rate": (n_ok / n_total) if n_total else "",
                "ape_mean": _mean(apes),
                "ape_std": statistics.stdev(apes) if len(apes) >= 2 else "",
                "kcal_mean": _mean(kcals),
                "name_accuracy": name_acc,
                "latency_ms_mean": _mean(latencies),
                "cost_jpy_mean": _mean(costs),
            }
        )
    return rows


def summarize(score_rows: list[dict]) -> list[dict]:
    """model 横断（dish×step の非加重平均）。"""
    by_model: dict[str, list[dict]] = {}
    for r in score_rows:
        by_model.setdefault(r["model"], []).append(r)

    out: list[dict] = []
    for model, rows in sorted(by_model.items()):
        out.append(
            {
                "model": model,
                "ape_mean": _mean([r["ape_mean"] for r in rows if _is_num(r["ape_mean"])]),
                "name_accuracy": _mean(
                    [r["name_accuracy"] for r in rows if _is_num(r["name_accuracy"])]
                ),
                "latency_ms_mean": _mean(
                    [r["latency_ms_mean"] for r in rows if _is_num(r["latency_ms_mean"])]
                ),
                "cost_jpy_mean": _mean(
                    [r["cost_jpy_mean"] for r in rows if _is_num(r["cost_jpy_mean"])]
                ),
            }
        )
    return out


def write_csv(rows: list[dict], path: str | Path, fields: Iterable[str]) -> Path:
    """rows を CSV に書き出す（欠損は空文字のまま）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fields))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


def write_labels_todo(logs: list[dict], path: str | Path) -> Path:
    """料理名判定の作業表（設計 §3.4）。ok 行の parsed_dish_name を並べ label 欄を空で出す。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ("dish", "model", "step", "trial", "parsed_dish_name", "label")
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(
            "# 料理名ラベリング作業表: label 列に 正解/惜しい/誤り を記入"
            "（判定基準: CAL-9-CAL-10-design §3.4）\n"
        )
        f.write("# 判定者: ____  判定日: ____\n")
        w = csv.DictWriter(f, fieldnames=list(fields))
        w.writeheader()
        for r in logs:
            if r.get("status") == "ok" and (r.get("parsed") or {}).get("dish_name"):
                w.writerow(
                    {
                        "dish": r["dish"],
                        "model": r["model"],
                        "step": r["step"],
                        "trial": r.get("trial"),
                        "parsed_dish_name": r["parsed"]["dish_name"],
                        "label": "",
                    }
                )
    return path
