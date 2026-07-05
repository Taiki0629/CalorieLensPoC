# calorielens — 料理写真カロリー推定 PoC 共通実装（CAL-5）

`base_url` の差し替えだけで OpenAI と ai& Inference を同一コードで叩き、全リクエストを
JSONL に記録する比較基盤。設計は `../20_design/CAL-5-design.md`。

## セットアップ

```bash
cd 30_development
uv sync            # 依存の解決（openai, pydantic, pyyaml, python-dotenv, pillow, pillow-heif, dev: pytest, ruff）
```

APIキーはリポジトリルートの `.env` に置く（`.env.example` にキー名のみ記載済み・コミット禁止）:

```
OPENAI_API_KEY=...
AIAND_API_KEY=...
AIAND_BASE_URL=...
```

> モデルID・単価・為替・正解kcal は `config.yaml` に集約。未確定は `要確認`（CAL-3/CAL-4 で確定）。

## 使い方（CLI）

```bash
# 1) HEIC → JPEG 変換（長辺1024/q85）＋ コンタクトシート生成（俯角順の目視確認用）
uv run calorielens convert-images

# 2) ドライラン（実APIを叩かずモック応答で経路確認・JSONL を1行出力）
uv run calorielens dry-run --dish conbini_bento --step S1

# 3) 本番スイープ（課金一括実行。人間承認が前提。--allow-paid が無いと拒否する）
uv run calorielens run --run-id <id> --allow-paid    # ← 承認前は実行しない
```

> 注: `--config` は**サブコマンドより前**に置く（例 `calorielens --config config.demo.yaml score`）。

## 分析パイプライン（採点 CAL-9 → 可視化 CAL-10）

`data/logs/*.jsonl` → 採点CSV（`data/results/`）→ 図表（`50_output/figures/`）の一方向。数値は
すべてログ/CSV/config 由来（手打ち禁止）。正解kcal（CAL-4）・単価（CAL-3）が `要確認` の間は該当指標は空。

```bash
# 実データ（S2 実行後）: 実 config で採点→可視化
uv run calorielens score                 # data/logs → data/results/scores.csv 等
uv run calorielens visualize             # 50_output/figures/*.png

# デモ（キー不要で end-to-end を通す。合成データ・図に「デモ」透かし・出力は /demo 配下）
uv run calorielens --config config.demo.yaml mock-logs
uv run calorielens --config config.demo.yaml score --labels data/labels/demo_labels.csv
uv run calorielens --config config.demo.yaml visualize   # demo:true のため自動でデモ扱い
```

生成物: `ape_vs_steps*.png`（枚数×精度＝頭打ち曲線）/ `cost_vs_ape.png`（コスト×精度）/
`ranking_table.png` / `daily_cost_table.png`（1日 `cost_scenario.daily_requests` req 試算）。
料理名の正解率は `data/labels/` のラベルCSV（`score` が `labels_todo.csv` を出力→人手記入）から算出。

## テスト（本サイクルの完了判定・AC1以外）

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

実APIは呼ばない（`tests/conftest.py` で client をモック）。AC1（実キーでの OpenAI・ai& 疎通）は
API キー到着後の追いPRで実施し、CAL-5 を完了する。

## ログ（`data/logs/*.jsonl`）

1リクエスト=1行。フィールドは設計 §7／`CLAUDE.md`（30_development）§4 を参照。集計・図表は
必ずこのログから再生成し、数値を手打ちしない。
