---
title: "TiRex: An HTAIP Framework Beyond HTAP for Unified Transactional, Analytical, and AI Workloads"
authors: [Jane Yu, Yu Dong, Rossi Sun, Lucas Sun, Liu Tang, Ed Huang, Max Liu]
venue: "ICDEW 2026 (2026 IEEE 42nd International Conference on Data Engineering Workshops)"
year: 2026
ids: {doi: "10.1109/ICDEW71238.2026.00021", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1109/ICDEW71238.2026.00021", pdf: "literature/pdfs/2026-icdew-yu-tirex.pdf", code: "https://github.com/kolafish/wiki-vec-bench"}
status: read
read_date: 2026-07-06
tags: [htap, htaip, retrieval, full-text-search, vector-search, mpp, bounded-staleness, log-driven-index, tidb, object-storage]
---

読んだ版: IEEE Xplore 版 PDF(手動取得)。p.1 のヘッダブロックで
「2026 IEEE 42nd International Conference on Data Engineering Workshops (ICDEW)」、
DOI 10.1109/ICDEW71238.2026.00021、pp.159–165、著者 7 名(全員 PingCAP Inc.、
corresponding author: Yu Dong)を確認。
`urls.code` は論文が公開するベンチマークドライバ/テストハーネス(ref [21],
"Wiki-vec-bench")であり、**TiRex 本体のコードは未公開**(「近く open-source 予定」§V-A)。
メタ情報: 原稿執筆に生成 AI(GPT-5 系 ChatGPT)を言語・構成の補助として使用した旨の
acknowledgement あり(実験データ・設計・結果には不使用と明記)(p.6)。

## TL;DR
HTAP は TX+AP を単一エンジンで統合するが、AI アプリを支える retrieval 中心ワークロード
(full-text search / vector similarity search)には設計されていない。TiRex(TiDB Retrieval
Execution Engine、内部名 TiCI。PingCAP 製)は HTAP を HTAIP へ拡張するフレームワークで、
retrieval インデックス構築を primary storage から分離し、トランザクションログから非同期に
構築して独立永続化(評価では S3)し、クエリ時は TiFlash の MPP エンジン上で retrieval
演算子と関係演算子を統一実行する。shard/immutable fragment ベースの組織と bounded-staleness
一貫性を持つ。評価では scan ベースライン比で term-match 38.6→6043.9 QPS(P99
1197.4→4.3ms)、vector top-k 526.3→3752.4 QPS、混合 31.1→1169.2 QPS、OLTP への影響は
スループット約 3% 減 + P99 増に留まると主張 (Table I, Table II)。

## Problem & motivation
- [paper] 既存 HTAP は scan・集約志向の AP に最適化されており、ストレージレイアウト・
  索引機構・実行モデルのいずれも retrieval 中心ワークロード(full-text search / vector
  similarity search。特化インデックス構造・高い更新スループット・ランキング志向の実行を
  要求)向けに設計されていない (§II-A)。
- [paper] 現実の対処は 2 択: (a) 外部システム(検索エンジン / ベクタ DB)併設 —
  データ複製・同期パイプライン・可視性遅延・運用複雑性・実行経路の分断を招き、
  retrieval 結果と関係演算子(filter/join/aggregation)を組み合わせるクエリがシステム
  境界を跨いで end-to-end 最適化を阻む (§II-B, p.3)。(b) ストレージエンジンへの密結合 —
  インデックスコストが OLTP/OLAP 性能と結合し、索引スループット・拡張性を制約し、
  急速に進化する retrieval 技術の取り込みを遅らせる (§II-A)。
- [paper] そこで HTAIP(Hybrid Transactional, Analytical, and AI Processing)を提唱:
  full-text / vector search を TX・AP と並ぶ first-class 実行対象として統一実行モデルで
  扱う DB の抽象 (§I-A)。retrieval ワークロードは低レイテンシとランキングを重視し、
  bounded staleness をしばしば許容する、という性質の違いが分離設計の根拠 (§I-A)。
- [paper] クラウド DB の storage/compute 分離トレンド(Snowflake の multi-cluster
  shared-data、Aurora の OLTP 向けストレージ分離)を「retrieval indexing の分離」へ
  延長するのが位置づけ (§II-C)。
- [paper] 既存との差別化 2 点: (1) TiDB/TiFlash・SingleStore・MySQL HeatWave・AlloyDB の
  ような HTAP 系と違い retrieval インデックスをストレージエンジンに埋め込まない、
  (2) 外部検索/ベクタ DB と違い retrieval をクエリプランナと実行エンジンに統合し、
  retrieval 演算子と関係演算子を単一 MPP パイプラインで実行する (§II-C)。
- [paper] 貢献: (i) HTAIP 抽象の導入、(ii) 既存 MPP 実行エンジンを再利用する decoupled
  indexing フレームワーク TiRex、(iii) shard ベースの indexing / scheduling モデル、
  (iv) 混合 TX+AP+retrieval ワークロードでの評価 (§I-C)。

## System model & assumptions
- [paper] 土台は TiDB の HTAP アーキテクチャ: TiKV = transactional row store(Raft 複製)、
  TiFlash = columnar analytical engine(MPP 有効)(§II-A, §III-A, §V-A)。
- [paper] データフロー: トランザクション commit 時に変更が transactional storage に
  永続化され durable log に append される。TiRex index service がこの log を**非同期に**
  消費し、retrieval インデックスを増分更新する。トランザクション実行はブロックしない
  (§III-A, §III-B, Fig. 2)。
- [paper] インデックス状態は transactional log のみから導出される(log が単一の導出元)。
  よって primary DB 状態に触れずに rebuild / reshard が可能 (§III-B)。
- [paper] shard = ストレージ・スケジューリング・実行の基本単位。shard 境界は
  transactional partition から独立で、retrieval 性能に最適化したレイアウトを取れる。
  各 shard は 1 つの MPP task が独立処理 (§III-C)。
- [paper] fragment = shard をさらに分解した immutable セグメントで、「有界な範囲の
  トランザクション更新」の上に構築される。seal 後は不変となりクエリ対象になる。
  shard 内 fragment は定期的に非同期 merge(lookup オーバーヘッド削減。クエリは
  ブロックしない)(§IV-B)。
- [paper] 一貫性モデル: 既定は bounded-staleness。retrieval クエリは「指定 checkpoint
  までの log から導出された index fragment の一貫スナップショット」上で実行され、
  1 クエリ内の全 retrieval 演算子は同一スナップショットを観測する (§IV-E)。より強い
  保証が必要な場合は retrieval 実行を transactional timestamp と協調させられる
  (indexing throughput と freshness のトレードオフと記述)(§IV-E)。評価では strong
  freshness を「full-text index の checkpoint が最新 commit を覆うまでクエリ側が待つ」
  方式で実現している (§V-D)。
- [paper] 永続化: 評価構成では index を AWS S3 object storage に materialize し、
  クエリ実行時に TiFlash が直接アクセスする (§V-A)。
- [paper] 障害・回復: fragment ベース設計により「log の再生による効率的な recovery」と
  全面再構築なしの online index evolution が可能と主張 (§IV-B)。それ以上の故障モデルの
  記述(index service 故障、S3 障害、checkpoint 破損等)はない。
- [inference] 評価クラスタには TiCDC ノードが 1 台含まれる (§V-A) が、本文は TiRex の
  log 消費経路と TiCDC の関係を明示しない。Raft log を直接読むのか CDC ストリーム経由かは
  読み取れない。[question] アーキテクチャ的には staleness bound と回復手順の実体は
  この消費経路に依存するはずで、本文の記述粒度では検証できない。
- [inference] 旧ノートの [question]「bound が何で規定されるか」への答え: 本文に形式定義は
  ないが、評価では「configured lag = 20s」という**時間ベースの設定値**として運用され、
  観測された可視性 lag P95 は 15.1s (§V-D, Table III)。設定 lag に対する保証(上限保証か
  best-effort か)は記述がない。
- [inference] 「without impacting transactional processing」(abstract) の実体は、
  (a) log 駆動・非同期のインデックス構築で OLTP write path から外す、(b) TiRex
  Meta/Worker を専用ノードに置く物理分離、の 2 点であり、リソースガバナンス
  (CPU/IO 制御)のような機構は記述されていない。実測では P99 は増える(下記)。

## Approach
- [paper] **Decoupled indexing model (§IV-A)**: retrieval インデックスは write path 上の
  同期更新ではなく transactional log 駆動で構築・維持される。これにより indexing コストが
  OLTP レイテンシに直接影響せず、indexing スループットを TX ワークロードから独立に
  スケールできると主張。full-text index は term dictionary・posting list・ranking metadata
  を持ち、vector index は embedding と ANN 構造を持つが、全 index type が共通の
  ライフサイクルに従う: log consumption → shard assignment → index update → persistence。
- [paper] **Fragment ライフサイクル (§IV-B)**: log 消費に伴い新 fragment を生成、seal で
  immutable 化しクエリ対象へ。shard 内で非同期 merge。増分構築・log replay による回復・
  全再構築なしのオンライン index evolution がこの設計の効能として挙げられる。
- [paper] **クエリプランニング (§IV-C, Fig. 3)**: プランナが retrieval インデックスで
  評価可能な述語(keyword matching / vector similarity 条件)を特定して retrieval operator
  に変換し、コスト見積りを付与して relational operator と同一実行プラン内でスケジュール
  する。filter / join / aggregation との自然な合成が可能。Fig. 3 は 1 つの SQL クエリが
  inverted index・vector index・その他 columnar index を横断検索する図。
- [paper] **MPP 実行 (§IV-D)**: retrieval operator は共有 MPP エンジンで実行。各 MPP task
  に 1 個以上の index shard を割当てて独立処理。full-text task は posting list 上で
  keyword 述語を評価し relevance score を計算、vector task は vector fragment 上で
  近似最近傍探索。結果は同一実行パイプライン内の下流 relational operator へ渡る。
- [paper] **一貫性実行 (§IV-E)**: 前節のとおり(checkpoint スナップショット + クエリ内
  スナップショット一貫性 + 選択的 strong freshness)。
- [inference] 全体構図は「log を single source of truth とする LSM 風の派生インデックス
  (immutable segment + merge)を、既存 MPP の演算子として同居させる」という工学的
  統合であり、新しいアルゴリズム(索引構造・CC プロトコル)の提案はない。索引構造自体は
  既存技術(inverted index、HNSW [14])をそのまま使う (§V-C)。

## Evaluation
- Setup [paper] (§V-A): AWS EC2、全コンポーネント c8i-flex.2xlarge(8 vCPU / 16 GiB)。
  TiKV 3 台 + PD / TiDB / TiFlash / TiCDC / TiRex Meta / TiRex Worker 各 1 台。index は
  S3 に materialize し TiFlash がクエリ時に読む。最新 OSS の TiDB/TiKV/TiFlash
  コードベース上に構築(TiRex 本体は未公開、ベンチハーネスは公開 [21])。データ:
  Wikipedia パラグラフ + 事前計算 sentence embedding(all-MiniLM-L6-v2、Hugging Face の
  Maloyan データセット [20])。各レコードは text・embedding・metadata(title、view 統計)。
  term-match 対象テーブルは 1,272,464 行 (§V-C)。ワークロードは (i) insert-only
  (1 txn = 1 insert)/ update-mixed(50% insert・50% 既存レコード update)(§V-B)、
  (ii) term-match(exact/prefix/ngram。relevance ranking なし)、(iii) vector top-k、
  (iv) composed(filter-then-count / 言語等での group-by + top-N / view 統計での top-N
  ranking)(§V-A, §V-C)。
- Baselines [paper]: TiRex index なしの同一クエリ意味論 — term-match は TiFlash MPP の
  scan + SQL LIKE 述語、vector は TiFlash vector index [22]。HNSW パラメータは TiRex /
  TiFlash とも同一(M=16, ef_construction=64, ef_search=16)、k=10 (§V-A, §V-C)。
- OLTP への影響 (Table I, §V-B): insert-only は 6349→6157 txn/s、P95 16.77→16.92ms、
  P99 19.03→26.51ms。update-mixed は 6658→6438 txn/s、P95 15.5→16.6ms、
  P99 29.9→52.6ms。著者の解釈は「スループットと typical latency への影響は限定的、
  P99 は modest に増加」。
  [inference] P99 の相対増は +39% / +76% であり「modest」はやや強気の表現。増加経路
  (log 消費の I/O 競合か、TiKV 側の追加負荷か)の分析は示されていない。
- Retrieval / 混合 (Table II, §V-C): term-match は 38.6→6043.9 QPS(約 157×
  [inference])、P99 1197.4→4.3ms。vector top-k は 526.3→3752.4 QPS(約 7.1×
  [inference])、P99 42.9→8.6ms(双方 HNSW、同一設定)。Mixed(term-match +
  metadata 述語 + 軽量集約)は 31.1→1169.2 QPS で、TiRex 時 P50 13.3 / P95 20.0ms
  (retrieval 段)、P99 23.9ms(analytical 段)— Mixed の P50/P95 は retrieval 段、
  P99 は analytical 段の tail という変則的な報告形式 (Table II caption)。
- 実運用報告 [paper] (§V-C, p.5–6): TiDB Cloud 上の実ユーザワークロード。100 億行 /
  base データ 10TB + TiRex index 6TB、TiRex + TiFlash 40 CPU コア。複数 filter + sort +
  LIMIT (top-N) の代表クエリで 3500 QPS 持続、P99 30ms。
- Freshness トレードオフ (Table III, §V-D): bounded(設定 lag 20s)= 可視性 lag P95
  15.1s、indexing 4004.4 row/s、query P95/P99 = 98/101ms。strong(0s)= lag P95 0.6s、
  3856.0 row/s、query P95/P99 = 623/655ms。strong は write path と indexing throughput
  にはほぼ影響しない(クエリ時待機で実現するため)が、クエリ P99 は 101ms→655ms。
  既定は bounded、最新可視性が必要なクエリのみ strong を推奨 (§V-D)。
- [inference] 評価がカバーしていないもの:
  - **外部専用システムとの比較がない。** 動機は「外部検索/ベクタ DB 併設のコスト」なのに
    (§II-B)、比較対象は自前の scan(LIKE)と TiFlash vector index のみ。LIKE scan は
    term-match の対抗としては最弱級のベースライン。
  - ANN の recall / 精度が未報告(ef_search=16 固定、レイテンシ/QPS のみ)。
  - relevance ranking は評価対象外(term-match は「ranking なし」と明記 §V-A)。
    §IV-A で ranking metadata の保持を謳うが、ランキングを含む検索品質・性能は未検証。
  - §V-B は「増加する write レート下で indexing throughput を評価」と書くが、示される
    数値は Table I の 2 ワークロード構成のみで、write レート掃引のスケーリング曲線は
    ない。TiRex Worker は 1 台で、shard ベース scheduling のスケールアウト
    (Worker/shard 数を振る実験)も未測定。
  - 共有 MPP エンジン上での AP と retrieval の資源競合(飽和時の相互干渉)、
    log replay による回復、reshard のコストは、いずれも設計上の主張のみで実験なし。
  - 主ベンチのテーブルは 127 万行と小規模。100 億行の結果は実運用報告であり、
    構成詳細・クエリ詳細が限定的で再現不能。
- [question] Table III の bounded モードの query P95 98ms は、Table II の term-match
  P95 3.6ms と 27 倍乖離している。並行 ingest(約 4000 row/s)下での測定と推測されるが
  測定条件の明示がなく、fragment 蓄積(merge 前の断片数増加)の影響かは本文から
  判別できない。

## Limitations
- Stated [paper]:
  - TiRex indexing 有効化で OLTP の P99 が増える(insert-only 19.03→26.51ms、
    update-mixed 29.9→52.6ms。著者は modest と評価)(Table I, §V-B)。
  - strong freshness はクエリレイテンシを大きく悪化させる(P99 101→655ms)。
    bounded staleness を既定とし、最新可視性が必要なクエリに限って strong を使う
    運用を推奨 (§V-D, Table III)。
  - transactional timestamp と協調する強い保証は indexing throughput と freshness の
    トレードオフを伴う (§IV-E)。
  - future work として: 対応 retrieval primitive の拡充、retrieval-aware なコストモデルの
    改善、learning-driven data processing とのより密な統合 (§VI)。
- Inferred [inference]:
  - TiRex 本体が未公開(§V-A「open-source 予定」)のため、主張の再現検証は現時点で
    ベンチハーネス [21] のみでは不可能。
  - shard 境界を「retrieval 性能に最適化できる」(§III-C) と言うが、境界の決定方法・
    再 shard のトリガ・コストは一切記述がない。shard 設計こそ scheduling モデルの
    肝のはずで、ワークショップ論文としても最も薄い部分。
  - immutable fragment 上での update / delete の扱い(tombstone、HNSW グラフからの
    削除、merge 時の再構築コスト)が記述されていない。update-mixed ワークロードは
    走らせている (Table I) が、update が retrieval index 側でどう処理されるかは不明。
  - bounded staleness が「設定 lag を超えない」保証を持つのか best-effort かが不明
    (Table III は設定 20s に対し観測 P95 15.1s という 1 点のみ)。
  - 旧ノートの [question]「レイテンシ志向の retrieval とスループット志向の AP の
    スケジューリング要求の衝突」は本文でも実質未回答 — cost estimate を付与して同一
    プランに載せる (§IV-C) 以上の機構(優先度、アドミッション制御)は記述がない。

## Relations
- 参照ベースライン/構成要素(本文): TiDB/TiKV/TiFlash [2]、TiFlash vector index [22]、
  HNSW [14]。関連系譜: HANA / HyPer / SingleStore / HeatWave / AlloyDB(HTAP、§II-A)、
  Lucene / FAISS / DiskANN / Milvus(検索・ベクタ、§II-B)、Snowflake / Aurora
  (storage-compute 分離、§II-C)。
- [[2026-pvldb-ding-jasper-htap.md]](Jasper: TiDB 上の HTAP ストレージレイアウト):
  同じ TiDB 系で、Jasper は TiKV↔TiFlash 同期がもたらす freshness と分離のトレードオフを
  レイアウト最適化で攻める。TiRex は第 3 のワークロード(retrieval)を log 由来の独立
  インデックスとして追加し、freshness を bounded staleness という明示ノブに落とす。
  [inference] TiRex の Table I の P99 増加は、Jasper が問題化した「同期による TP 干渉」の
  retrieval インデックス版と読め、干渉経路の分析には Jasper の測定手法が流用できそう。
- [[2026-pvldb-wu-aqd.md]](AQD: HTAP クエリディスパッチ): AQD は行/列 2 エンジンの
  ディスパッチを学習で解く。TiRex は retrieval operator に cost estimate を付与して
  relational と同一プランでスケジュールする (§IV-C) が、コストモデルの中身は未記述で
  改善は future work (§VI)。[inference] HTAIP ではディスパッチ/プランニング問題が
  TX/AP/retrieval の 3 系統に拡張されるので、AQD 型の学習ディスパッチの自然な適用先。
- [[2026-pvldb-kuschewski-btrlog.md]](BtrLog: クラウド WAL サービス): [inference]
  接点は「durable log を single source of truth として下流の派生構造を導出する」構図。
  BtrLog は log サービス自体の低遅延化・エンジン非依存化、TiRex はその log の下流消費者
  (派生 retrieval インデックス、§III-B)。log 側の checkpoint / 再生 API の設計が
  TiRex 型派生インデックスの staleness bound と回復にどう効くかは、両ノートを跨ぐ論点。

## Idea seeds
- [inference] **Freshness の中間クラス設計。** TiRex の評価は bounded(20s)と strong
  (クエリ時待機)の両極のみ (Table III)。per-query の freshness 要求(例: セッション内
  read-your-writes、特定 shard のみ強制追いつき)を宣言でき、checkpoint 前進を
  クエリ需要駆動で優先制御するスケジューラは、Table III の 6.5× のレイテンシ断崖を
  なだらかにできる可能性がある。検証第一歩: 公開ハーネス
  (https://github.com/kolafish/wiki-vec-bench) で lag 設定を 0–20s の間で掃引し、
  待機時間と可視性 lag の分布(断崖か連続か)を測る。
- [inference] **vector fragment の merge ポリシーは未開拓の核心。** immutable fragment +
  非同期 merge (§IV-B) は LSM 的だが、HNSW のようなグラフ ANN は追記融合できず
  merge = 再構築に近いはず。fragment 数(=検索対象グラフ数)× recall × merge コストの
  トレードオフは、LSM compaction 研究の retrieval 版として独立した研究になり得る。
  検証第一歩: fragment 数を人工的に振り、top-k 検索の latency と recall の劣化曲線を
  実測する(TiRex 非公開のため、まずは Lucene/HNSW 系 OSS 上で模擬)。
- [question] **HTAIP ベンチマークの不在(旧ノートの question を本文で確認)。** 本文は
  Wikipedia データ + 自作ハーネスで評価しており、TX+AP+retrieval の標準混合ベンチマークは
  使われていない(存在への言及もない)(§V-A)。CH-benCHmark に term-match / vector /
  composed クエリと freshness 指標(可視性 lag)を接ぎ木した「HTAIP-bench」は、
  TiRex 型(log 派生)・密結合型(TiFlash vector index)・外部併設型を同一条件で比較する
  土台になる。第一歩: Table II 相当のクエリ 4 種を CH-benCHmark のスキーマに写像できるか
  机上検討。
- [question] **並行 ingest 下の retrieval レイテンシ劣化の要因分解。** Table II(3.6ms)と
  Table III(98ms)の P95 乖離が ingest 併走によるものなら、その内訳(S3 読み、fragment
  数、checkpoint 待ち)の測定は log 派生インデックス一般の設計指針になる。公開ハーネスで
  ingest レートを振って再現するところから。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: 検証パスによる修正(Evaluation 節の引用を原文どおり「low-latency full-text and vector search」に訂正)
- 2026-07-06: full-text 格上げ(status: abstract-only → read。手動取得した PDF 全文を読解し全節を執筆)
