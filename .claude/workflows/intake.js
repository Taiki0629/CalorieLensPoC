export const meta = {
  name: 'intake',
  description: 'フロー①: S0〜S5バックログを ドラフト(Fable)→ticket-reviewer(Opus)→Jira書き込み(Fable) で起票する',
  phases: [
    { title: 'Draft', detail: '要件を課題ドラフトJSONに落とす (Fable)', model: 'fable' },
    { title: 'Review', detail: 'ticket-reviewer で点検 (Opus)', model: 'opus' },
    { title: 'Write', detail: 'Jira プロジェクトCALへ書き込む (Fable)', model: 'fable' },
  ],
}

const CLOUD_ID = '16ca1158-2cf4-4eb9-ba6a-8f0f2b089765'
const PROJECT = 'CAL'

const BACKLOG_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    epics: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          summary: { type: 'string' },
          description: { type: 'string' },
          stories: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                summary: { type: 'string' },
                description: { type: 'string' },
              },
              required: ['summary', 'description'],
            },
          },
        },
        required: ['summary', 'description', 'stories'],
      },
    },
  },
  required: ['epics'],
}

const REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    verdict: { type: 'string', enum: ['起票可', '要修正'] },
    fixes: { type: 'array', items: { type: 'string' } },
  },
  required: ['verdict', 'fixes'],
}

const PLAN = `
Epic A「開発基盤・準備」
 - 開発基盤整備（規約・Claude設定・レビュー自動化の整備）
 - S0-1: ai& Inference の vision対応モデルIDと料金を実APIで確定（推測禁止・出典/確認日）
 - S0-2: 正解カロリー/PFCの確定（すき家 牛丼・コンビニ弁当、出典付き）
 - 共通実装: OpenAI互換クライアント＋JSON固定出力＋実験ログ(JSONL)基盤（base_url切替）
Epic B「アングル積み増し実験」
 - S1: 2品 × 4アングル（0°/45°/22.5°/11.25°）撮影
 - S2: 全モデル・全条件 × 3試行 実行（=120件、usage/latency記録）※本番実行は課金承認ゲート
 - S3: 採点（APE・料理名ラベリング・速度・コスト集計）
 - S4: 可視化（枚数×精度／コスト×精度／1日あたりコスト試算）
Epic C「記事執筆」
 - 記事①: テーマ本体（カロリー推定モデル比較）
 - 記事②: AI駆動開発の方法論
`

phase('Draft')
const draftPrompt = `あなたは本PoC「料理写真カロリー推定」のJira起票ドラフト担当。次を読んで、下のバックログ計画をJira課題ドラフトに落としてください。まだJiraには書き込まない。
- 10_management/背景.md（§10 実装ステップ）
- 10_management/20_Jira運用規約.md
- 10_management/templates/Jira課題テンプレート.md
バックログ計画:
${PLAN}
要件: 各エピック・各ストーリーについて、テンプレに沿って description に「背景/目的」「受け入れ条件(AC)（合否を機械的に言える箇条書き）」「Definition of Done」「関連（ドキュメントパス等）」を日本語で記述する。ストーリーは対応するエピック配下に入れる。`
let backlog = await agent(draftPrompt, { model: 'fable', schema: BACKLOG_SCHEMA, phase: 'Draft', label: 'draft:backlog' })

phase('Review')
for (let i = 0; i < 2; i++) {
  const rev = await agent(
    `あなたはJira起票レビュー担当。まず .claude/agents/ticket-reviewer.md を読み、そのチェックリストと 10_management/20_Jira運用規約.md・10_management/templates/Jira課題テンプレート.md に従って、次のバックログドラフトを審査せよ。ACが機械判定可能か、DoD網羅、エピック/ストーリーの階層、スコープ（2品・S1〜S4）、推測の混入を点検。判定（起票可/要修正）と必須修正点を返す。\nドラフトJSON:\n${JSON.stringify(backlog, null, 2)}`,
    { model: 'opus', schema: REVIEW_SCHEMA, phase: 'Review', label: `review:round${i + 1}` },
  )
  log(`ticket-reviewer 判定: ${rev.verdict}（指摘 ${rev.fixes.length}件）`)
  if (rev.verdict === '起票可') break
  backlog = await agent(
    `次の指摘を反映してバックログドラフトを修正してください。テンプレ構成は維持。\n指摘:\n- ${rev.fixes.join('\n- ')}\n現ドラフト:\n${JSON.stringify(backlog, null, 2)}`,
    { model: 'fable', schema: BACKLOG_SCHEMA, phase: 'Draft', label: `redraft:round${i + 1}` },
  )
}

phase('Write')
const writePrompt = `あなたはJira書き込み担当。まず ToolSearch で "select:mcp__atlassian__createJiraIssue,mcp__atlassian__searchJiraIssuesUsingJql" を実行してツールを読み込む。
プロジェクト ${PROJECT}（cloudId=${CLOUD_ID}）に、下記バックログを作成する。
手順:
1. searchJiraIssuesUsingJql で 'project = ${PROJECT}' を検索し、既に同じ summary の課題があればスキップ（重複作成しない）。
2. 各エピックを issueTypeName="エピック" で作成し、返ってきた課題キーを控える。
3. 各エピック配下のストーリーを issueTypeName="ストーリー" で作成し、parent にそのエピックのキーを指定する。parent 指定が拒否された場合は additional_fields でエピックリンク相当を試す。
4. description は contentFormat="markdown" で渡す。
5. 作成した全課題のキーとURL、スキップした項目を一覧で報告する。
バックログJSON:
${JSON.stringify(backlog, null, 2)}`
const result = await agent(writePrompt, { model: 'fable', phase: 'Write', label: 'write:jira' })

return { backlog, writeReport: result }
