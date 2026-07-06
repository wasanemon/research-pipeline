---
title: "TVA: A Version-aware Temporal Graph Storage System for Real-time Analytics"
authors: [Wenhao Li, Zhanhao Zhao, Jinhao Dong, Jiamin Hou, Wei Lu, Yunhai Wang, Xiaoyong Du]
venue: "PVLDB, 19(10):2536-2548, 2026 (PDF 自己申告。arXiv:2607.00406v1 [cs.DB] としても公開)"
year: 2026
ids: {doi: "10.14778/3828612.3828613", arxiv: "2607.00406", dblp: ""}
urls: {paper: "http://arxiv.org/abs/2607.00406v1", pdf: "literature/pdfs/2026-arxiv-li-tva.pdf", code: "https://github.com/Sakuraaa0/TVA.git"}
status: read
read_date: 2026-07-06
tags: [temporal-graph, multi-version-storage, version-chain, hopscotch-hashing, simd, snapshot-isolation, columnar-storage, wal, graph-storage]
---

## TL;DR
時系列グラフ(temporal graph)の履歴問合せは、既存システムでは version chain の線形走査
(AeonG)・スナップショット+デルタの再構築(Clock-G)・全バージョン独立保持(T-GQL)の
いずれかで遅いか重い。TVA はバージョンメタデータ(Temporal Table)と実データ
(columnar な Current Storage + append-only な Temporal Buffer)を分離し、トポロジ側は
hopscotch hash を時系列版管理向けに拡張(bitmap を FrontInfo/BackInfo に置換、有界
オフセット内に版を時系列順格納)して版探索を O(log N_v) にし、さらに NextOffset
(version-skipping)で複数オブジェクトに跨る同時刻スキャンの再探索を省く。SOTA 比で
最大 9.9× の temporal query latency 低減・2.2× のストレージ削減を主張(abstract)。

## Problem & motivation
- [paper] 時系列グラフは静的グラフでは見えない洞察(不正検知・SNS 分析等)を与える。
  例: IP 所在地が急変した直後の取引という時系列パターンは、時刻 t_{n+1} の静的
  スナップショットだけでは検出できず、[t_{n-1}, t_{n+1}] を含む時系列グラフが要る
  (§1, Example 1, Fig. 1)。
- [paper] 既存システムの不足 (§1): 現在状態しか保持しないグラフシステムがある
  [GraphOne/Stinger/Sortledton 系]; T-GQL は版を独立オブジェクトとして保存し
  ストレージ過大; Clock-G は定期フルスナップショット+デルタログで、デルタからの
  スナップショット再構築が高価; AeonG は細粒度バージョニングだが、大きな部分グラフの
  version chain 走査で冗長トラバーサルと大量のランダム I/O が発生する。
- [paper] 汎用ストレージも不適: RDBMS は multi-hop トラバーサルで join が高価
  (hop 数増で中間結果が組合せ爆発)、KV ストアは構造への意識が無く temporal range
  scan が非効率 (§1 p.2, §8)。
- [paper] 3 つの課題 (§1): ❶ delta ベース符号化(変更プロパティのみ格納)は省容量だが
  完全な版の復元に version chain 走査が要る — 低冗長と高速版取得の両立が非自明。
  ❷ 1 頂点に多数のエッジがぶら下がり各自 version chain を持つ。既存構造は最新版
  アクセスに最適化され、履歴は単純な linked 構造で追記されるため履歴問合せが
  最適化の恩恵を受けない。高次数頂点でこれらを統一管理する構造が課題。
  ❸ temporal query は複数頂点の近傍スキャンを含むが、既存システムは各スキャンを
  独立処理し、クエリ間の temporal locality を捨てている。
- [paper] MVCC 系 DB との違い (§8): 古典的 MVCC では履歴版は隔離の副産物で、
  version chain は短い前提 + 積極的 GC/vacuum で除去する。temporal graph DB は
  長い履歴を保存し続ける必要があり、スキャン間の temporal locality がクリティカル。

