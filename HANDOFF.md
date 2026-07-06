# 引き継ぎドキュメント(research-pipeline)

**作成日**: 2026-07-06
**引き継ぎ元**: Claude Code (Fable 5) — ローカルの作業ディレクトリで作業
**引き継ぎ先**: Notion AI (Fable) — GitHub リポジトリ経由で作業を継続
**リポジトリ**: https://github.com/wasanemon/research-pipeline (`origin/main`)

このドキュメントは、リポジトリだけを参照して作業を継続するための自己完結した引き継ぎである。
プロジェクトの方針は [CLAUDE.md](CLAUDE.md)、収集手順は
[skills/paper-collection/SKILL.md](skills/paper-collection/SKILL.md)、ノート形式は
[skills/literature-notes/SKILL.md](skills/literature-notes/SKILL.md) に一次情報がある。
**まずこの3つを読むこと。** 以下はその上での現状と申し送りである。

---

## 1. このプロジェクトは何か

データベースシステム分野(DB / DBMS / concurrency control / storage engines /
distributed transactions)の**半自律リサーチパイプライン**。目的は
「文献リサーチ → 課題発見 → 検証 → 論文化」を人間のゲートを挟みながら回すこと。

**現在は Phase 1(文献収集と構造化ノートの蓄積)** のみがスコープ。
課題選択・研究方針の決定は行わない(それは人間のゲート)。

### 絶対に守るルール(CLAUDE.md の「絶対ルール」より。違反は成果物全体の信頼性を毀損する)

1. **記憶からの引用禁止。** タイトル・著者・数値・主張は、実際に取得したソース
   (PDF / API レスポンス / 公式ページ)で確認せずに書かない。確認できないものは書かない。
2. **BibTeX は必ず DBLP から機械取得。** 手書き・記憶からの再構成・コピー改変は禁止。
   DBLP に無いもの(arXiv 等)のみ arXiv API から生成し `note = {arXiv preprint}` を付ける。
3. **すべてのノートにソース URL 必須。**
4. **abstract しか読んでいない論文は `status: abstract-only` と明示。** そこから技術的詳細を書かない。
5. **`[paper claims]`(論文の主張)と `[my inference]`(自分の推論)をラベルで区別。**
   本パイプラインの実運用では `[paper]` / `[inference]` / `[question]` の3ラベル+
   アンカー(`(§4.2)` `(Fig. 7)` `(Table 3)` `(p.7)` `(abstract)`)を使っている。
6. **既存ノートを上書きで消さない。** 追記または明示的改訂とし、git コミット単位で追跡可能に。

---

## 2. 現在の状態(数字で)

| 項目 | 値 |
|---|---|
| キュー総エントリ | 87 |
| ├ ノート化済み `- [x]` | 63 |
| ├ PRUNED(剪定除外・履歴として残置) | 21 |
| └ **真の未着手 `- [ ]`(PRUNED でない)** | **3**(下記※要対応) |
| ノート総数 | 63(read 56 / abstract-only 7) |
| references.bib エントリ | 87 |
| git コミット | 83 |
| ローカル PDF | 56本(**gitignore 対象。GitHub には無い**。ノートに抽出済み詳細あり) |

