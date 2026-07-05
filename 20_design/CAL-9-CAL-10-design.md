---
対応課題: CAL-9（S3 採点）, CAL-10（S4 可視化）
種別: 設計ドキュメント（draft → design-reviewer 承認で確定）
関連: CAL-5（ログ基盤・本設計の入力元）/ CAL-3（単価確定）/ CAL-4（正解kcal確定）/ CAL-8 S2実行（実ログ供給）/ CAL-12 記事①（本成果物が Blocks）
更新日: 2026-07-05
改訂: r2（design-reviewer 指摘 M1〜M4・中軽微を反映: デモ二経路化・cost_scenario の config 化・cost/latency 母集団定義・欠損sentinel・ソートキー 等）
---

# CAL-9/CAL-10 分析パイプライン設計: 採点（APE・料理名・速度・コスト）＋可視化

## 1. 目的と連結の理由

S2 実行ログ（JSONL）を**唯一のデータソース**に、採点（CAL-9）→ 図表生成（CAL-10）を**再現可能な
パイプライン**にする。数値は一切手打ちしない（`CLAUDE.md §2-3`）。CAL-10 は CAL-9 の集計 CSV に
直接依存する一続きの成果物のため、**1ブランチ・1設計で連結実装**し、両チケットを閉じる。

```
data/logs/*.jsonl ──score──▶ data/results/scores.csv (+ summary/ranking/daily_cost)
                                     └──visualize──▶ 50_output/figures/*.png (+ 表CSV)
```

## 2. スコープと「実 / デモ」二経路（M1・M2 対応）

正解kcal（CAL-4）・単価（CAL-3）・実ログ（CAL-8）が未確定のため、**実経路とデモ経路を完全分離**する。

| 経路 | config | ログ | 出力先 | 数値の性質 |
|------|--------|------|--------|-----------|
| **実** | `config.yaml`（truth/単価は `要確認` のまま不変） | `data/logs/*.jsonl`（S2実行後） | `data/results/*.csv`・`50_output/figures/*.png` | 実測のみ。未確定は空 |
| **デモ** | `config.demo.yaml`（デモ用の偽 truth・偽単価。**実 config は触らない**） | `data/logs/demo/demo-*.jsonl`（`mock-logs` 生成） | `data/results/demo/*.csv`・`50_output/figures/demo/*.png` | 合成値。**図中に「デモ（合成データ）」透かし** |

- 本サイクルの完了判定は**デモ経路で end-to-end（合成ログ→採点→頭打ち折れ線・コスト図まで）**が通ること。
- 実経路はコード同一・入力差し替えのみ（実ログ・実 config）。実数値が `要確認` の間は該当指標を**空**にし推測しない。
- デモ成果物は `/demo/` 配下かつ透かし付きで、記事①の**実結果と誤認されない**（推測禁止の精神 `CLAUDE.md §2`）。

## 3. 採点（CAL-9）

### 3.1 入力とデータ選別（AC6 欠損・失敗の扱い）
- 対象ログ: 指定ディレクトリの `*.jsonl`。実経路は `data/logs/`（`demo/`・`_dryrun/` は含めない）。
- **APE 対象**: `status=="ok"` かつ `parsed.total_kcal` が数値の行のみ。
- `parse_error`/`api_error`/`vision_unsupported` は APE から**除外**し、`success_rate`（=ok件数/全件数）に
  計上する（落とさず母数に残す）。欠損の補完はしない（除外方式）。ルールはコード docstring と本節に明示。

### 3.2 指標と母集団（M4 対応）
- **APE**（`CLAUDE.md §7`）: `|parsed.total_kcal − truth_kcal| / truth_kcal × 100`。`truth_kcal` は
  `config.dishes[].truth.total_kcal`。実 config では `要確認`＝**APE は空**、デモ config では偽 truth で算出。
- **料理名正解率**: ラベルファイル `data/labels/dish_name_labels.csv`（列 `dish,model,step,trial,label`／
  `label∈{正解,惜しい,誤り}`）を join。正解率 = 正解 /（ラベル付き件数）。基準は §3.4。ラベル無しは空。
