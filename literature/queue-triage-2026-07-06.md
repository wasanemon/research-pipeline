# キュー剪定一覧(2026-07-06)

対象: 未ノート化の adjacent 32 本 + borderline 16 本(計 48 本)。
各論文の abstract を取得し、CLAUDE.md のスコープ規約と第1回スイープの却下基準に
沿って機械的に推奨を付けた(4評価エージェント+整合性レビュー)。

**使い方**: 推奨に同意なら何もしなくて OK。覆す場合は行頭のチェックボックスに x を
入れてください(`[x]` = 推奨と逆にする)。確認が終わったら「剪定反映して」と一言ください。
`drop` 確定分は queue.md で `relevance` 行に `PRUNED` を追記し(エントリ自体は履歴として残す)、
`keep` 分を次のノート化バッチに回します。

集計: 残す 33 / 保留 0 / 落とす 15

## 残す(ノート化対象) — 33本

### CXL/disaggregated
- [ ] **Declarative Memory Services** — CIDR 2026(元判定: adjacent)
  - 推奨理由: HBM・PIM・CXL 等の新メモリデバイスを宣言的に扱う CIDR ビジョン論文で、キーワード disaggregated memory とメモリ-ディスク階層研究に直接材料を与える。
  - id: dblp:conf/cidr/CastrillonGHKSS26 | https://vldb.org/cidrdb/2026/declarative-memory-services.html
- [ ] **Hash Joins Meet CXL: A Fresh Look** — CIDR 2026(元判定: adjacent)
  - 推奨理由: CXL メモリと DRAM 間のデータ移動コストを織り込んだ hash join の性能モデルと配置戦略で、キーワード disaggregated memory・メモリ階層に直結。クエリ実行系だが CXL キーワードへの直接フックがある点で idx 33/37/39 と区別して keep。
  - id: dblp:conf/cidr/HuangLT26 | https://vldb.org/cidrdb/2026/hash-joins-meet-cxl-a-fresh-look.html
- [ ] **Xerxes: Extensive Exploration of Scalable Hardware Systems with CXL-Based Simulation Framework** — FAST 2026(元判定: adjacent)
  - 推奨理由: 最新 CXL 機能を忠実にモデル化するオープンソースシミュレータで、disaggregated memory 研究の実験基盤を与える(監視会場 FAST)。スコープキーワード直結の評価ツールは keep とする基準(idx 30/36/45 と同じ)。
  - id: dblp:conf/fast/AnY00ZZ000L026 | https://www.usenix.org/conference/fast26/presentation/an
- [ ] **Cylon: Fast and Accurate Full-System Emulation of CXL-SSDs** — FAST 2026(元判定: adjacent)
  - 推奨理由: CXL-SSD のフルシステムエミュレータ(実機検証済み)で、disaggregated memory キーワードに関わる CXL 研究の評価基盤を提供。スコープキーワード直結の評価ツールは keep とする基準(idx 23/36/45 と同じ)。
  - id: dblp:conf/fast/YoonILINL26 | https://www.usenix.org/conference/fast26/presentation/yoon

### LSM/コンパクション
- [ ] **RecDB: An LSM-Tree based Storage System for Training Large Recommendation Model in Low-Resource Scenarios** — EDBT 2026(元判定: adjacent)
  - 推奨理由: 応用は推薦モデル学習だが、貢献は compaction picker・compaction scheduler・read/compaction 干渉回避という汎用 LSM エンジン内部技術(スコープキーワード LSM-tree、監視会場 EDBT)。判断軸は「貢献が汎用エンジン技術か ML ワークロード特化か」であり、KV キャッシュ管理が中核の idx 6 と異なり汎用側なので keep。
  - id: doi:10.48786/EDBT.2026.37 | https://doi.org/10.48786/edbt.2026.37
