# qa-copilot

Human-gated QA agent. It finds work, scores it by **payout**, prepares a sandbox, helps you test, and writes a report. **It never applies, bids, comments, or messages a marketplace.**

狙いは「案件を勝手に受けるボット」ではなく、

**発見 → 条件判定（金額×適合度）→ テスト環境準備 → 実行支援 → レポート → 最終承認だけ人間**

です。各サービスの自動化・AI規約を読み、違反しない範囲の最小構成だけを実装しています。詳細は [docs/POLICY.md](docs/POLICY.md)。

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Python 3.11 以上が必要です。

## Pipeline

```bash
qa-copilot policy                          # ソース可否の一覧
qa-copilot discover --source github_bounties,careerjet,arbeitnow
qa-copilot triage                          # 報酬額 × QA適合度で「今やる案件」を並べる
qa-copilot inbox add examples/paste-crowdworks.md
qa-copilot list
qa-copilot show <id>
qa-copilot prepare <id> --no-clone         # GitHub issue なら clone 可
qa-copilot execute <id>
qa-copilot report <id>
qa-copilot approve <id> --operator you --i-understand
qa-copilot packet <id>                     # ローカル APPLY.md を書くだけ。送信しない
```

`triage` は **報酬額を第一、QA適合度を第二** に並べます。バウンティ案件は `$500` のような金額を
本文・ラベルから拾い、年収レンジや時給（`$140K–$160K`、`$30/hr`）は報酬ではなく給与として無視します。
GitHub のラベルは金額そのもの（`$780`、`$1.2k`）であることが多く、そこからも読み取ります。

既定の `triage` は **実際に取りに行ける案件だけ** を出します。次は自動で除外/降格されます。

- すでにアサイン済み（ほぼ取られている）
- アグリゲータの転載（本文が別の issue を「Source URL / 原始链接」として指す）
- リポジトリが自分を fixture / sandbox / demo と説明している
- fork が star を大きく上回る（自動PRファームの疑い）／アーカイブ済み

`triage --all` で降格分も含めて全部見えます。**金額が付いていても、払わないリポジトリは多い** ためです。

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

## Sources

| source | アクセス | 金額 | 備考 |
| --- | --- | --- | --- |
| `github_issues` / `github_bounties` | official API | バウンティあり | 実作業の大半をエージェントが担当できる本命 |
| `remotive` / `remoteok` / `jobicy` / `himalayas` / `working_nomads` | official API | 給与のみ | 求人発見。応募は元サイトで |
| `arbeitnow` | official API | 給与のみ | キー不要。欧州/リモート中心 |
| `fourdayweek` | official API | 給与のみ | キー不要。4日勤務の求人 |
| `careerjet` | official API | 給与のみ | 無料だが `CAREERJET_AFFID` 推奨（既定 `0` は 401 になりやすい）。`ja_JP`/`en_GB` を横断 |
| `adzuna` | official API | 給与のみ | 無料キー。`jp,gb,us` など国単位で英語/日本語を横断 |
| `hn_hiring` | official API | 給与のみ | Hacker News「Who is hiring」の今月スレッド |
| `apify` | official API (opt-in) | 案件次第 | Apify のホスト型スクレイパー経由。**自分は api.apify.com しか叩かない**。有料。`discover --source apify` か config で明示的に有効化 |
| `crowdworks` / `lancers` / `coconala` / `upwork` | paste only | 案件次第 | 自分でブラウザで開いた案件を貼る。HTTPは一切叩かない |
| `usertesting` / `utest` / `freelancer_com` / `hackerone` / `bugcrowd` | disabled | - | AI規約・自動化規約により対象外 |

### Environment

| 変数 | 用途 |
| --- | --- |
| `GITHUB_TOKEN` / `GH_TOKEN` | GitHub Search のレート制限を緩める（公式PAT。スクレイピングではない） |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | [developer.adzuna.com](https://developer.adzuna.com/) の無料キー。`adzuna` を使う場合のみ |
| `ADZUNA_COUNTRIES` | 既定 `jp,gb,us` |
| `CAREERJET_LOCALES` | 既定 `ja_JP,en_GB` |
| `CAREERJET_AFFID` | 既定 `0`。本番アフィリエイトIDがあれば設定 |
| `APIFY_TOKEN` | [console.apify.com](https://console.apify.com/) のAPIトークン。`apify` を使う場合のみ（有料） |
| `APIFY_CHANNELS` | 任意。actor と入力テンプレのJSON配列。未設定なら既定チャンネル（下記） |

キーが無いソースは discover 時に「キーを設定してください」と明示してスキップします（無言で失敗しません）。

### Apify (opt-in, 有料)

CrowdWorks のような公開APIが無いサイトも、Apify の actor（ホスト型スクレイパー）経由なら
発見できます。このツールは `api.apify.com` にしか HTTP を話しません（対象サイトには直接触らない）。

```sh
export APIFY_TOKEN=apify_api_xxx
qa-copilot discover --source apify --limit 20
```

- **規約は消えません。** Apify を使うことは対象サイトの規約違反を合法化しません。取得は読み取り専用の
  発見までで、ログイン・応募・入札・DM は絶対にしません（BANされると売上0）。リスクは利用者が受け入れる前提。
- **既定は off。** お金がかかるので `discover` は実行しません。`--source apify` か config で有効化します。
- **既定チャンネル**（`APIFY_CHANNELS` で上書き可。actor ID は変わることがあるので必ず Apify ストアで確認）:
  - EN: Upwork (`neatrat~upwork-job-scraper`)、Indeed (`misceres~indeed-scraper`)、LinkedIn (`crawlworks~linkedin-jobs-scraper`)、Google Jobs (`epctex~google-jobs-scraper`)
  - JA: Lancers (`youfuxu~lancers-japan-freelance-jobs-scraper`)、CareerCross (`jungle_synthesizer~career-cross-scraper`)、Japan Dev (`getascraper~japan-dev-scraper`)
- **入出力は actor ごとにバラバラ**なので、アダプタは総称的です。`APIFY_CHANNELS` で
  `{"id","actor","locale","query","input"}` を渡し、`input` 内の `{limit}` `{query}` は置換されます。
  出力は一般的なフィールド名（`title`/`jobTitle`/`positionName` など）を順に拾って正規化します。

## What it will not do (and why it would cost you money)

- 対象マーケットプレイスへ**直接**スクレイピングしない（`paste` のみ。`apify` を使う場合も自分は api.apify.com しか叩かない）
- 応募・入札・DM を自動送信しない（BANされると売上は0になる）
- Upwork へ HTTP を一切話しかけない（paste のみ。入札は必ず本人が公式UIで）
- UserTesting / uTest を受けない（規約上AI回答が禁止＝成果物が提出できない）
- バグバウンティへ未検証レポートを投げない
- 求人広告を見ただけで本番サイトを叩かない（明示のテスト許可が必要）
- Apify を既定で実行しない（有料＋対象サイトの規約は利用者の責任。`--source apify` で明示的に）

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
src/qa_copilot/policy.py      # ハードゲート（config で緩められない）
src/qa_copilot/qualify/payout.py  # 報酬額の抽出
src/qa_copilot/discover/sources.py # 公式APIフェッチャ
docs/POLICY.md                # 規約調査メモ
examples/                     # 貼り付けサンプル
fixtures/site/                # ローカル実行用 HTML
```

## License

MIT. 利用前に対象プラットフォームの現行規約を自分で再確認してください。規約は変わります。