- **latency_ms_mean**: `latency_ms` が非 null の**全行**（＝応答が返った試行）で平均。
- **cost_jpy_mean**: `cost_jpy` が非 null の**全行**（`parse_error`/`api_error` でも課金が発生した分を含む＝
  `CAL-5 §6` の課金完全計上に整合）で平均。ok 行のみにすると1日コストを過少表示するため全課金行で取る。

### 3.3 集計出力（`data/results[/demo]/`・再実行で同一＝AC5）
- `scores.csv`: 1行 = (dish, model, step)。列: `dish,model,step,n_total,n_ok,success_rate,ape_mean,ape_std,
  kcal_mean,name_accuracy,latency_ms_mean,cost_jpy_mean`。3試行以上を集約。
- `summary.csv`: model 横断（全 dish×step の加重なし平均）。
- **欠損 sentinel（中1）**: 値が無い数値セルは**空文字列 `""`** で書く（`nan`/`要確認` は書かない）。visualize は
  空セルを**欠測として系列からスキップ**する。これで再実行の byte 同一（AC5）を保つ。
- **エッジケース（中4）**: `n_ok==0` → `ape_mean=""`・`ape_std=""`。`n_ok==1` → `ape_std=""`（stdev 不能）。
  例外を出さず決定的に空にする。
- 乱数なし・入力順に依存しない安定ソート（キー: dish, model, step）。float は丸めず raw を書き、表示丸めは可視化側。

### 3.4 料理名 判定基準（AC2・ドキュメント化）
- **正解**: 料理の一般名が一致（表記ゆれ・言語差は許容。例 正解「牛丼」に「牛丼」「beef bowl」）。
- **惜しい**: 上位カテゴリは合うが具体が外れる（例「丼もの」「肉料理」）。
- **誤り**: 別物（例「カレー」）。
- 判定者・判定日をラベルファイル先頭コメントに残す（記事②トレーサビリティ）。
- **ラベリング作業表（軽微1）**: `score` は未ラベル行の作業表 `data/results[/demo]/labels_todo.csv`
  （列 `dish,model,step,trial,parsed_dish_name,label(空欄)`）を出力し、人手ラベル付けを再現可能にする。

## 4. 可視化（CAL-10）

`scores.csv`/`summary.csv` を入力に、図を `50_output/figures[/demo]/` へ、表 CSV を `data/results[/demo]/` へ
生成する。すべて CSV 由来で手動編集なし（AC5）。日本語は `matplotlib-fontja` で表示（AC6）。
デモ経路の図には `figure` 全体に薄い「デモ（合成データ）」透かしを描く（M2）。

- **枚数×精度 折れ線**（AC1）: x=ステップ(S1〜S4), y=APE平均, 系列=モデル。dish ごと＋全体。
  `figures/ape_vs_steps[_<dish>].png`。空セルの step は線を繋がず欠測とする。「頭打ち」を読む主図。
- **コスト×精度 散布**（AC2）: x=1リクエスト平均コスト(円), y=APE, 点=モデル×ステップ。`figures/cost_vs_ape.png`。
- **モデル別ランキング表**（AC3）: 列= kcal誤差(APE平均)・料理名正解率・速度(ms)・コスト(円/req)。
  **ソート（中2）: `ape_mean` 昇順（小さいほど上位）→ タイブレーク `cost_jpy_mean` 昇順 → `model` 名昇順**。
  空 APE のモデルは末尾。`data/results/ranking.csv` ＋ 表画像 `figures/ranking_table.png`。
- **1日あたりコスト試算**（AC4）: 基準 **DAU 1万 × 1人1回 = 10,000 req/日**（`config.cost_scenario.daily_requests`。
  出所=`背景.md §8` の確定シナリオ）。**行単位（中3）: (model, step) ごと**に
  `daily_jpy = cost_jpy_mean × daily_requests`。`data/results/daily_cost.csv` ＋ 表画像。step 依存で枚数が
  増えるほどコストが上がる様子も読めるよう step 別に出す。
- 単位・ラベル: 軸に「APE(%)」「1日あたりコスト(円/日)」「ステップ(枚数)」等を日本語で明記。

## 5. モジュールと CLI