- [ ] **FicusDB: Scalable Multi-Versioned Authenticated Archival Storage** — EuroSys 2026(元判定: adjacent)
  - 推奨理由: 対象は Ethereum アーカイブノードだが、貢献は CoW トライ向けログ構造化ストレージ層の再設計(コンパクション不要の追記ログ、CoW-aware キャッシュ、書き込み増幅削減)で、多バージョンストレージエンジン/キャッシュ設計に直接材料を与える(監視会場 EuroSys)。ブロックチェーン応用でも汎用ストレージ貢献ありの例外に該当。
  - id: doi:10.1145/3767295.3803601 | https://doi.org/10.1145/3767295.3803601

### MVCC/HTAP
- [ ] **TVA: A Version-aware Temporal Graph Storage System for Real-time Analytics** — arXiv 2026(元判定: adjacent)
  - 推奨理由: 対象はグラフ分析だが、中核は version metadata と実データを分離する多版ストレージアーキテクチャとランダム I/O 削減であり、MVCC 系・ストレージエンジン設計に直接材料を与える。グラフ応用でも貢献が汎用ストレージ技術なら keep とする基準(idx 2/5/9 と同じ)に合致。
  - id: arxiv:2607.00406 | http://arxiv.org/abs/2607.00406v1
- [ ] **ByteGraph-Dione: An Adaptive Dual-Format Graph Engine with Hotspot Awareness and Transaction Efficiency for Production-Scale Workloads** — SIGMOD Companion 2026(元判定: adjacent)
  - 推奨理由: OLTP 更新と Snapshot Isolation 下の OLAP 読取の緊張による過剰バージョン保持という MVCC/HTAP の中核課題を本番規模で扱う。グラフエンジンだがトランザクション機構・フォーマット適応が主題で採択圏(abstract は冒頭段落のみ入手可の点は留意)。
  - id: doi:10.1145/3788853.3803073 | https://doi.org/10.1145/3788853.3803073

### SSD/IO経路
- [ ] **UnICom: A Universally High-Performant I/O Completion Mechanism for Modern Computer Systems** — FAST 2026(元判定: adjacent)
  - 推奨理由: polling と interrupt の欠点を統合的に解消する I/O completion 機構で、NVMe/CXL-SSD 時代の I/O スタックのソフトウェアオーバーヘッドを削る。監視会場 FAST で、ストレージエンジンの I/O 経路研究に直接材料を与える。
  - id: dblp:conf/fast/Pan0NLGKX26 | https://www.usenix.org/conference/fast26/presentation/pan
- [ ] **DPAS: A Prompt, Accurate and Safe I/O Completion Method for SSDs** — FAST 2026(元判定: adjacent)
  - 推奨理由: SSD の polling/interrupt/hybrid polling を動的に切り替える I/O completion 手法で、YCSB 評価が示す通り DB 的ワークロードの I/O パスに直接効く(監視会場 FAST)。idx 24 と同種の keep。
  - id: dblp:conf/fast/SeoJYCJLD26 | https://www.usenix.org/conference/fast26/presentation/seo
- [ ] **Characterizing and Emulating FDP SSDs with WARP** — FAST 2026(元判定: adjacent)
  - 推奨理由: FDP SSD の write amplification 特性を RUH 分離とオブジェクト寿命の観点で実測・エミュレートしており、LSM-tree / WAL のデータ配置研究に直接材料を与える(監視会場 FAST)。
  - id: dblp:conf/fast/SongQ0BNL26 | https://www.usenix.org/conference/fast26/presentation/song
- [ ] **Unleashing Zoned UFS: Cross-Layer Optimizations for Next-Generation Mobile Storage** — FAST 2026(元判定: borderline)
  - 推奨理由: モバイル向けだが、zoned storage の逐次書き込み制約下での write ordering 保証・ゾーン GC・デバイス側バッファ管理は LSM-on-ZNS 研究と同一の問題空間で、監視会場 FAST のストレージエンジン/メモリ-ディスク階層の材料になる。
  - id: dblp:conf/fast/KimKCPKKOLAJVK26 | https://www.usenix.org/conference/fast26/presentation/kim-jungae