## System model & assumptions
- [paper] データモデル: G=(X,E)。頂点はプロパティ集合 ρ と有効区間 τ=[t_start, t_end)、
  エッジは (src, dst, τ, ρ)。議論簡略化のため各オブジェクトは単一ラベルと仮定 (§2.1)。
- [paper] バージョニング意味論は論理版番号(txn ID)と物理タイムスタンプの両対応。
  例は物理時刻区間で記述 (§2.1)。
- [paper] 更新は履歴保存型: Delete は τ の終端を閉じるだけ(論理削除)、Update は
  旧版の τ を閉じて歴史版化し、新版を [t_2, +∞) で作る (§2.1)。
- [paper] temporal query の定義: 述語 P(o) を満たしかつ o.τ ∩ t_q ≠ ∅ のオブジェクト
  集合(時点でも区間でも可)。結果は t_q で有効なオブジェクトのみの静的スナップショット
  と見なせる (Eq. 1, §2.1)。
- [paper] 並行性制御: Snapshot Isolation (SI) をサポート。各オブジェクトの
  Temporal Table / HopscotchHash Table の Header に細粒度ロックを置き、グローバル
  ロックを避ける (§6)。
- [paper] 永続化: WAL(4B マジックナンバー・版識別子・操作種別・フラグのヘッダ +
  8B タイムスタンプ + ペイロード長 + 可変長ペイロード + CRC32)。PersistManager が
  2 モードを提供: Pointer Mode = コア構造はメモリ常駐のまま、かさばるプロパティ値を
  64-bit DiskOffset で append-only ディスクファイルへ; Full Mode = RocksDB バックエンドで
  user:{uid}:ts:{timestamp} / friend:{src}:{dst}:ts:{timestamp} という時刻エンコード
  キーにより LSM-tree の辞書順を利用して履歴版をディスク上で物理隣接させる (§6)。
- [paper] 実装は C++ 約 7,000 行。プロパティ無しグラフ入力なら Dynamic Topology
  Storage のみでグラフ全体を扱う (§6)。
- [paper] 評価は単一マシン・デフォルト 5 スレッドで、公平性のため全システムの全データを
  メモリにキャッシュ(Clock-G / T-GQL は元々全メモリ常駐)。また GC の干渉を排除する
  ため全システムで完全な版履歴を保持させる (§7.1)。
- [inference] 対象は実質シングルノード・メモリ常駐前提の設計(§8 で分散指向の
  Kineograph を「分散環境と直近変更のみ対象」と区別している)。分散化・レプリケーション・
  ノード故障は扱っていない。永続化はモードとして持つが、リカバリ実行そのもの
  (WAL replay の正しさ・復旧時間)は本文で評価されていない。

## Approach
- [paper] **全体構造 (§3.1, Fig. 3)**: 更新は Relationship Classifier が振り分ける —
  頂点の内在プロパティ変更 → Temporal Property Storage、エッジの生成・削除・変更 →
  Dynamic Topology Storage。両者に共通する中心アイデアは「バージョンメタデータと
  実データの分離」。版取得は「メタデータを特定 → 参照解決(dereference)」の 2 段で
  済み、ランダム I/O を最小化する (§1, §3.1)。