※ キューの `- [ ]`(未チェック)24件のうち21件は `【PRUNED 2026-07-06】` 印付き=剪定除外で意図的に未ノート化。
**残り3件は Mode B 引用追跡で追加した未ノート化の重要文献**で、剪定対象ではなく**ノート化すべき対象**:
- FoundationDB: A Distributed Unbundled Transactional Key Value Store (SIGMOD'21) — DiStash/BtrLog の基盤
- Moving on From Group Commit: Autonomous Commit ... (PACMMOD'25) — BtrLog 評価の土台
- Milliscale: Fast Commit on Low-Latency Object Storage (arXiv) — BtrLog と相補
(LazyLog は第3バッチでノート化済み。この3本は前任の見落としで漏れた。§4 の最優先タスクに含めた。)

### ノートの構成(63本)
- **core 36本**: 第1〜第2バッチ。全て status: read、敵対的検証済み。
- **Mode B 引用追跡 4本**: FoundationDB (SIGMOD'21), Autonomous Commit (PACMMOD'25),
  LazyLog (SOSP'24), Milliscale (arXiv)。ノート中の重要被引用文献を追加したもの。
- **第3バッチ 27本**: 剪定で残した adjacent/borderline。

---

## 3. 【最優先の申し送り】未完のタスク

### (A) 第3バッチ 11本の敵対的検証パスが未実施 ★要対応
セッション上限で中断した。**ノート自体は書かれているが、独立エージェントによる
ソース照合(数値・アンカー・捏造チェック)を通していない。** コミットメッセージに
「検証パス未実施」と明記してある。該当11本:

```
2026-edbt-gao-recdb            2026-fast-pan-unicom
2026-edbt-shen-dcsr            2026-fast-park-lockify
2026-edbt-chen-thunderbolt     2026-fast-song-warp
2026-vldbj-simatis-temporal-indexing   2026-fast-tu-most
2026-fast-an-xerxes            2026-fast-yoon-cylon
                               2026-fast-kim-zoned-ufs
```
**やること**: 各ノートを、対応する抽出テキスト(ローカルなら
`scratchpad/txt/<slug>.txt`。ただし scratchpad はリポジトリ外なので、Notion AI 環境では
`literature/pdfs/<slug>.pdf` から再抽出が必要)と照合し、[paper] クレームの数値・
アンカーを1つずつ検証、誤りは修正して Changelog に
`- <日付>: 検証パスによる修正(...)` を追記する。**敵対的に**(誤りがある前提で)当たること。

### (B) abstract-only 7本のフルテキスト化 ★中優先
以下は abstract しか読めておらず、Approach / Evaluation 等が
`(abstract-only のため未記載)` になっている。フルテキスト PDF を取得できれば
status: read に格上げできる(手順は §5「フルテキスト格上げ」参照)。

```
2026-sigmod-chen-bytegraph-dione   (ACM。dl.acm.org は 403。ブラウザ手動 DL 必要)
2026-sigmod-baltieri-bigtable-20years  (同上)
2026-tods-mo-filters-adapt-or-cache    (同上)
2026-eurosys-coquisart-pacar           (同上)
2026-eurosys-kumar-tierscape           (同上)
2026-eurosys-zhang-ficusdb             (同上)
2024-sosp-luo-lazylog                  (同上 / SOSP'24)
```
**注意**: ACM の PDF は自動取得が 403 で弾かれる。人間がブラウザでダウンロードして
`literature/pdfs/<slug>.pdf` に置くのを待つのが現実的。急がなくてよい。

### (C) BibTeX の DBLP キー未取得
第1回スイープ由来のエントリの多くは `ids.dblp` が空。特に:
- **BtrLog** (arXiv 2606.27051): PVLDB DOI 10.14778/3828612.3828640 採番済みだが DBLP 未収載。
  収載を確認したら BibTeX を DBLP 版へ差し替え、queue エントリに会場追記。
- **ACM/IEEE 13本 + 第3バッチの一部**: DBLP 収載後に BibTeX を機械取得して references.bib を更新。
次回の週次スイープ時にまとめてチェックするのが効率的。

---

## 4. 次にできる作業(優先度順・人間のゲート待ち含む)

0. **Mode B 追加3本のノート化**(§2※)— FoundationDB / Autonomous Commit / Milliscale。
   前任の見落としで漏れた。ノート化後 queue.md の該当行を `- [x]` に。§6 の手順で。
1. **上記 (A) の検証パス** — 最優先。信頼性の担保。
2. **次回の週次スイープ** — 手順は [skills/paper-collection/SKILL.md](skills/paper-collection/SKILL.md)
   の「Mode A(Weekly sweep)」。前回が初回フルベースライン化だったので、次回は差分のみで軽量。
   **前回 DBLP 未収載だった会場を再チェック**: DaMoN 2026 / SOSP 2026 / OSDI 2026 / USENIX ATC 2026。
   また PVLDB Vol.19 の 2025年内発行分(year:2025)はベースライン未取得——バックフィルするかは人間判断。
3. **横断マップの作成(Phase 2 への橋渡し)** — 63ノートをテーマ別クラスタ
   (WAL/コミット系、LSM系、CXL/disaggregated系、HTAP系、CC/合意系、テスティング系 等)に
   整理し、各ノートの `## Idea seeds` と `[question]` を集約した俯瞰ドキュメント。
   **課題選択そのものは人間のゲート**なので、AI がやるのは「材料の整理」まで。
4. **(B) の abstract-only 格上げ**(PDF が揃い次第)、**(C) の BibTeX 整備**。

---

## 5. 運用ノウハウ(前任の作業で得た実地知見。リポジトリ外のメモリにあったものをここに移植)

### DBLP API の実地制約(重要)
- `h=300` や `h=1000` を指定しても**実効的に100件しか返らない**ことがある。
  `result.hits["@total"]` と突き合わせ、`f=<offset>`(100刻み)でページングが必要。
- 重いクエリ(h=1000)を1秒間隔で連発すると **3リクエスト目以降 "Connection reset by peer"** で
  ブロックされ数分続く。60秒クールダウン+10秒間隔に落とすと安定。
- 会場フィルタ構文: `q=stream:streams/conf/<key>: year:2026:`(自由文検索は誤マッチする)。
  ストリームキー例: `journals/pvldb`, `conf/sigmod`, `conf/icde`, `conf/edbt`, `conf/cidr`,
  `journals/tods`, `journals/vldb`, `conf/damon`, `conf/eurosys`, `conf/sosp`, `conf/osdi`,
  `conf/usenix`(=ATC), `conf/fast`。
- 空結果は「未収載」と「ストリームキー誤り」の両方があり得るので、前年 `year:2025:` プローブで区別する。
- `skills/paper-collection/scripts/fetch_paper.py` が arXiv / DBLP / Semantic Scholar を
  ラップしている。`python scripts/fetch_paper.py --help` を先に読むこと。

### abstract 取得のフォールバック
- ACM(dl.acm.org)は自動 PDF 取得が **HTTP 403**。IEEE はペイウォール。
- abstract の代替ソースとして **OpenAlex API**
  (`https://api.openalex.org/works/doi:<DOI>` の `abstract_inverted_index` から語順復元)が有効だった。
  Semantic Scholar (`api.semanticscholar.org/graph/v1/paper/DOI:<doi>?fields=abstract`) も併用可。
  **どちらも復元 abstract であり publisher の verbatim ではない**点をノートに明記すること。

### 却下(スコープ外)ポリシー — 剪定の運用実績
以下は adjacent/borderline から **drop** した類型(判断軸=「貢献が汎用 DB/ストレージ技術か、
特定ワークロード特化か」):
- LLM サービング/学習向けストレージ・KVキャッシュ(例: TokaDB, グラフ埋め込み学習)
- ベクトル検索(ANN)特化(例: グラフ ANN の I/O 最適化, hybrid vector-graph 索引)
- ML4DB / LLM 支援ツール(例: LLM によるクエリ性能説明)
- 純クエリ実行加速(GPU/FPGA/ASIC。TP/ストレージへの接点なし)
- HW アクセラレータ活用最適化で DB 接点が間接的(評価がマイクロベンチ止まり)
- 運用系・クラウドインフラ(資源プール、ベンダーサービス回顧、アクセス制御ミドルウェア)

**逆に keep した例外**:
- ブロックチェーン動機でも**汎用 CC/consensus 技術の貢献**があれば keep(例: Thunderbolt の
  動的 concurrency controller)。
- グラフ応用でも**貢献が汎用ストレージ/索引/並行データ構造**なら keep(例: TVA の多版ストレージ)。
- スコープキーワード(CXL, recovery, buffer management 等)に**直結する評価ツール/シミュレータ**は keep。
- スコープ中核の**エンジン自体の産業回顧**は keep(Bigtable 20年)、ただしインフラサービス回顧は drop。

剪定の全記録は [literature/queue-triage-2026-07-06.md](literature/queue-triage-2026-07-06.md) にある。

### レート制限(CLAUDE.md より)
- arXiv: 3秒間隔 / Semantic Scholar: 1 req/s / DBLP: 1秒以上(重いクエリは上記の通りもっと緩く)。
- ネットワークエラー時はリトライ(最大3回、指数バックオフ)。失敗は queue.md に
  `FETCH-FAILED` として残す(**黙って捨てない**)。

---

## 6. ノートの書き方(実運用フォーマット)

雛形は [skills/literature-notes/assets/note-template.md](skills/literature-notes/assets/note-template.md)。
密度と粒度の**手本**は [literature/notes/2026-fast-wei-dmtree.md](literature/notes/2026-fast-wei-dmtree.md)
や [literature/notes/2026-pvldb-weng-pisco.md](literature/notes/2026-pvldb-weng-pisco.md) を参照。

- ファイル名: `<year>-<venue>-<firstauthor>-<slug>.md`(venue は DBLP 略称を小文字、arXiv は `arxiv`)。
- frontmatter: title / authors / venue / year / ids{doi,arxiv,dblp} / urls{paper,pdf,code} /
  status / read_date / tags。
- 本文セクション: TL;DR / Problem & motivation / System model & assumptions(徹底的に) /
  Approach / Evaluation(見出し数値+アンカー、**カバーしていない点を [inference] で明記**) /
  Limitations(stated + inferred) / Relations(既存ノートへ `[[filename]]` でリンク。捏造禁止) /
  Idea seeds([inference]/[question] のみ) / Changelog。
- **全ての [paper] 行にアンカー必須。** アンカーできないクレームは書かない。
- **フルテキスト格上げ手順**: PDF を `literature/pdfs/<slug>.pdf` に置く → 全文抽出
  → 既存 abstract-only ノートを read に書き直し(全節執筆、abstract 復元との食い違いも照合)
  → Changelog に `- <日付>: full-text 格上げ(...)` を追記 → 独立の検証パスを回す。

---

## 7. マルチエージェント運用(参考)

前任は Claude Code の Workflow(多エージェントオーケストレーション)で
「取得 → 執筆 → 敵対的検証」のパイプラインを組んで一括処理していた。Notion AI 環境で
同等の並列化ができない場合は、**1本ずつ「執筆 → 別視点で敵対的検証」を必ず2段で**回すこと。
検証を省略したノートは信頼できない(だから §3(A) を最優先にしている)。

コミットは **1ノート1コミット**、メッセージに検証状態を明記(前任の慣習)。
git コミット末尾には `Co-Authored-By` 行を付けていた。

---

## 8. 作業を始める前のチェックリスト

- [ ] [CLAUDE.md](CLAUDE.md) の絶対ルールを読んだ
- [ ] [skills/paper-collection/SKILL.md](skills/paper-collection/SKILL.md) と
      [skills/literature-notes/SKILL.md](skills/literature-notes/SKILL.md) を読んだ
- [ ] このドキュメントの §3(未完タスク)を確認した
- [ ] git の状態を確認した(`git log --oneline`、`git status`)
- [ ] 記憶からの引用は絶対にしない、を肝に銘じた
