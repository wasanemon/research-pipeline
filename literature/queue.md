# Literature Queue

## 2026-07

<!-- weekly-sweep 2026-07-06: arXiv cs.DB/cs.DC/cs.OS last 10 days + DBLP monitored venues year:2026 -->

- [ ] **DiStash: A Disaggregated Multi-Stash Transactional Key-Value Store** — Yiming Gao et al., TPCTC (LNCS, Springer), 2025
  - id: doi:10.1007/978-3-032-18070-4_8  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1007/978-3-032-18070-4_8  | pdf: https://arxiv.org/pdf/2606.27979v1
  - relevance: core — disaggregated なトランザクショナルKVストア。DRAM/SSD/HDD/NVM 横断の stash 管理はメモリ階層×TPの中心課題

- [ ] **BtrLog: Low-Latency Logging for Cloud Database Systems** — Maximilian Kuschewski et al., arXiv, 2026
  - id: doi:10.14778/3828612.3828640  | added: 2026-07-06 | via: weekly-sweep
  - url: http://arxiv.org/abs/2606.27051v2  | pdf: https://arxiv.org/pdf/2606.27051v2
  - relevance: core — クラウドDB向け低遅延WAL。リモートストレージ上のロギングは WAL/durability の中心課題

- [ ] **FlintKV: A Fast Durable Storage Engine for Modern Databases** — Sergey Egorov et al., arXiv, 2026
  - id: arxiv:2607.02401  | added: 2026-07-06 | via: weekly-sweep
  - url: http://arxiv.org/abs/2607.02401v1  | pdf: https://arxiv.org/pdf/2607.02401v1
  - relevance: core — NVM前提の durable ストレージエンジン。トランザクション等のDB向けインタフェース保証を扱う

- [ ] **Breaking the Isolation-Freshness Trade-off: Joint Adaptive Storage Optimization for HTAP Systems** — Zhenghao Ding et al., Proc. VLDB Endow., 2026
  - id: dblp:journals/pvldb/DingZZSXLD26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.vldb.org/pvldb/vol19/p1142-ding.pdf  | pdf: none
  - relevance: core — HTAP の isolation-freshness トレードオフをストレージ最適化で扱う(HTAP/isolation)

- [ ] **How to Write to SSDs** — Bohyun Lee et al., Proc. VLDB Endow., 2026
  - id: dblp:journals/pvldb/LeeZL26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.vldb.org/pvldb/vol19/p1469-lee.pdf  | pdf: none
  - relevance: core — SSD 書き込みパスの検討。ストレージエンジンの I/O 階層設計に直結

- [ ] **ArceKV: Towards Workload-driven LSM-compactions for Key-Value Store Under Dynamic Workloads** — Junfeng Liu et al., Proc. VLDB Endow., 2026
  - id: dblp:journals/pvldb/LiuXL26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.vldb.org/pvldb/vol19/p958-liu.pdf  | pdf: none
  - relevance: core — 動的ワークロード下の LSM コンパクション方針(LSM-tree)

- [ ] **Terark-DS: A High-Performance and Storage-Efficient Key-Value Separation Storage Engine on Disaggregated Storage** — Jianshun Zhang et al., Proc. VLDB Endow., 2026
  - id: dblp:journals/pvldb/ZhangDWOWWCFF26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.vldb.org/pvldb/vol19/p822-zhang.pdf  | pdf: none
  - relevance: core — disaggregated ストレージ上の KV 分離ストレージエンジン

- [ ] **SIDLE: Tree-structure Aware Indexes for CXL-based Heterogeneous Memory** — Haoru Zhao et al., Proc. VLDB Endow., 2026
  - id: dblp:journals/pvldb/ZhaoDWC26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.vldb.org/pvldb/vol19/p1499-zhao.pdf  | pdf: none
  - relevance: core — CXL ヘテロメモリ向け木構造インデックス(disaggregated memory/CXL)

