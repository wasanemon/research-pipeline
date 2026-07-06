---
title: "Declarative Memory Services"
authors: [Jeronimo Castrillon, Jana Giceva, Yu Hua, Kimberly Keeton, Akhil Shekar, Kevin Skadron, Tianzheng Wang, Huanchen Zhang]
venue: "CIDR 2026 (16th Annual Conference on Innovative Data Systems Research, CIDR '26)"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/cidr/CastrillonGHKSS26"}
urls: {paper: "https://vldb.org/cidrdb/2026/declarative-memory-services.html", pdf: "literature/pdfs/2026-cidr-castrillon-declarative-memory.pdf", code: ""}
status: read
read_date: 2026-07-06
tags: [vision-paper, declarative-programming, memory-services, cxl, pim, near-memory-processing, disaggregated-memory, tiered-memory, buffer-management, rdma, dataflow, programming-model]
---

## TL;DR
ビジョン論文(実装・定量評価なし)。HBM や PIM 等の新メモリデバイスと CXL 等の
インターコネクトにより、メモリは「単一ノード DRAM」の伝統的仮定(揮発・byte-addressable・
ノード内コヒーレント)から乖離し、圧縮・暗号化・複製・計算内蔵など多様な特性を持つように
なった。しかし現行のプログラミングモデルは load/store・RDMA read/write 等の低レベル命令的
抽象しか与えず、開発者はデバイスごとに手作りの実装(disaggregated B+-tree 等)を強いられ、
移植性・保守性・適応性を欠く。著者らは Declarative Memory Services (DMS) を提唱:
開発者はメモリ領域やデータフロータスクに「望む特性」(coherent, cacheable, latency SLO 等)を
宣言するだけにし、抽象化層 / メモリサービス層(ランタイム)/ 較正層の3層構成で、
特性→デバイスへの写像をランタイムが行う。3つのケーススタディで動機付けし、
6つの研究課題を提示する。

## Problem & motivation
- [paper] 数十年間「メモリ」は単一ノード DRAM の特性と同義だった: 揮発、byte-addressable、
  ストレージより桁違いに速い、コヒーレンスはノードレベルのみ。この従来型メモリは
  高速アロケータ・cache-conscious アルゴリズム・numactl / madvise 等の確立された
  部品で扱えた (§1, p.1)。
- [paper] しかしメモリデバイスの発展はプログラミングモデルの発展を追い越した。CXL では
  多様な特性のメモリデバイスが、厳密な階層を形成せずに disaggregated システム内に共存
  できる。メモリは揮発にも永続にもなり、計算要素を内蔵しうるし、byte-addressable な
  アクセスが常に最も効率的とは限らず、コヒーレンス保証は「一部の(全部ではない!)」
  メモリ領域についてプロセッサ間に拡張される (§1, p.1)。
- [paper] これらの先進特性は、アドレス空間・ポインタの有効性・データ配置・コヒーレンス・
  更新セマンティクス・障害処理に関する長年の仮定を壊す。例: メモリ階層内での計算は
  CPU キャッシュとコヒーレントに保たれなければ stale データ上で計算してしまう (§1, p.1)。
- [paper] 結果として DBMS 開発者は、各デバイス固有の特性を活かすためにデータ配置・移動、
  コヒーレンス、同期、障害処理に関する広大な設計空間を自力で航行することになり、
  プログラミング効率の低下・保守/移植コストの増大・適応性の欠如を招く。例: ある世代の
  メモリハードウェア向けに構築・チューニングした index は新世代で性能が出ないことがある
  (§1, p.1)。
- [paper] 既存プログラミングモデルは load/store・atomic 命令(やその上の latch)といった
  低レベルで命令的(imperative)な抽象を強い、開発者が「how」(実装詳細)を手書きコードで
  指定しなければならない。本論文の主張は、将来のメモリ技術のプログラミングモデルは
  宣言的(declarative)であるべき、というもの (§1, p.1)。
- [paper] プログラマビリティの課題: 新メモリ技術の多くは von Neumann アーキテクチャから
  逸脱する。RDMA write には順序保証が無いため同期用途には実用的でない(ref [74])。
  CXL ベースの解はこの制限を克服できるが、partial fault(リンク障害時にポインタと
  その先のオブジェクトの整合性はどうなるか)等の新しい故障モードを持ち込む。初期の
  プロトタイプは hand-crafted な最適化で実現可能性を示したが、一般化には自動化・
  コンパイラ支援・適切な抽象・堅牢なランタイムが要る (§2 "A Programmability Challenge",
  p.3)。
