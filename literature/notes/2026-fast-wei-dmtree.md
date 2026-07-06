---
title: "DMTree: Towards Efficient Tree Indexing on Disaggregated Memory via Compute-side Collaborative Design"
authors: [Guoli Wei, Yongkun Li, Haoze Song, Tao Li, Lulu Yao, Yinlong Xu, Heming Cui]
venue: "FAST '26 (24th USENIX Conference on File and Storage Technologies)"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/fast/Wei0SLY0C26"}
urls: {paper: "https://www.usenix.org/conference/fast26/presentation/wei", pdf: "literature/pdfs/2026-fast-wei-dmtree.pdf", code: "https://github.com/muouim/DMTree"}
status: read
read_date: 2026-07-06
tags: [disaggregated-memory, rdma, range-index, b+tree, fingerprint, caching, locking, concurrency-control, one-sided-rdma]
---

## TL;DR
Disaggregated memory (DM) 上の range index は、private compute-side caching という
共通パラダイムのせいで bandwidth ボトルネック(B+-tree / learned index の read
amplification)か IOPS ボトルネック(ART の細粒度アクセス)のどちらかに落ちる。
DMTree は FP-B+-tree 構造(leaf 内 fingerprint table)を土台に、①fingerprint table を
compute server 群で共有する collaborative cache、②lock フィールドごと compute 側に
置く collaborative locking で、data locating と locking の RDMA を memory server から
compute server 間の未飽和 RDMA 資源へオフロードする。既存 SOTA 比で最大 5.7×
のスループット向上を主張。

## Problem & motivation
- [paper] DM は compute pool(CPU 多・メモリ小)と memory pool(メモリ大・CPU 少)を
  分離し、one-sided RDMA で memory server の CPU を介さず直接アクセスする構成が
  好まれる (§1, §2.1, Fig. 1)。
- [paper] RDMA 資源は2種類: 計算資源 = IOPS(NIC が処理できる op 数/秒)と
  通信資源 = bandwidth(Gbps)。既存研究は片方の最適化を優先し、もう片方のコストを
  著しく増やす (§1, §2.1)。
- [paper] 連続レンジ格納型(B+-tree / learned index)は read amplification による
  bandwidth ボトルネック: node あたり 32 エントリなら 1 エントリ読みに ≈32× の
  増幅 (§2.2.1)。Sherman / ROLEX(SOTA の DM 向け B+-tree / learned index)は
  期待 search 性能(read amplification 無しの 1 RDMA read)の 16.3–18.8% しか
  出ない (§1, §2.2.1, Fig. 3a)。
- [paper] 精密 K-V 位置特定型(ART)は IOPS ボトルネック: scan で小さな leaf を
  多数 RDMA 読みし、insert で internal node の頻繁な更新が要る。SMART の scan は
  Sherman の 35.5%、insert は期待値(2 RDMA)の 35.8% (§2.2.2, Fig. 3b, 3c)。
- [paper] dLSM(DM 向け LSM-tree)は compaction を memory server にオフロードするが、
  memory server の CPU(1コア)がボトルネック化し、insert が期待値の 14.9–41.4% に
  低下(一方 Zipfian update は local memtable で捌けるため期待値超え)(§2.2.3, Fig. 3)。
- [paper] 折衷案 = 連続レンジ格納 + leaf 内精密位置特定(CHIME: leaf 内 hopscotch
  hashing、FP-B+-tree: 1B fingerprint table)。search で Sherman/ROLEX 比 2.2–4.5×、
  scan で SMART 比 2.5× 改善 (§2.3, Fig. 3, Fig. 4)。
- [paper] しかし DM に素朴に載せると: Limitation#1 = 精密位置特定のための追加 RDMA
  (fingerprint table の読み書き、CHIME はハッシュ衝突処理)で FP-B+-tree の search は
  期待値の半分(IOPS 消費が2倍)、CHIME / FP-B+-tree の insert は 23.9–45.4%
  (§2.4, Fig. 3a, 3b)。
  Limitation#2 = leaf のロック(RDMA_CAS でロック、RDMA_WRITE でアンロック)の
  IOPS 消費で update は期待値の 48.1–61.8% (§2.4, Fig. 3d)。
- [paper] 機会: 複数 compute server の要求は memory server に集約されるため
  memory server 側 NIC が先にボトルネック化し、compute server 側の RDMA 資源
  (compute 間含む)は常に未飽和 (§2.4, Fig. 5)。

