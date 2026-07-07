---
対応課題: CAL-3（S0-1: モデルID・料金・vision対応の実API確定）
種別: 仕様ドキュメント（比較対象モデルの正式確定）
確認日: 2026-07-08
確認方法: 実API `/models`（capability・料金）＋ OpenAI 公式料金ページ ＋ vision 実送信テスト
---

# 比較対象モデルの確定（CAL-3）

推測を排し（CLAUDE.md §2-2）、モデルID・vision対応・料金を **実API と公式情報**で確定した記録。
数値・IDはすべて本表と `30_development/config.yaml` に集約し、記事・コードに直書きしない。

## 0. 一次証跡（すべて `90_resources/CAL-3_evidence/`＝コミット対象・永続）

| 証跡 | 取得元 | 保存先ファイル |
|------|--------|--------|
| ai& `/models` 生レスポンス（9モデル・capability・料金） | `https://api.aiand.com/v1/models`（2026-07-08） | `aiand_models.json` |
| OpenAI `/models` 生レスポンス（122モデル） | `https://api.openai.com/v1/models`（2026-07-08） | `openai_models.json` |
| OpenAI 料金スナップショット（gpt-5.4/5.4-mini/5.4-nano/5.5） | 公式 pricing ページ引用（2026-07-08） | `openai_pricing_snapshot.md` |
| vision 実送信テスト結果（4モデル・生応答/usage） | `cal3_vision_probe.py`（下記） | `vision_probe_result.json` |
| seed 受理テスト結果（4モデル） | `cal3_finalize_evidence.py`（下記） | `seed_probe_result.json` |
| 実証スクリプト（再現用） | 使い捨てだが監査のため保存 | `cal3_vision_probe.py`, `cal3_finalize_evidence.py` |

> 下表 §2-3・§5 の数値・応答は **`vision_probe_result.json` / `seed_probe_result.json` の保存値と一致**
> させている（記録＝証跡）。応答テキストは temperature 既定で**毎回変動**するため「ある保存ランの応答」
> として扱い、vision 対応可否（status=ok）と usage の桁感だけを確定事実とする。

## 1. ai& Inference（vision 対応の実API判定）

`/models` の `capabilities` 配列に `vision` を含むかで判定（画像非対応モデルは画像リクエストが
拒否される仕様のため、含むモデルのみ採用可）。単価は同レスポンスの `input_per_1m` / `output_per_1m`
（通貨 `usd`）。※ **9モデル中 vision 対応は 3 つのみ**。

| モデルID | vision | 入力/出力 $/1M | ctx | 採否 | 備考 |
|----------|:------:|----------------|-----|:----:|------|
| **google/gemma-4-31b-it** | ✅ | 0.20 / 0.50 | 262k | **採用** | ai& 最安 vision＝激安の目玉 |
| **moonshotai/kimi-k2.6** | ✅ | 0.85 / 3.50 | 262k | **採用** | 中量級。推論トークンが多め（後述） |
| moonshotai/kimi-k2.7-code | ✅ | 0.75 / 3.50 | 262k | 除外 | code 特化。料理写真タスクに不適 |
| qwen/qwen3.6-27b | ❌ | 0.00 / 0.00 | 262k | 除外 | **¥0だが vision 非対応→採用不可** |
| openai/gpt-oss-120b | ❌ | 0.15 / 0.60 | 131k | 除外 | vision 非対応 |
| deepseek-ai/deepseek-v4-flash | ❌ | 0.15 / 0.25 | 1M | 除外 | vision 非対応 |
| deepseek-ai/deepseek-v4-pro | ❌ | 1.00 / 2.50 | 1M | 除外 | vision 非対応 |
| zai-org/glm-5.2 | ❌ | 1.00 / 4.00 | 1M | 除外 | vision 非対応 |
| zai-org/glm-5.1 | ❌ | 1.40 / 4.40 | 203k | 除外 | vision 非対応 |

> **重要な発見**: `背景.md` §3・§7 は「¥0 の Qwen3.6-27B」を激安の目玉と想定していたが、
> 実APIで **Qwen3.6-27B は vision 非対応**と判明。§3 の⚠️「vision は推測せず capability で確定」が
> 的中。**激安 vision の主役は Gemma 4（$0.20/$0.50）に置き換える**（背景.md を更新）。

## 2. OpenAI（公式料金＋vision 実証）

料金出典: `https://developers.openai.com/api/docs/pricing`（確認日 2026-07-08）。
vision は「pricing ページの表記」ではなく **実際にテスト画像を送信して受理を確認**（下記 §3）。

