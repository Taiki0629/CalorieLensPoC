---
対応課題: CAL-5
種別: 動作確認記録（Flow② ⑥ テスト/動作確認）
実施日: 2026-07-05
実施者: Claude（Opus）
---

# CAL-5 共通実装 動作確認

実APIは叩かない（AC1 のライブ疎通はキー到着後の追いPR）。本記録は骨格＋モックによる
AC2〜6 の確認。環境は `30_development` で `uv sync` 済み。

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
| AC1 | OpenAI・ai& 実キー疎通 | ⏸ 追いPR | API キー未投入（CAL-3/§2.1 実確認事項）|

## 4. 既知の残作業（キー到着後）
- AC1 ライブ疎通（`base_url`/`api_key` 切替で OpenAI・ai& 両方に画像付き実リクエスト成功）。
- 設計 §2.1 の実API依存項目（usage 実形状・vision非対応の実エラー形・data URL 受理・seed 対応可否・為替）。
