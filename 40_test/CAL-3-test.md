---
対応課題: CAL-3（S0-1: モデルID・料金・vision対応の実API確定）
種別: 動作確認記録（Flow② ⑥ テスト/動作確認）
実施日: 2026-07-08
実施者: Claude（Opus）
---

# CAL-3 実API確認 動作確認

実 API（`/models`・chat.completions）を実際に叩き、モデルID・料金・vision対応・seed受理を
確定した記録。実証スクリプトは共通実装を使わない使い捨て（循環依存回避）だが、監査・再現のため
永続コピーを `90_resources/CAL-3_evidence/` に保存（生証跡 json も同ディレクトリ）。
課金は vision 実証 4 コール＋seed 実証 2 コール＝**最小の疎通のみ**（一括実行ではない）。

## 1. /models 疎通とモデル一覧（無料）

```bash
cd 30_development
# /models 生レスポンスを取得日時付きで保存＋採用4モデルの seed 受理を実証
uv run python ../90_resources/CAL-3_evidence/cal3_finalize_evidence.py
```

- OpenAI `/models`: HTTP 200・122 モデル（gpt-5.4 / gpt-5.4-mini / gpt-5.5 等を確認）。
- ai& `/models`: HTTP 200・9 モデル。**`capabilities` に `vision` を含むのは 3 つのみ**
  （gemma-4-31b-it / kimi-k2.6 / kimi-k2.7-code）。Qwen3.6-27B は¥0だが vision 非対応。
- 生レスポンスを取得日時付きで保存: `90_resources/CAL-3_evidence/{openai,aiand}_models.json`（AC1）。

## 2. vision 実証（テスト画像1枚を実送信）

```bash
uv run python ../90_resources/CAL-3_evidence/cal3_vision_probe.py
```

画像 `data/derived/IMG_0420.jpg`（コンビニ弁当・ほぼ真上）を4モデルへ送信し全て `status=ok`。
以下は永続保存ラン `90_resources/CAL-3_evidence/vision_probe_result.json` の値（記録＝証跡）:

| モデル | 応答 | prompt/completion tok |
|--------|------|----------------------|
| gpt-5.4 | 幕の内弁当 | 953 / 9 |
| gpt-5.4-mini | お弁当 | 953 / 7 |
| google/gemma-4-31b-it | 弁当 | 304 / 2 |
| moonshotai/kimi-k2.6 | そぼろ弁当 | 1074 / **3494**（20s） |

→ OpenAI 側の vision も pricing 表記ではなく実送信で確認（AC3・AC5）。応答テキストは**run 毎に変動**
（別 run では gpt-5.4「弁当」等）＝§7-A のブレを早期実証。Kimi は回答前の推論トークンが突出
（この run 3494・別 run 645＝コスト/速度考察の種）。

## 3. seed 受理の実証

`seed=12345` 付き最小テキストリクエストで、**採用4モデルすべて受理（エラーなし）**
（`90_resources/CAL-3_evidence/seed_probe_result.json`）。→ config `send_seed:true`（推定を残さず全実証）。
`temperature=0` 併用。

## 4. config 反映と手打ち禁止の担保

```bash
uv run python -c "from calorielens import config; from calorielens.cost import compute_cost_jpy; \
cfg=config.load_config(); ms=config.enabled_models(cfg); fx=cfg['pricing']['fx']; \
u={'input_tokens':953,'output_tokens':9}; \
[print(m['id'], compute_cost_jpy(u,m,fx)) for m in ms]"
```

- `enabled` 4 モデルを確認。実 usage(953/9) からの実コスト(JPY)算出が機能:
  gpt-5.4 ¥0.4075 / gpt-5.4-mini ¥0.1223 / gemma-4 **¥0.0316** / kimi-k2.6 ¥0.1362。
  → **Gemma 4 は gpt-5.4 の約 1/13**（激安の目玉が数値で裏づく。単価は config 由来＝手打ちなし）。
- 単価・為替は 20_design/CAL-3-モデル確定.md と `aiand_models.json`／公式ページに一致（確認日2026-07-08）。

## 5. lint / 単体テスト

```bash
uv run pytest -q          # → 56 passed
uv run ruff check .       # → All checks passed!
uv run ruff format --check .  # → 27 files already formatted
```

- **テスト密閉化を追加**: `.env` に実キーを入れた結果、`resolve_provider`→`load_env`(load_dotenv) が
  実キー/実 base_url を復活させ、「キー無し」「base_url 未設定」検証（`test_runner_mock.py`）が
  失敗した。conftest に autouse フィクスチャ `_hermetic_env` を追加し `config.load_env` を無効化して
  ユニットテストを実 .env から隔離（再発防止）。

## 6. AC 充足

| AC | 状況 | 根拠 |
|----|------|------|
| /models 生レスポンスを取得日時付き保存 | ✅ | 90_resources/CAL-3_evidence/*.json |
| vision 対応モデルID一覧（根拠・確認日・出典）を 20_design に記載 | ✅ | CAL-3-モデル確定.md §1-2 |
| 採用候補にテスト画像送信し正常応答をログ確認 | ✅ | §2・cal3_vision_result.json |
| 各採用モデルの入出力単価（公式出典・確認日） | ✅ | config.yaml・CAL-3-モデル確定.md |
| OpenAI 2モデルのID・料金・vision を公式再確認 | ✅ | §2・公式pricing一致 |
| 未確定は「要確認」明示・断定なし | ✅ | nano/5.5/kimi-code を要確認・保留で明記 |