### WAL/コミット
- [ ] **LazyLog: A New Shared Log Abstraction for Low-Latency Applications** — SOSP 2024(元判定: adjacent)
  - 推奨理由: shard 横断の linearizable 順序付けを読み出し時まで遅延束縛する shared log 抽象で、ログ/コミット順序・分散トランザクションのスコープに直結。BtrLog が対置する設計点の一次文献としても必要(監視会場 SOSP)。
  - id: doi:10.1145/3694715.3695983 | https://doi.org/10.1145/3694715.3695983

### ストレージインフラ
- [ ] **Twenty Years of Bigtable** — SIGMOD Companion 2026(元判定: borderline)
  - 推奨理由: LSM 系ストレージエンジンそのものである Bigtable の 20 年の機能追加・大規模運用知見を述べる産業回顧で、一次資料として採択圏(SIGMOD 系)。クラウドインフラ回顧の idx 29(drop)とは対象がスコープ中核のエンジンである点で区別。
  - id: doi:10.1145/3788853.3803095 | https://doi.org/10.1145/3788853.3803095
- [ ] **Cloudspecs: Cloud Hardware Evolution Through the Looking Glass** — CIDR 2026(元判定: borderline)
  - 推奨理由: ネットワーク帯域は改善する一方 NVMe 性能は停滞というボトルネック移動を定量化する CIDR の計測分析で、disaggregated memory/storage やストレージエンジン設計の前提を直接与える。ベンダーサービス回顧の idx 29(drop)とは、エンジン設計判断に使える定量データが主体である点で区別。
  - id: dblp:conf/cidr/SteinertKL26 | https://vldb.org/cidrdb/2026/cloudspecs-cloud-hardware-evolution-through-the-looking-glass.html

### ストレージ階層/tiering
- [ ] **TierScape: Harnessing Multiple Compressed Tiers to Tame Server Memory TCO** — EuroSys 2026(元判定: adjacent)
  - 推奨理由: 圧縮メモリ多層とバイトアドレサブル層をまたぐデータ配置・移動のコストモデルと動的管理で、監視会場 EuroSys の memory-disk 階層(tiering)研究として採択圏。larger-than-memory / buffer management 研究の材料。
  - id: doi:10.1145/3767295.3769321 | https://doi.org/10.1145/3767295.3769321
- [ ] **Getting the MOST out of your Storage Hierarchy with Mirror-Optimized Storage Tiering** — FAST 2026(元判定: adjacent)
  - 推奨理由: ホットデータの部分ミラーリングで tiering の空間効率と負荷分散を両立するストレージ階層化で、メモリ-ディスク階層・larger-than-memory 系研究に直結(監視会場 FAST)。
  - id: dblp:conf/fast/TuWAA26 | https://www.usenix.org/conference/fast26/presentation/tu

### テスティング/ツール
- [ ] **ResBench: A Comprehensive Framework for Evaluating Database Resilience** — SIGMOD Companion 2026(元判定: borderline)
  - 推奨理由: トランザクション処理中に障害イベントを注入し recovery 含む8次元で DB のレジリエンスを定量化するベンチマークで、スコープキーワード recovery の評価系に実質的に関わる。運用系(障害予測等)の却下基準とは異なる研究評価ツール(idx 45 と同種)。
  - id: doi:10.1145/3788853.3801615 | https://doi.org/10.1145/3788853.3801615
- [ ] **2DIO: Configurable and Cache-Accurate Trace Generation for Storage Benchmarking** — EuroSys 2026(元判定: borderline)
  - 推奨理由: 性能クリフ/プラトーを含むキャッシュ挙動を eviction policy 横断で正確に再現できるトレース生成器で、buffer management・キャッシュ(スコープキーワード)研究の評価手法に直接材料を与えるツール(監視会場 EuroSys)。スコープ直結の評価ツールは keep の基準(idx 23/30/36 と同じ)。
  - id: doi:10.1145/3767295.3769391 | https://doi.org/10.1145/3767295.3769391

