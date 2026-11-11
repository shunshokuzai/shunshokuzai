# 旬食材まるわかり v0.7 — 自動更新の修正版

**2026年11月11日付のGitHub ZIPをもとに修正した検証版です。**

アプリのデザインは v0.6 のまま維持し、青果の価格取得、魚の時系列、旬の話題、データ更新状況の表示を改善しました。

**最初に** [更新版_導入手順_v0.7.md](更新版_導入手順_v0.7.md) を読んでください。すでにGitHub上に公開されているアプリを更新する手順です。GitHubのアカウントやリポジトリを作り直す必要はありません。

## 修正点

1. **青果CSVの解析**：農水省の表が複数行ヘッダーでも、品目名と「数量（t）／金額（千円）／価格（円/kg）」の数値関係を照合して価格を抽出します。数値の整合性が確認できないときは**更新しません**。実CSVのネットワーク取得試験はまだ行っていません。
2. **過去の価格と参考平年比**：青果は同月・同旬の過去最大5年から3年以上、魚は同月・同週の過去最大5年から3年以上の比較資料が得られた場合のみ参考平年比を計算します。**公式発表の平年比ではありません**。実際の更新に成功すれば青果は最大12旬分、魚は月をまたいで最大8週分を価格推移として取得します。取得できた期だけ表示します。
3. **Gemini接続の方式**：無料枠ではGoogle検索グラウンディングが利用できない `gemini-3.1-flash-lite` に切り替えました。農水省の公表ページを先に取得し、その内容だけをGeminiに渡して要約します。**公表資料のURLをAIに作らせません**。Geminiがエラーの場合は、一次資料からの抜粋を残し、AI接続成功とは表示しません。
4. **話題の件数**：農水省の2026年11月の野菜生育・価格見通しを15品目分追加。話題は合計34件、うち今年の公的資料に基づく話題は24件です。この15件は人が出典を照合して作成した要約で、Gemini生成ではありません。
5. **画面**：「旬の話題」の食材カードにも保存済みの卸売価格の参考値を併記。食材名の横のドットは、実測の平年比を計算できたときだけ青（安い）・緑（普通）・赤（高い）になります。未判定は灰色です。データ更新が失敗した場合、その状態を画面に表示します。

## 現時点の収録状況

- 食材名鑑：144品目
- 保存済みの実価格スナップショット：青果58品目・魚11品目（合計69品目）
- 旬の話題：34件（今年の一次資料に基づくもの24件）
- **価格はまだGitHubでの新しい自動更新が成功したものではありません**。画面に表示する統計対象年月・出典・最終更新状態を確認してください。古い価格を当日の価格として扱わないでください。
- 魚の「1尾・1杯」の概算は、卸売円/kg×公表サイズから換算した**参考値**であり、実際の小売価格でも市場での1尾売価でもありません。

## 絶対に区別すること

- **単体テスト**：Python 14件合格、JavaScript構文チェック合格。ブラウザの画面表示確認も実施。
- **未検証**：本番の農水省CSVパース成功・過去3年以上の平年比生成・Gemini APIへの認証付きリクエスト・この修正版のGitHub Actions稼働。これらは更新版をGitHubへ反映し、Actions実行ログで確認する必要があります。
- 公的データを取得できなかった場合、プログラムは**前回の保存データを維持**します。緑色のActions全体成功マークだけで個々の更新成功とは判断できません。

## 基本的な仕組み

- **GitHub Actions**：毎日10:23 JSTごろ定期実行。青果・魚は毎回確認、Geminiは火・木・土と手動実行時に最大6回試行。定期実行の時刻は保証されません。
- **GitHub Pages**：静的HTML/JS/CSSを配信。アクセスごとにAIを実行しません。
- **Gemini API**：`GEMINI_API_KEY` をGitHubの `Settings > Secrets and variables > Actions` に登録。公開ソースコードやHTMLには入れません。
- **無料運用**：`gemini-3.1-flash-lite` のテキスト入出力はFree Tier対象。ただしGoogle検索グラウンディングは無料対象外であり、使いません。料金枠、リクエスト上限や利用資格はGoogleの最新設定を確認してください。追加課金を避けるため、請求先を有料プランに変更しないでください。

## 手元でテストする場合

Python 3.12以上を用い、このREADMEのあるフォルダで：

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/preflight.py
python scripts/build_standalone.py
python scripts/build_site.py
```

GitHub Actionsでは依存関係を自動で用意してから `python scripts/run_refresh.py --live` が実行されます。実行結果は `UPDATE STATUS {"vegetableFruit":...,"fish":...,"gemini":...}` および `SOURCE-FIRST TOPICS` を確認してください。

## 主なファイル

| ファイル | 内容 |
|---|---|
| `index.html` / `app.js` / `styles.css` | 公開画面 |
| `data/seed.json` / `data.js` | ソース付き収録データ |
| `scripts/update_data.py` | 青果CSV、同旬の参考平年比、過去12旬の推移 |
| `scripts/update_fish.py` | 豊洲市場の魚・同週比較、過去8週の推移 |
| `scripts/update_topics.py` | 農水省の月次見通し取得、Geminiテキスト要約 |
| `scripts/run_refresh.py` | 3系統の更新結果を記録 |
| `.github/workflows/update.yml` | Actionsでの定期取得・GitHub Pages公開 |
| `tests/` | 再発防止用テスト |

## 情報源と利用規約

- [農林水産省・青果物卸売市場調査（旬別）](https://www.maff.go.jp/j/tokei/syohi/shunbetu/2026/hinmoku.html)
- [農林水産省・野菜の生育状況及び価格見通し（2026年11月）](https://www.maff.go.jp/j/press/nousan/engei/261030.html)
- [東京都中央卸売市場・水産物週間市況](https://www.shijou.metro.tokyo.lg.jp/torihiki/week/suisan)
- [Google Gemini APIの料金](https://ai.google.dev/gemini-api/docs/pricing?hl=ja)
- [GitHub Actions公式資料](https://docs.github.com/en/actions)
