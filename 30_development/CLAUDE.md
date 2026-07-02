# 30_development — 開発規約

ルート `/CLAUDE.md` の下位。コードに関する規約はここが正。違反は `experiment-validator` サブエージェントと `/code-review` で検出する。

---

## 1. 環境・ツール

- **言語**: Python（3.12+ 目安）
- **依存管理**: `uv`（`pyproject.toml` / `uv add` / `uv run`）。`pip install` 直叩き禁止。
- **整形・lint**: `ruff`（`ruff format` + `ruff check --fix`）。コミット前に通す（編集後フックでも自動実行）。
- **秘密情報**: APIキー・base_url は `.env` から読む（`os.environ` / `python-dotenv`）。コードに直書き禁止。

## 2. ディレクトリ（30_development配下）

```
30_development/
  pyproject.toml
  config.yaml          # モデル一覧・料金・正解kcal・実験条件。数値はここに集約
  src/                 # 実装
  data/
    logs/              # 実験ログ（JSONL）。1リクエスト=1行
    results/           # 集計CSV・図表（スクリプト生成物のみ）
```

## 3. 設定の外出し（手打ち防止の起点）

- モデルID・単価・正解kcal・PFC・試行回数・temperature 等は **`config.yaml`** に集約。
- 単価・モデルID・vision対応は**推測禁止**。`/models` 等の実APIと公式情報で確定し、`config.yaml` に**確認日と出典**を併記する。確定前は値を入れず `要確認` とする。

## 4. 実験ログ仕様（JSONL・最重要）

全API呼び出しを `data/logs/*.jsonl` に1行1レコードで記録する。集計・図表はすべてこのログから生成し、**記事・ドキュメントに数値を手打ちしない**。

各行のフィールド:

| フィールド | 説明 |
|-----------|------|
| `timestamp` | ISO8601 |
| `run_id` | 実行バッチ識別子 |
| `provider` | `openai` / `aiand` |
| `base_url` | 使用したエンドポイント |
| `model` | モデルID |
| `dish` | 料理識別子（例 `sukiya_gyudon`） |
| `step` | `S1`〜`S4` |
| `n_images` | 投入画像枚数 |
| `trial` | 試行番号（1〜3） |
| `temperature` | 既定0 |
| `prompt_version` | プロンプトのバージョン |
| `image_refs` | 画像のパス/ハッシュ（生base64は記録しない） |
| `response_raw` | モデルの生応答 |
| `parsed` | `{dish_name,total_kcal,protein_g,fat_g,carb_g,confidence}` |
| `usage` | `{input_tokens,output_tokens,total_tokens}` |
| `latency_ms` | 応答時間 |
| `cost_jpy` | `usage × config.yamlの単価` で算出 |
| `price_ref` | 単価の出典・確認日 |
| `status` | `ok`/`vision_unsupported`/`api_error`/`parse_error` |
| `error` | エラー内容（なければ null） |

## 5. 実装上の必須事項

- **base_url 切替で1本化**: OpenAI も ai& も同一の OpenAI 互換 SDK で叩く（`背景.md` §10）。
- **堅牢性**: vision非対応・APIエラー・JSON崩れを `status` で分類し、落とさず記録する。
- **再現性**: `temperature=0`、各条件3試行、条件は `config.yaml` 由来。乱数を使う箇所は seed 固定。
- **集計/可視化**: `data/logs` → `data/results`（CSV・図）を生成するスクリプトを用意し、図表は必ずスクリプト経由で再生成可能にする。

## 6. テスト/動作確認

- 小さく動かして確認（1モデル1枚など）してから本番。**課金が走る一括実行（120件等）は人間承認**（`/CLAUDE.md` §2）。
- 動作確認の手順・記録は `40_test/` に残す。
