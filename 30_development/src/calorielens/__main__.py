"""CLI（設計 §4）。convert-images / dry-run / run（課金一括はガード）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

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

    args = parser.parse_args(argv)
    cfg = load_config(args.config)

    if args.command == "convert-images":
        return cmd_convert_images(cfg)
    if args.command == "dry-run":
        return cmd_dry_run(cfg, args.dish, args.step, args.run_id)
    if args.command == "run":
        return cmd_run(cfg, args.run_id, args.allow_paid)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