- [paper] 貢献は4つ: (1) 破壊的メモリ技術の俯瞰、(2) 将来のメモリ向けプログラミング
  モデルは宣言的であるべきという主張、(3) DMS ビジョンの提案と実用的ユースケースによる
  可能性の提示、(4) 完全実現に向けた課題と研究アジェンダの提示 (p.2)。

## System model & assumptions
- [paper] 想定するメモリ地形は Table 1 の特性分類で表される: Performance
  (例: latency < 20µs, bandwidth > 2GB/s)、Volatility(不揮発/揮発)、Active/Passive
  (PIM か通常 DRAM か)、Location(local / NUMA / remote (CXL or RDMA))、Granularity
  (byte-addressable / page ベースとページサイズ)、Coherency(coherent / not / partially)、
  Security(暗号化の有無)、Compression(圧縮の種類)、Ordering(strong/weak メモリモデル、
  明示 fence、causal consistency)、Fault Semantic(atomicity, exactly once)、Fault Model
  (transient, partial fault)(Table 1, p.2)。
- [paper] Passive memory: 通常の DDR DRAM は load/store・atomics・SIMD の同期命令で
  プログラムされ、I/OAT で非同期メモリ操作も可能。だが現代マシンでは NUMA 効果に加え、
  CPU キャッシュのブラックボックス性や chiplet 効果が絡み、扱いが難しくなっている。
  例: DDIO は PCIe デバイスからのデータを CPU キャッシュラインの一部に直接配送するため、
  ソフトウェアは eviction 前の適時にデータを消費しないと利得が出ない。キャッシュ分割は
  ベンダ固有 intrinsic や OS 改造頼み (§2, p.2)。
- [paper] Computational memory: PNM(DRAM チップ外・モジュール近傍にロジック)と
  PIM(DRAM ダイ内。bank レベル、あるいは subarray 統合でアナログ/デジタルロジック)の
  2 系統。ReRAM / PCM は超並列アナログ内積などの追加プリミティブを提供。PNM は DRAM
  内部帯域(all-bank 並列性)を活かせず、PIM は特殊で高価・低容量になりがちで、メモリ
  インターフェースへの並行アクセス競合も増やしうる。両者とも CPU キャッシュとの
  コヒーレンスが課題で、PIM オフロードのためにまずキャッシュから明示 flush が要るなら
  データ移動がむしろ増えることもある (§2, p.2)。
- [paper] Tiered memory: メモリコスト高騰を背景に、hyperscaler は cold ページを
  圧縮メモリ・SSD・NVM・CXL 接続メモリ等の低速・安価な層へ、性能劣化目標の範囲内で
  移す構成を急速に導入している (§2, p.2)。
- [paper] Resource disaggregation: InfiniBand の RDMA は Ethernet 比で超低レイテンシ。
  CXL は PCIe 上のプロトコルで DRAM を CPU から完全に切り離すことを約束し、ホスト
  CPU と周辺デバイス間の低レイテンシでコヒーレントな通信を可能にする。異種メモリの
  完全 disaggregated プールや、メモリコントローラ内の知能へのロジックオフロードも
  可能になる。3D NAND + NVMe の進歩により、flash を裏に持つ byte-addressable な
  CXL メモリ拡張カードも登場している (§2, p.2)。
- [inference] 本論文は特定のワークロード・整合性レベル・故障モデルを仮定する
  「システム」ではなく、上記の多様なデバイス地形そのものが前提条件。暗黙の仮定は
  (i) アプリの要求が Table 1 程度の語彙で宣言可能であること、(ii) ランタイムが
  デバイス能力を較正・追跡できること、(iii) 宣言→実装の写像コストが手書き最適化との
  差を許容範囲に収められること、の3点に見える(いずれも §5 の課題として部分的に
  著者ら自身が認めている)。

## Approach
本体は3つのケーススタディ(§3)によるボトムアップの動機付けと、3層アーキテクチャ
(§4, Fig. 1)の提案。

