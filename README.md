> はじめて公開する方は、最初に **`はじめに_公開と自動更新の設定.md`** をお読みください。

# 旬食材まるわかり — v0.6 魚の1尾換算価格・カード整列版

作成日：2026-10-30。v0.5 のデザインを維持し、魚の1尾・1杯あたり参考換算価格と推移、カードの画像・テキストの上端揃えを追加しました。

## まず見る

- `旬食材まるわかり_プロトタイプ.html`：ブラウザでそのまま開ける、**2026年10月末時点の保存版**。
- `index.html`：オンライン公開用。`data.js`, `app.js`, `styles.css` などと一緒に置いて利用。
- **HTMLをローカルで開いただけでは自動更新されません。** Gemini APIもローカルHTMLから実行されません。APIキーをソースに書くことは禁止します。

## v0.6 で追加した内容

- サンマ・サバ・アジ・イワシ・カツオ・キンメダイ・ハマチは、2026年10月第4週の市況表に記載された魚体サイズ帯または入数を使い、円/kgから **1尾あたりの参考概算** を表示。スルメイカは1杯あたり換算。グラフも同じ重量を仮定した1尾/1杯の参考推移。
- マグロ・カレイは重量の記載がないため勝手に1尾単価を付けず、詳細画面で重量を入力すれば試算できます。カキはむき身のため1個換算できません。表示される1尾価格は**卸売のkg単価×仮定重量**であり、市場における1尾の実売価格・小売価格ではありません。
- 注目食材カードはイラスト領域・見出し・本文・下部ボタンの縦位置を揃え、本文の長短でカードの上下位置がずれないようにしました。
- 将来の自動更新でも、魚の市況PDFにサイズ表記がある場合だけ換算重量を更新。記載がなければ「換算不可」に戻す設計です。

## 今回追加した内容

1. 食材名の横：**青／緑／赤／灰色の小さな丸だけ**で判定。スクリーンリーダーではラベルを通知する（アクセシビリティを維持）。価格一覧の専用列や凡例のテキストは残します。
2. 青果：農林水産省の「青果物卸売市場調査（旬別結果）」のCSVを定期確認。最新旬の1kg当たり卸売価格を収録。過去5年の**同月・同旬**を取得し、3年以上の比較可能な値がある場合、単純平均から独自の参考平年比を計算。直近の公表旬の推移をグラフ化。
3. 魚：東京都中央卸売市場（豊洲市場）の「水産物週間市況」を確認。PDFまたは公表済み過去HTML資料のうち、検証可能な**中値**だけ抽出。過去5年の**同月・同週**の資料から3年以上あれば独自参考平年比を計算。対象月の週別価格をグラフ化。比較できない場合は**判定を表示しない**。
4. Gemini：Google Search groundingを使い、週3回、旬の食材をローテーションで調査。**出典URLが付いている場合だけ**AI要約を公開。自動生成テキストは画面で「Gemini要約・未検証」と明記。
5. 更新プログラム：GitHub Actionsで毎日実行する設定を追加。取得に失敗したデータは前回値を保持し、成否と最終確認時刻をデータに保存。GitHub Pages公開の設定ファイルを含む。

## 現時点で確認できたこと／できていないこと

- ✅ **画面動作**：Playwright + Chromiumで 1440px・390px 両方の検索、判定ドット、魚の詳細・価格推移、出典を確認。
- ✅ **ローカル計算テスト**：価格分類、平均値、比較資料不足の処理、CSV・魚の表形式解析、Gemini応答のモックテストが成功。
- ✅ **実価格スナップショット**：青果58品目と魚11品目（v0.4公的資料に基づいて収録した値）を保持。
- ❗ **未検証**：この生成環境から公的CSV・魚PDFの実ダウンロード、Gemini APIへの認証付き実通信、GitHub Actionsの公開先での実行は確認できていません。**自動更新が本番で動いたとは主張していません。**
- ❗ **青果の平年比は現行保存版では未算出**。GitHub Actionsで実データ取得に成功した場合のみ計算して反映します。
- ❗ 魚の過年度資料は古いHTMLページ等に形式の差があり、抽出不能な資料がある場合は一部品目の判定を保留します。

## GitHubで自動更新・公開を有効にする手順

APIキーをチャットに貼らないでください。リポジトリのSecretsに設定します。