- [paper] **Temporal Property Storage (§4.1, Fig. 4)**:
  - Current Storage: 各頂点は各プロパティにつき現在値を高々 1 つしか持たない、という
    観察に基づき、現在状態は columnar layout(頂点 ID が主キー、ラベルとプロパティキーで
    列を索引)。最新状態クエリは O(1) 直接アクセス。
  - Historical Storage: プロパティごとの Temporal Buffer(append-only 領域)。更新時に
    旧値が連続領域へ追記される。
  - Temporal Table: 頂点ごとに Header + Version エントリ列。Header は LOCK(8B)と
    ExistBitmap(どの列に現在データがあるか)。Version は Lifecycle(8B、その歴史状態の
    有効区間 [t_start, t_end))、ModifyBitmap(この版で変更された列)、列数 k 個の
    Offset(各 2B、Temporal Buffer 内の履歴値位置。nullptr なら Current Storage 参照)、
    NextOffset(2B)を持つ。メタデータは密に連続配置され直接ルックアップ可能。
  - 更新パス (Algorithm 1): 新値を Current Storage の該当列へ直接書き(有効区間は
    暗黙に [t, +∞))、旧値を Temporal Buffer へ追記、旧版の終端 t とアーカイブ先
    オフセットを記録した新 Version を Temporal Table に追記する。
  - NextOffset: Version 生成時に「次の行(頂点)のその時点の最新 Version」を指すよう
    設定される。これらが複数の version chain を形成し、同一時間文脈での後続データ取得を
    高速化する (§4.1)。Theorem 1: Version i の NextOffset が指す Version j とは
    lifecycle が交差し、かつ t^i_start > t^j_start が成り立つ(証明は GitHub [27])。
    これにより次オブジェクトの版探索を時間的に近い位置から開始できる (§5.1)。
- [paper] **Dynamic Topology Storage (§4.2, Fig. 5)**: 1 頂点に同一リレーションの
  エッジが多数つき件数も予測不能なため、columnar の予測可能オフセットは使えない。
  同一頂点のエッジ間に強い順序相関は無いが、同一エッジの版は時系列順格納が最良、
  という観察に基づき cold/hot 混合格納を採る:
  - Cold = Sparse Array: 頂点ごとに固定サイズスロットを事前割当。空間局所性が高く
    スキャン効率が良い。エッジは頂点領域内に時系列順で挿入。満杯になったら全データを
    HopscotchHash Table へ移す。
  - Hot = 拡張 HopscotchHash Table: 次数が T_deg を超えるか、総版数
    Σ_{e∈E(v)} N_v(e) ≥ T_ver で移行。移行は非同期(書き込みはフラグを立てて即完了、
    background worker が新バケット割当・再編成・ポインタのアトミック更新)。逆方向の
    移行は vacuum/purge で古いデータを消して閾値を割った時のみ (§4.2, §7.5.3)。
    Vertex Map が頂点を格納先へ振り分ける。
  - 統一最小格納単位: VEValue(e_i, x_j)(トポロジ情報)、Lifecycle(有効区間)、
    EPPtr(エッジプロパティの格納位置へのポインタ)(§4.2)。
  - テーブル構成: Header(Label 4B, MaxHopSize 1B, Lock 8B)、64-bit ハッシュの
    HashFunction(上位 7 bit を ControlInfo に記録、SIMD 用)、最新版位置を引く
    専用ハッシュ表 LatestValuePtr、HopInfo = 4 配列(ControlInfo / FrontInfo /
    BackInfo / NextOffsetInfo)。FrontInfo・BackInfo は時系列的に前後の版への双方向
    オフセット。MaxHopDistance が「あるエッジの全版は有界オフセット内」を保証 (§4.2)。
- [paper] **拡張 hopscotch アルゴリズム (§2.2, §4.2, Algorithm 2)**: 原典の hopscotch
  hashing [12] は H-bit bitmap で近傍制約を守るがデータ順序は保存せず、時系列版管理は
  想定外。TVA は bitmap を item 中心の FrontInfo/BackInfo に置換して版間関係を明示的に
  持つ (§4.2 Discussion, p.7)。新版の挿入は LatestValuePtr で最新位置 p を引き、
  [p+1, p+MaxHopDistance] 内に置く。空きが無ければ「Hopscotch」で既存 item を移動して
  空きスロットを作る。2 戦略を距離閾値 d_judge で切替: (a) single-step hopping =
  空きスロットが近ければ 1 item ずつ交換可能かを検査して移動; (b) chain hopping =
  遠い場合、FrontInfo で各 item の最古版位置を辿り、それがターゲット位置より後なら
  item 全体(全版)を後方へ一括移動する。各 item を次 item の位置へ、最後の item を
  空きバケットへ動かす(hop 距離制約を破らないので再検証不要)(Algorithm 2)。
  full-chain traversal を防ぎ、版探索の対数時間と局所化された近傍を保つ (p.7)。