- [paper] **Case 1: 手作業で disaggregated 化された B+-tree (§3.1, p.3)**。メモリプール
  (大メモリ・弱 CPU)にツリーノードを置き、compute プール(数十〜数百コア・小メモリ)
  から one-sided / two-sided RDMA でアクセスする構成では、設計空間が広大になる:
  (i) コヒーレンスとキャッシング — RDMA はサーバ間コヒーレンスを保証しないため、
  compute サーバ間の coherence メッセージが素朴実装では大量に発生(ref [40])。inner /
  leaf のどちらをキャッシュするか、eviction ポリシは何か等も開発者が決める必要がある。
  (ii) データ配置と複製 — ツリーノードをメモリサーバ群にどう分割するか、複製を
  いつ/使うか。(iii) オフロード — メモリプール側にも多少の計算があるので、メモリサーバを
  過負荷にせずデータ転送コストを減らすために何をいつどうオフロードするか。既存モデルは
  RDMA read/write 等の低レベルプリミティブしか与えないため、既存の disaggregated
  B+-tree は設計をハードコードしてきた: Sherman は inner node のみキャッシュする戦略を、
  DEX は leaf もキャッシュし compute-side logical partitioning でコヒーレンスを回避する
  戦略と、データ分割・オフロード戦略をハードコードした (§3.1, p.3)。
- [paper] **Case 2: PIM によるフィルタリング加速 (§3.2, p.3)**。フィルタ述語は高度に
  データ並列で、bank レベル PIM(Membrane, ref [57])によるオフロードの好適例。だが
  (i) データ配置 — bank 並列性最大化にはテーブルデータを全 DRAM bank に均等分配する
  必要があるが、既存の仮想メモリページ割当は物理アドレス写像をほぼ制御できない。
  (ii) コヒーレンス — DRAM が offload された on-chip 演算と CPU の両方からアクセス
  されるため、いつキャッシュラインを flush するか、どの flush を省けるかの判断が性能と
  正しさの両方に効く。(iii) オフロード — クエリプラン内のタスクとデータフロー、並列
  実行の調整をデータフロー全体で最適化しないと、無駄なデータ移動と高価な同期を招く
  (§3.2, p.3)。
- [paper] **Case 3: buffer cache のメモリ階層化 (§3.3, p.3–4)**。HyMem / Spitfire の
  3層バッファ、vmcache(ページテーブル流用で page id→pointer 変換、page fault と
  eviction の制御を DBMS が保持、madvise(MADV_DONTNEED) で無償 eviction)、その CXL
  拡張(ref [52])が下地。課題: (i) データキャッシング — 一度だけ順次読まれるデータ
  (scan)は buffer cache を汚染すべきでなく、hash table 構築/probe のような繰返し
  ランダムアクセスは滞在させるべきだが、この意図を既存インターフェースでは buffer
  manager に伝えられない。(ii) 圧縮とエンコーディング — base データは DSM/PAX 列指向、
  中間データは NSM 行指向であり、remote メモリプールやストレージへの「冷却」時の
  encoding/圧縮はデータ形式とターゲットハードの能力に依存するが、透明性が無いと
  汎用圧縮に頼るしかない。(iii) 同期とコヒーレンス — worker スレッド間の細粒度調整に
  使う構造はコヒーレント領域に、調整なしで共有するだけの構造は非コヒーレント領域に、
  thread-local 構造は worker の近くに置きたい(CXL メモリプール前提。ref [4])(§3.3, p.4)。
- [paper] **既存モデルの欠点の総括 (§3.4, p.4)**: (1) 設計・実装が複雑で並行・分散
  プログラミング技能を要求する。(2) 設計判断は実装時に固定され、想定デバイスでのみ
  最適。DEX や Membrane 用パイプラインの別ハードへの移植は、わずかな機能差でも既存
  最適化が無効になりうる。アプリロジックの変更もメモリシステム設計と干渉しうる。
  (3) 手作業アプローチは単一データ構造/アプリに閉じた局所最適化しか提供しない。
  PIM オフロードの効果は end-to-end タスクグラフ・システムのメモリ構成・対象データ
  構造のサイズ/位置/移動コストの3要因に依存し、後2者は開発時には普通わからないため、
  判断をランタイムに遅延させる方が効率的でスケーラブルになりうる。(4) hand-crafted
  システムは重要な機能を欠く部分解になりがち。例: disaggregated メモリ向け index の
  設計で可用性と複製を考慮した研究はほとんど無い (§3.4, p.4)。