## System model & assumptions
- [paper] ハードウェアモデル: compute server は CPU 10s〜100s コア・メモリ 1〜10GB、
  memory server はメモリ 100s〜1000s GB・CPU 1〜2 コア。相互接続は RDMA や CXL
  等の高速インターコネクト (§2.1)。評価では memory server に 1 CPU コアのみ割当、
  compute server に 25GB メモリ割当 (§5.1)。
- [paper] index 操作は one-sided RDMA のみに依存(two-sided は memory server の
  CPU を使うため不採用)(§2.1, §4.3)。RDMA はキャッシュライン粒度(例: 64B)の
  read/write 原子性を保証すると仮定し、それ以下のエントリには CRC を付けない
  (§3.3)。RDMA NIC の sequential write 特性(書き込みが順に適用される)を
  embedded unlocking の正しさの根拠にする (§3.3)。
- [paper] DMTree は複数 memory server に分散配置される想定 (§3.1)。ただし評価は
  memory server 1台 (§5.1)。
- [paper] ワークロード仮定: 固定長 24B key + 8B value(value はアプリデータへの
  ポインタ)という 32B KV が DM 系 index の通例として採用される (§5.1)。
- [paper] 並行性制御: write-write 競合は悲観ロック(leaf をロックしてから書く)、
  read-write 競合は楽観方式(8B CRC チェックで再読み)(§3.3)。
- [paper] 整合性モデル: fingerprint の cached copy は非同期更新で一時的不整合を許容し、
  検出時に primary から引き直す optimistic 方式。primary fingerprint table のみ
  write 時に同期更新 (§3.2.2)。
- [paper] 故障モデル: compute server 故障は RDMA 要求失敗の監視や liveness probe 等の
  軽量検出と両立する設計、と主張。故障検出後は membership list から除外し、残る
  replica から新 primary を選出、リモートメモリ上の KV データを検証・同期して
  fingerprint table を再構築できる (§4.3)。primary の所有権は
  consistent_hash(fp_offset) による consistent hashing ring で決まり、無効化された
  server は ring から追い出される (§3.2.3)。
- [inference] memory server 側の故障・データ永続性は本文で扱われていない(タイトルは
  FAST だが対象は揮発メモリ上の index 構造で、recovery は compute 側メタデータの
  再構築のみ)。lock フィールドが primary fingerprint table と同居して compute server
  上にある (§3.3) ため、ロック保持中の compute server 故障時のロック解放手順は
  §4.3 の記述からは読み取れない。
- [paper] CXL 互換性: one-sided RDMA と server 間通信のみに依存する設計は CXL の
  load/store・CPU 間メモリ共有と整合する。CXL でも高並行時は memory 側が
  ボトルネック化しうるため設計は有効と主張(ただし相対的利得は減りうる)(§4.3)。

## Approach
- [paper] **構造**: FP-B+-tree を採用。各 tree node は右 sibling ポインタと子ポインタを
  持ち、各 leaf は fingerprint table(leaf 内 key の 1B ハッシュを N 個順に並べた表)を
  持つ。point 操作で leaf 全体を読む必要を無くす (§3.1, Fig. 4, Fig. 6)。span 32 で
  leaf は約 1.3KB (§5.1)。
- [paper] **Compute-side collaborative caching (§3.2)**:
  - Private internal cache: 各 compute server が internal tree をキャッシュ。ただし
    bottom-level internal node のみキャッシュし、上位レベルはローカル構築(更新同期を
    bottom-level に限定)。internal node の更新は leaf の追加・削除時のみで稀
    (leaf が 32 スロットなら split まで 32 insert 必要)(§3.2.1)。
  - Collaborative fingerprint storage: 各 leaf の fingerprint table は単一 compute server
    上に primary として置かれ、他の server にキャッシュされる。leaf エントリを
    memory server から読む前に fingerprint table を peer compute server から読んで
    ローカルにキャッシュし、fingerprint スキャンで leaf 内位置を特定。write では
    primary のみ同期更新、キャッシュは非同期 (§3.2.1, Fig. 7)。fingerprint は
    1 entry あたり 1B なので compute 側メモリで賄える。メモリ不足時は internal
    node を FIFO で追い出し、新規 fingerprint table は memory server 置きに退避。
    メモリは internal tree cache を優先 (§3.2.1)。
  - 整合性 (§3.2.2, Fig. 8): cached fingerprint の不整合は2種のみで、いずれも直接
    検出可能 — (i) fingerprint はヒットしたが取得した KV エントリの key が違う、
    (ii) 要求 fingerprint がキャッシュに無い。検出時は primary を引いてキャッシュ更新。
    internal entry(bottom-level)には primary fingerprint table へのポインタを格納。
    さらに leaf KV エントリ・internal entry・fingerprint table に 8B version ID を
    持たせ、leaf のレンジが変わる度にインクリメント。version 不一致でキャッシュ
    無効化 → リモート internal tree を辿り直す(entry-level consistency verification。
    node split/merge の未同期を検出するため。K_max / K_min と右 sibling ポインタも
    各 node が保持)。
  - スケーラビリティ (§3.2.3): 複数 compute server が同一 NIC register memory offset に
    fingerprint table の同一コピーを置き、consistent hashing で primary を決定。
    server 縮退時は ring から evict して primary を再配布、次回アクセス時に同期。
    virtual node でホットな fingerprint の負荷分散も可能と主張。