### トランザクション/CC
- [ ] **Lockify: Understanding Linux Distributed Lock Management Overheads in Shared Storage** — FAST 2026(元判定: adjacent)
  - 推奨理由: 共有ディスクファイルシステムにおける分散ロックマネージャのオーバーヘッド分析と所有権の非同期管理による改善で、共有ストレージ上のロック管理・並行性制御に実質的に関わる(監視会場 FAST)。
  - id: dblp:conf/fast/ParkJHNH26 | https://www.usenix.org/conference/fast26/presentation/park
- [ ] **Thunderbolt: Concurrent Smart Contract Execution with Non-blocking Reconfiguration for Sharded DAGs** — EDBT 2026(元判定: borderline)
  - 推奨理由: ブロックチェーン文脈だが、abstract に read/write set の事前宣言なしに実行時依存解決を行う動的 concurrency controller と決定的順序付けという、deterministic database / CC 研究に直接接続する汎用技術貢献が明示されている。「一般的 CC/consensus 貢献があればブロックチェーン特化却下の例外」とした idx 13/17 と同じ基準で keep に統一。
  - id: doi:10.48786/EDBT.2026.07 | https://doi.org/10.48786/edbt.2026.07

### バッファ/キャッシュ
- [ ] **PaCaR: Improved Buffered I/O Locality on NUMA Systems with Page Cache Replication** — EuroSys 2026(元判定: adjacent)
  - 推奨理由: NUMA ノード間でページキャッシュを透過的に複製し buffered I/O の局所性を高める OS レイヤ機構で、buffer management・メモリ階層に実質的に関わる(監視会場 EuroSys)。DB バッファ管理研究の材料。
  - id: doi:10.1145/3767295.3769359 | https://doi.org/10.1145/3767295.3769359
- [ ] **ScaleSwap: A Scalable OS Swap System for All-Flash Swap Arrays** — FAST 2026(元判定: adjacent)
  - 推奨理由: 全フラッシュ swap アレイ上の OS スワップのコア/SSD スケーラビリティ改善(LRU ロック競合緩和等)で、キーワード larger-than-memory とメモリ-ディスク階層に直結。DB の far-memory 研究の直接の材料。
  - id: dblp:conf/fast/AhnY0S26 | https://www.usenix.org/conference/fast26/presentation/ahn

### レプリケーション/合意
- [ ] **Proof-of-Execution: Low-Latency Consensus via Speculative Execution** — ACM Trans. Database Syst. 2026(元判定: adjacent)
  - 推奨理由: ブロックチェーン動機だが、投機実行による遅延最小化と単一ラウンド check-commit という汎用の低遅延コンセンサス技術の貢献があり、「一般的 CC/consensus 貢献がない場合のみ却下」の例外に当たる(監視誌 TODS)。idx 17/38 と同じ基準。
  - id: doi:10.1145/3774322 | https://doi.org/10.1145/3774322
- [ ] **OptiLog: Assigning Roles in Byzantine Consensus** — EuroSys 2026(元判定: adjacent)
  - 推奨理由: ブロックチェーン文脈の BFT だが、貢献はプロトコル横断で適用できる役割割当・レプリカ説明責任という一般的コンセンサス最適化で、ブロックチェーン特化の却下基準には当たらない(監視会場 EuroSys)。idx 13/38 と同じ基準。
  - id: doi:10.1145/3767295.3769342 | https://doi.org/10.1145/3767295.3769342
- [ ] **Avicenna: Masking Slowdowns in Replicated State Machines with Counterfactual Evaluation** — EuroSys 2026(元判定: adjacent)
  - 推奨理由: fail-slow レプリカを許容しつつ Multi-Paxos 並みの通常時レイテンシを保つ汎用合意プロトコル(EuroSys)。一般的 consensus/レプリケーション技術の貢献で distributed transactions のスコープに実質的に関わる。
  - id: doi:10.1145/3767295.3803615 | https://doi.org/10.1145/3767295.3803615

### 分散DB/シャーディング
- [ ] **TDSQL-Boundless: A Distributed Database System for Large-scale Heterogeneous Multi-Table Workloads** — SIGMOD Companion 2026(元判定: adjacent)
  - 推奨理由: abstract(冒頭のみ取得可)でクロスサーバのシャーディング、メタデータ管理・分散協調オーバーヘッドという分散 DBMS の中核課題を扱うと明言。分散トランザクション/DBMS のスコープに直球の産業システム論文。
  - id: doi:10.1145/3788853.3803090 | https://doi.org/10.1145/3788853.3803090

