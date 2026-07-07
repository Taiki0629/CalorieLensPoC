---
対応課題: CAL-5
種別: 動作確認記録（Flow② ⑥ テスト/動作確認）
実施日: 2026-07-05
実施者: Claude（Opus）
---

# CAL-5 共通実装 動作確認

§1-3 は骨格＋モックによる AC2〜6 の確認（2026-07-05）。§5 に **AC1 ライブ疎通**（キー投入後・
2026-07-08 追記）を記録。環境は `30_development` で `uv sync` 済み。

## 1. lint / 単体テスト

```bash
cd 30_development
uv run ruff format --check .   # → 19 files already formatted
uv run ruff check .            # → All checks passed!
uv run pytest -q               # → 37 passed
```

- テスト内訳: parsing（フェンス/前後文/raw_decode/coercion/confidence寛容/必須欠落）、images（HEIC変換・
  manifest累積・sha256・data URL）、cost（USD×為替→JPY・JPY・未確定=None・通貨欠損=None）、logger
  （ホワイトリスト・秘密情報非混入・1行1レコード）、client（usage名マッピング object/dict/欠損・messages構築）、
  runner（ok/parse_error(リトライ)/api_error/vision_unsupported/キー無し/base_url未設定・**リトライ課金積算**・
  **image_refs相対**・条件列挙数）。

## 2. CLI スモーク

### 2.1 convert-images（AC2 前提）
```bash
uv run calorielens convert-images
```
→ HEIC 6枚を `data/derived/*.jpg`（長辺1024・q85・EXIF正立）に変換、`contact_sheet.jpg` を生成。
sha256 は EXIF 補正前後で不変（例 IMG_0420=`8676d08b8970…`）＝二重回転なし・決定的変換を確認。

### 2.2 dry-run（AC2/AC3/AC4：モックで経路確認）
```bash
uv run calorielens dry-run --step S3
```
→ `status=ok` / `n_images=3`（複数画像の積み上げ）/ parsed 取得 / usage 名マッピング動作 /
`cost_jpy=null`（単価 `要確認` のため正しく None）。出力は **`data/logs/_dryrun/` に隔離**され、
実ログ `data/logs/*.jsonl` を汚さないことを確認（`ls data/logs/*.jsonl` → 該当なし）。

### 2.3 課金ガード（承認ゲート）
```bash
uv run calorielens run --run-id smoke2      # --allow-paid なし
```
→ `[停止] これは課金一括実行に該当します…実行していません` を表示し **exit=2**（CLAUDE.md §2）。
`--allow-paid` 未指定では実 API を1件も叩かないことを確認。

## 3. AC 別の充足状況

| AC | 内容 | 本サイクル | 根拠 |
|----|------|-----------|------|
| AC2 | 複数画像(1〜4)の積み上げ送信 | ✅ | dry-run S3 で n_images=3、`test_run_one_ok`(S2=2枚) |
| AC3 | 固定JSONパース＋不正時リトライ・失敗記録 | ✅ | `test_parsing.*` / `test_run_one_parse_error_retries`（3回・parse_error）|
| AC4 | JSONL 1行記録（全フィールド） | ✅ | `LOG_FIELDS` 21+attempts、`test_logger.*` |
| AC5 | 秘密情報は .env のみ | ✅ | ホワイトリスト・`test_secret_not_written` |
| AC6 | uv構築・ruff通過 | ✅ | 上記 §1 |
| AC1 | OpenAI・ai& 実キー疎通 | ✅ | §5 ライブ疎通（`smoke` で 4/4 ok・両provider）|

## 4. 実API依存項目の解消（設計 §2.1）
- usage 実形状・data URL 受理・seed 対応可否・為替: CAL-3 と §5 smoke の実応答で確定（seed 4モデル受理、
  usage は input/output/total を実取得、data URL 受理OK、為替 161.87）。
- vision 非対応の実エラー形: 採用4モデルは全て vision 対応のため本実験では発火しない。分類ロジック
  （`_classify_exception`）は単体テストで担保済み（`test_run_one_vision_unsupported`）。

## 5. AC1 ライブ疎通（2026-07-08・キー投入後）

キー投入後、**課金一括ではない疎通専用サブコマンド `smoke`** を追加（enabled 各1件・S1・trial1＝
本番の全step×全trialにならない）。共通 runner（`run_one`）経由で base_url 切替により両provider へ
画像付きリクエストを実送信する。

```bash
uv run calorielens smoke --run-id cal5-ac1
```

結果（`data/logs/_smoke/cal5-ac1.jsonl`・4行）:

| provider | model | status | usage(in/out) | cost_jpy |
|----------|-------|:------:|---------------|---------:|
| openai | gpt-5.4 | ok | 1113 / 76 | 0.635 |
| openai | gpt-5.4-mini | ok | 1113 / 56 | 0.176 |
| aiand | google/gemma-4-31b-it | ok | 448 / 76 | **0.021** |
| aiand | moonshotai/kimi-k2.6 | ok | 1230 / **2144** | **1.384** |

- **base_url 切替で OpenAI・ai& 双方に画像付きリクエストが成功**（4/4 ok・両provider）＝AC1 充足。
- JSONL 完全性を検証: 全行 21 必須フィールド欠損なし・`image_refs` は相対パス＋sha256・**キー非混入**
  （`sk-`/`api_key` の混入なし）・usage を実取得・`cost_jpy`＝usage×config単価×為替で算出。
- **考察の種**: Kimi K2.6 は出力 2144 トークン（推論）で 1コール **¥1.38＝gpt-5.4(¥0.63)より高い**。
  「per-token 単価が安くても実コールは高い」を実データで確認（§8 コスト軸で回収）。
- 安全性: `smoke` は `--allow-paid` 不要だが「enabled 各1件」に限定。本番一括 `run` は従来どおり
  `--allow-paid`＋人間 GO が停止点（`test_cli.test_cmd_smoke_*`・課金ガードは §2.3）。
