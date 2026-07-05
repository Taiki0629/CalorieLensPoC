"""CLI（設計 §4）。convert-images / dry-run / run（課金一括はガード）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

from . import mockgen, scoring
from .config import enabled_models, load_config
from .images import build_contact_sheet, convert_heic_to_jpeg
from .logger import append_jsonl
from .runner import count_conditions, iter_conditions, run_one


class _MockChatCompletions:
    def __init__(self, content: str):
        self._content = content

    def create(self, **_kwargs):
        msg = SimpleNamespace(content=self._content)
        choice = SimpleNamespace(message=msg)
        usage = SimpleNamespace(prompt_tokens=1000, completion_tokens=50, total_tokens=1050)
        return SimpleNamespace(choices=[choice], usage=usage)


class MockClient:
    """dry-run 用の擬似クライアント（実APIを叩かない）。固定の JSON を返す。"""

    def __init__(self, content: str | None = None):
        content = content or (
            '{"dish_name":"のり弁当","total_kcal":720,"protein_g":18.0,'
            '"fat_g":22.0,"carb_g":105.0,"confidence":0.4}'
        )
        self.chat = SimpleNamespace(completions=_MockChatCompletions(content))


def cmd_convert_images(cfg: dict) -> int:
    root = Path(cfg["_root"])
    resources = (root / cfg["paths"]["resources_dir"]).resolve()
    derived = root / cfg["paths"]["derived_dir"]
    img = cfg["image"]
    for jpg_name, heic_name in img["originals"].items():
        src = resources / heic_name
        dst = derived / jpg_name
        if not src.exists():
            print(f"[skip] 原本が無い: {src}")
            continue
        convert_heic_to_jpeg(src, dst, max_dim=img["max_dim"], quality=img["jpeg_quality"])
        print(f"[ok] {heic_name} -> {dst}")
    entries = [
        (f"{step} {name} ({label})", derived / name)
        for step, name, label in img["contact_sheet_order"]
        if (derived / name).exists()
    ]
    if entries:
        cs = build_contact_sheet(entries, derived / "contact_sheet.jpg")
        print(f"[ok] contact sheet -> {cs}")
    return 0


def cmd_dry_run(cfg: dict, dish: str, step: str, run_id: str) -> int:
    root = Path(cfg["_root"])
    # dry-run は捏造値。実ログ（data/logs/*.jsonl）を汚さぬよう専用サブディレクトリへ隔離する
    log_path = root / cfg["paths"]["logs_dir"] / "_dryrun" / f"{run_id}.jsonl"
    mock_model = {
        "id": "mock-model",
        "provider": "openai",
        "price_input_per_1m": "要確認",
        "price_output_per_1m": "要確認",
        "price_currency": "usd",
        "price_ref": "要確認",
    }
    rec = run_one(cfg, dish, step, mock_model, 1, run_id, client=MockClient())
    append_jsonl(log_path, rec)
    print(f"[dry-run] status={rec['status']} n_images={rec['n_images']} parsed={rec['parsed']}")
    print(f"[dry-run] logged -> {log_path}")
    return 0 if rec["status"] == "ok" else 1


def cmd_run(cfg: dict, run_id: str, allow_paid: bool) -> int:
    total = count_conditions(cfg, models=enabled_models(cfg))
    print(f"[run] 対象リクエスト数: {total}（enabled モデルのみ）")
    if not allow_paid:
        print(
            "[停止] これは課金一括実行に該当します（CLAUDE.md §2 承認ゲート）。\n"
            "       人間承認のうえ --allow-paid を付けて再実行してください。実行していません。",
            file=sys.stderr,
        )
        return 2
    if total == 0:
        print(
            "[run] enabled なモデルがありません（CAL-3 未確定）。config.yaml を確認してください。"
        )
        return 1
    root = Path(cfg["_root"])
    log_path = root / cfg["paths"]["logs_dir"] / f"{run_id}.jsonl"
    ok = 0
    for dish_id, step, model_cfg, trial in iter_conditions(cfg, models=enabled_models(cfg)):
        rec = run_one(cfg, dish_id, step, model_cfg, trial, run_id)
        append_jsonl(log_path, rec)
        ok += rec["status"] == "ok"
    print(f"[run] 完了: {ok}/{total} ok -> {log_path}")
    return 0


def _repo_root(cfg: dict) -> Path:
    return Path(cfg["_root"]).parent


def cmd_mock_logs(cfg: dict, out_dir: str | None, seed: int) -> int:
    records = mockgen.generate(cfg, seed=seed)
    logs_dir = Path(out_dir) if out_dir else Path(cfg["_root"]) / cfg["paths"]["logs_dir"]
    path = mockgen.write_logs(records, logs_dir)
    labels_path = Path(cfg["_root"]) / "data" / "labels" / "demo_labels.csv"
    mockgen.write_demo_labels(records, labels_path)
    print(f"[mock-logs] {len(records)} 行 -> {path}")
    print(f"[mock-logs] demo labels -> {labels_path}")
    return 0


def cmd_score(cfg: dict, logs_dir: str | None, out_dir: str | None, labels_path: str | None) -> int:
    root = Path(cfg["_root"])
    logs_dir = Path(logs_dir) if logs_dir else root / cfg["paths"]["logs_dir"]
    out_dir = Path(out_dir) if out_dir else root / cfg["paths"]["results_dir"]
    labels = scoring.load_labels(labels_path) if labels_path else {}
    logs = scoring.load_logs(logs_dir)
    score_rows = scoring.aggregate(logs, cfg, labels)
    summary = scoring.summarize(score_rows)
    scoring.write_csv(score_rows, out_dir / "scores.csv", scoring.SCORE_FIELDS)
    scoring.write_csv(summary, out_dir / "summary.csv", scoring.SUMMARY_FIELDS)
    scoring.write_labels_todo(logs, out_dir / "labels_todo.csv")
    print(f"[score] logs={len(logs)}行 -> {out_dir}/scores.csv, summary.csv, labels_todo.csv")
    return 0 if score_rows else 1


def cmd_visualize(cfg: dict, demo: bool) -> int:
    import csv as _csv

    from . import visualize  # matplotlib は重いので遅延 import

    # デモ性は config 由来でも強制（demo:true で --demo 付け忘れ時の混入を防ぐ）
    demo = demo or bool(cfg.get("demo"))
    root = Path(cfg["_root"])
    results_dir = root / cfg["paths"]["results_dir"]

    scores_path = results_dir / "scores.csv"
    if not scores_path.exists():
        print(
            f"[visualize] {scores_path} が無い。先に score を実行してください。",
            file=sys.stderr,
        )
        return 1

    def _read(name: str) -> list[dict]:
        with (results_dir / name).open(encoding="utf-8") as f:
            return list(_csv.DictReader(f))

    score_rows = _read("scores.csv")
    summary = _read("summary.csv")
    # 色/マーカーは全モデル集合から一度だけ決め、全図で一貫させる（料理間で色がずれない）
    all_models = sorted({r["model"] for r in score_rows})
    colors = visualize.model_colors(all_models)
    markers = visualize.model_markers(all_models)
    figures = _repo_root(cfg) / "50_output" / "figures" / ("demo" if demo else "")
    visualize.line_ape_vs_steps(
        score_rows, figures / "ape_vs_steps.png", demo=demo, colors=colors, markers=markers
    )
    for d in sorted({r["dish"] for r in score_rows}):
        visualize.line_ape_vs_steps(
            score_rows,
            figures / f"ape_vs_steps_{d}.png",
            dish=d,
            demo=demo,
            colors=colors,
            markers=markers,
        )
    visualize.scatter_cost_ape(
        score_rows, figures / "cost_vs_ape.png", demo=demo, colors=colors, markers=markers
    )
    visualize.ranking_table(summary, figures / "ranking_table.png", demo=demo)
    daily = cfg["cost_scenario"]["daily_requests"]
    visualize.daily_cost_table(score_rows, daily, figures / "daily_cost_table.png", demo=demo)
    scoring.write_csv(
        visualize.ranking_rows(summary), results_dir / "ranking.csv", scoring.SUMMARY_FIELDS
    )
    scoring.write_csv(
        visualize.daily_cost_rows(score_rows, daily),
        results_dir / "daily_cost.csv",
        ["model", "step", "cost_jpy_mean", "daily_requests", "daily_jpy"],
    )
    print(f"[visualize] 図 -> {figures} / 表CSV -> {results_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="calorielens", description="料理写真カロリー推定 PoC")
    parser.add_argument("--config", default=None, help="config.yaml のパス")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("convert-images", help="HEIC→JPEG 変換＋コンタクトシート生成")

    p_dry = sub.add_parser("dry-run", help="実APIを叩かずモックで経路確認")
    p_dry.add_argument("--dish", default="conbini_bento")
    p_dry.add_argument("--step", default="S1")
    p_dry.add_argument("--run-id", default="dryrun")

    p_run = sub.add_parser("run", help="本番スイープ（課金一括・要人間承認）")
    p_run.add_argument("--run-id", required=True)
    p_run.add_argument("--allow-paid", action="store_true", help="人間承認済みを明示（無いと拒否）")

    p_mock = sub.add_parser("mock-logs", help="デモ用 合成ログ生成（config.demo.yaml 前提）")
    p_mock.add_argument("--out", default=None)
    p_mock.add_argument("--seed", type=int, default=12345)

    p_score = sub.add_parser("score", help="ログ→採点CSV（APE・正解率・latency・コスト）")
    p_score.add_argument("--logs", default=None)
    p_score.add_argument("--out", default=None)
    p_score.add_argument("--labels", default=None)

    p_viz = sub.add_parser("visualize", help="採点CSV→図表（50_output/figures）")
    p_viz.add_argument("--demo", action="store_true", help="デモ透かし＋figures/demo へ出力")

    args = parser.parse_args(argv)
    cfg = load_config(args.config)

    if args.command == "convert-images":
        return cmd_convert_images(cfg)
    if args.command == "dry-run":
        return cmd_dry_run(cfg, args.dish, args.step, args.run_id)
    if args.command == "run":
        return cmd_run(cfg, args.run_id, args.allow_paid)
    if args.command == "mock-logs":
        return cmd_mock_logs(cfg, args.out, args.seed)
    if args.command == "score":
        return cmd_score(cfg, args.logs, args.out, args.labels)
    if args.command == "visualize":
        return cmd_visualize(cfg, args.demo)
    return 0  # required=True のため未知コマンドはここに来ない


if __name__ == "__main__":
    raise SystemExit(main())