- [paper] **クエリ処理と計算量 (§5.1, §5.2, Table 1)**: N = 頂点数、N_v = 平均版数、
  N_e = 次数、S = Sparse Array サイズ、H = MaxHopDistance、M = バケット内最大 item 数。
  - プロパティ最新版: 該当列を頂点 ID オフセットで直接読み(約 1 ランダムアクセス)。
  - プロパティ歴史版: Temporal Table を ModifyBitmap と Lifecycle で二分探索 →
    Offset で実データ取得。O(log N_v)。version chain 方式の O(N_v) と比べ、Version が
    連続配列なのでランダム I/O は最終段の 1 回のみ(chain 方式は各ステップで発生)(§5.1)。
  - 全オブジェクトの同時刻スナップショット: 先頭頂点のみフル探索、以降は NextOffset で
    該当領域へ直接ジャンプし少数 k 回のプローブで確定。全体 O(N)(最適化無しだと
    O(N·N_v))(§5.1)。
  - トポロジ最新版: N_v·N_e ≤ S なら Sparse Array の有界スキャン O(S)、超えれば
    LatestValuePtr で O(1) (§5.2, Table 1)。
  - トポロジ歴史版: Sparse は O(S)、Hopscotch はソート済み格納とポインタにより
    二分探索 O(log N_v) (§5.2)。全オブジェクトなら NextOffsetInfo で O(N·N_e)。
  - 挿入: Sparse O(1)。Hopscotch は平均 O(1)、リサイズ発生時の最悪 O(N_v·N_e)。
    ただし hop 失敗確率は 1/(M·H!) と低い(Theorem 2、証明は GitHub [27])(§5.2, p.8)。
- [paper] **SIMD 高速化 (§5.3, Algorithm 3)**: ControlInfo の 8-bit 制御フィールド
  (0x00–0x7F = 有効エントリ+ハッシュ上位 7 bit、0x80 = 空、0xFF = 削除済)を
  _mm_loadu_si128 / _mm_cmpeq_epi8 / _mm_movemask_epi8 で 16 スロット同時照合し、
  候補を一括フィルタしてから実データ比較する SIMD 二分探索(GetTemporalEdge)。
  MaxHopDistance ≤ 16 なら版付きエッジ群を密格納と見なせる(§5.2、実験 7.5.1 で裏付け)。
  Temporal Property Storage の Version 探索にも同様に適用 (§5.3)。

## Evaluation
- Setup [paper]: Intel Xeon Gold 5220 @2.20GHz、128GB RAM、Ubuntu 20.04、GCC 11.3.0
  -O3、デフォルト 5 スレッド (§7.1)。ベースライン: temporal 系 = Clock-G / T-GQL /
  AeonG + PostgreSQL(temporal 拡張 RDBMS 代表)+ RocksDB(KV 代表)、current 系
  (temporal 非対応)= GraphOne / Stinger / Sortledton。全システム全データをメモリに
  キャッシュし、完全版履歴を保持(GC 干渉排除)(§7.1)。データセット: IMDB, DBLP,
  YouTube, Epinions, Pokec, LDBC SNB。ワークロード: T-mgBench(Pokec + mgBench に
  FOR TT AS OF / FROM–TO 句)、T-LDBC(IS1–IS7 + AS OF)、T-gMark(頂点プロパティ 24・
  エッジプロパティ 82 のプロパティ集約型)、current 系は BFS / SSSP / PR / WCC (§7.1)。
