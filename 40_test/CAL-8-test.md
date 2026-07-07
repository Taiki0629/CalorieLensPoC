---
対応課題: CAL-8（S2 実行）／ CAL-4（正解kcal・部分）
種別: 動作確認記録（Flow② ⑥ ＝本番実行の記録）
実施日: 2026-07-08
実施者: Claude（Opus）
承認: 人間 GO 取得済み（Phase1・4モデル選択）
---

# Phase1 本番実行 動作確認（CAL-8 Phase1）

**課金一括実行**。人間 GO を取得のうえ、弁当1品（conbini_bento）で S1〜S4 × 4モデル × 3試行 =
**48リクエスト**を実行した。すき家牛丼（Phase2・+48件）は未実行のため CAL-8 は部分完了。

## 1. 実行

```bash
cd 30_development
uv run calorielens run --allow-paid --run-id phase1-20260708
# → [run] 完了: 48/48 ok -> data/logs/phase1-20260708.jsonl
uv run calorielens score        # 正解kcal=579（CAL-4）で APE 算出
uv run calorielens visualize    # 実データ図（demo:false → 50_output/figures 直下・透かしなし）
```

## 2. ログ完全性（実験の正しさ）

- 48行・**全 status=ok**（失敗ゼロ）。各(model,step)ちょうど3試行。
- 22必須フィールド欠損ゼロ・**キー非混入**（`sk-`/`api_key` なし）・`image_refs` 相対+sha256。
- `run_id=phase1-20260708` で一意。usage/cost は実取得×config単価×為替で算出（手打ちなし）。
- APE 検算一致（例 gpt-5.4-mini S1 = 980 kcal×3 → |980-579|/579 = 69.3%）。

## 3. 結果サマリ（正解 579 kcal）

総合（`data/results/summary.csv`・APE昇順＝精度良い順）:

| 順位 | モデル | 平均APE | 平均latency | 平均コスト/コール |
|:--:|--------|-------:|-----------:|-----------:|
| 1 | google/gemma-4-31b-it | **61.5%** | 2678ms | **¥0.034** |
| 2 | gpt-5.4-mini | 69.3% | 1490ms | ¥0.345 |
| 3 | gpt-5.4 | 75.6% | 2355ms | ¥1.158 |
| 4 | moonshotai/kimi-k2.6 | 90.7% | 13143ms | ¥2.004 |

ステップ別 APE（`data/results/scores.csv`）:

| モデル | S1 | S2 | S3 | S4 | 傾向 |
|--------|---:|---:|---:|---:|------|
| gemma-4-31b-it | 64.1 | 64.1 | 58.9 | 58.9 | わずかに改善（最良） |
| gpt-5.4 | 69.3 | 75.0 | 69.3 | 88.8 | 改善せず・S4で悪化 |
| gpt-5.4-mini | 69.3 | 69.3 | 69.3 | 69.3 | 完全フラット（±0・角度無反応） |
| kimi-k2.6 | 110.7 | 84.2 | 66.4 | 101.5 | 高分散（±13〜28）・不安定 |

## 4. 主な発見（記事①の核）

- **全モデルが 579 kcal を 59〜111% 過大評価**（この弁当は見た目より低カロリー）。
- **「角度を積めば精度が上がる」仮説はこの弁当では概ね不支持**: 単調改善は gemma のみ、gpt-5.4 は
  S4 で悪化、gpt-5.4-mini は S1〜S4 完全フラット（追加アングルを使っていない）。
- **コストと精度が逆相関**: 最安 gemma（¥0.034）が最良精度、最高額 kimi（¥2.00）が最低精度＆最遅（13s）。
  「高い＝良い」が成立しない。gemma は gpt-5.4 の約 1/34 のコスト。
- **再現性の差**: temperature=0 で gemma・gpt-5.4-mini は3試行 APE±0（完全決定的）、gpt-5.4・kimi は
  ブレる（kimi S1 ±28）。

## 5. 図（`50_output/figures/`・透かしなし＝実データ）

- `ape_vs_steps.png`（主図・頭打ち折れ線）: 日本語ラベル正常表示・色覚安全配色＋マーカー・単一軸。目視確認済み。
- `ape_vs_steps_conbini_bento.png` / `cost_vs_ape.png` / `ranking_table.png` / `daily_cost_table.png`。

## 6. 残作業
- CAL-8 Phase2: すき家牛丼（+S1〜S4×4モデル×3試行=48件）＝要 GO。
- CAL-4: 料理名ラベリング（name_accuracy）・パッケージ写真証跡・商品名/購入店/日・すき家公式値。
- 正解kcal はユーザーのパッケージ読み取り（579）。写真証跡の保存で監査性が上がる。