- [ ] **Pisco: An Isolation Bug Case Reduction and Deduplication Framework** — Siyang Weng et al., Proc. VLDB Endow., 2026
  - id: dblp:journals/pvldb/WengYHZPYZCHP26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.vldb.org/pvldb/vol19/p1413-weng.pdf  | pdf: none
  - relevance: core — トランザクション分離バグのケース縮約・重複排除。isolation テスティングは serializability 研究に直結

- [ ] **AQD: Online Adaptive Query Dispatcher for HTAP Databases** — Yang Wu et al., Proc. VLDB Endow., 2026
  - id: dblp:journals/pvldb/WuLZWYZXZ26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.vldb.org/pvldb/vol19/p1586-wu.pdf  | pdf: none
  - relevance: core — HTAP DB 向け適応的クエリディスパッチ(HTAP)

- [ ] **Aurora PostgreSQL Limitless Database: Building a Highly Scalable OLTP Database** — Dmitry Arkhangelskiy et al., SIGMOD Companion, 2026
  - id: doi:10.1145/3788853.3803089  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3788853.3803089  | pdf: none
  - relevance: core — Aurora PostgreSQL Limitless: スケーラブル分散 OLTP の産業論文

- [ ] **CloudJump III: Optimizing Cloud Databases for Tiered Storage** — Zongzhi Chen et al., SIGMOD Companion, 2026
  - id: doi:10.1145/3788853.3803084  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3788853.3803084  | pdf: none
  - relevance: core — クラウド DB の階層ストレージ最適化(メモリ/ディスク階層)

- [ ] **Scalable Leader Leases For Multi Consensus Groups in CockroachDB** — Ibrahim Kettaneh et al., SIGMOD Companion, 2026
  - id: doi:10.1145/3788853.3803081  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3788853.3803081  | pdf: none
  - relevance: core — CockroachDB のマルチ合意グループ向けリーダーリース(分散トランザクション/レプリケーション)

- [ ] **Scalable and Resilient Storage Tier for Azure SQL Hyperscale** — Alejandro Hernandez Saenz et al., SIGMOD Companion, 2026
  - id: doi:10.1145/3788853.3803083  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3788853.3803083  | pdf: none
  - relevance: core — Azure SQL Hyperscale のストレージ層(ストレージ/回復性、産業論文)

- [ ] **RIOT: Replicated Independently-Ordered Transactions** — Jim Webber et al., SIGMOD Companion, 2026
  - id: doi:10.1145/3788853.3803094  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3788853.3803094  | pdf: none
  - relevance: core — RIOT: レプリケートされた独立順序トランザクション(タイトルから CC/レプリケーション新方式)

- [ ] **LakeMem: An Elastic Disaggregated-Memory Caching Layer for Analytical Processing Systems** — Xinyi Yu et al., SIGMOD Companion, 2026
  - id: doi:10.1145/3788853.3803100  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3788853.3803100  | pdf: none
  - relevance: core — 分析処理向け disaggregated メモリ・キャッシュ層(disaggregated memory)

- [ ] **Hot-Page-Aware Checkpointing for Flash SSDs** — Geunhyun Park et al., ICDEW, 2026
  - id: doi:10.1109/ICDEW71238.2026.00007  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1109/ICDEW71238.2026.00007  | pdf: none
  - relevance: core — フラッシュ SSD 向けホットページ対応チェックポインティング(checkpoint)

- [ ] **TiRex: An HTAIP Framework Beyond HTAP for Unified Transactional, Analytical, and AI Workloads** — Jane Yu et al., ICDEW, 2026
  - id: doi:10.1109/ICDEW71238.2026.00021  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1109/ICDEW71238.2026.00021  | pdf: none
  - relevance: core — HTAP を超える統合(HTAIP)を掲げるフレームワーク(HTAP)

- [ ] **Evaluating Learned Indexes in LSM-tree Systems: Benchmarks, Insights and Design Choices** — Junfeng Liu et al., EDBT, 2026
  - id: doi:10.48786/EDBT.2026.16  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.48786/edbt.2026.16  | pdf: none
  - relevance: core — LSM-tree システムにおける learned index の評価(LSM×索引)