- ストレージ消費 [paper]: T-mgBench で AeonG 比最大 2.2×、Clock-G 比 3.6×、T-GQL 比
  4.7× 少ない (Fig. 6a, §7.2.1)。T-LDBC では 1.2× / 6.7× / 4.3×。TVA は Historical Data
  部分が Current Data に比べ顕著に小さい一方、Clock-G は定期フルスナップショットで
  Historical が大半を占める (Fig. 6c)。
- グラフ操作レイテンシ [paper]: T-mgBench 400k 操作時点で AeonG 比 3×、Clock-G 比
  3.1×、T-GQL 比 1197.6× 高速 (Fig. 6b, §7.2.2)。T-LDBC では 2.9× / 8.1× / 28.9×
  (Fig. 6d)。Clock-G は大規模グラフでスナップショット生成の CPU/I/O 消費が実時間
  操作性能を圧迫 (§7.2.2)。
- temporal クエリ [paper]: T-mgBench Q1–Q4 で平均レイテンシ最大 206.9× 低減
  (Fig. 7a–c, §7.2.3)。T-LDBC で AeonG / Clock-G / T-GQL 比最大 4.4× / 6.6× / 207.1×
  (Fig. 7d–e)。9.28M 頂点・52.7M エッジの大規模グラフでは T-GQL が OOM で脱落、
  残る AeonG / Clock-G 比で最大 4.7× / 83.9× (Fig. 7f)。PostgreSQL 比 126.4×
  (join ベース multi-hop の組合せ爆発をポインタ参照解決に置換)、RocksDB は点問合せは
  速いが構造非認識でスキャンが非効率 (Fig. 7g–h)。temporal データを除いた非時系列
  mgBench でも AeonG 比 21.7×(アーキテクチャ自体の効率と主張)(Fig. 7i)。
  プロパティ集約型 T-gMark ではメタデータ特定後の複数プロパティ並列取得が効き
  5.1× / 132.9× / 33.4× (Fig. 7j)。
- current グラフ [paper]: ストレージ空間利用効率は Sortledton / GraphOne / Stinger 比
  最大 1.4× / 1.8× / 5.1×。ただし IMDB と Epinions では低次数頂点への固定サイズ
  事前割当のため Sortledton よりわずかに悪い(挿入スループットのための設計選択と
  弁護)(Fig. 8a, §7.3.1)。挿入スループットは最大 6.1× / 2× / 4.5×。YouTube のみ
  GraphOne がわずかに上(高次数頂点集中によるハッシュ衝突増。なお GraphOne は本実験で
  エッジ存在チェックを省いており、有効化すると約 5 edges/s [17] まで落ちるとの指摘)
  (Fig. 8b, §7.3.2)。グラフ解析(BFS/PR/SSSP/WCC)は最大 6.5× / 18.4× / 5.6× 高速だが、
  BFS では skip list で近傍を辿れる Sortledton が最良で、TVA はエッジトラバーサル時の
  ハッシュ表ルックアップが余分なコスト (Fig. 9, §7.3.3)。
- TemporalChain / 永続化 [paper]: 特定時刻の item 群の問合せで、TemporalChain
  (item 間リンクで後続の関連版へ直接ナビゲート)は独立ルックアップ比最大 6.2×
  (Fig. 10a, §7.4.1)。Pointer Mode(TVA_1)/ Full Mode(TVA_2)のメモリフットプリントと
  レイテンシを測定し、WAL 込みでも「わずかなレイテンシペナルティ」で堅牢な性能を
  維持と主張(Fig. 10b–c, §7.4.2。本文は定性的記述のみで具体倍率なし)。
  - [inference] §7.4.1 の「TemporalChain」は §4.1/§5.1 の NextOffset 連鎖
    (abstract の "version-skipping strategy")と同一機構を指すように読めるが、
    本文中で用語の対応は明示されていない。
