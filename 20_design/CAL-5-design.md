---
対応課題: CAL-5
種別: 設計ドキュメント（draft → design-reviewer 承認で確定）
関連: CAL-3（モデルID・単価確定・Blocks）/ CAL-4（正解kcal確定）/ CAL-8 S2実行（本課題が Blocks）
更新日: 2026-07-05
改訂: r2（design-reviewer 指摘反映: S1〜S4既定化・cost_jpy通貨正規化・画像順検証・usageマッピング 等）
---

# CAL-5 共通実装 設計: OpenAI互換クライアント＋JSON固定出力＋実験ログ(JSONL)基盤

## 1. 目的

`base_url` の差し替えだけで **OpenAI** と **ai& Inference** を同一コードで叩ける比較基盤を作る。
全リクエストの入出力・usage・latency を **JSONL に1行1レコード**で記録し、以降の採点・可視化・
コスト集計（`CLAUDE.md §2-3` 数値手打ち禁止）の**唯一のデータソース**にする。

## 2. スコープ（本サイクル / 追いPR）

| 区分 | 対応AC | 本サイクル |
|------|--------|-----------|
| 複数画像(1〜4枚)の積み上げ送信の組み立て | AC2 | ✅ 実装＋モックテスト |
| 固定JSONスキーマのパース＋不正JSON時リトライ・失敗記録 | AC3 | ✅ 実装＋モックテスト |
| JSONL 1行記録（全フィールド） | AC4 | ✅ 実装＋モックテスト |
| 秘密情報は `.env` のみ／コード・ログに含めない | AC5 | ✅ 実装＋テスト |
| uv構築・ruff通過 | AC6 | ✅ |
| **base_url/api_key 切替で OpenAI・ai& 両方に実リクエスト成功** | **AC1** | ⏸ **キー到着後の追いPR**（`.env` 未投入のため）|

> AC1 が未達のため CAL-5 は本サイクルでは **Done にしない**（骨格＋モックテストを載せた PR をマージし、
> レビュー中のまま追いPRで疎通を足して完了する）。モデルID・単価は CAL-3 待ちのため `config.yaml` では
> `要確認` を保持し、コードは **config 参照**で組む（値に依存しない＝循環依存なし）。

### 2.1 AC1（追いPR）で実API相手に必ず再検証する項目
モックで代替できない「実API依存」の挙動。キー到着後の追いPRのチェックリストにする（取りこぼし防止）:
- `response_format`（json_schema / json_object）の**実サポート可否**（OpenAI / ai& 各々）
- `usage` の**実フィールド形状**（特に ai& 側。`prompt_tokens/completion_tokens/total_tokens` かどうか）
- vision 非対応時の**実エラー形**（`vision_unsupported` 判定の根拠にする）
- 画像 **data URL（base64）** がそのまま受理されるか
- ai& の `base_url` 値と、OpenAI 単価の **USD→JPY 為替**（`§7.1`）を CAL-3 で確定

## 3. アングル積み増しマニフェスト（本PoCの主役実験の入力定義）

Phase 1 は **コンビニ弁当1品**。**既定は憲法どおり S1〜S4（使用画像 1〜4枚）**（`CLAUDE.md §7 用語集`・
`30_development/CLAUDE.md §4`・`背景.md §6` の 120件コスト基準に整合）。撮影した6枚は**素材**とし、
真俯瞰から角度が広く散るよう**4枚を選抜**して S1〜S4 に割り当てる。残り2枚は予備（下記 §3.1 の任意拡張）。

| step | n_images | 追加画像（累積） | 目視の俯角 | 種別 |
|------|----------|------------------|-----------|------|
| S1 | 1 | IMG_0420 | ほぼ真上 | 既定 |
| S2 | 2 | ＋IMG_0423 | 斜め上（約55°） | 既定 |
| S3 | 3 | ＋IMG_0421 | やや低い（約40°） | 既定 |
| S4 | 4 | ＋IMG_0425 | 低い（約24°） | 既定 |
| （予備） | — | IMG_0422（約50°）/ IMG_0424（約30°） | — | S5/S6 拡張時に使用 |

