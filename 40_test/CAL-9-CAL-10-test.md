---
対応課題: CAL-9（S3 採点）, CAL-10（S4 可視化）
種別: 動作確認記録（Flow② ⑥ テスト/動作確認）
実施日: 2026-07-05
実施者: Claude（Opus）
---

# CAL-9/CAL-10 分析パイプライン 動作確認

実 API・実験ログはまだ無い（CAL-3/CAL-4/CAL-8 待ち）。本記録は**合成ログ（デモ経路）で
end-to-end（ログ→採点→図表）を通した確認**。実 config は `要確認` のまま不変。

## 1. lint / 単体テスト

```bash
cd 30_development
uv run ruff format --check .   # → 27 files already formatted
uv run ruff check .            # → All checks passed!
uv run pytest -q               # → 56 passed
```

追加テスト: `test_scoring`（APE・母集団=失敗課金含む cost/全応答 latency・欠損空文字・n_ok=0/1・
ラベル正解率・**再実行 byte 同一**）、`test_mockgen`（スキーマ適合・頭打ち・cost充填・決定性）、
`test_visualize`（数値正規化・色の実体固定割当・ランキングソート・日次コスト）、
`test_config`（相対 --config でも `_root` 絶対＝図の出力先が潰れない回帰）、
`test_pipeline`（**CSV を文字列で読み戻す統合経路**で図生成＋頭打ち確認）。

## 2. デモ経路 end-to-end

```bash
uv run calorielens --config config.demo.yaml mock-logs
uv run calorielens --config config.demo.yaml score --labels data/labels/demo_labels.csv
uv run calorielens --config config.demo.yaml visualize        # demo:true で自動デモ扱い
```

- 合成ログ 24行（1品×2モデル×S1〜S4×3試行、うち1行 parse_error）。
- `scores.csv`: APE が S1→S4 で低下（例 demo-gpt 19.8→9.6→6.9→7.5＝**頭打ち**）、`success_rate` 反映、
  安価モデルの `cost_jpy_mean` が高価モデルの約 1/17（コスト差）。
- 図（`50_output/figures/demo/`）: `ape_vs_steps.png`（折れ線）/`cost_vs_ape.png`（散布）/
  `ranking_table.png`/`daily_cost_table.png`。**日本語ラベルが正しく表示**（豆腐化なし・目視確認）、
  各図に「デモ（合成データ）」透かし。配色は色覚安全（dataviz 検証済み slot）＋マーカー形状で二次エンコード。

## 3. 分離・再現性・手打ち禁止の確認

- **数値手打ち禁止**: `10,000`（1日試算）は `config.cost_scenario.daily_requests` のみ由来。図・表の数値は
  すべて CSV/config 由来（コード直書きなし。experiment-validator が grep で確認）。
- **再実行同一**: `mock-logs→score` を2回実行し `scores.csv` は byte 完全一致。
- **デモ/実の分離**: 実 config は truth/単価が `要確認` のまま（diff は cost_scenario 追加のみ）。デモ値は
  `config.demo.yaml`（`demo: true`）に隔離。`--demo` 付け忘れでも demo:true で透かし＋`/demo` 出力を強制。
- **出力先**: 相対 `--config` でも図はリポジトリルート `50_output/figures/demo`（`config.py` の `_root` 絶対化で修正、`test_config` で回帰防止）。

## 4. AC 別の充足状況（スクリプトとして達成・実数値は実データ後）

| 課題 | AC | 状況 | 根拠 |
|------|----|------|------|
| CAL-9 | APE(3試行平均/分散) | ✅ | scores.csv・`test_scoring` |
| CAL-9 | 料理名ラベリング(形式/基準/反映) | ✅ | labels CSV・§3.4基準・name_accuracy・`labels_todo.csv` |
| CAL-9 | latency 集計 | ✅ | scores/summary |
| CAL-9 | 実コスト=usage×単価 | ✅ | cost_jpy（CAL-5）集計・母集団定義 |
| CAL-9 | 再実行同一・手打ちなし | ✅ | byte 一致・config由来 |
| CAL-9 | 失敗/欠損の扱い | ✅ | 除外＋success_rate・空 sentinel |
| CAL-10 | 枚数×APE 折れ線 | ✅ | ape_vs_steps.png |
| CAL-10 | コスト×精度 散布 | ✅ | cost_vs_ape.png |
| CAL-10 | モデル別ランキング表 | ✅ | ranking_table.png/ranking.csv |
| CAL-10 | 1日コスト試算(10,000req) | ✅ | daily_cost_table.png/daily_cost.csv |
| CAL-10 | パイプライン再現・手動編集なし | ✅ | ログ→CSV→図の一方向 |
| CAL-10 | 日本語ラベル・単位 | ✅ | matplotlib-fontja・目視確認 |

> 実データ（実ログ CAL-8・正解kcal CAL-4・単価 CAL-3・実ラベル）到着後、同じコマンドで実図が
> 決定的に再生成される（コード改修不要）。
