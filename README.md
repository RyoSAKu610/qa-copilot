# qa-copilot

Human-gated QA agent. It finds work, scores it, prepares a sandbox, helps you test, and writes a report. **It never applies, bids, comments, or messages a marketplace.**

狙いは「案件を勝手に受けるボット」ではなく、

**発見 → 条件判定 → テスト環境準備 → 実行支援 → レポート → 最終承認だけ人間**

です。各サービスの自動化・AI規約を 2026-08-28 時点で読み、違反しない範囲の最小構成だけを実装しています。詳細は [docs/POLICY.md](docs/POLICY.md)。

## What it will not do

- CrowdWorks / Lancers / Coconala / Upwork をスクレイピングしない
- 応募・入札・DM を自動送信しない
- UserTesting / uTest を受けない（規約上、人間前提 or AI回答禁止）
- バグバウンティへ未検証レポートを投げない
- 求人広告を見ただけで本番サイトを叩かない（明示のテスト許可が必要）

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

GitHub Search のレート制限を緩めるなら `GITHUB_TOKEN` か `GH_TOKEN` を環境変数に置きます（公式 PAT。スクレイピングではありません）。

## Pipeline

```bash
qa-copilot policy                          # ソース可否の一覧
qa-copilot discover --source github_issues,remotive
qa-copilot inbox add examples/paste-crowdworks.md
qa-copilot list
qa-copilot show <id>
qa-copilot prepare <id> --no-clone         # GitHub issue なら clone 可
qa-copilot execute <id>
qa-copilot report <id>
qa-copilot approve <id> --operator you --i-understand
qa-copilot packet <id>                     # ローカル APPLY.md を書くだけ。送信しない
```

クラウドワークス等は公式のワーカー向け求人 API が無いので、ブラウザで開いた案件を YAML front matter 付きで貼ります。

```yaml
---
source: crowdworks
title: テスト項目作成
client_allows_ai: unknown
ai_disclosed: false
test_target: https://staging.example.com
permission_to_test: true
---
本文
```

`client_allows_ai: no` や「生成AI禁止」と書いてある案件は qualifier が reject します。

## Agent fit

エージェントが実際に手伝える案件はだいたいこれです。

- 公開 GitHub issue の再現とテスト追加
- 仕様からのテスト計画・ケース作成
- 許可された staging のスモーク / ざっくり a11y
- 再現手順つきバグ票
- ドキュメントの抜け確認

来社、顔出し動画、口コミ代行、スクレイピング請負、権限のない脆弱性診断は対象外です。

## Layout

```
src/qa_copilot/policy.py   # ハードゲート（config で緩められない）
docs/POLICY.md             # 規約調査メモ
examples/                  # 貼り付けサンプル
fixtures/site/             # ローカル実行用 HTML
```

## License

MIT. 利用前に対象プラットフォームの現行規約を自分で再確認してください。規約は変わります。