### 索引
- [ ] **Efficient Temporal Subgraph Management: A New Interval Index** — Proc. VLDB Endow. 2026(元判定: adjacent)
  - 推奨理由: 対象アプリはグラフだが、abstract 自身が汎用の区間索引構造(線形サイズ・準最適問合せ時間・更新コスト最適)と位置づける提案で、監視会場 PVLDB の索引研究として採択圏。グラフ応用でも汎用索引貢献なら keep の基準に合致。
  - id: dblp:journals/pvldb/OuyangWWZLL26 | https://www.vldb.org/pvldb/vol19/p1170-wen.pdf
- [ ] **LiBox: A Learned Index as an Array to Minimize Last-Mile Search** — Proc. VLDB Endow. 2026(元判定: adjacent)
  - 推奨理由: learned index の last-mile search を AVX-512 一命令に抑える索引構造の設計と再編成コスト隠蔽で、PVLDB の索引研究そのもの。却下基準の ML4DB はノブ/インデックス推薦チューニングを指し、learned index 構造自体は対象外ではない。
  - id: dblp:journals/pvldb/ZhouWZZJ26 | https://www.vldb.org/pvldb/vol19/p836-jiang.pdf
- [ ] **DCSR: A Fast Data Structure with Leaf-Oriented Locks for Streaming Graph Processing** — EDBT 2026(元判定: adjacent)
  - 推奨理由: 対象はストリーミンググラフだが、実体は PMA ベースのリーフ単位ロック+分離リバランスという並行ソート済みデータ構造の更新戦略で、索引・並行データ構造研究に直接材料を与える(監視会場 EDBT)。グラフ応用でも汎用データ構造貢献なら keep の基準に合致。
  - id: doi:10.48786/EDBT.2026.29 | https://doi.org/10.48786/edbt.2026.29
- [ ] **Raster is Faster: Rethinking Ray Tracing in Database Indexing** — CIDR 2026(元判定: adjacent)
  - 推奨理由: ラスタライゼーションによる column indexing(RasterScan)を提案し索引の構築・検索性能を評価。監視会場 CIDR かつ indexing は採択圏の明示対象。
  - id: dblp:conf/cidr/DoraiswamyH26 | https://vldb.org/cidrdb/2026/raster-is-faster-rethinking-ray-tracing-in-database-indexing.html
- [ ] **Mitigating False Positives in Filters: To Adapt or to Cache?** — ACM Trans. Database Syst. 2026(元判定: adjacent)
  - 推奨理由: Bloom/quotient 系フィルタは LSM 等ストレージエンジンの基本部品であり、適応フィルタとキャッシュ付きフィルタの偽陽性率を理論・実験両面から比較する TODS 論文。エンジン内フィルタ選択の直接的な材料。
  - id: doi:10.1145/3786324 | https://doi.org/10.1145/3786324
- [ ] **Scalable lighting-fast temporal indexing** — VLDB J. 2026(元判定: adjacent)
  - 推奨理由: temporal indexing で live/dead レコードを分離する LIT と、メモリ予算超過分をディスクに退避する LIT+ の提案で、索引かつ larger-than-memory / メモリ-ディスク階層のキーワードに直接合致。
  - id: doi:10.1007/S00778-026-00968-6 | https://doi.org/10.1007/s00778-026-00968-6

## 落とす(ノート化しない) — 15本

### HWアクセラレータ
- [ ] **LightDSA: Enabling Efficient DSA Through Hardware-Aware Transparent Optimization** — EuroSys 2026(元判定: adjacent)
  - 推奨理由: Intel DSA オフロードの内部機構分析と透過的最適化ライブラリで、評価はマイクロベンチと Redis に留まり、DB/ストレージエンジンへの接点は「利用可能性」止まり。HW アクセラレータ活用が主眼で DB 接点が間接的という点は idx 44(ASIC 圧縮アクセラレータ)と同型のため、同じ扱いで drop に統一。
  - id: doi:10.1145/3767295.3769356 | https://doi.org/10.1145/3767295.3769356