- [paper] **DMS の利点**: 異種メモリデバイス横断のより良い最適化、デバイス固有ロジックと
  高レベルコードの分離、将来の未知アーキテクチャ向けプログラミングの単純化 (§3.4, p.4)。
  使い方の例: モノリシックな B+-tree から始めてソースに特性注釈を付ける(ノードを
  cacheable / coherent と宣言、操作関数に offloadable を注釈して PIM 等の active memory
  があれば効かせる)。データ分析ではテーブルサイズや cardinality 等のデータ特性に基づく
  ランタイムオフロード戦略を記述。buffer cache ではどのデータ構造がコヒーレンスを
  要するか、どのデータ型にどの encoding を使うかを宣言 (§3.4, p.4)。
- [paper] **3層アーキテクチャ (§4, Fig. 1, p.5)**: 較正層が (1) ハードウェア能力を発見し
  device catalog に各デバイスの API とともに索引化、その API で (2) 共通メモリサービス群を
  構築し、アプリは注釈とデータフローでそれを使う。ランタイムが (3a) 一括で最適化(jointly optimize)し
  (3b) 実行する (Fig. 1)。
- [paper] **抽象化層 (§4.1, p.4–5)**: logical region ベースの抽象(ref [4] を採用)と
  データフローの2本立て。対象は低レベルデータ構造(B+-tree)から end-to-end システム
  (DBMS や ML フレームワーク)まで。
  - Logical memory region: メモリブロックレベルで質的/量的特性を宣言。例:
    スレッド間同期に使う状態なら `[shared, coherent]`、SLO なら
    `[latency < 1µs, read bandwidth >= 2GB/s]`。B+-tree 開発者は新規ツリーノードを
    `[cacheable, latency < 10µs] LeafNode *n = allocate(...);` と宣言でき、DMS は
    較正層が保持する既定のキャッシング実装で compute 側 DRAM を使える。robust query
    processing では private state に性能 SLO(hash join の hash table が下流に
    X cycles/tuple で消費される等)を注釈し、デバイス上メモリ不足時は DMS が透過的に
    local storage / remote DRAM / object storage へ spill して OOM や性能クリフを
    回避する (§4.1, p.5)。
  - Dataflow: 計算タスクと論理データ転送をデータフローグラフとして明示的にモデル化。
    ストリーミング可能なら融合(task/operator fusion)できるパイプラインをマークし、
    pipeline breaker では状態(hash table 等)を明示。タスクに前述の特性を注釈する
    (Fig. 1 上部の T3=cacheable, T4=offloadable)。PIM フィルタリング例では、データの
    レイアウトと構造を記述する注釈が bank 並列性のための配置と、PIM ユニットとホスト間の
    コヒーレントなビューの維持を導く。高レベルタスクグラフ表現は複数フィルタ操作の
    融合・同時オフロードの機会も晒す (§4.1, p.5)。
- [paper] **較正層 (§4.2, p.5–6)**: (1) 新デバイスの発見、(2) 特性の追跡、(3) ハードの
  機能を実装した API 群の提供、を device catalog(Table 2)の維持によって行う。例:
  local DRAM = coherence + byte-addressable、API は dram-load / dram-store / dram-dsa
  (DSA プリミティブ)。CXL DRAM = partial coherence + byte-addressable、cxl-load /
  cxl-store。Membrane = compute + byte-addressable、pim-load / pim-store / pim-offload。
  PIM デバイスはさらに対応データ型(数値 vs 文字列)や実行可能な計算(比較、正規表現
  対応の有無)等のデバイス固有能力を広告しうる。これらの API は関係演算子の物理実装に
  相当し、同一データアクセス操作の CXL 版 API と PIM 版 API の比較は hash join と
  sort-merge join の比較に似る、というアナロジー (§4.2, Table 2, p.5–6)。
