---
name: ticket
description: 要件を Jira 課題(CAL)ドラフト化 → ticket-reviewer でレビュー → Jira書き込み まで行う（フロー①）。単発の起票に使う。引数で起票したい要件・作業の概要を受け取る。
---

フロー①（Jira起票）を実行する。段ごとにモデルを使い分ける。要件は引数で渡される。

## 手順
1. **ドラフト化（Fable）**: `10_management/20_Jira運用規約.md` と `10_management/templates/Jira課題テンプレート.md` に沿って、要件を Jira 課題ドラフトに落とす。課題タイプを判断し、説明欄に **背景/目的・受け入れ条件(AC)・DoD・関連** を記入。AC は合否を機械的に言える粒度で。まだ書き込まない。
2. **レビュー（Opus）**: `ticket-reviewer` サブエージェント（agent type: `ticket-reviewer`）にドラフトを渡してレビューさせる。「要修正」なら指摘を反映して 1〜2 に戻る（最大2回）。
3. **書き込み（Fable）**: 「起票可」になったら `createJiraIssue`（cloudId=16ca1158-2cf4-4eb9-ba6a-8f0f2b089765, projectKey=CAL）で作成。エピック配下は親を指定。作成した課題キー・URLを報告。

注意: 単発の作成は自動でよい。**削除・大量一括変更は人間承認**（`/CLAUDE.md` §2）。一括起票は Workflow `intake`（`.claude/workflows/intake.js`）を使う。