- [ ] **ASIC-based Compression Accelerators for Storage Systems: Design, Placement, and Profiling Insights** — EuroSys 2026(元判定: borderline)
  - 推奨理由: ASIC 圧縮アクセラレータのマイクロアーキテクチャ設計・データセンター内配置・電力効率プロファイリングが主眼で、hyperscale ストレージインフラ向けの HW 側の知見。TP/ストレージエンジン研究への接点は間接的でスコープ外(idx 20 と同じ扱いに統一)。
  - id: doi:10.1145/3767295.3769384 | https://doi.org/10.1145/3767295.3769384

### ML/LLM応用
- [ ] **TokaDB: A Unified Storage Engine for Training-Serving Data Management in Large Recommendation Models** — SIGMOD Companion 2026(元判定: adjacent)
  - 推奨理由: Transformer ベース推薦モデルの training-serving 向けストレージで、エクサバイト級 KV Cache 管理が中核。貢献が ML ワークロード特化(学習/サービング向けストレージ・KV キャッシュ)であり却下基準に該当。汎用 LSM 内部技術が貢献の idx 8 とは判断軸(汎用か特化か)で区別。
  - id: doi:10.1145/3788853.3803078 | https://doi.org/10.1145/3788853.3803078
- [ ] **When Classic Cache Policies Fail: Learning-Augmented Replacement for Semantic Retrieval Buffers** — arXiv 2026(元判定: borderline)
  - 推奨理由: 対象は LLM エージェントの semantic retrieval buffer で、embedding 類似度マッチという設定は DB のバッファ管理と本質的に異なる(temporal locality 不在を自ら指摘)。LLM サービング系キャッシュの却下基準に該当し、buffer management のキーワード一致は表面的。
  - id: arxiv:2607.00394 | http://arxiv.org/abs/2607.00394v1
- [ ] **Query Performance Explanation through Large Language Model for HTAP Systems** — EDBT 2026(元判定: borderline)
  - 推奨理由: HTAP はキーワード一致だが、主題は RAG+LLM によるクエリ性能差の自然言語説明フレームワークで、ML4DB/ユーザ支援系の却下カテゴリに該当。HTAP システム内部への技術的貢献はなく接点は表面的。
  - id: doi:10.48786/EDBT.2026.09 | https://doi.org/10.48786/edbt.2026.09
- [ ] **Efficient graph embedding at scale: optimizing CPU-GPU-SSD integration** — VLDB J. 2026(元判定: borderline)
  - 推奨理由: 貢献(prefetch 順序、GPU-SSD 直結ドライバ、GPU 稼働率最大化)はグラフ埋め込み学習という ML ワークロード専用の最適化で、ML 学習向けストレージの却下カテゴリに該当(idx 6 と同じ扱い)。memory-disk 階層のキーワード一致は表面的。
  - id: doi:10.1007/S00778-026-00974-8 | https://doi.org/10.1007/s00778-026-00974-8

### クエリ実行/加速
- [ ] **CoddSpeed: Hardware Accelerated Query Processing in Microsoft Fabric** — SIGMOD Companion 2026(元判定: borderline)
  - 推奨理由: GPU/FPGA/ASIC による分析(OLAP)クエリ実行の加速が主題で、TP/ストレージエンジン/索引/回復/メモリ-ディスク階層のいずれにも実質的に関わらない。純クエリ実行加速は drop とする基準(idx 37/39 と同じ)。
  - id: doi:10.1145/3788853.3803077 | https://doi.org/10.1145/3788853.3803077
- [ ] **Rethinking Relational Operators as Hardware-Accelerated Matrix Operations** — ICDEW 2026(元判定: borderline)
  - 推奨理由: AMX/AVX512 を用いた分析クエリのリレーショナル演算子の行列演算化で、純粋なクエリ実行加速。TP・ストレージ・回復・メモリ階層への接点はなくスコープ外(idx 33/39 と同じ基準)。
  - id: doi:10.1109/ICDEW71238.2026.00006 | https://doi.org/10.1109/ICDEW71238.2026.00006
