# OpenAI API 料金スナップショット（CAL-3 証跡）

- 取得日: 2026-07-08
- 出典（一次）: OpenAI 公式 pricing ページ `https://platform.openai.com/docs/pricing`
  （301 リダイレクト先 `https://developers.openai.com/api/docs/pricing`）
- 取得方法: WebFetch で公式ページを取得。`openai_models.json`（/models）は料金フィールドを持たない
  （ID のみ）ため、料金は本スナップショットで補完する。

| モデル | 入力 $/1M | 出力 $/1M | cached入力 $/1M | 採否 |
|--------|----------:|----------:|----------------:|:----:|
| gpt-5.4 | 2.50 | 15.00 | 0.25 | 採用 |
| gpt-5.4-mini | 0.75 | 4.50 | 0.075 | 採用 |
| gpt-5.4-nano | 0.20 | 1.25 | 0.02 | 保留 |
| gpt-5.5 | 5.00 | 30.00 | 0.50 | 対象外（高価） |

- 上記は `10_management/背景.md` §3 の想定値と完全一致（GPT-5.4=$2.50/$15、Mini=$0.75/$4.50、5.5=$5/$30）。
- vision 対応は pricing ページの表記に依存せず、`vision_probe_result.json`（テスト画像の実送信）で確定。
- 注意: 料金は改定されうる。本番一括実行（課金・要 GO）の直前に確認日を更新して再取得することを推奨。