- Ablation [paper]: Zipf 偏度を変えても挿入の 99% の hop 距離はピーク 8、厳密に 16
  未満 — SIMD 幅 16 に収まる根拠 (Fig. 11a, §7.5.1)。標準的 MVCC version-chain
  ベースライン [15] 比で履歴長が伸びるほど有利になり最大 2.9× (Fig. 11b)。SIMD は
  最大 1.4× のクエリ高速化だが、履歴版が長く・データ量が大きくなるほど相対利得は縮小
  (Fig. 11c, §7.5.2)。hot/cold 移行境界は次数を振った正規化実行時間で最適点を特定
  (Fig. 11d, §7.5.3)。スレッド数に対しほぼ線形なスループットスケーリング、
  write-read 比を変えた混合負荷でも Header 単位ロックの SI 実装により read を
  ブロックせず高スループット維持と主張 (Fig. 11e–f, §7.5.4)。
- [inference] 評価がカバーしていないもの:
  - abstract / §1 の「最大 9.9× 高速」という代表値が §7 のどの実験に対応するのか
    本文から特定できない(本文の個別倍率は 2.9×〜1197.6× と大きくばらつく)。[question]
    9.9× の算出根拠(平均か、特定ベースラインか)は要確認。
  - T_deg / T_ver の具体値・感度分析が本文に無い(Fig. 11d は境界の存在を示すのみ)。
  - vacuum/purge(Hopscotch→Sparse への逆移行、§4.2)のコストと、GC を切った評価
    設定 (§7.1) の裏返しとして「履歴を消す運用」での挙動が未測定。
  - WAL からのリカバリ(クラッシュ後の復元正しさ・復旧時間)の実験が無い(§7.4.2 は
    定常時オーバーヘッドのみ)。
  - スレッド数はデフォルト 5、スケーラビリティ実験 (Fig. 11e) 以外は低並列。SI の
    隔離性そのものの検証(anomaly テスト)は無い。
  - 図中数値の多く(Fig. 6–11 の軸・凡例)は本 PDF テキスト抽出では判読不能のため、
    本ノートの数値はすべて本文プローズから取っている。

## Limitations
- Stated [paper]:
  - 低次数頂点への固定サイズ事前割当は、極低次数頂点が多いグラフ(IMDB / Epinions)で
    空間の無駄になる(挿入スループットとのトレードオフとして許容と主張)(§7.3.1)。
  - Hopscotch 挿入はリサイズ発生時に最悪 O(N_v·N_e)(hop 失敗確率 1/(M·H!) で稀と
    主張)(§5.2, Table 1)。
  - SIMD の相対利得は履歴版チェーンが長く・データ量が大きくなると縮小する (§7.5.2)。
  - エッジトラバーサル頻発型アルゴリズム(BFS)ではハッシュ表ルックアップの
    オーバーヘッドで Sortledton に劣る (§7.3.3)。
- Inferred [inference]:
  - Theorem 1(NextOffset の時間的整合)と Theorem 2(hop 失敗確率)の証明が論文
    本体でなく GitHub 参照 [27] に委ねられており、論文単体では検証できない。
    特に 1/(M·H!) という形は前提(ハッシュ一様性・負荷率)が本文に明示されていない。
  - Version 内の Offset / NextOffset は各 2B (Fig. 4)。2B のアドレス空間で大規模・
    長履歴の Temporal Buffer / 隣接行の版位置をどう指せるのかは本文から読み取れない。
    [question] ベース+相対オフセット等の実装詳細はコード確認が必要。
  - NextOffset 連鎖は「Version 生成時点の次行の最新 Version」を指す静的リンク (§4.1)。
    その後の並行更新・削除・(存在するなら)purge でリンク先が動いた場合の整合性維持は
    本文に記述が無い。Theorem 1 の不変量が SI 並行更新下で保たれる論証も無い。
  - エッジ更新はトポロジ側(HopscotchHash Table)とプロパティ側(EPPtr 先)の両方に
    触れるはずだが、ロックはオブジェクトごとの Header 単位 (§6) で、複数構造に跨る
    更新の原子性をどう保証するかは記述されていない。
  - メモリ常駐前提の単一ノード設計であり、メモリ超過時は Pointer/Full Mode に頼る。
    Full Mode(RocksDB)での temporal クエリ性能はメモリ常駐時と同列に比較されて
    いない(Fig. 10b–c は T-mgBench のみ)。