- [paper] **Compute-side collaborative locking (§3.3, Fig. 9)**:
  - leaf node の lock フィールドを primary fingerprint table と一緒に compute server 上に
    分散配置し、RDMA_CAS(0→1)は compute server 間で行う。
  - Embedded unlocking: lock フィールドを fingerprint table 末尾に置き、insert では
    fingerprint table の書き戻しとアンロック(lock=0)を単一 RDMA_WRITE に融合
    (NIC の sequential write 特性でテーブル書き込み後にアンロックされることを保証)。
    fingerprint table を更新しない update は別 RDMA_WRITE でアンロック。更新が稀な
    internal node の lock は従来通り memory server 上 (§3.3)。
  - 効果の説明: FP-B+-tree の update は 5 RDMA(①lock ②fingerprint read ③entry read
    ④entry write ⑤unlock)を要するが、①②⑤を compute 側に移し、memory server への
    RDMA を 5 本中 3 本削減 (Fig. 9, §3.3)。
  - 既存研究のロック最適化(同一 server 内のローカル競合解決・write バッチング)は
    「競合しない通常の write」の locking コストを見落としている、という位置付け (§3.3)。
- [paper] **RDMA 最適化 (§4.1)**: scan 時に fingerprint table で空エントリをフィルタして
  未書き込み領域の読みを省き bandwidth を節約 (Fig. 10)。既存研究由来の read
  delegation / write combining も採用しつつ、バッチサイズ上限を設けて超過分は
  直接実行(大バッチによる遅延悪化の防止)(§4.1)。
- [paper] **操作 (§4.2)**: Search = internal cache → cached fingerprint 照合 → 該当
  slot のみ remote 読み。miss 時は primary fingerprint table を peer から読んで検証、
  無ければ NULL。Write = leaf と fingerprint table を RDMA_CAS でロック → 既存
  エントリは直接更新、新規はテーブルと leaf の空 slot に書き込み → RDMA_WRITE で
  アンロック。テーブルが満杯なら B+-tree 同様に split して半分を移し、internal に
  key-pointer を追加。Delete = エントリを NULL 化(論理削除)、leaf 全削除で隣接
  node と merge、解放 node は background thread が回収。Scan = 開始 leaf を cache で
  特定 → fingerprint table で空をフィルタしつつ leaf を読み、足りなければ右隣へ。

## Evaluation
- Setup [paper]: 7 台(compute 6 + memory 1)、各 2×40-core Intel Xeon Gold /
  128GB DRAM / 100Gbps Mellanox ConnectX-6、100GbE switch、MLNX_OFED-5.4。
  memory server は 1 CPU コア、compute server は 25GB メモリ。YCSB(uniform /
  Zipfian 0.99)、10 億件 preload + 1 億 op、32B KV、scan 長上限 100、実行前に
  全件アクセスで cache warm-up。スレッドは 1 コア 1 スレッド + 4 coroutine
  (dLSM のみ coroutine 非対応)(§5.1, §5.2.1)。
- Baselines [paper]: Sherman、dLSM、ROLEX、SMART、CHIME(全て公開実装)。
  ROLEX は CHIME 提供実装で全ロードデータを事前学習。CHIME の Masked-CAS は
  新ドライバ非対応のため代替実装に置換 (§5.1)。span は Sherman/CHIME/DMTree = 32、
  ROLEX = 8(予測誤差 8)、dLSM は 64MB SSTable (§5.1 Parameters)。
- Headline numbers(micro-bench, Fig. 11–12, §5.2.1):
  - Search: Sherman/ROLEX 比 4.5–5.2×(read amplification 回避)、dLSM 比 2.8–3.1×。
    DMTree / SMART / CHIME は期待 search 性能に接近。
  - Insert: Sherman/ROLEX 比 3.7–4.3×、SMART/CHIME 比 2.3–3.5×、dLSM 比 2.1–5.7×。
  - Update: uniform で全 baseline 比 1.4–4.3×。Zipfian では集中 update を要求集約で
    捌く SMART/CHIME に対しても locking オフロード分 1.1–1.5×(dLSM は Zipfian
    update では local memtable のため非常に強い)。
  - Scan: SMART 比 3.2×、Sherman/CHIME 比 1.1–1.3×(空エントリのフィルタ)。
    ROLEX は leaf が小さく DMTree と同等の scan 性能。
