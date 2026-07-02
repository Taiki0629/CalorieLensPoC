---
name: article-review
description: Qiita記事の原稿（50_output 配下）を article-reviewer サブエージェントでレビューする。記事①②の投稿前に使う。引数で原稿ファイルのパスを受け取る。
---

`article-reviewer` サブエージェント（agent type: `article-reviewer`）を起動し、対象原稿をレビューさせる。

- 対象: 引数で渡されたファイルパス。未指定なら `50_output/` 配下の最新原稿。
- 判定（投稿可/要修正）と指摘（数値の出所・出典・注意書き・過度な一般化）を要約して報告する。
