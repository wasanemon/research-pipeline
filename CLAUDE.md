# Research Pipeline — CLAUDE.md

このリポジトリは、データベースシステム(DB / DBMS / concurrency control / storage engines /
distributed transactions)分野の研究パイプラインである。
目的: 文献リサーチ → 課題発見 → 検証 → 論文化 を、人間のゲートを挟みながら半自律で回す。

現在のスコープは **Phase 1: 文献収集と構造化ノートの蓄積** である。

## ディレクトリ構成

```
research-pipeline/
├── CLAUDE.md               # 本ファイル(方針・禁止事項)
├── skills/
│   ├── paper-collection/   # 論文収集プロトコル(arXiv / DBLP / Semantic Scholar)
│   └── literature-notes/   # 文献ノートの形式と検証ルール
├── literature/
│   ├── queue.md            # 収集済み・未ノート化の論文キュー
│   ├── notes/              # 1論文1ファイルのノート
│   ├── pdfs/               # 取得したPDF(gitignore対象にしてよい)
│   └── references.bib      # BibTeX(機械取得のみ。手書き禁止)
└── ideas/                  # 課題候補と却下理由のログ(Phase 2)
```

## 絶対ルール(違反は成果物全体の信頼性を毀損する)

1. **記憶からの引用禁止。** 論文のタイトル・著者・数値・主張を、実際に取得した
   ソース(PDF / API レスポンス / 公式ページ)で確認せずにノートや BibTeX に書かない。
   確認できないものは書かない。「たぶんこうだった」は存在しない。
2. **BibTeX は必ず DBLP から機械的に取得する。** 手書き・記憶からの再構成・
   他ノートからのコピー改変は禁止。DBLP に無いエントリ(arXiv プレプリント等)のみ
   arXiv API のメタデータから生成し、`note = {arXiv preprint}` を付ける。
3. **すべてのノートにソース URL 必須。** URL のないクレームはノートに残さない。
4. **abstract しか読んでいない論文は `status: abstract-only` と明示する。**
   abstract-only のノートから技術的詳細(アルゴリズムの動作、実験数値)を書かない。
5. **論文の主張と自分の推論を区別する。** ノート内で `[paper claims]` と
   `[my inference]` のラベルを使い分ける(形式は skills/literature-notes を参照)。
6. **既存ノートを上書きで消さない。** 更新は追記または明示的な改訂とし、
   git のコミット単位で追跡可能にする。

## ワークフロー(Phase 1)

週次実行を基本とする。手順の詳細は各 skill を参照:

1. **収集**: `skills/paper-collection/SKILL.md` に従い、新着・関連論文を収集し
   `literature/queue.md` に追加(重複排除込み)。
2. **ノート化**: キューから優先度順に PDF を取得・読解し、
   `skills/literature-notes/SKILL.md` の形式でノートを作成。
3. **報告**: 実行のたびに、追加した論文数 / 作成したノート / 特に重要そうな論文
   (理由付き)を短くまとめて人間に報告する。**課題選択・研究方針の決定は行わない**
   (それは人間のゲート)。

## 実行環境の注意

- API アクセスにはレート制限を守る(arXiv: 3 秒間隔、Semantic Scholar: 1 req/s 目安)。
- 長時間ジョブは tmux セッション内で実行し、ログを `logs/` に残す。
- ネットワークエラー時はリトライ(最大 3 回、指数バックオフ)し、
  失敗したエントリは queue.md に `FETCH-FAILED` として残す(黙って捨てない)。

## 監視対象(初期設定。人間が随時編集する)

- **arXiv カテゴリ**: cs.DB(主)、cs.DC / cs.OS(従)
- **DBLP 会議・論文誌**: PVLDB, SIGMOD, ICDE, EDBT, CIDR, TODS, VLDB Journal,
  DaMoN, EuroSys, SOSP, OSDI, USENIX ATC, FAST
- **キーワード**: concurrency control, transaction processing, serializability,
  MVCC, OCC, deterministic database, larger-than-memory, buffer management,
  LSM-tree, write-ahead logging, checkpoint, recovery, HTAP, disaggregated memory