- P99 レイテンシ (Fig. 13, §5.2.2): search で Sherman/ROLEX 比最大 64% 減、Zipfian で
  SMART/CHIME 比 26–31% 減(集約キュー長を制限するため)。insert は 28–80% 減。
  scan は SMART 比 70% 減、Sherman/CHIME 比 10–19% 減。Sherman は Zipfian update で
  ロック集中により 20ms。dLSM は 99% 超の write をローカルで処理し低レイテンシだが、
  remote flush/compaction がブロックされると >600ms に跳ねる。
- YCSB (Fig. 14, §5.2.3): E 以外で Sherman/ROLEX 比 3.8–9.7×、E で SMART 比 3.2×、
  dLSM 比 1.4–8.6×(insert を含む D で顕著)、CHIME 比 1.1–1.7×(ハッシュ衝突
  処理のオーバーヘッド)。Zipfian の search/write 系では SMART と DMTree が同等だが、
  SMART はより多くの compute 側メモリを要する。
- オーバーヘッド (§5.3):
  - 計算: search では fingerprint 走査は全体レイテンシの 5%(0.4us)、同期は無し。
    write では fingerprint 走査+同期(0.4us + 4.5us)が全体の 19.4%(locking 8.2us、
    K-V 8.7us 等は range index 共通コスト)(Table 1)。
  - compute 側メモリ: DMTree 5.4GB(internal cache 2.3GB + fingerprint storage 3.1GB)。
    比較: Sherman 2.1GB、SMART 22.5GB、ROLEX_8 5.6GB、ROLEX_16 1.5GB、
    CHIME 4.5GB (§5.3)。cache を 20GB→2.5GB に絞ると SMART は最大 72% 低下、
    DMTree は維持(CHIME も hotness-aware cache で健闘)(Fig. 15)。
  - memory 側メモリ: version 8B(+64B 超のエントリには CRC 8B)の追加で、10 億件
    32B KV で Sherman 54.2GB vs DMTree 60.1GB (§5.3)。
- Ablation (Fig. 16, §5.4): FP-B+-tree 基点に、+RDMA Opt で scan 1.3×、+Cache で
  search/write 1.2–1.9×、+Concur で insert/update 1.5–1.6×。compute server の IOPS
  利用率は FP-B+-tree の 17.5% から 32.9% に向上 (Fig. 17)。
- ワークロード特性 (§5.5): KV サイズ掃引(メモリ制約で preload を 1 億件に縮小)では
  YCSB-A Zipfian で Sherman/ROLEX 比 3.3–13.5×。scan は 16B で SMART 比 4.8× だが
  128B では bandwidth 律速となり SMART と同等 (Fig. 18)。scan 長 1000 で SMART 比
  3.5–3.9×、Sherman 比は全長で 1.1–1.2× (Fig. 19)。
- [inference] 評価がカバーしていないもの:
  - memory server は常に 1 台。§3.1 は「複数 memory server に分散」と言うが、複数
    memory server でのスケーリング・データ分散の実験は無い。compute server 数の
    スケール(増減時の consistent hashing 再配布コスト、§3.2.3 の主張)も未測定。
  - §4.3 の故障処理(primary 再選出・fingerprint table 再構築)は設計記述のみで、
    故障注入実験や復旧時間の測定は無い。
  - key は固定長 24B のみ。可変長 key・大 value(inline 格納)での fingerprint 衝突率や
    version/CRC オーバーヘッドの挙動は未評価。
  - fingerprint primary のホットスポット(Zipfian で特定 leaf の table に read/lock が
    集中した場合の compute 間 NIC 負荷)は、virtual node での分散が「可能」と
    主張されるのみ (§3.2.3) で実験が無い。
  - DEX(related work で言及される logical partitioning ベースの scalable B+-tree, §6)
    は baseline に含まれていない。