- [paper] **メモリサービス層 (§4.3, p.6)**: DBMS 等の上位アプリが対話するランタイム。
  呼び出し時に提供されるサービス(メモリ割当等)と、資源効率と SLO 執行のために
  バックグラウンドで走るサービスがある。割当時には宣言特性に最適合する logical region の
  データ配置を支援。バックグラウンドでは region 使用状況の軽量メタデータ追跡
  (CXL-root complex でデバイス間共有される文脈等)、データ移動、tiering、GC、データ変換を
  行う。データフローレベルでは、offload 可の region についてスケジューラがメモリ
  サービスに「パイプライン内の計算タスクがサポートされるか、どのコストでか」を照会する。
  具体例: B+-tree ではキャッシングサービス(cacheable region を compute 側 local DRAM に
  キャッシュ)とデータ配置サービス(ツリーノードをメモリサーバ群に分配)が DEX /
  Sherman の手作業を不要にし、オフロードサービスがオフロード判断と実装を DEX 本体から
  切り離す。PIM フィルタリングでは、ランタイムのオフロードサービスが実行時にしか
  分からない列サイズに基づき動的にオフロード可否を決める(小さい dimension table の列は
  オフロードのオーバーヘッドが利得を上回りうる)。buffer cache では、ワークロードの
  データ利用計画(大 scan の一度きり順次読み vs worker 間同期を伴う多数回ランダム)を
  宣言して配置を導き、非自明なアクセスパターンも注釈できる — B+-tree の probe が厳密な
  parent-child パスを辿ることを利用して DEX が手作りした path-based caching(inner node の
  早期 eviction 回避)は宣言的注釈で置換できる、上流演算子の帯域要求に基づく spill の
  調整や、ページ内部構造(PAX / NSM)のヒントによる「冷却」時の encoding/圧縮方式の
  選択も可能、と主張 (§4.3, p.6)。
- [paper] **研究課題 (§5, p.6–7)**: 6つ提示。
  - C1 (較正) デバイス特性化: アクセス粒度のような単純な特性を超えて、負荷レベル依存の
    性能や一貫性保証のような微妙な特性を正確に捕捉・表現するのは難しい。当座は専門家が
    API をハードコードする stop-gap で、device catalog がハードとサービス要求とともに
    自己進化する枠組みが未解決 (§5, p.6)。
  - C2 (抽象化+サービス) 特性→サービスの写像: 同じサービス(例: オフロード)は
    メモリサーバでも PIM でも実装でき、どの実装/変種を使うかの決定が問題。アプリの
    ヒントを使った自動決定が興味深い方向 (§5, p.6)。
  - C3 (サービス) SLA 保証: 量的 SLA(平均アクセスレイテンシ 100ns 以内等)の執行は
    ワークロードとハードの進化の中で特に難しい。ランタイムでメトリクスを監視し、SLO
    未達ならサービス移行等で調整。SLA 同士の重複・衝突(マルチテナントで tail latency
    優先と throughput 優先が衝突、あるいは中間データ共有による共同最適化の機会)を調停する
    必要 (§5, p.6)。
  - C4 (較正+サービス) 拡張性と合成可能性: 新デバイスの能力を捕捉できる forward-
    compatible なインターフェース定義が必要(refs [26, 46] の活発な領域)(§5, p.6)。
  - C5 (全層) デプロイ: コンパイル時/実行時に複数サーバから要求を集める必要があり、
    サーバ毎のローカル DMS コンポーネント + 全体のグローバルサービスという構成を示唆。
    device catalog の可用性が重要で、無視できるオーバーヘッドで DMS 自体の高可用性を
    どう提供するかが課題 (§5, p.7)。
  - C6 (全層) 正しさとデバッグ: DMS ベースの実行がユーザ定義セマンティクスを本当に
    満たすかの保証と、プログラムがどう実行されるか・なぜ SLO を外したかを探れる
    デバッグ/診断ツール。breakpoint / single-stepping、record-replay、テレメトリ、
    宣言的クエリのデバッグ技術の再訪が要る (§5, p.7)。