- [ ] **Disaggregated Data System Architecture - State-of-the-Art and Open Challenges** — Alexander Krause et al., EDBT, 2026
  - id: doi:10.48786/EDBT.2026.77  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.48786/edbt.2026.77  | pdf: none
  - relevance: core — disaggregated データシステムのサーベイ/課題整理(文献フェーズに有用)

- [ ] **Exploring Dynamic Memory Allocation of CXL Memory Pools in Enterprise In-Memory Database Management Systems** — Donghun Lee et al., EDBT, 2026
  - id: doi:10.48786/EDBT.2026.58  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.48786/edbt.2026.58  | pdf: none
  - relevance: core — エンタープライズ in-memory DBMS での CXL メモリプール動的割当(CXL/disaggregated)

- [ ] **AdCache: Adaptive Cache Management with Admission Control for LSM-tree Key-Value Stores** — Jiarui Ye et al., EDBT, 2026
  - id: doi:10.48786/EDBT.2026.12  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.48786/edbt.2026.12  | pdf: none
  - relevance: core — LSM KV ストア向け適応キャッシュ管理(LSM×バッファ管理)

- [ ] **A Multi-tenant Relational OLTP Database at Salesforce** — Vaibhav Arora et al., CIDR, 2026
  - id: dblp:conf/cidr/AroraCCFHMMW26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://vldb.org/cidrdb/2026/a-multi-tenant-relational-oltp-database-at-salesforce.html  | pdf: none
  - relevance: core — Salesforce のマルチテナント OLTP(産業論文)

- [ ] **Flexible I/O for Database Management Systems with xNVMe** — Emil Houlborg et al., CIDR, 2026
  - id: dblp:conf/cidr/HoulborgTLWR00T26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://vldb.org/cidrdb/2026/flexible-io-for-database-management-systems-with-xnvme.html  | pdf: none
  - relevance: core — xNVMe による DBMS の柔軟な I/O パス(ストレージ I/O)

- [ ] **Rosé: Flexible Replication With Strong Semantics For Partitioned Databases** — Ioannis Zarkadas et al., CIDR, 2026
  - id: dblp:conf/cidr/ZarkadasKGYBCE26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://vldb.org/cidrdb/2026/rose-flexible-replication-with-strong-semantics-for-partitioned-databases.html  | pdf: none
  - relevance: core — パーティション DB 向けの強いセマンティクスのレプリケーション

- [ ] **Update NDP: On Offloading Modifications to Smart Storage with Transactional Guarantees in Near-Data Processing DBMS** — Arthur Bernhardt et al., ACM Trans. Database Syst., 2026
  - id: doi:10.1145/3774753  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3774753  | pdf: none
  - relevance: core — near-data processing DBMS でトランザクション保証付き更新オフロード(NDP×TP)

- [ ] **An Evaluation of B-tree Compression Techniques** — Sikang Sun et al., VLDB J., 2026
  - id: doi:10.1007/S00778-025-00950-8  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1007/s00778-025-00950-8  | pdf: none
  - relevance: core — B-tree 圧縮技術の評価(ストレージエンジン/索引の実証研究)

- [ ] **FUR: Fast and Unlimited Reads on Persistent Memory Transactions** — João Barreto et al., EuroSys, 2026
  - id: doi:10.1145/3767295.3769343  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3767295.3769343  | pdf: none
  - relevance: core — 永続メモリ・トランザクションの高速読み出し(PM×CC)

- [ ] **Scalable RDMA-accelerated Distributed Locks with Shared Stream Abstraction** — Miao Cai et al., EuroSys, 2026
  - id: doi:10.1145/3767295.3803598  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3767295.3803598  | pdf: none
  - relevance: core — RDMA 加速の分散ロック(ロック/分散 CC)

- [ ] **A Logically Disaggregated Cache for Replicated Storage Systems** — Kiran Hombal et al., EuroSys, 2026
  - id: doi:10.1145/3767295.3803608  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3767295.3803608  | pdf: none
  - relevance: core — レプリケートされたストレージ向け論理 disaggregated キャッシュ

- [ ] **Accelerating Transactional Execution via Processing-In-Memory** — André Lopes et al., EuroSys, 2026
  - id: doi:10.1145/3767295.3803621  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3767295.3803621  | pdf: none
  - relevance: core — processing-in-memory によるトランザクション実行の加速(PIM×TP)