## Limitations
- Stated [paper]:
  - compute 側メモリが不足すると internal node の FIFO 追い出し + 新規 fingerprint
    table の memory server 退避が起きる(性能はその分劣化する設計)(§3.2.1)。
  - write の追加オーバーヘッド(fingerprint 走査+同期)は全体レイテンシの 19.4%
    (性能向上に見合うと主張)(§5.3, Table 1)。
  - 整合性フィールド(version 8B、64B 超は CRC 8B)による memory 側の追加消費
    (54.2GB→60.1GB。SMART も同種のフィールドを持つと弁護)(§5.3)。
  - CXL 環境ではメモリ性能向上により DMTree の相対的利得が縮む可能性(ボトルネックが
    software 側にシフトするので設計自体は有効と主張)(§4.3)。
- Inferred [inference]:
  - 全ての write が「peer compute server 上の primary fingerprint table + lock」を
    経由するため、可用性とレイテンシが第三者ノード(peer compute server)に結合する。
    Table 1 の write 内訳でも locking 8.2us + FP sync 4.5us と、compute 間往復が
    クリティカルパスの過半を占める。compute server の一時的なスローダウン(GC、
    負荷偏り)が index 全体の write タイムアウトに波及する挙動は論じられていない。
  - lock フィールドが compute server 上にあるため、ロック保持中に primary が故障した
    場合の lock 解放と in-flight write の扱いが §4.3 の記述からは不明(fingerprint
    table の再構築は KV データから可能だが、ロック状態は KV からは復元できない
    はず)。
  - 「compute 間 RDMA は未飽和」という前提 (§2.4, Fig. 5) は compute:memory = 6:1 の
    構成での観測。memory server 台数を増やして負荷が分散する構成では、オフロードの
    利得が縮む可能性がある(実験は memory 1 台のみ)。
  - 1B fingerprint は「各 key がほぼ一意の fingerprint を持つ」(§2.3) 前提。leaf 内
    32 エントリなら衝突は稀だが、span を大きくする・キー分布が偏る場合の偽陽性
    (余計な entry read)は分析されていない。

## Relations
- 競合 baseline(本文 §5): Sherman(B+-tree)、ROLEX(learned index)、SMART(ART)、
  CHIME(hybrid)、dLSM(LSM-tree)。構造的土台は FP-B+-tree [38] (§2.3, §3.1)。
- [[2026-pvldb-zhao-sidle.md]](SIDLE: CXL 索引配置): DMTree §4.3 は CXL 環境への
  適用可能性を「ボトルネックが software 側にシフトする」と論じており、CXL 上の
  索引配置を扱う SIDLE と正面から接続する。RDMA-DM(明示的メッセージ)と
  CXL(load/store)で「compute-side collaborative design がどこまで有効か」は
  両ノートを跨ぐ比較軸になる。
- [[2026-pvldb-liu-arcekv.md]](ArceKV: LSM コンパクション): DMTree の dLSM 分析
  (§2.2.3, memory server の 1 コアが compaction で飽和し insert が崩壊)は、
  コンパクション資源制約というテーマで接点がある(こちらは DM、ArceKV 側の文脈は
  各ノート参照)。

## Idea seeds
- [inference] DMTree の collaborative locking は「lock を data と別の場所(compute 側)に
  置ける」ことを示した。これをトランザクション処理に持ち上げ、DM 上の 2PL/OCC の
  lock table 自体を compute server 間で consistent hashing 分散する CC プロトコルが
  考えられる(FORD/Motor 系の DM トランザクションは本文 refs [55,56] にあるが本文は
  index 単体)。最初の検証: 公開コードの lock パスを流用し、複数 leaf に跨る
  atomic multi-put(ミニトランザクション)を実装してロック配置(memory 側 vs
  compute 側)の IOPS 消費を比較する。
- [question] ロック保持中の compute server 故障時に lock 状態を安全に復元する
  プロトコルは何か(§4.3 は fingerprint table の再構築のみ言及)。lease 付き lock や
  epoch ベースの強制解放を足した場合、embedded unlocking(1 RDMA 融合)の利得が
  どこまで残るかは開いた問題に見える。検証: 公開コードで primary kill 時の挙動
  (書き込みハング有無)を観察するところから。
- [inference] 「memory server 1 台 + compute 6 台」構成は本論文の便益(compute 間
  RDMA の未飽和)を最大化する設定になっている。memory server 台数 / compute:memory
  比を掃引して collaborative design の利得が消える境界を特定する再現実験は、
  artifact(https://github.com/muouim/aefast26, Appendix A)が公開されているため
  比較的低コストで着手できる。DM index 論文の評価構成の慣行(1 memory server)自体を
  問う調査にもなり得る。

## Changelog
- 2026-07-06: created (status: read, USENIX 公式 PDF を読解)
- 2026-07-06: 検証パスによる修正(§2.4 の insert 低下率 23.9–45.4% の主語を「CHIME / FP-B+-tree」に明確化。原文は両者を併記)