## Relations
- 本文内の位置づけ [paper]: temporal 系ベースライン = AeonG [13]、Clock-G [20]、
  T-GQL [6]。汎用系 = PostgreSQL(temporal 拡張)、RocksDB。current/dynamic 系 =
  GraphOne [16]、Stinger [7]、Sortledton [10] (§7.1)。構造的土台は Hopscotch
  Hashing [12] (§2.2)。MVCC 文脈では version chain 短前提+GC 依存の従来 MVCC
  [15, 29, 36] と対比される (§8)。
- [inference] 著者の重なり(Jiamin Hou・Zhanhao Zhao・Wei Lu・Xiaoyong Du が
  AeonG [13] の著者欄にも並ぶ、p.1 著者欄 + p.13 ref [13])から、TVA は AeonG と
  同グループの後継・改良系の仕事と見られる(本文にその明言は無い)。
- コーパス内(既存 49 ノート): temporal graph storage を直接扱うノートは無く、
  継承・競合関係にある既存ノートは見当たらないためリンクしない。

## Idea seeds
- [inference] NextOffset / TemporalChain の核は「直前スキャンで得た版位置を、時間的
  不変量(Theorem 1)を根拠に次オブジェクトの探索起点に再利用する」ことにある。
  これは graph 固有ではなく、リレーショナル MVCC の time-travel scan(AS OF での
  大量タプル走査)にも移植できるはず — §8 自身が「MVCC は chain 短前提・GC 依存で
  temporal 分析に不向き」と指摘しており、逆に MVCC 側へこの機構を持ち込む研究余地が
  ある。最初の検証: 公開コード(https://github.com/Sakuraaa0/TVA.git)で
  TemporalChain の on/off 差(Fig. 10a 相当)を再現した後、多版 column store の
  スナップショット走査にオブジェクト間版リンクを試作してプローブ数を比較する。
- [question] abstract の 9.9× と本文の個別倍率(206.9×・1197.6× 等)の対応が不明。
  アーティファクトでベンチ設定を確認し、代表値の算出方法を特定する(再現実験の
  入口として手頃)。
- [question] 2B オフセット(Offset / NextOffset, Fig. 4)のアドレッシング限界と、
  purge 後の dangling リンク処理。コードの当該構造体を読むのが第一歩。壊れ方が
  分かれば「長履歴 temporal storage におけるメタデータ圧縮 vs 到達可能性」という
  一般問題に接続できる。
- [inference] hot/cold 移行閾値(T_deg / T_ver)は静的で、Fig. 11d は静的最適境界を
  示すのみ。時間とともに hot 集合が動くワークロード(skew ドリフト)下での適応的
  マイグレーション(閾値の自動調整、逆移行の積極活用)は開いている。検証: Zipf α を
  時間変化させたマイクロベンチで固定閾値の性能劣化を測る。
- [question] SI 実装の隔離性は実験で検証されていない(§7.5.4 はスループットのみ)。
  複数構造(トポロジ+プロパティ)に跨るエッジ更新で read が中間状態を観測しないか、
  公開コードに対する並行テスト(Pisco 系の isolation テスト手法の適用対象として
  手頃なサイズ ~7,000 LOC)で確かめる価値がある。

## Changelog
- 2026-07-06: created (status: read)
- 2026-07-06: 検証パスによる修正(§7 個別倍率レンジの下限を 3× → 2.9× に修正。ソースは T-LDBC 操作レイテンシで AeonG 比 2.9× を報告)
