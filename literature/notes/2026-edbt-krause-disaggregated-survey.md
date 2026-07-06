---
title: "Disaggregated Data Systems – State-of-the-Art and Open Challenges"
authors: [Alexander Krause, Johannes Pietrzyk, Alexander Boehm]
venue: "EDBT 2026 (Tutorial Paper), pp.772-775"
year: 2026
ids: {doi: "10.48786/EDBT.2026.77", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.48786/edbt.2026.77", pdf: "literature/pdfs/2026-edbt-krause-disaggregated-survey.pdf", code: ""}
status: read
read_date: 2026-07-06
tags: [disaggregation, disaggregated-memory, disaggregated-storage, cxl, rdma, near-data-processing, dpu, computational-storage, tiered-memory, cloud, tutorial]
---

## TL;DR
TU Dresden + SAP による EDBT'26 チュートリアル論文(4ページ)。disaggregated
システム研究を①産業界のストレージ分離の歴史、②メモリ分離(RDMA-Split / CXL-Pool)
の現代研究、③データパス計算(NDP)の3部で整理する。実験・新規システムは無く、
設計空間の構造化と open challenges の提示が成果物: 特に「update 可能な NDP の
移植可能な正しさ抽象(MVCC 可視性・ロック・ログ/リカバリを RDMA/CXL 横断で)」を
第一級の未解決問題として挙げる (§4.2)。

- [inference] 注意: キューのメタデータ上のタイトルは "Disaggregated Data System
  Architecture - ..." だが、PDF ヘッダ (p.1) の自己表記は "Disaggregated Data
  Systems – State-of-the-Art and Open Challenges"。本ノートは後者を採用。

## Problem & motivation
- [paper] disaggregation はサーバ筐体の固定リソース比を壊し、compute / storage /
  memory を独立に弾性スケールできるようにする約束。完全実装には至らないが、
  production クラウドで既に部分的に可視(durable storage は compute と別管理、
  DRAM・NVMe SSD などの「ローカル」資源も pooling / remote access の対象に
  なりつつある)(§1)。
- [paper] データ管理システムへの帰結は「データ移動と control-path オーバヘッドの
  管理」の重要性増大: ファブリック上のバイト、プロトコル/I/O スタックの CPU
  サイクル、クリティカルパス上の追加ラウンドトリップ (§1)。
- [paper] 何も無料ではない: リモートアクセスはレイテンシ感度を増幅し、キャッシングと
  concurrency control にストレスを与え、明示的な配置判断(何を compute の近くに
  置くか、何をリモート層に置けるか、処理パイプラインのどの部分をデータ側に動かすか)
  を強制する (§1)。
- [paper] チュートリアルの目的: RDMA 型 Split と CXL 型 Pool という異なる性能
  エンベロープの含意が OS 機構→バッファ管理→アクセスパス→クエリ実行へ伝播する
  設計空間を構造化して概観し、SOTA を要約し、open challenges を提示すること。
  対象聴衆は研究者・実務家双方で、「CXL とメモリ共有をめぐる現在の隆盛と hype の
  理解」を助けることも狙い (§1)。

## System model & assumptions
チュートリアル/サーベイなので単一システムの仮定ではなく、「論文が前提とする
ハードウェア・クラウドの景色」を仮定として列挙する。

- [paper] クラウド IaaS モデル: 顧客は VM の shape(CPU/メモリ構成)を選び、
  durable storage は別途追加(VM にマウントされるブロックデバイス、または
  比較的安価に大容量を GET/PUT セマンティクスで提供する object storage)。
  compute と storage の分離により CPU/DRAM とディスク容量の組合せは事実上自由
  (例: 1 vCPU の小さな仮想サーバに TB 級の永続ストレージを接続可能)(§2)。
- [paper] ただし local SSD と DRAM は依然 VM に紐付いており、サーバ内の資源比が
  アプリの要求比と合わない(in-memory DBMS は web サーバより DRAM 要求が高い)
  ことから resource stranding が発生する(顧客側またはクラウド事業者側)。DRAM
  stranding は DRAM 価格の高さゆえ特に深刻 (§2.2)。
- [paper] メモリ分離の2アーキテクチャ分類(Fig. 1、出典は survey [9] の Fig. 2 に
  準拠): **Split** = サーバが RDMA で「別の discrete サーバ内の DRAM」を直接
  アクセス。**Pool** = CXL により byte-addressable なメインメモリを PCIe 経由で
  接続 (§3)。
- [paper] CXL のハードウェア成熟度の前提: 仕様バージョン 4 は 2025 年に公開済み
  だが、**商用入手可能なのは CXL 2.0 準拠ハードウェアまで**。CXL 2.0 では専用
  CXL スイッチ経由でメモリプールを共有(fabric 越しのメインメモリアクセス)。
  CXL 3.0 デバイスが一般入手可能になれば複数 CPU が同一 DIMM を共有可能になる
  (§3, Fig. 2)。Fig. 2 の例は Unit 1 が Unit n に RDMA で、(メモリ)Unit m に
  CXL で接続する構成 (§3)。
- [paper] CXL のコスト前提は業界内でも割れている: Google のような major player
  ですら cost-benefit の見解が「godsend」(脚注1,2 の LinkedIn 投稿)から
  「クラウド事業者の救世主になるには高すぎる」[16] まで不一致 (§3.2)。
- [paper] CXL レイテンシは接続形態依存: PCIe ソケット直挿しの add-in カードと、
  CXL スイッチ背後に複数メモリ拡張デバイスを連結する場合とで penalty が大きく
  変わる → tiered memory 構成でのアクセス/配置最適化の重要基準 (§3.2)。
- [paper] local SSD の分離には NVMe-over-TCP 等のネットワークアクセスプロトコルが
  候補だが、リモート通信の追加レイテンシを消費側が許容できることが条件 (§2.2)。
- [inference] 全体として「クラウド事業者視点の資源効率(stranding 解消)」が分離の
  経済的動機として置かれており、オンプレミス単一テナントでの動機付けは本文では
  論じられていない。

## Approach
新規手法ではなく、3部構成のチュートリアルとしての整理・分類が内容 (§1)。

**Part 1: Disaggregated Infrastructure(産業界の歴史)(§2)**
- [paper] disaggregated インフラの恩恵を受けるデータ管理設計を3クラスで例示 (§2.1):
  1. 新規システム: Map/Reduce [6]、BigQuery/Dremel [21,22] 等。伝統的 DBMS との
     設計差と DB コミュニティでの受容 [8] を議論。
  2. serverless データ処理: SaaS として提供し VM の存在と shape を顧客から隠蔽。
     産業(AWS Athena [30])と学術(Lambada [23], Skyrise [4])の双方を扱う。
  3. 既存アーキテクチャの漸進進化: 先駆者は Aurora [27,28] — MySQL/PostgreSQL を
     「クエリ処理フロントエンド」と「ストレージバックエンド」に分離して
     コンポーネント化。同様のアプローチに AlloyDB [24] や Socrates [1] (§2.1)。
- [paper] 残る課題として local SSD / DRAM の VM 紐付けと stranding、DRAM stranding
  対策の文献 [17,18]、NVMe-over-TCP を紹介 (§2.2)。

**Part 2: メモリ分離と DB スタック(§3)**
- [paper] まず memory disaggregation と storage disaggregation の混同を解き
  (どちらも資源をホストから分離する点は共通)、Split/Pool の対比を導入 (§3)。
- [paper] DB ソフトウェアスタックを下から上に辿ってメモリ分離研究を配置 (§3.1):
  - OS レベル: Infiniswap [12]、Software-defined far memory [14] — far memory を
    ローカル swap の拡張に使う、または cold/stale データを外部メモリへ移す。
  - バッファ層〜ストレージ/アクセス系〜クエリ処理層を横断。NUMA の時代から
    データ移動と near-data processing が第一級の問題。
  - PolarDB CXL [32]: RDMA に固有の非同期性・統合オーバヘッドに対し、DB 内容を
    far memory に置くことで対抗。
  - Pipeline Grouping [10]: 並行クエリ実行で十分な base data の重なりがあれば、
    naïve な load/store 適用は「インテリジェントな read/write 操作」に負ける。
  - 実 CXL ハードウェア上の in-memory 処理の包括的レビュー [31] も扱う。
- [paper] open challenges: CXL のコストが実用性に見合わない可能性、接続形態による
  レイテンシ差 → tiered memory の配置最適化基準 (§3.2)。

**Part 3: Computing on the Data Path(NDP)(§4)**
- [paper] disaggregation は支配的コストを演算からデータ移動+control path へシフト
  させる。この「disaggregation tax」への解が NDP = data-path computing: リモート
  アクセス経路上に計算を挿入し、転送バイト数とホスト CPU オーバヘッドを削る (§4)。
- [paper] 近年の研究に一貫するパターン: 最大かつ確実な利得は (i) データ削減率の
  高い仕事の push-down、(ii) 低オーバヘッドなインタフェース、(iii) 更新がホスト–
  デバイス境界を跨ぐ場合の正しさの保証、から来る [2,3,15,19,29,34] (§4)。
- [paper] NDP 配置の分類 (§4, §4.1):
  - **Storage 側**: ストレージサーバへの operator pushdown から、SSD/FPGA/SoC
    コントローラ内で制限付きカーネルを走らせる computational storage まで。SOTA は
    「バイト削減第一」: scan 中心カーネル(filter/projection/軽量集約)をストレージ
    近傍で実行し、縮約結果のみ fabric を渡らせる。ホストは DMA フレンドリな
    ストリーミングインタフェースで転送をオーケストレーション [26,29]。
  - **Storage-engine/format 境界**: 鍵となる転換は「run code near data」から
    「run **DBMS-aware** code near data」へ。エンジン固有レイアウトと MVCC 可視性を
    デバイスフレンドリなストリームとコンパクトな coordination metadata に橋渡しし、
    version/visibility 処理を**どこで**行うかを明示管理して、ホスト–デバイス境界を
    跨ぐ random-access amplification を避ける [15,29]。
  - **Query/operator 層**: 実用設計は主に高データ削減オペレータ(filter、部分集約、
    早期 projection)を push down して転送バイトを削る [19,29]。
  - **更新系 NDP**: read-mostly を超えて、明示的な transactional contract の下で
    stateful modification をオフロードする研究が出始めた。cache-coherent shared
    locking や coordination metadata パスで正しさを保ちつつ、フォアグラウンド作業
    への干渉を抑える [2,3]。
  - **Memory 側 NDP**(Split=RDMA / Pool=CXL fabric): 支配的機構はカーネル
    オフロードではなく**構造的**なもの — index / アクセスパス設計が concurrency
    control・キャッシング・validation を作り替え、ラウンドトリップとリモート同期を
    減らし、ポインタ多用のトラバーサルがリモートレイテンシ支配の control-path stall
    に化けるのを防ぐ [20]。
  - **Network/DPU データパス**: DPU はプロトコル・コピーのオーバヘッド除去
    (zero-copy リクエスト処理、軽量 parsing/dispatch)に有効だが、真のフロンティアは
    co-processing と配置。利得は構成・入力特性・DPU 資源制約に依存し、**静的な
    オフロードポリシーは適応的な分割判断なしには劣化しうる** [11,34]。
- [paper] open research problem の再定式化: 「オフロード可能なカーネルの同定」では
  なく「contention と正しさ制約の下で計算断片をどう配置・協調させるか」[11,13] (§4.1)。

**§4.2 の open challenges(本論文の主要な知的貢献)**
1. [paper] End-to-end で適応的な配置: オプティマイザとランタイムが selectivity
   (データ削減)、デバイス飽和、再構成コスト、共有デバイス下の contention/干渉を
   同時にモデル化すべき [11,13,20,34]。
2. [paper] **Update 可能な NDP の移植可能な正しさ**: MVCC 可視性・ロック・ログ/
   リカバリ・障害処理のための最小限で再利用可能な抽象を、異種 near-data エンジンと
   異なるファブリック(RDMA vs コヒーレントな CXL 級リンク)にプラットフォーム毎の
   再設計なしで跨がせる [2,3,15,29]。
3. [paper] 再利用可能な表現と可観測性: 計算がデバイス側へ移っても split execution
   が理解・検証可能であり続けるための、canonical データフォーマット、layout-aware
   変換、プロファイリング/デバッグ支援 [11,15,34]。

## Evaluation
- [paper] 本論文は 4 ページのチュートリアル論文であり、実験・ベンチマーク・
  新規システムの評価は一切含まれない(全文確認済み: §1–§5 + 参考文献のみ。
  §5 は講師3名の経歴)(p.1–p.4)。
- [paper] 定量的な記述は引用文献に委ねられており、本文中の数値主張はハードウェア
  仕様の事実(CXL spec 4 は 2025 年公開、商用は CXL 2.0 まで)程度 (§3)。
- [inference] したがって本ノートの価値は「事実の典拠」ではなく「設計空間の地図と
  研究課題リストの典拠」。個々のシステム(PolarDB CXL、Pipeline Grouping、SMART、
  UpdateNDP 等)の技術的詳細・数値はこの論文からは書けない — 必要なら原典
  ([32],[10],[20],[2] 等)を queue に積んで別途ノート化すべき。
- [inference] チュートリアルの性質上、取り上げる研究の選定は講師陣の研究系譜
  (TU Dresden の CXL/RDMA 研究、SAP HANA Cloud、Petrov グループの NDP 研究が
  引用の相当部分を占める)に寄っている可能性がある。網羅的サーベイとしての
  完全性は主張されていない(あくまで tutorial scope)(§1, §5, References)。

## Limitations
- Stated [paper]:
  - disaggregation のビジョンは「not yet fully implemented」(§1)。
  - CXL はハード分離の鍵だが「its cost may not offset its usability」— 業界の
    見解も不一致 (§3.2)。
  - NVMe-over-TCP による SSD 分離は追加レイテンシ許容が条件 (§2.2)。
- Inferred [inference]:
  - 4 ページの拡張アブストラクト形式で、各研究の比較軸(性能・API・一貫性保証)は
    定性的な文章にとどまり、表形式の体系的比較は無い。Split vs Pool の「異なる
    性能エンベロープ」(§1) と言いつつ、その定量的な差(レイテンシ・帯域の具体値)は
    本文に現れない。
  - トランザクション処理(CC プロトコルそのもの)への分離の影響は「stresses
    caching and concurrency control」(§1) や §4.2 の課題2として言及されるが、
    serializability / isolation の観点からの掘り下げは無い。HTAP への言及も
    引用 [29] 経由のみ。
  - CXL 4 仕様の内容、CXL 3.0 の共有 DIMM のコヒーレンス機構など、将来ハードの
    技術的詳細は一切展開されない。

## Relations
- 直接関連: [[2026-pvldb-zhao-sidle.md]] — SIDLE の CXL 上の索引配置は、本論文が
  §3.2 で挙げる「接続形態でレイテンシが大きく変わる CXL の tiered memory 配置
  最適化」および §4.1 の「memory 側 NDP は構造的(index/アクセスパス設計)」という
  枠組みのまさに実例に位置づく。
- 関連: [[2026-pvldb-zhang-terark-ds.md]] — Terark-DS は分離ストレージ上の KV で、
  本論文 Part 1 の storage disaggregation(compute/storage 分離)の文脈に載る。
- 関連: [[2026-pvldb-kuschewski-btrlog.md]] — BtrLog のクラウド WAL サービスは、
  §2.1 の「既存 DBMS の漸進的コンポーネント化(Aurora/Socrates 系譜)」の設計
  クラスに属する具体例として読める。
- [inference] 本論文が §4.2 で挙げる「update 可能 NDP の正しさ抽象」は、当
  パイプラインの主テーマ(concurrency control)と分離インフラの交点であり、
  Phase 2 の課題候補領域として最も筋が良さそうに見える。

## Idea seeds
- [inference] **RDMA/CXL 横断の可視性・ロック抽象のミニマル API 設計**: §4.2 課題2
  は「MVCC 可視性・locking・logging/recovery をファブリック非依存に抽象化せよ」と
  問題提起のみで解を示さない。one-sided RDMA(非コヒーレント)と CXL(キャッシュ
  コヒーレント)では原子性・可視性の原語が根本的に違うため、共通抽象の設計自体が
  研究になる。初手の検証: 両ファブリックの原子操作プリミティブ(RDMA CAS vs CXL
  上の CPU atomics)で同一の version-visibility チェック(例: read-your-writes +
  snapshot read)を実装し、意味論のずれと性能差を表にする。
- [inference] **適応的オフロード配置のコストモデル検証**: §4.1 は「静的オフロード
  ポリシーは適応的分割判断なしに劣化しうる」[11,34] と述べる。selectivity・
  デバイス飽和・contention を入力とする配置コストモデル(§4.2 課題1)が実際どの
  程度の精度で「オフロードすべきでない点」を当てられるかは開いた実証問題。初手:
  filter pushdown のみの単純系で、selectivity と並行クエリ数を振って host-only /
  device-only / split の勝敗境界を実測し、線形モデルで予測できるか見る。
- [question] 本論文は CXL のコスト論争(godsend vs too expensive [16])を紹介する
  だけで裁定しない (§3.2)。DB ワークロード側から「CXL プールが DRAM stranding
  削減で元を取れる条件」(ワーキングセット比、tail latency 許容)を定式化した研究は
  引用中に見当たらない — [17,18](DRAM stranding 対策)と [16](反対論)を原典
  で読み比べる価値がある。queue 追加候補。

## Changelog
- 2026-07-06: created (status: read)
