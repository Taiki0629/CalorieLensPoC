export const meta = {
  name: 'dev-cycle',
  description: 'フロー②: 指定Jira課題を 起草→設計レビュー→実装→コードレビュー→テスト→記録→クローズ まで自律実行（全Opus）。課金一括実行の手前で停止する。',
  phases: [
    { title: '起草', detail: '設計/方針を 20_design に起草', model: 'opus' },
    { title: '設計レビュー', detail: 'design-reviewer で点検', model: 'opus' },
    { title: '実装', detail: 'コードを実装', model: 'opus' },
    { title: 'コードレビュー', detail: 'code-review / experiment-validator', model: 'opus' },
    { title: 'テスト', detail: '動作確認', model: 'opus' },
    { title: 'クローズ', detail: '記録・commit・push・PR・マージ・Jira Done', model: 'opus' },
  ],
}

const CLOUD_ID = '16ca1158-2cf4-4eb9-ba6a-8f0f2b089765'

// args: 課題キーの配列（例 ["CAL-12","CAL-13"]）または文字列1件
const keys = Array.isArray(args) ? args : args ? [args] : []
if (keys.length === 0) {
  return { error: 'args に処理する課題キーを渡してください（例 ["CAL-12"]）' }
}

const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    verdict: { type: 'string', enum: ['OK', '要修正'] },
    issues: { type: 'array', items: { type: 'string' } },
  },
  required: ['verdict', 'issues'],
}

const RULES = `本PoCの規約に従うこと: /CLAUDE.md（最重要ルール: 日本語・推測禁止・数値手打ち禁止・秘密情報は.env）、10_management/10_開発プロセス規約.md、30_development/CLAUDE.md。`

async function runTicket(key) {
  const notes = []

  // ① 要件確認 ＋ ② 起草
  phase('起草')
  await agent(
    `${RULES}\n課題 ${key}（cloudId=${CLOUD_ID}）に取り組む。まず ToolSearch で "select:mcp__atlassian__getJiraIssue,mcp__atlassian__transitionJiraIssue,mcp__atlassian__addCommentToJiraIssue" を読み込み、getJiraIssue で AC/DoD を確認する。課題を「進行中」に遷移。\n次に設計/方針を 20_design/${key}-design.md に draft で書く（背景.md の目的整合・AC網羅・再現性・推測禁止を満たす）。`,
    { model: 'opus', phase: '起草', label: `起草:${key}` },
  )

  // ③ 設計レビュー（最大2回ループ）
  phase('設計レビュー')
  for (let i = 0; i < 2; i++) {
    const rev = await agent(
      `あなたは設計レビュー担当。まず .claude/agents/design-reviewer.md を読み、そのチェックリスト（目的整合・AC網羅・推測検出・再現性・スコープ・記事化）に従って 20_design/${key}-design.md をレビューせよ。判定（OK/要修正）と重大指摘を返す。`,
      { model: 'opus', schema: VERDICT_SCHEMA, phase: '設計レビュー', label: `設計レビュー:${key}:r${i + 1}` },
    )
    if (rev.verdict === 'OK') break
    await agent(
      `${RULES}\n設計 20_design/${key}-design.md に次の重大指摘がある。反映して修正せよ。\n- ${rev.issues.join('\n- ')}`,
      { model: 'opus', phase: '起草', label: `設計修正:${key}:r${i + 1}` },
    )
    if (i === 1) notes.push('設計レビュー: 2回で未解決の指摘が残った可能性')
  }

  // ④ 実装
  phase('実装')
  await agent(
    `${RULES}\n課題 ${key} の設計 20_design/${key}-design.md に従い実装する。ブランチ feat/${key}-... を作成し、30_development 配下にコードを書く。課題キーをコミットに含める。\n重要: 課金が発生するAPIの一括実行（本番の120リクエスト等）は絶対に実行しない。必要なら小規模のdry-run/モックに留める。`,
    { model: 'opus', phase: '実装', label: `実装:${key}` },
  )

  // ⑤ コードレビュー（最大2回ループ／未解決はエスカレーション）
  phase('コードレビュー')
  let codeOk = false
  for (let i = 0; i < 2; i++) {
    const rev = await agent(
      `${RULES}\n課題 ${key} の実装（feat/${key} ブランチの差分）をレビューせよ。実験関連コードは特に「数値手打ち禁止・ログ完全性・コスト算出・堅牢性・再現性・秘密情報」を確認（experiment-validator の観点）。汎用のバグ・簡潔性も見る。判定と重大指摘を返す。`,
      { model: 'opus', schema: VERDICT_SCHEMA, phase: 'コードレビュー', label: `コードレビュー:${key}:r${i + 1}` },
    )
    if (rev.verdict === 'OK') { codeOk = true; break }
    await agent(
      `${RULES}\n課題 ${key} の実装に次の重大指摘がある。修正せよ。\n- ${rev.issues.join('\n- ')}`,
      { model: 'opus', phase: '実装', label: `コード修正:${key}:r${i + 1}` },
    )
  }
  if (!codeOk) {
    notes.push('コードレビュー未通過のためクローズを保留（人間エスカレーション）')
    return { key, status: 'escalated', notes }
  }

  // ⑥ テスト/動作確認
  phase('テスト')
  await agent(
    `${RULES}\n課題 ${key} の実装が動くか小さく確認する（課金一括実行はしない）。手順と結果を 40_test/${key}-test.md に記録する。`,
    { model: 'opus', phase: 'テスト', label: `テスト:${key}` },
  )

  // ⑦ 記録 ＋ ⑧ クローズ（commit/push/PR/マージ/Jira Done）
  phase('クローズ')
  const close = await agent(
    `${RULES}\n課題 ${key} をクローズする。\n1. 介入ログを 10_management/介入ログ.md に1段落追記（テンプレ: templates/介入記録テンプレート.md）。\n2. commit → push → PR作成 → マージ（すべて自律。秘密情報混入を git diff で確認）。\n3. ToolSearch で "select:mcp__atlassian__transitionJiraIssue,mcp__atlassian__addCommentToJiraIssue" を読み込み、課題 ${key} を「完了」に遷移し、成果（PR・成果物パス）をコメントで残す。\n注意: この課題が課金一括実行を要する場合は、実行せず準備完了だけ報告し、Jiraは「完了」にせずコメントで人間承認待ちと記す。`,
    { model: 'opus', phase: 'クローズ', label: `クローズ:${key}` },
  )
  return { key, status: 'done', notes, close }
}

const results = []
for (const key of keys) {
  log(`▶ ${key} のサイクル開始`)
  results.push(await runTicket(key))
}
return results
