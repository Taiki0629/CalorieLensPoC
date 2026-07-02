---
name: design-review
description: 設計/仕様ドキュメント（20_design 配下の draft）を design-reviewer サブエージェントでレビューする。設計を確定する前に使う。引数でレビュー対象のファイルパスを受け取る。
---

`design-reviewer` サブエージェント（agent type: `design-reviewer`）を起動し、対象ドキュメントをレビューさせる。

- 対象: 引数で渡されたファイルパス。未指定なら `20_design/` 配下の直近 draft。
- サブエージェントの判定（APPROVE可/要修正）と指摘を要約して報告し、重大指摘があれば対応方針を提案する。