- [paper] 関連研究との差分 (§6, p.7): SDFG はデータ中心 IR だが性能エンジニアの対話的
  修正が要る。XMem はプログラマがメモリ特性を指定し global attribute table + HW/SW
  協調設計で実装するが、単一ノードの低レベル DRAM アクセス性能に焦点があるのに対し、
  DMS は DRAM 以外の現代メモリ技術を単一ノードと disaggregated の両環境で支える。
  X10 は PGAS の文脈で配置とスケジューリングをランタイムに分離したが、DMS はさらに
  サービス→デバイスの写像をランタイムにオフロードして最適化空間を広げる。Anneser らの
  fully disaggregated システム向け宣言的プログラミングビジョンからは logical memory
  region を抽象化層に採用。Unified Memory Framework のメモリプールは DMS の building
  block として採用可能。DataPipes はデータ移動を宣言的・明示的に指定させ移動プリミティブの
  選択をランタイムに任せるが、DMS は一歩進めてデバイス間データ移動操作の明示指定なしに
  高レベル特性を指定させる (§6, p.7)。

## Evaluation
- [paper] 本論文の「実証」は3つのケーススタディ(disaggregated B+-tree、PIM フィルタ
  リング、buffer cache の tiering)による定性的な動機付けと、DMS を使えば何が宣言に
  置き換わるかの議論であり、貢献 3 は「実用的ユースケースで可能性を示す」と記述されて
  いる (p.2, §3, §4.3)。
- [inference] プロトタイプ実装・定量評価・API の具体的シグネチャ(Table 2 の API 名を
  除く)は本文に存在しない(全文確認)。「DMS ランタイムが hand-crafted 実装(Sherman /
  DEX / Membrane 等)の性能をどこまで回収できるか」「注釈のオーバーヘッド」「較正層の
  維持コスト」はいずれも数値ゼロで、主張の検証可能性は今後の研究に全面依存する。
- [inference] ケーススタディの根拠も既存研究の引用(Sherman / DEX / vmcache /
  Membrane 等)に基づく議論であり、本論文独自の測定は無い。

## Limitations
- Stated [paper]:
  - §5 の6課題(デバイス特性化、特性→サービス写像、SLA 保証と衝突調停、拡張性、
    デプロイと DMS 自体の可用性、正しさとデバッグ)は著者ら自身が未解決として提示
    (§5, p.6–7)。
  - 較正層の当面の現実解は「専門家が API をハードコードする」stop-gap であることを
    認めている (§5 Challenge 1, p.6)。
- Inferred [inference]:
  - 宣言の語彙(Table 1)と実装の間のギャップが最大の未知数。たとえば
    `[shared, coherent]` の宣言に対しランタイムがソフトウェアコヒーレンスで応えた場合の
    性能は、DEX のような「コヒーレンスを設計で回避する」hand-crafted 解に及ばない
    可能性があるが、この種のセマンティクス等価だが性能非等価な写像の扱いは論じられて
    いない。
  - DBMS は既に buffer manager・query optimizer という「宣言→物理」の写像機構を内蔵
    しており、DMS ランタイムとの間で判断の重複・衝突(例: DBMS の eviction 判断と
    DMS の tiering 判断)が起きうる。§4.3 は buffer cache が DMS に仕事を委譲する側の
    例だけを描き、既存 DBMS コンポーネントとの権限分界は未整理。
  - 故障セマンティクス(Table 1 の Fault Semantic / Fault Model)は分類には登場するが、
    §4 のサービス設計では partial fault 時の回復手順やトランザクション的保証との統合が
    具体化されていない(§2 で CXL の partial fault を新故障モードとして指摘している
    にもかかわらず)。
  - マルチテナントの SLA 調停 (§5 Challenge 3) は、調停の主体・課金/優先度モデル・
    分離保証のいずれも未定義で、クラウド環境での実現には資源管理レイヤ(OS /
    ハイパーバイザ)との統合という本文で触れられていない次元がある。

## Relations
- [[2026-fast-wei-dmtree.md]](DMTree: DM range index): DMS の Case 1 (§3.1) が列挙する
  設計空間(compute 側キャッシング、compute サーバ間コヒーレンス、データ配置、
  オフロード)を、まさに hand-crafted に解いた最新例。DMS が「ハードコードの典型」と
  して挙げる Sherman (§3.1) は DMTree のベースラインでもある。§3.4 の指摘
  「disaggregated index で可用性・複製を考慮した研究はほとんど無い」は、DMTree ノートで
  推論したロック保持中故障の未整理と正確に響き合う。