| モデルID | vision | 入力/出力 $/1M | cached入力 | 採否 | 備考 |
|----------|:------:|----------------|-----------|:----:|------|
| **gpt-5.4** | ✅ | 2.50 / 15.00 | 0.25 | **採用** | 本番推奨の中量級 |
| **gpt-5.4-mini** | ✅ | 0.75 / 4.50 | 0.075 | **採用** | コスト最適化版 |
| gpt-5.4-nano | 要確認 | 0.20 / 1.25 | 0.02 | 保留 | 余力あれば追加検討 |
| gpt-5.5 | 要確認 | 5.00 / 30.00 | 0.50 | 対象外 | フラッグシップだが高価（背景.md §3） |

> `背景.md` §3 の想定値（5.4=$2.50/$15・5.4-mini=$0.75/$4.50・5.5=$5/$30）は公式ページと **完全一致**。

## 3. vision 実証（テスト画像 1 枚の実送信）

画像 `30_development/data/derived/IMG_0420.jpg`（コンビニ弁当・ほぼ真上）を各モデルに送信し、
「料理名を短く」で正常応答を確認（アドホック `cal3_vision_probe.py`。共通実装は不使用）。
以下は保存ラン `vision_probe_result.json`（tested_at 2026-07-08T01:06:45+09:00）の**そのままの値**。

| モデル | 応答 | usage(prompt/completion) | 判定 |
|--------|------|--------------------------|------|
| gpt-5.4 | 「幕の内弁当」 | 953 / 9 | ✅ vision可 |
| gpt-5.4-mini | 「お弁当」 | 953 / 7 | ✅ vision可 |
| google/gemma-4-31b-it | 「弁当」 | 304 / 2 | ✅ vision可 |
| moonshotai/kimi-k2.6 | 「そぼろ弁当」 | 1074 / **3494** | ✅ vision可・推論トークン突出（20s） |

> **考察の種1（ブレ）**: 同一画像・同一プロンプトでも応答は run 毎に変動（別 run では gpt-5.4=「弁当/そぼろ弁当」等）。
> これは §7-A「temperature=0 でも出るブレ」を CAL-3 段階で早くも実証したもの。精度の断定は本実験（3試行）で行う。
> **考察の種2（コスト）**: Kimi K2.6 は回答前の推論トークンが突出（この run で 3494・別 run では 645）。
> gpt 系は completion 一桁、Gemma は 2〜3。「per-token 単価が安くても 1 コールは高い/遅い」典型例で、§8
> コスト試算・latency 軸で回収する。画像のトークン化も差が大きい（prompt: gpt953 / gemma304 / kimi1074）。

## 4. 為替（fx）

| 項目 | 値 | 出典・確認日 |
|------|----|--------------|
| USD/JPY | 161.87 | tradingeconomics.com/japan/currency（2026-07-07 スナップショット・確認日2026-07-08） |

> **両provider とも USD 建て**（ai& `/models` も `currency:usd`）。よって為替は §8 の絶対円換算
> （「1日◯円」）だけに効き、**OpenAI vs ai& の相対コスト比較には影響しない**。

## 5. seed 対応

`seed=12345` 付きテキスト最小リクエストで **採用4モデルすべて**受理を確認
（`cal3_finalize_evidence.py`・保存値 `seed_probe_result.json`）。

| provider | モデル | seed_accepted | config `send_seed` |
|----------|--------|:------:|:------:|
| openai | gpt-5.4 | ✅ | true |
| openai | gpt-5.4-mini | ✅ | true |
| aiand | google/gemma-4-31b-it | ✅ | true |
| aiand | moonshotai/kimi-k2.6 | ✅ | true |

> 「受理」＝パラメータが拒否されない、の意（4モデルとも実証。推定は残さない）。決定性そのものは
> 未検証で、§3 のとおり応答は run 毎に変動しうるため、再現性は `temperature=0` と 3 試行の分散記録で担保する。

## 6. 採用ラインナップと本番規模（要 GO）

**採用 4 モデル**: `gpt-5.4` / `gpt-5.4-mini` / `google/gemma-4-31b-it` / `moonshotai/kimi-k2.6`。

- `背景.md` §8 の当初想定は「5 モデル＝120 リクエスト」だったが、ai& の vision 対応が 3 つに限られ、
  うち code 特化の kimi-k2.7-code を除外したため **4 モデル**に調整。
- 本番規模の目安: 2品 × 4step(S1〜S4) × 4モデル × 3試行 = **96 リクエスト**（+ S5/S6 は任意）。
- 本番一括実行は課金が走るため **人間の GO が停止点**（CLAUDE.md §2）。3モデル目の ai& や
  gpt-5.4-nano／gpt-5.5 を加えるかは GO 時に最終決定できる。

## 7. 未確定（要確認として残す）

- gpt-5.4-nano / gpt-5.5 の vision 対応は未実証（採用しないため保留）。
- kimi-k2.7-code は vision 対応だが不採用（code 特化）。採用に転じる場合は別途実証。
- 為替は日次変動するスナップショット。§8 の絶対値提示時に確認日を併記して再取得してよい。