- 角度は**実測値ではなく目視順**。順序（S1=真上…S4=最も低い）は本サイクルで6枚を目視確認済み
  （確認者: Claude / 2026-07-05。`convert-images` のコンタクトシート §8.1 で人間も再確認可能）。
- 割り当ては **`config.yaml` 由来**。選抜4枚の入替・並べ替えは config 編集のみ（コード非修正）。

### 3.1 S5/S6 への任意拡張（承認ゲート付き）
6枚全部を使う S5/S6 拡張は**任意**。採用する場合は実験プロトコルとコスト基準の変更にあたるため、
(1) `decisions/ADR-****` に決定（何を・なぜ・代替案・結果）を残し、(2) `CLAUDE.md §7 用語集`と
`30_development/CLAUDE.md §4` の「S1〜S4」を同時に更新し、(3) 増える件数と概算コストを再算出して
**課金一括実行の承認ゲートを再通過**する。既定では拡張しない。

> Phase 2 で「すき家牛丼」を2品目として追加（同形式の steps を config に足す）。
> 件数: Phase1 = 1品×S1〜S4×5モデル×3試行 = **60件** / Phase1+2 = 2品×… = **120件**（`背景.md §6` 基準に一致）。

## 4. モジュール構成（`30_development/`）

```
30_development/
  pyproject.toml           # uv / 依存（openai, pydantic, pyyaml, python-dotenv, pillow, pillow-heif; dev: pytest, ruff）
  config.yaml              # モデル・料金・為替・正解kcal・実験条件・manifest（数値集約。未確定は 要確認）
  README.md                # 実行方法（DoD: 30_development/ の実行方法）
  src/calorielens/
    __init__.py
    config.py              # config.yaml + .env のロード（api_key は環境変数名で参照し値は保持しない）
    images.py              # HEIC→JPEG変換・リサイズ・sha256・data URL・manifest 解決（step→累積パス）・コンタクトシート
    prompts.py             # プロンプトの版管理（v1）。「複数枚は同一料理の別アングル」である旨を明示
    schema.py              # 出力の固定スキーマ（pydantic: dish_name,total_kcal,protein_g,fat_g,carb_g,confidence）
    parsing.py             # 生応答→JSON抽出→検証、リトライ回数・失敗を status で分類
    client.py              # OpenAI互換クライアント（base_url/api_key切替）。messages組み立て・呼び出し・usage/latency取得・usage名マッピング
    cost.py                # cost_jpy = usage × config単価 →（USD建ては config の為替でJPY換算）。price_ref を持ち回る
    logger.py              # JSONL 1行1レコード書き出し（base64・キーは絶対に書かない）
    runner.py              # 1リクエスト実行（dish×step×model×trial→1ログ行）／sweep（課金一括はガード）
    __main__.py            # CLI: convert-images / dry-run(モック) / run(ガード付き)
  tests/
    conftest.py            # OpenAI SDK 呼び出しをモックする fixture、変換済みJPEGの fixture
    test_images.py         # HEIC変換・manifest累積・sha256・data URL
    test_parsing.py        # 正常JSON・コードフェンス付き・不正JSON→リトライ→parse_error
    test_logger.py         # 全フィールド出力・秘密情報/base64フィールド非混入
    test_cost.py           # USD建て×為替→JPY、JPY建てはそのまま
    test_runner_mock.py    # モック応答で end-to-end に1ログ行が ok で残る
  data/
    derived/               # HEIC→JPEG 変換キャッシュ（image_refs はこのパス＋sha256）
    logs/                  # 実験ログ（JSONL）
    results/               # 集計CSV・図（後続課題で生成）
```