- [ ] **CAMEL Hash Table: Striking a Balance Between CPU and Memory Efficiency in Main-Memory Hash Join** — EDBT 2026(元判定: borderline)
  - 推奨理由: 主記憶ハッシュ結合用ハッシュテーブルは分析クエリ実行演算子のデータ構造で、純クエリ実行加速として drop した idx 33/37 と同種。idx 12 が keep なのは CXL/disaggregated memory キーワードに直結するためで、本件にはそのフックがなく(abstract 欠落で技術的接点も確認できない)、一貫性のため drop。
  - id: doi:10.48786/EDBT.2026.27 | https://doi.org/10.48786/edbt.2026.27

### ストレージインフラ
- [ ] **SACK: Shielding Dynamic Attribute-based Access Control in Persistent Key-Value Stores** — Proc. VLDB Endow. 2026(元判定: adjacent)
  - 推奨理由: 主眼は SGX による ABAC(アクセス制御)の高速化・鍵更新であり、KV separation や crash consistency は手段としての言及に留まる。TP/ストレージエンジン研究への材料は薄く、セキュリティ/インフラ寄りとしてスコープ外。
  - id: dblp:journals/pvldb/RenLL26 | https://www.vldb.org/pvldb/vol19/p1128-ren.pdf
- [ ] **Here, There and Everywhere: The Past, the Present and the Future of Local Storage in Cloud** — FAST 2026(元判定: adjacent)
  - 推奨理由: Alibaba Cloud のローカルストレージサービスの変遷を振り返るベンダー展望・経験論文で、クラウドインフラ/仮想化寄り。エンジン研究への材料は背景知識に留まる。LSM ストレージエンジンそのものの回顧である idx 35(keep)とは対象の違いで区別。
  - id: dblp:conf/fast/YangZZZZWSLLNZW26 | https://www.usenix.org/conference/fast26/presentation/yang
- [ ] **CLAPS: A Load-Aware Proxy Resource Pooling System for Reducing Resource Redundancy in Large-Scale Cloud Storage** — SIGMOD Companion 2026(元判定: borderline)
  - 推奨理由: クラウドストレージのプロキシ資源のプール化・弾力的割当・負荷分散といった資源効率のインフラ運用エンジニアリングで、TP/ストレージエンジン内部への接点が表面的。運用系・インフラ系の却下基準の系譜。
  - id: doi:10.1145/3788853.3803082 | https://doi.org/10.1145/3788853.3803082

### ベクトル検索/ANN
- [ ] **I/O Optimizations in Graph-Based Disk-Resident Approximate Nearest Neighbor Search: A Design Space Exploration** — Proc. VLDB Endow. 2026(元判定: adjacent)
  - 推奨理由: SSD 常駐グラフ ANN 索引の I/O 削減が主題で、第1回スイープで運用済みの「ベクトル検索(ANN)」却下基準に直接該当。ページレベル I/O モデルの示唆はあるが設計・評価とも ANN 特化で接点は表面的(idx 34 と同じ扱い)。
  - id: dblp:journals/pvldb/LiGYWW26 | https://www.vldb.org/pvldb/vol19/p1484-li.pdf
- [ ] **LEGEND: A Learned Explainable Graph-Enhanced Navigable Index for Hybrid Vector-Graph Search** — SIGMOD Companion 2026(元判定: borderline)
  - 推奨理由: abstract 未取得のためタイトル・原初メモで判断。hybrid vector-graph search 向け学習型索引はベクトル検索(ANN)の明確な却下基準に該当し(idx 1 と同じ扱い)、索引のキーワード一致は表面的。
  - id: doi:10.1145/3788853.3801586 | https://doi.org/10.1145/3788853.3801586