1. GitHubにログインして **Public リポジトリ**（例 `shunshokuzai`）を新規作成。
2. ZIPを解凍し、**このZIPを解凍したフォルダの中身**をリポジトリのルートにアップロード。`.github/workflows/update.yml` の隠しフォルダも含めます。ブラウザからアップロードする場合、隠しファイルが含まれたことを確認してください。
3. GitHubの **Settings → Actions → General** で Actions を許可し、必要なら **Workflow permissions: Read and write permissions** を設定します。
4. **Settings → Pages → Build and deployment → Source: GitHub Actions** を選びます。
5. [Google AI Studio](https://aistudio.google.com/apikey) でGemini APIキーを作成（無料枠と最新条件を必ず確認）。GitHubの **Settings → Secrets and variables → Actions → New repository secret** で名前を `GEMINI_API_KEY` として登録します。**HTML、JavaScript、リポジトリの公開ファイルに記入しないでください。**
6. GitHubの **Actions → Update food prices, Gemini topics, and publish site → Run workflow** を実行します。正常終了後、**Settings → Pages** から公開URLを確認できます。
7. 自動実行は日本時間の毎日10:23ごろを予定していますが、GitHub Actionsの定期実行は遅延・省略されることがあります。未使用の公開リポジトリでは定期実行が停止することがあります。
8. Actionsのログで、青果・魚・Geminiの取得成否を確認してください。通信やレイアウト変更でエラーが出た場合は、保存されている直近の公的データをそのまま掲載し、新しい価格を捏造しません。

**注意：APIキーを登録しない場合でも、価格データの取得・更新処理は独立して実行されます。** Gemini要約のみスキップします。検索連携の無料枠はGoogle側のモデル・プラン・時期で変わります。デフォルトは `gemini-2.5-flash-lite`、検索は定期実行時に火・木・土に最大6件/回です。初回の手動「Run workflow」では曜日を問わず最大6件を試行します。料金発生を保証なしで自動回避する仕組みではないので、Google側で請求設定や上限を確認してください。

## 手元で確認する場合（Windows / macOS / Linux）

Python 3.12以上で、プロジェクトのルートから：

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -p 'test_*.py' -v
python scripts/build_standalone.py
python scripts/build_site.py
```

ネットワークがある環境で、公開情報を更新したい場合：

```bash
python scripts/run_refresh.py --live
```

`GEMINI_API_KEY` を環境変数に設定しない限り、Geminiへのリクエストは送信されません。手元でAI処理の動作確認をする場合も、キーをリポジトリ内のファイルに保存しないでください。

## 主なファイル

- `app.js` / `styles.css` — UIと価格判定
- `data/seed.json` / `data.js` — 公開情報（ソースURL・日付・価格・話題）
- `scripts/update_data.py` — 公的な青果CSVと過年度の同旬比較
- `scripts/update_fish.py` — 豊洲の週間市況PDF・HTMLから中値と過年度比較
- `scripts/update_topics.py` — GeminiのGoogle検索連携
- `scripts/run_refresh.py` — 更新処理を順番に実行、失敗時の処理と状態記録
- `.github/workflows/update.yml` — 毎日の自動確認とサイト公開
- `scripts/build_standalone.py` — 配布用単体HTML作成
- `scripts/build_site.py` — GitHub Pages用静的ファイル生成
- `tests/` — 自動テスト

## 比較値の注意

**参考平年比 = 最新の市場価格 ÷ 比較可能な直近3～5年の同時期の市場価格（単純平均）×100**。農水省・東京都が公式発表した「平年比」ではありません。価格は小売価格ではありません。青果と魚は市場・集計方式が異なり、同じ数字でも同条件とは限りません。

出典：
- [農林水産省 青果物卸売市場調査（品目別CSV）](https://www.maff.go.jp/j/tokei/syohi/shunbetu/2026/hinmoku.html)
- [東京都中央卸売市場 豊洲市場・水産週間市況](https://www.shijou.metro.tokyo.lg.jp/torihiki/week/suisan)
- [Google Gemini API・検索グラウンディング](https://ai.google.dev/gemini-api/docs/google-search)
- [Gemini APIの料金と無料枠](https://ai.google.dev/gemini-api/docs/pricing)
- [GitHub Actions・スケジュール](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