- 秘密情報は**リポジトリルートの `.env`** から読む（`.env.example` は既に存在＝キー名のみ）。`config.py` は
  `find_dotenv()` で上位を辿ってルート `.env` をロードする（`CLAUDE.md §2-4`）。

## 5. 出力スキーマ（モデルに固定させる JSON）

```json
{ "dish_name": "string", "total_kcal": 0, "protein_g": 0.0, "fat_g": 0.0, "carb_g": 0.0, "confidence": 0.0 }
```

- pydantic v2 で検証。数値は数値型に強制（文字列で来たら coercion、無理なら parse_error）。
- **全モデル同一手法**（プロンプト指示＋抽出パース）で統一する。`response_format`（json_schema/
  json_object）はモデルごとの対応差が比較の公平性を損なうため**使わない**（experiment-validator 指摘）。
  対応可否自体は §2.1 で実確認するが、採用有無は別途 ADR で判断する。
- `confidence` は**寛容**に扱う（モデル自己申告でスケール・欠損が揺れるため、範囲を強制せず欠損は
  `null`）。`confidence` の不備で kcal/PFC の行ごと脱落（比較バイアス）を起こさない。`total_kcal`
  等の必須項目が欠ければ従来どおり `parse_error`。

## 6. パース／リトライ方針（AC3）