### 索引
- [ ] **Fast Landmark Reconfiguration for Highway Cover Indexes** — EDBT 2026(元判定: borderline)
  - 推奨理由: abstract 未取得のためタイトル・原初メモで判断。highway cover index の再構成はグラフ問合せアルゴリズムの話で、「索引」の語が一致するだけでストレージエンジンの索引構造・TP・回復・メモリ階層への接点が見当たらない(汎用貢献のあるグラフ系 idx 2/9 とは区別)。
  - id: doi:10.48786/EDBT.2026.18 | https://doi.org/10.48786/edbt.2026.18

## 整合性レビューが修正した判定ブレ

- idx 8 の keep 理由が「却下基準は LLM 向けであり推薦モデルは文言上該当しない」という文言依存で、推薦/ML 学習向けストレージを drop した idx 6・43 と矛盾していた。判断軸を「貢献が汎用エンジン技術か ML ワークロード特化か」に統一し、idx 8 は汎用 LSM compaction 内部技術の貢献を根拠に keep を維持(理由を書き換え)、idx 6(KV Cache 管理が中核)・idx 43(埋め込み学習専用最適化)は drop を維持。
- idx 38(Thunderbolt)を unsure から keep に変更。ブロックチェーン動機でも汎用 CC/consensus 貢献があれば keep とする運用が idx 13(TODS 投機コンセンサス)・idx 17(BFT 役割割当)で確立しており、38 の動的 concurrency controller・決定的順序付けは同種(むしろ deterministic database キーワードに近い)の貢献であるため同じ扱いに揃えた。
- idx 39(CAMEL Hash Table)を unsure から drop に変更。主記憶ハッシュ結合はクエリ実行演算子で、純クエリ実行加速として drop した idx 33・37 と同種。hash join でも idx 12 が keep なのは CXL/disaggregated memory キーワード直結のためで、39 にはそのフックがない(abstract 欠落だが、abstract 欠落の idx 34/40 も基準ベースで drop 済みであり unsure 温存の理由にならない)。クラスタも 索引 → クエリ実行/加速 に移動。
- idx 20(LightDSA)を unsure から drop に変更。HW アクセラレータの活用最適化で DB への接点が間接的(評価はマイクロベンチ+Redis)という構図は、決然と drop された idx 44(ASIC 圧縮アクセラレータ)と同型のため扱いを統一。両者を新設の HWアクセラレータ クラスタにまとめた。
- クラスタ名の統合: 「ベクトル検索/ANN」と「ベクトル検索(ANN)」→ ベクトル検索/ANN。「ストレージ階層/tiering」と「メモリ階層/tiering」→ ストレージ階層/tiering。「MVCC/多版ストレージ」と「HTAP」→ MVCC/HTAP。「ロック/CC」と「トランザクション/CC」→ トランザクション/CC。「ML4DB/LLM」を ML/LLM応用 に改名し、ML ワークロード特化で drop した idx 6(ストレージインフラから)・31(バッファ/キャッシュから)・43(SSD/IO経路から)を同クラスタに移動して却下カテゴリの見通しを良くした。
- 産業回顧・背景論文の扱いを点検: idx 35(Bigtable = スコープ中核の LSM エンジン自体の回顧)keep、idx 42(エンジン設計前提を与える HW トレンドの定量計測)keep、idx 29(クラウドローカルストレージのベンダーサービス回顧 = インフラ系)drop。対象の違いによる区別として一貫していると判断し、各理由に区別の根拠を明記した。
- グラフ応用論文の扱いを点検: 貢献が汎用のストレージ/索引/並行データ構造/トランザクション機構なら keep(idx 0, 2, 5, 9, 21)、グラフ問合せアルゴリズム限定なら drop(idx 40)、ML 学習特化なら drop(idx 43)で一貫しており変更なし。
- 評価ツール・シミュレータの扱いを点検: スコープキーワード(CXL/disaggregated、recovery、buffer management)に直結する研究評価基盤は keep(idx 23, 30, 36, 45)で一貫しており変更なし。
- 最終集計: keep 33 / drop 15 / unsure 0(unsure 3 件をすべて基準ベースで解消)。