- [ ] **Discard-Based Garbage Collection for Distributed Log-Structured Storage Systems in ByteDance** — Runhua Bian et al., FAST, 2026
  - id: dblp:conf/fast/BianZLZZGGGLZZC26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.usenix.org/conference/fast26/presentation/bian  | pdf: none
  - relevance: core — 分散ログ構造化ストレージの GC(ByteDance 産業論文、log-structured)

- [ ] **Holistic and Automated Task Scheduling for Distributed LSM-tree-based Storage** — Yuanming Ren et al., FAST, 2026
  - id: dblp:conf/fast/RenS00L26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.usenix.org/conference/fast26/presentation/ren  | pdf: none
  - relevance: core — 分散 LSM ストレージのタスクスケジューリング(LSM-tree)

- [ ] **DMTree: Towards Efficient Tree Indexing on Disaggregated Memory via Compute-side Collaborative Design** — Guoli Wei et al., FAST, 2026
  - id: dblp:conf/fast/Wei0SLY0C26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.usenix.org/conference/fast26/presentation/wei  | pdf: none
  - relevance: core — disaggregated メモリ上の木インデックス(disaggregated memory×索引)

- [ ] **Rearchitecting Buffered I/O in the Era of High-Bandwidth SSDs** — Yekang Zhan et al., FAST, 2026
  - id: dblp:conf/fast/ZhanWPHW000026  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.usenix.org/conference/fast26/presentation/zhan  | pdf: none
  - relevance: core — 高帯域 SSD 時代の buffered I/O 再設計(バッファ管理×I/O 階層)

- [ ] **"Range as a Key" is the Key! Fast and Compact Cloud Block Store Index with RASK** — Haoru Zhao et al., FAST, 2026
  - id: dblp:conf/fast/Zhao0XW026  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.usenix.org/conference/fast26/presentation/zhao  | pdf: none
  - relevance: core — クラウドブロックストア向け高速コンパクト索引 RASK(索引×ストレージ)

- [ ] **TVA: A Version-aware Temporal Graph Storage System for Real-time Analytics** — Wenhao Li et al., arXiv, 2026
  - id: arxiv:2607.00406  | added: 2026-07-06 | via: weekly-sweep
  - url: http://arxiv.org/abs/2607.00406v1  | pdf: https://arxiv.org/pdf/2607.00406v1
  - relevance: adjacent — バージョン対応の時系列グラフ・ストレージシステム(ストレージエンジン設計だが対象はグラフ分析)

- [ ] **I/O Optimizations in Graph-Based Disk-Resident Approximate Nearest Neighbor Search: A Design Space Exploration** — Liang Li et al., Proc. VLDB Endow., 2026
  - id: dblp:journals/pvldb/LiGYWW26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.vldb.org/pvldb/vol19/p1484-li.pdf  | pdf: none
  - relevance: adjacent — ディスク常駐 ANN 索引の I/O 設計空間(索引×ディスク階層だが対象はベクトル検索)

- [ ] **Efficient Temporal Subgraph Management: A New Interval Index** — Dian Ouyang et al., Proc. VLDB Endow., 2026
  - id: dblp:journals/pvldb/OuyangWWZLL26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.vldb.org/pvldb/vol19/p1170-wen.pdf  | pdf: none
  - relevance: adjacent — 時間的部分グラフ向け区間インデックス(索引だが対象はグラフ)

- [ ] **SACK: Shielding Dynamic Attribute-based Access Control in Persistent Key-Value Stores** — Yanjing Ren et al., Proc. VLDB Endow., 2026
  - id: dblp:journals/pvldb/RenLL26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.vldb.org/pvldb/vol19/p1128-ren.pdf  | pdf: none
  - relevance: adjacent — 永続 KV ストアでの動的アクセス制御(ストレージエンジン×セキュリティ)