- `scoring.py`: `load_logs` / `compute_ape` / `load_labels` / `aggregate`（scores/summary を返す）/ CSV 書き出し
  / `write_labels_todo`。欠損 sentinel・母集団・エッジケースは §3 に従う。
- `visualize.py`: `line_ape_vs_steps` / `scatter_cost_ape` / `ranking_table` / `daily_cost_table`。matplotlib＋
  `matplotlib-fontja`。`--demo` 指定時は透かしを描く。
- `mockgen.py`: 合成 JSONL 生成（デモ・テスト用）。**デモ config の偽 truth を中心に**、step が進むほど誤差が
  縮み途中で頭打ちする `parsed.total_kcal` を生成。`usage` を埋め `cost.compute_cost_jpy`（デモ単価）で
  `cost_jpy` を充填（M1）。一部を `parse_error` にして success_rate/課金計上も再現。乱数は seed 固定で決定的。
  `run_id` は `demo-*`、出力は `data/logs/demo/` へ（M2）。
- CLI 追加: `score --config <yaml> --logs <dir> --out <dir>` / `visualize --scores <dir> --out <dir> [--demo]` /
  `mock-logs --config <yaml> --out <dir> [--seed N]`。既定は実経路の config/paths。
- **デモ一括**: `README` に「`mock-logs`（config.demo.yaml）→ `score`（config.demo.yaml・demo dir）→
  `visualize --demo`」の3コマンドを記載し、デモ図の再生成手順を残す。

## 6. 依存追加と config 追加

- 依存: `matplotlib`（作図）、`matplotlib-fontja`（日本語フォント同梱・`import matplotlib_fontja` で有効化。
  `japanize-matplotlib` は Python 3.12+ の `distutils` 廃止で import 不可のため不採用。描画確認済み 2026-07-05）。
  集計は標準ライブラリ（`csv`/`statistics`/`json`）で行い pandas は入れない（小規模・依存最小化）。
- **config 追加（M3）**: `config.yaml` に確定シナリオを追加（`要確認` ではない固定値。出所コメント付き）:
  ```yaml
  cost_scenario:
    daily_requests: 10000   # DAU 1万 × 1人1回撮影（出所: 背景.md §8。固定シナリオ）
  ```
- `config.demo.yaml`: `config.yaml` と同形式で、`dishes[].truth`・`models[].price_*`・`enabled:true`・
  `send_seed:false` を**デモ用の偽値**で埋めたもの（先頭に「デモ専用・実結果ではない」コメント）。

## 7. テスト方針（本サイクルの完了判定）
- `scoring`: APE 計算、欠損/失敗の除外と success_rate、母集団（cost/latency は全課金/全応答行）、集計値、
  ラベル join の正解率、空 sentinel、n_ok=0/1 のエッジ、**再実行同一（同入力→同一 CSV byte）**。
- `visualize`: 図 PNG が生成され非空、表 CSV が scores 由来、daily_cost が `cost×daily_requests`、
  空セル系列のスキップ、`--demo` で透かし要素が描かれる。
- `mockgen`: 生成行が LOG スキーマ適合、status 分布、step 依存の APE 低下、`cost_jpy` 充填、`run_id=demo-*`。
- 日本語表示は自動判定が難しいため、デモ図 PNG を**目視確認**（□でない）し 40_test に記録（軽微2: 併せて
  フォント family 解決の軽い assert を入れる）。
- ruff / pytest 全緑。

## 8. 未確定（要確認・実経路では実数値を出さない）
| 項目 | 依存 | 実経路の扱い | デモ経路 |
|------|------|-------------|----------|
| 正解kcal/PFC | CAL-4 | `要確認`→APE 空 | `config.demo.yaml` の偽 truth で算出 |
| モデル単価 | CAL-3 | `要確認`→cost 空 | `config.demo.yaml` の偽単価で `cost_jpy` 充填 |
| 実ログ | CAL-8 S2 | 実行後に同コマンドで実図再生成 | `mock-logs` の合成データ |
| 料理名の実ラベル | 実データ後 | `labels_todo.csv` を人手で埋める | 合成ラベルで join を検証 |
| daily_requests | — | **確定値 10000（背景§8）を config 化。要確認ではない** | 同一 |