1. 生応答から JSON を抽出（```json フェンス→全体→先頭オブジェクト `raw_decode` の順。後続の地の文に強い）。
2. pydantic 検証。成功→ `status=ok`。
3. 失敗時は最大 `experiment.max_json_retries` 回まで再要求。**リトライは画像を再送せず**、直前の応答を
   「指定JSONのみで出し直せ」と整形させる（base64 再送コストを回避）。
4. 使い切っても不正なら `status=parse_error`、`error` に理由、`parsed=null`、生応答は `response_raw` に保持。
5. API例外は `status=api_error`、vision非対応の明示エラーは `status=vision_unsupported`。**落とさず1行記録**。
6. **課金の完全計上**: `usage` は全試行を合算し、`cost_jpy` はその合算 usage から算出。実呼び出し回数を
   `attempts` に記録する（リトライ分のコストが過少計上されないため。experiment-validator 重大指摘対応）。

## 7. JSONL ログスキーマ（確定・`30_development/CLAUDE.md §4` を本設計で正式化）

1リクエスト=1行。`data/logs/<run_id>.jsonl`。集計・図表は必ずこのログから再生成。

| フィールド | 型 | 説明 |
|-----------|----|------|
| `timestamp` | str(ISO8601) | 記録時刻 |
| `run_id` | str | 実行バッチ識別子（CLI引数 or 生成） |
| `provider` | str | `openai` / `aiand` |
| `base_url` | str/null | 使用エンドポイント（OpenAI既定は null 可） |
| `model` | str | モデルID |
| `dish` | str | 料理ID（例 `conbini_bento`） |
| `step` | str | `S1`〜`S4`（config由来。S5/S6 拡張時は §3.1） |
| `n_images` | int | 投入画像枚数 |
| `trial` | int | 試行番号（1〜`experiment.trials`、既定3） |
| `temperature` | number | 既定0 |
| `seed` | int/null | 再現性のため送る（対応プロバイダ・config由来。`30_development/CLAUDE.md §5`） |
| `prompt_version` | str | プロンプト版（例 `v1`） |
| `image_refs` | array | `[{path, sha256}]`（**生base64は記録しない**） |
| `response_raw` | str/null | モデル生応答（最後の試行の応答） |
| `parsed` | object/null | `{dish_name,total_kcal,protein_g,fat_g,carb_g,confidence}`（confidence は null 可） |
| `usage` | object/null | `{input_tokens,output_tokens,total_tokens}`（**全試行の合算**。SDKの `prompt/completion_tokens` を**この名前にマッピング**。ai& 側の実形状は §2.1 で確認、取得不能なら null） |
| `attempts` | int | 実際に API を呼んだ回数（1＋リトライ回数）。コスト・リトライ挙動の復元用 |
| `latency_ms` | int/null | 最後の試行の応答時間 |
| `cost_jpy` | number/null | `usage × config単価`で算出（§7.1・手打ち禁止） |
| `price_ref` | str/null | 単価＋為替の出典・確認日（config由来） |
| `status` | str | `ok`/`vision_unsupported`/`api_error`/`parse_error` |
| `error` | str/null | エラー内容（なければ null） |

### 7.1 コスト計算と通貨正規化（中指摘の反映）
- OpenAI 単価は **USD/1M**、ai& は **JPY/1M**。`cost_jpy` を全プロバイダで**円**に揃えて比較可能にする
  （`背景.md §8` の1日コスト逆算の前提）。為替レートも `数値手打ち禁止` の対象。
- `config.yaml` に各モデルの `price_input_per_1m` / `price_output_per_1m` / `price_currency`(`usd`|`jpy`) /
  `price_ref`、および `pricing.fx.usd_jpy`(+ `ref`) を持つ（すべて本サイクルは `要確認`）。
- `cost.py`: `native = input/1e6*pin + output/1e6*pout`。`price_currency=usd` なら `× fx.usd_jpy` で JPY 化、
  `jpy` はそのまま。`price_ref` はモデル単価＋（USD時）為替の出典・確認日を連結してログに残す。

## 8. HEIC→JPEG 変換（AC2 の前提・Vision入力の実体）

- 撮影は HEIC。Vision API は JPEG/PNG が無難なため、`images.py` で **pillow-heif** により JPEG 変換。
- 変換は決定的（長辺 `image.max_dim` 既定1024・quality 85）。`data/derived/<stem>.jpg` にキャッシュ。
- `image_refs` は **derived の相対パス＋sha256**。送信時のみ base64 data URL 化（ログには残さない）。
- 変換自体はネット不要なので本サイクルで実装・テストできる。

### 8.1 画像順の目視検証（中指摘の反映）
- `convert-images` は変換に加え、S1〜S4（＋予備）を並べた**コンタクトシート** `data/derived/contact_sheet.jpg`
  を出力する。俯瞰→斜めの順序（S1=真上…S4=最も低い）を人間が目視再確認でき、記事②のトレーサビリティに使う。

## 9. 秘密情報（AC5）

- `api_key` は **環境変数名だけ** を config に持ち（例 `api_key_env: OPENAI_API_KEY`）、値は ルート `.env`＋`os.environ`。
- キーやbase64を **ログ・例外メッセージ・commit に含めない**。test で「ログ文字列にキーが出ない」ことを検証。
- `.env.example`（ルート・既存）にキー名のみ記載を維持。`.env` はコミット禁止。

## 10. テスト方針（本サイクルの完了判定・AC1以外）

- 実APIは呼ばない。`conftest.py` で client の呼び出し関数をモックし、canned な応答/usage を返す。
- 画像 fixture は変換済み弁当JPEG（`data/derived/`）を使用。
- ruff format / check 通過、pytest 全緑を本サイクルの完了条件とする。

## 11. 未確定（要確認・本サイクルでは埋めない）

| 項目 | 依存課題 | 扱い |
|------|----------|------|
| モデルID・入出力単価・price_currency・vision対応 | CAL-3 | `config.yaml` に `要確認`。確定後に差し替え |
| 為替 `pricing.fx.usd_jpy`（レート・出典・確認日） | CAL-3 | 同上（USD単価のJPY換算に必須） |
| 弁当の正解 kcal / PFC / 商品名 / 出典 | CAL-4 | 同上（`dishes[].truth` を `要確認`） |
| 実キーでの疎通（AC1）＋ §2.1 の実API依存項目 | APIキー投入 | 追いPRで実施し CAL-5 を完了 |