- [ ] **LiBox: A Learned Index as an Array to Minimize Last-Mile Search** — Jian Zhou et al., Proc. VLDB Endow., 2026
  - id: dblp:journals/pvldb/ZhouWZZJ26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.vldb.org/pvldb/vol19/p836-jiang.pdf  | pdf: none
  - relevance: adjacent — learned index のラストマイル探索最小化(索引)

- [ ] **ByteGraph-Dione: An Adaptive Dual-Format Graph Engine with Hotspot Awareness and Transaction Efficiency for Production-Scale Workloads** — Chao Chen et al., SIGMOD Companion, 2026
  - id: doi:10.1145/3788853.3803073  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3788853.3803073  | pdf: none
  - relevance: adjacent — 本番規模グラフエンジン。トランザクション効率を扱う

- [ ] **TokaDB: A Unified Storage Engine for Training-Serving Data Management in Large Recommendation Models** — Peng Fang et al., SIGMOD Companion, 2026
  - id: doi:10.1145/3788853.3803078  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3788853.3803078  | pdf: none
  - relevance: adjacent — 推薦モデル学習/サービング向け統合ストレージエンジン(応用はML系)

- [ ] **TDSQL-Boundless: A Distributed Database System for Large-scale Heterogeneous Multi-Table Workloads** — Yuxing Chen et al., SIGMOD Companion, 2026
  - id: doi:10.1145/3788853.3803090  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3788853.3803090  | pdf: none
  - relevance: adjacent — TDSQL-Boundless: 大規模ヘテロワークロード向け分散 DB(産業論文)

- [ ] **RecDB: An LSM-Tree based Storage System for Training Large Recommendation Model in Low-Resource Scenarios** — Ming Gao et al., EDBT, 2026
  - id: doi:10.48786/EDBT.2026.37  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.48786/edbt.2026.37  | pdf: none
  - relevance: adjacent — LSM ベースの学習用ストレージシステム(LSM エンジン、応用は推薦)

- [ ] **DCSR: A Fast Data Structure with Leaf-Oriented Locks for Streaming Graph Processing** — Yue Shen et al., EDBT, 2026
  - id: doi:10.48786/EDBT.2026.29  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.48786/edbt.2026.29  | pdf: none
  - relevance: adjacent — リーフ単位ロックの並行データ構造(並行性、対象はストリーミンググラフ)

- [ ] **Declarative Memory Services** — Jerónimo Castrillón et al., CIDR, 2026
  - id: dblp:conf/cidr/CastrillonGHKSS26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://vldb.org/cidrdb/2026/declarative-memory-services.html  | pdf: none
  - relevance: adjacent — 宣言的メモリサービス(メモリ階層のビジョン)

- [ ] **Raster is Faster: Rethinking Ray Tracing in Database Indexing** — Harish Doraiswamy et al., CIDR, 2026
  - id: dblp:conf/cidr/DoraiswamyH26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://vldb.org/cidrdb/2026/raster-is-faster-rethinking-ray-tracing-in-database-indexing.html  | pdf: none
  - relevance: adjacent — レイトレーシング HW を DB 索引に使う再考(HW×索引)

- [ ] **Hash Joins Meet CXL: A Fresh Look** — Wentao Huang et al., CIDR, 2026
  - id: dblp:conf/cidr/HuangLT26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://vldb.org/cidrdb/2026/hash-joins-meet-cxl-a-fresh-look.html  | pdf: none
  - relevance: adjacent — CXL 上のハッシュ結合の再検討(CXL×クエリ実行)

- [ ] **Proof-of-Execution: Low-Latency Consensus via Speculative Execution** — Jelle Hellings et al., ACM Trans. Database Syst., 2026
  - id: doi:10.1145/3774322  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3774322  | pdf: none
  - relevance: adjacent — 投機実行による低遅延コンセンサス(一般のコンセンサス技術)

- [ ] **Mitigating False Positives in Filters: To Adapt or to Cache?** — Tianchi Mo et al., ACM Trans. Database Syst., 2026
  - id: doi:10.1145/3786324  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3786324  | pdf: none
  - relevance: adjacent — フィルタ(Bloom 等)の偽陽性対策: 適応 vs キャッシュ(ストレージエンジン部品)