- [[2026-pvldb-zhao-sidle.md]](SIDLE: CXL 索引配置): 木構造の特性(パス型アクセス等)に
  合わせた node 粒度配置を hand-craft した研究であり、DMS §4.3 の「B+-tree probe の
  parent-child パス特性に基づく DEX の path-based caching は宣言的注釈で置換できる」
  という主張の検証対象そのもの。SIDLE の配置ロジックを DMS 的な注釈+ランタイムに
  分解できるかは良いリトマス試験になる。
- [[2026-edbt-krause-disaggregated-survey.md]](disaggregation チュートリアル): 同じ
  地形(RDMA-split / CXL-pool / NDP)を整理し「移植可能な正しさ抽象」を第一級の
  未解決問題として挙げる。DMS はその問いへの(性能・配置寄りの)抽象の提案であり、
  正しさ(CC・リカバリ)側の抽象は DMS でも Challenge 6 として未解決のまま。
- [[2026-eurosys-lopes-pim-txn.md]](PIM-TIDE: UPMEM 上のトランザクション): DMS の
  Case 2 (§3.2) が扱う PIM オフロードの、フィルタではなくトランザクション処理版の
  hand-crafted 実例。DPU への配置・バッチ構成などがハードコードされており、DMS の
  「オフロード判断はランタイムへ」という主張が CC のような正しさ制約付きタスクにまで
  伸びるかを試す材料。
- [[2026-tods-bernhardt-update-ndp.md]](update NDP): cache-coherent interconnect 上の
  共有仮想メモリにロックテーブルを置く設計は、DMS §3.3 の「同期用データ構造は CXL
  プールのコヒーレント領域に置く」という指針の具体的実装例に相当する。オフロード
  サービス (§4.3) がトランザクション保証付き更新オフロードまで抽象化できるかという
  問いを共有する。
- [[2026-edbt-lee-cxl-pools.md]](CXL スイッチプール実測): DMS の較正層 (§4.2, §5
  Challenge 1) が捕捉すべき「負荷レベル依存の性能」等の実デバイス特性を、実機 CXL
  プール + HANA で測った例。device catalog に何を載せるべきかの実証データ源として接続。

## Idea seeds
- [inference] DMS の写像可能性を測る最小実験: DMTree / SIDLE のような公開実装から
  ハードコードされた判断(何をキャッシュするか・どこに置くか・何をオフロードするか)を
  設定ファイル/注釈に外出しし、「素朴なランタイムが注釈から再構成した構成」と「原実装」の
  性能差を測る。差が小さければ DMS の中核主張(宣言で十分)の支持証拠、大きければ
  hand-craft の暗黙知(§3.4 でいう局所最適化)の定量化になる。CIDR ビジョンの
  反証可能な検証としてコストが低い。
- [question] 宣言的メモリサービスとトランザクション的正しさの合成は開いた問題に見える。
  Table 1 は Fault Semantic (atomicity, exactly once) を特性として列挙する (Table 1) が、
  §4 のサービス群(caching / placement / offloading / compression)はどれも正しさ保証の
  合成規則を持たない。[shared, coherent] な region 上の latch と、non-coherent region 上の
  データが混在するとき、リカバリ時に何が保証されるのか。検証の第一歩: CXL の partial
  fault (§2, p.3) を注入できるエミュレータ上で、region 特性の組合せごとに壊れ方を
  分類する故障マトリクスを作る。
- [inference] §4.2 の「メモリ API = 関係演算子の物理実装」アナロジーを真に受けるなら、
  DBMS のコストベース最適化機構(統計・コストモデル・plan enumeration)をメモリ
  サービス選択に流用できるはず。最初の検証: フィルタ1演算について CXL 実行 vs PIM
  オフロードの二択を、列サイズ・選択率を入力とする単純コストモデルで予測し、実測
  (UPMEM 等の実 PIM か simulator)との予測誤差を測る「explain for memory」ツールを
  作る。§4.3 が挙げる「小さい dimension table はオフロードで損」という判断 (§4.3, p.6) が
  モデル化の最初のターゲットになる。

## Changelog
- 2026-07-06: created (status: read)
- 2026-07-06: 検証パスによる修正(第一著者名の綴りを PDF 表記 "Jeronimo Castrillon" に統一。アクセント記号はソース未確認のため除去)