- [ ] **Scalable lighting-fast temporal indexing** — Panagiotis Simatis et al., VLDB J., 2026
  - id: doi:10.1007/S00778-026-00968-6  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1007/s00778-026-00968-6  | pdf: none
  - relevance: adjacent — スケーラブルな時間インデックス(索引)

- [ ] **PaCaR: Improved Buffered I/O Locality on NUMA Systems with Page Cache Replication** — Jérôme Coquisart et al., EuroSys, 2026
  - id: doi:10.1145/3767295.3769359  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3767295.3769359  | pdf: none
  - relevance: adjacent — NUMA でのページキャッシュ複製(OS レイヤのバッファ管理)

- [ ] **OptiLog: Assigning Roles in Byzantine Consensus** — Hanish Gogada et al., EuroSys, 2026
  - id: doi:10.1145/3767295.3769342  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3767295.3769342  | pdf: none
  - relevance: adjacent — BFT コンセンサスの役割割当(一般のコンセンサス技術)

- [ ] **Avicenna: Masking Slowdowns in Replicated State Machines with Counterfactual Evaluation** — Christopher Hodsdon et al., EuroSys, 2026
  - id: doi:10.1145/3767295.3803615  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3767295.3803615  | pdf: none
  - relevance: adjacent — 複製状態機械の遅延マスキング(レプリケーション)

- [ ] **TierScape: Harnessing Multiple Compressed Tiers to Tame Server Memory TCO** — Sandeep Kumar et al., EuroSys, 2026
  - id: doi:10.1145/3767295.3769321  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3767295.3769321  | pdf: none
  - relevance: adjacent — 圧縮メモリ多層化によるメモリ階層管理(tiering)

- [ ] **LightDSA: Enabling Efficient DSA Through Hardware-Aware Transparent Optimization** — Yuansen Wang et al., EuroSys, 2026
  - id: doi:10.1145/3767295.3769356  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3767295.3769356  | pdf: none
  - relevance: adjacent — Intel DSA オフロードの透過的最適化(データ移動 HW、エンジンで利用され得る)

- [ ] **FicusDB: Scalable Multi-Versioned Authenticated Archival Storage** — Hongbo Zhang et al., EuroSys, 2026
  - id: doi:10.1145/3767295.3803601  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3767295.3803601  | pdf: none
  - relevance: adjacent — 多バージョンの authenticated アーカイブストレージ(バージョニング×ストレージ)

- [ ] **ScaleSwap: A Scalable OS Swap System for All-Flash Swap Arrays** — Taehwan Ahn et al., FAST, 2026
  - id: dblp:conf/fast/AhnY0S26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.usenix.org/conference/fast26/presentation/ahn  | pdf: none
  - relevance: adjacent — 全フラッシュ swap の OS スワップ機構(larger-than-memory の OS 側)

- [ ] **Xerxes: Extensive Exploration of Scalable Hardware Systems with CXL-Based Simulation Framework** — Yuda An et al., FAST, 2026
  - id: dblp:conf/fast/AnY00ZZ000L026  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.usenix.org/conference/fast26/presentation/an  | pdf: none
  - relevance: adjacent — CXL ベースのシミュレーション基盤(CXL 研究のツール)

- [ ] **UnICom: A Universally High-Performant I/O Completion Mechanism for Modern Computer Systems** — Riwei Pan et al., FAST, 2026
  - id: dblp:conf/fast/Pan0NLGKX26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.usenix.org/conference/fast26/presentation/pan  | pdf: none
  - relevance: adjacent — 汎用 I/O completion 機構(DB の I/O スタックに関係)

- [ ] **Lockify: Understanding Linux Distributed Lock Management Overheads in Shared Storage** — Taeyoung Park et al., FAST, 2026
  - id: dblp:conf/fast/ParkJHNH26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.usenix.org/conference/fast26/presentation/park  | pdf: none
  - relevance: adjacent — 共有ストレージでの分散ロック管理(DLM)のオーバーヘッド分析(ロック)

- [ ] **DPAS: A Prompt, Accurate and Safe I/O Completion Method for SSDs** — Dongjoo Seo et al., FAST, 2026
  - id: dblp:conf/fast/SeoJYCJLD26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.usenix.org/conference/fast26/presentation/seo  | pdf: none
  - relevance: adjacent — SSD の I/O completion 手法(I/O パス)

- [ ] **Characterizing and Emulating FDP SSDs with WARP** — Inho Song et al., FAST, 2026
  - id: dblp:conf/fast/SongQ0BNL26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.usenix.org/conference/fast26/presentation/song  | pdf: none
  - relevance: adjacent — FDP SSD の特性評価とエミュレーション(データ配置はLSM/WAL 研究に有用)

- [ ] **Getting the MOST out of your Storage Hierarchy with Mirror-Optimized Storage Tiering** — Kaiwei Tu et al., FAST, 2026
  - id: dblp:conf/fast/TuWAA26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.usenix.org/conference/fast26/presentation/tu  | pdf: none
  - relevance: adjacent — ミラー最適化ストレージ階層化(tiering、メモリ/ディスク階層)

- [ ] **Here, There and Everywhere: The Past, the Present and the Future of Local Storage in Cloud** — Leping Yang et al., FAST, 2026
  - id: dblp:conf/fast/YangZZZZWSLLNZW26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.usenix.org/conference/fast26/presentation/yang  | pdf: none
  - relevance: adjacent — クラウドのローカルストレージの過去・現在・未来(展望、階層設計の背景)

- [ ] **Cylon: Fast and Accurate Full-System Emulation of CXL-SSDs** — Dongha Yoon et al., FAST, 2026
  - id: dblp:conf/fast/YoonILINL26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.usenix.org/conference/fast26/presentation/yoon  | pdf: none
  - relevance: adjacent — CXL-SSD のフルシステムエミュレーション(CXL 研究のツール)

- [ ] **When Classic Cache Policies Fail: Learning-Augmented Replacement for Semantic Retrieval Buffers** — Yushi Sun et al., arXiv, 2026
  - id: arxiv:2607.00394  | added: 2026-07-06 | via: weekly-sweep
  - url: http://arxiv.org/abs/2607.00394v1  | pdf: https://arxiv.org/pdf/2607.00394v1
  - relevance: borderline — キャッシュ置換ポリシー(学習拡張)。アルゴリズムはバッファ管理だが対象はLLMエージェントの意味的バッファ

- [ ] **CLAPS: A Load-Aware Proxy Resource Pooling System for Reducing Resource Redundancy in Large-Scale Cloud Storage** — Xiuqi Huang et al., SIGMOD Companion, 2026
  - id: doi:10.1145/3788853.3803082  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3788853.3803082  | pdf: none
  - relevance: borderline — 大規模クラウドストレージのプロキシ資源プール(インフラ寄り)

- [ ] **CoddSpeed: Hardware Accelerated Query Processing in Microsoft Fabric** — Matteo Interlandi et al., SIGMOD Companion, 2026
  - id: doi:10.1145/3788853.3803077  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3788853.3803077  | pdf: none
  - relevance: borderline — ハードウェア加速クエリ処理(クエリ実行系。TP/ストレージの中心ではない)

- [ ] **LEGEND: A Learned Explainable Graph-Enhanced Navigable Index for Hybrid Vector-Graph Search** — Joydeep Chandra et al., SIGMOD Companion, 2026
  - id: doi:10.1145/3788853.3801586  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3788853.3801586  | pdf: none
  - relevance: borderline — ベクトル-グラフ混合の学習型索引(索引だがベクトル検索寄り)

- [ ] **Twenty Years of Bigtable** — Fabio Baltieri et al., SIGMOD Companion, 2026
  - id: doi:10.1145/3788853.3803095  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3788853.3803095  | pdf: none
  - relevance: borderline — Bigtable 20年の産業回顧(ストレージシステム史。分量・形式は要確認)

- [ ] **ResBench: A Comprehensive Framework for Evaluating Database Resilience** — Puyun Hu et al., SIGMOD Companion, 2026
  - id: doi:10.1145/3788853.3801615  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3788853.3801615  | pdf: none
  - relevance: borderline — DB レジリエンス評価フレームワーク(recovery 関連の評価系)

- [ ] **Rethinking Relational Operators as Hardware-Accelerated Matrix Operations** — Jannis Karampetsos et al., ICDEW, 2026
  - id: doi:10.1109/ICDEW71238.2026.00006  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1109/ICDEW71238.2026.00006  | pdf: none
  - relevance: borderline — リレーショナル演算子の行列演算化(ハードウェア加速クエリ処理)

- [ ] **Thunderbolt: Concurrent Smart Contract Execution with Non-blocking Reconfiguration for Sharded DAGs** — Junchao Chen et al., EDBT, 2026
  - id: doi:10.48786/EDBT.2026.07  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.48786/edbt.2026.07  | pdf: none
  - relevance: borderline — ブロックチェーン文脈だがスマートコントラクトの並行実行+非停止再構成という CC 技術

- [ ] **CAMEL Hash Table: Striking a Balance Between CPU and Memory Efficiency in Main-Memory Hash Join** — Sudip Chatterjee et al., EDBT, 2026
  - id: doi:10.48786/EDBT.2026.27  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.48786/edbt.2026.27  | pdf: none
  - relevance: borderline — 主記憶ハッシュ結合の CPU/メモリ効率(クエリ実行系データ構造)

- [ ] **Fast Landmark Reconfiguration for Highway Cover Indexes** — David Coudert et al., EDBT, 2026
  - id: doi:10.48786/EDBT.2026.18  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.48786/edbt.2026.18  | pdf: none
  - relevance: borderline — 最短路系インデックスの再構成(索引だがグラフ問合せ)

- [ ] **Query Performance Explanation through Large Language Model for HTAP Systems** — Haibo Xiu et al., EDBT, 2026
  - id: doi:10.48786/EDBT.2026.09  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.48786/edbt.2026.09  | pdf: none
  - relevance: borderline — HTAP キーワードには合致するが LLM による性能説明が主題

- [ ] **Cloudspecs: Cloud Hardware Evolution Through the Looking Glass** — Till Steinert et al., CIDR, 2026
  - id: dblp:conf/cidr/SteinertKL26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://vldb.org/cidrdb/2026/cloudspecs-cloud-hardware-evolution-through-the-looking-glass.html  | pdf: none
  - relevance: borderline — クラウドハードウェア進化の観測(エンジン設計の背景情報)

- [ ] **Efficient graph embedding at scale: optimizing CPU-GPU-SSD integration** — Zhonggen Li et al., VLDB J., 2026
  - id: doi:10.1007/S00778-026-00974-8  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1007/s00778-026-00974-8  | pdf: none
  - relevance: borderline — CPU-GPU-SSD 統合の最適化(メモリ/ディスク階層だが対象はグラフ埋め込み)

- [ ] **ASIC-based Compression Accelerators for Storage Systems: Design, Placement, and Profiling Insights** — Tao Lu et al., EuroSys, 2026
  - id: doi:10.1145/3767295.3769384  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3767295.3769384  | pdf: none
  - relevance: borderline — ストレージ向け ASIC 圧縮アクセラレータ(HW 寄り)

- [ ] **2DIO: Configurable and Cache-Accurate Trace Generation for Storage Benchmarking** — Yirong Wang et al., EuroSys, 2026
  - id: doi:10.1145/3767295.3769391  | added: 2026-07-06 | via: weekly-sweep
  - url: https://doi.org/10.1145/3767295.3769391  | pdf: none
  - relevance: borderline — ストレージベンチマーク用トレース生成(評価ツール)

- [ ] **Unleashing Zoned UFS: Cross-Layer Optimizations for Next-Generation Mobile Storage** — Jungae Kim et al., FAST, 2026
  - id: dblp:conf/fast/KimKCPKKOLAJVK26  | added: 2026-07-06 | via: weekly-sweep
  - url: https://www.usenix.org/conference/fast26/presentation/kim-jungae  | pdf: none
  - relevance: borderline — Zoned UFS のクロスレイヤ最適化(zoned storage は LSM 研究と関係するがモバイル向け)
