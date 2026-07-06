---
title: "LakeMem: An Elastic Disaggregated-Memory Caching Layer for Analytical Processing Systems"
authors: [Xinyi Yu, Yingqiang Zhang, Hao Chen, Zhaoxiang Huang, Xinjun Yang, Feifei Li, Chuan Sun, Jing Geng, Jiong Xie, Ninglong Weng, Yiming Zhang]
venue: "SIGMOD Companion '26 (Companion of the International Conference on Management of Data)"
year: 2026
ids: {doi: "10.1145/3788853.3803100", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3788853.3803100", pdf: "literature/pdfs/2026-sigmod-yu-lakemem.pdf", code: ""}
status: read
read_date: 2026-07-06
tags: [disaggregated-memory, caching, analytical-processing, lakehouse, olap, rdma, elasticity, spilling, intermediate-data, buffer-management]
---

ソース: 手動取得した ACM DL の PDF 全文(pp. 518–531)。PDF は p.1 で
"SIGMOD Companion '26, May 31-June 05, 2026, Bengaluru, India" と自己表記しており、
著者リスト(Alibaba Cloud + 厦門大 + 上海交通大 + 浙江大)も PDF ヘッダで確認済み (p.1)。
対応著者は Hao Chen と Yiming Zhang (p.1 脚注)。

## TL;DR
lakehouse 上の OLAP は「共有される base-table キャッシュ」と「クエリ私有の中間データ
(join hash table、sort/shuffle buffer)」の二重のメモリ圧で memory-bound になるが、
既存の disaggregated memory (DM) キャッシュは byte-uniform で両者の意味的非対称性を
無視し、私有データにまで coherence やロックのコストを課す。LakeMem は Alibaba の
分散メモリプール (DMP) の上に、共有 base-table 用の server-coordinated な SharedCache と
私有中間データ用の client-centric な PrivateCache という dual-path を建て、
需要駆動でプール内のメモリ所有権を両者間でリバランスする。DuckDB 統合プロトタイプで、
DRAM-SSD ハイブリッドキャッシュ比 memory-bound クエリ 2.0–5.9×、I/O-intensive
クエリ 1.2–2.6× の高速化 (abstract, §6.2)。

## Problem & motivation
- [paper] lakehouse/lakebase の普及で分析ワークロードは共有オブジェクトストア +
  open table format 上で走るようになったが、依然として memory-demanding:
  base table のキャッシュと大量の中間状態の両方を抱える (§1)。両者はライフタイムと
  再利用パターンが根本的に異なる — base-table データは長寿命でクエリ横断に再利用、
  中間データは短寿命でクエリ私有 (§1, §2.2)。
- [paper] 動機実験(DuckDB + DRAM-SSD ハイブリッドキャッシュ、全データはリモート
  オブジェクトストア): メモリを 20%→100% にすると I/O-intensive な Q1/Q5 は 2.5×、
  memory-bound な Q13/Q18 は最大 9.2×/9.8× 改善(中間データの spill が消えるため)
  (§3.1, Fig. 2)。
- [paper] 中間データ量はワークロード間で1桁以上異なる: I/O-intensive は Q1 260MiB /
  Q3 7.5GiB / Q5 6.2GiB / Q8 4.1GiB、memory-bound は Q9 113.7GiB / Q13 42.6GiB /
  Q18 83.1GiB / Q21 57.2GiB (Table 1)。
- [paper] メモリ不足への応答も非対称: base-table データは永続なので追い出しても
  再ロードで済み劣化は graceful。中間データは spill-and-reload がクリティカルパスに
  乗る(hash join は build 側を再構築するまで probe できない)ため、spill が起きた
  瞬間に性能が崖落ちする (§3.1)。同一データセット上でもクエリにより中間結果量が
  数桁変わるため適切なキャッシュサイズは決められない (§3.2)。
- [paper] 既存クラウド OLAP の対処は粗粒度な水平スケーリングだが、①ノード単位の
  弾力性でクラスタ再構成に数十秒、②CPU とメモリが結合しておりメモリ増のために
  CPU を買わされ、ピーク時 spill 回避のため高価な大メモリインスタンスを常備する
  ことになる (§3.2)。
- [paper] DM は中間データの要件と2軸で合致: ①揮発・非永続メモリは中間結果の
  一時性に合う(不要な durability コストを避ける)、②細粒度オンデマンド割当で
  需要スパイクを吸収し、完了後は即返却できる (§3.3)。
- [paper] しかし汎用 DM システムは semantically blind: 全データに一様に、multi-RTT の
  メタデータ参照・eviction サンプリング、coherence のための RDMA_CAS / RDMA ロック、
  crash consistency のための複製・ロギングを課す。私有中間データにはどれも不要で、
  そのレイテンシがクエリ実行のクリティカルパスに直接乗る (§1, §3.5)。
- [paper] 結論としての設計命題: OLAP のメモリ層は elastic なだけでなく semantically
  aware であるべきで、「単一の汎用パス + ポリシービット」ではなく共有データ用と
  私有データ用の別個のデータパスが要る (§3.5)。

## System model & assumptions
- [paper] 基盤は著者らが先行研究 [21, 48] で実装済みの distributed memory pool (DMP):
  slab node (SN) が自身の DRAM をプールに供出しデータアクセスを担い、centralized な
  home node (HN) がクラスタメンバーシップ・割当状態のメタデータを保持。API は
  Allocate / Resize / Free の3つ。管理単位 slab は固定サイズの RDMA 登録済み領域で、
  クライアントは Allocate で得た descriptor 以降 HN を介さず one-sided RDMA
  (READ/WRITE) で slab に直接アクセスする (§3.4, Fig. 3)。region は複数リモート slab に
  裏付けられた remote heap として細粒度割当を支える (§3.4)。
- [paper] LakeMem はこの DMP を汎用メモリ基盤として残し、その上の control plane
  (メタデータ・配置・リバランスポリシー)だけを OLAP 向けに特殊化する。data plane は
  one-sided RDMA のまま軽量に保ち、クエリエンジンにも DM 基盤にも侵襲的変更を
  避ける layering (§1, §4.2, §4.3)。
- [paper] ワークロード仮定: OLAP は read-heavy で大規模シーケンシャルスキャン中心
  (§2.2)。base-table データは Parquet/ORC 等の不変カラムナファイルで、ブロックは
  数百 KB〜数 MB。スループットとキャッシュ再利用が優先で、アクセスあたり
  レイテンシは二次的 (§2.2, §5.1)。中間データはクエリタスクに強く束縛された
  ephemeral なデータで、クエリ間・ノード間で共有されず、完了時に破棄される。
  ただしアクセスはクリティカルパス上にあり低レイテンシが必須 (§2.2)。中間データは
  予測可能な固定サイズパターンを示すことが多い、という割当設計上の仮定もある (§5.2)。
- [paper] 整合性モデル: SharedCache は centralized metadata server (MS) 経由の
  globally coherent なキャッシュ (§4.2)。ただし lakehouse のテーブルフォーマット
  (Delta Lake / Iceberg)が不変ファイル + MVCC なので、base table の更新は新ファイル
  として現れる。したがって複雑なキャッシュコヒーレンスプロトコルは不要で、新ファイルは
  オンデマンドでロード、旧ファイルのブロックは eviction が自然に回収する (§5.1)。
  PrivateCache は単一クエリタスク所有を前提にクラスタ規模の coherence・分散ロックを
  一切省く(エンジン内スレッド間はローカルの lock-free queue 等で同期)(§5.2)。
- [paper] クライアントライブラリ: 各 compute node に同居し、Put/Get/Has/Remove の
  KV インタフェースを提供。設定可能な RDMA 登録済みローカルバッファ(デフォルト
  1GiB)を bounded staging buffer として持つが、クエリエンジンのアロケータは
  置き換えず、spill が必要なときだけ呼ばれる (§4.2, §5.2, Fig. 6)。
- [paper] 故障モデル (§5.4):
  - compute node 故障: 中間データは transient なので喪失しても永続データや他クエリの
    正しさは害さない。クエリ失敗(キャンセル・エラー)時はエンジンが明示的に
    cleanup API を呼び、ノードクラッシュ時は MS が liveness lease(ハートビート
    タイムアウト)で当該ノードの全セグメントを回収する。
  - MS 故障: leader-follower 複製。SharedCache エントリ挿入や PrivateCache への
    セグメント割当などクリティカル操作は leader が全 follower に同期複製してから ACK。
  - DM 層故障: DM 層が「高可用なメタデータサービス」と「故障ノードのメモリの自動
    補充」を提供すると仮定。MS は DM 層のメモリトポロジを定期ポーリングし、消えた
    ノード上のキャッシュエントリを即時無効化。揮発の PrivateCache エントリに依存する
    クエリはアボートして再実行、SharedCache データは永続ストレージから再ロード。
- [inference] 「globally coherent」の実体は不変ファイル前提によるところが大きい。
  in-place 更新のあるワークロード(HTAP 的な書き込み)には §5.1 の簡略化は成立せず、
  SharedCache の設計は lakehouse の不変性に強く依存している。
- [inference] 中間データは「ノード私有」仮定 (§2.2) だが、§1 と §2.2 は shuffle buffer を
  中間データの代表例に挙げている。分散 shuffle では生産ノードと消費ノードが異なり
  うるので、この仮定が multi-node シャッフルでどう保たれるかは本文に明示がない
  (評価の GraySort は smallpond の partition shuffling フェーズを測定から除外している
  §6.6)。

## Approach
- [paper] **設計原則 (§4.1)**: ①fast, fine-grained elasticity(小さい単位の割当 +
  ms〜µs 級のリバランス判断)、②semantic-aware caching(dual-path)、
  ③demand-driven rebalancing(PrivateCache は最小容量で開始し、需要発生時に
  SharedCache から回収)。
- [paper] **アーキテクチャ (§4.2, Fig. 4)**: LakeMem = SharedCache + PrivateCache +
  各 compute node のクライアントライブラリ。SharedCache は MS がリモートメモリと
  全キャッシュエントリを管理する cluster-wide キャッシュ。PrivateCache はノード毎の
  client-centric キャッシュで、メタデータ・索引をクライアント側に置く。
- [paper] **2レベルメモリ管理 (§4.3)**: 起動時に MS が DMP の Allocate で初期 region
  (リモートアドレス・rkey 含む)を取得し、内部でサブ割当。各 compute node の
  PrivateCache に小さいデフォルト割当(例 1GiB)を予約し、残りは SharedCache へ。
  この境界は流動的で、需要に応じて PrivateCache が SharedCache の管理空間から
  追加メモリを獲得し、解放時は共有プールへ返す。粗粒度にはMS が DMP の
  Resize/Free を呼び region 全体を伸縮する。
- [paper] **SharedCache (§5.1)**:
  - MS が全メモリの所有区分(shared/private)と SharedCache エントリ→物理位置の
    細粒度マッピングを管理。クライアントは RDMA ベース RPC で MS に問い合わせて
    アドレスを解決し、その後 slab node へ直接 one-sided RDMA read/write (Fig. 5a)。
  - アロケータ: OLTP バッファプールの固定ページと違い、Parquet 等のブロックは
    数百 KB〜数 MB の可変長なので、size-segregated segment class ベースのカスタム
    アロケータを使用。最大クラス超過分は複数連続セグメントを併合する専用
    large-object アロケータで賄い内部断片化を回避。
  - スケーラビリティ: ブロックが大きいため MS 参照はデータ転送に比べ短く、
    メタデータはブロック粒度なのでエントリ数も穏当。scan-heavy なので連続ブロックの
    メタデータ参照をバッチ化できる。さらに全クリティカルメタデータパスを lock-free 化
    (細粒度アトミック + non-blocking データ構造。free list / index はグローバルロック
    なし、eviction は multi-versioned concurrent queue で recency を in-place 更新せず
    追記、segment class 毎に独立 LRU リスト)。
  - Put: MS に問い合わせ、既存エントリならその remote address を、なければ新規割当
    アドレスを返す → クライアントが one-sided RDMA write → MS 上の index 更新は
    データ書き込み後まで遅延され background で非同期実行 (Fig. 5a)。Get: MS の index
    からアドレス取得 → one-sided RDMA read (Fig. 5a)。
- [paper] **PrivateCache (§5.2)**:
  - client-centric: リモートアクセスに必要な全メタデータ(remote address / entry size /
    rkey)と索引をクライアントが保持し、RDMA_CAS や RDMA ロック等の分散同期を
    通常データパスから排除。サーバ側の関与はリバランス時のみ (Fig. 5b)。
  - hybrid allocator: RDMA 登録済みローカルバッファとリモートメモリの両方を管理。
    中間データの固定サイズ傾向を突いて、頻出オブジェクトサイズを専用 segment class に
    シャーディングしスレッド間競合を削減。ローカルバッファはあくまで bounded staging
    で、spill されたデータの最終的な置き場は DMP のリモートメモリ。
  - query-driven lifetime: エントリはクエリエンジンが読み戻すまで全保持し、読み戻し後に
    obsolete 化して解放可能にする。ライフタイムをクエリが握るので eviction ポリシー
    自体が不要(recency/frequency 追跡のオーバーヘッドもない)。
  - asynchronous spilling: エンジンはローカルバッファに書いて spill 要求を投げたら、
    staging バッファが残る限り remote write 完了を待たず実行を再開できる。spill は
    multi-producer single-consumer (MPSC) の複数キューで実装し、foreground スレッドは
    最小負荷キューに投入して semaphore で background スレッドに通知。空きバッファが
    無ければ foreground は回収まで待つ(無制限なメモリ成長ではなく backpressure)。
  - Get: spill 未完了ならローカルバッファから直接返して保留中の spill をキャンセル
    (無駄な remote write を回避)。spill 済みならローカル index のアドレスへ one-sided
    RDMA read。どちらも MS 非関与 (Fig. 5b, §5.2)。
- [paper] **Elasticity とリバランス (§5.3)**:
  - DMP の Resize をワークロード変動のたびに呼ぶのは粗すぎる(region レベルの調整
    レイテンシがあり、割当済みだが遊休のセグメントを転用できない)ので、
    ①割当済みプール内の fast fine-grained リバランス + ②最終手段としての粗粒度
    Resize の2レベル戦略。
  - Intra-pool: priority-driven ownership model。SharedCache が共有プールのデフォルト
    所有者、各 PrivateCache は最小フットプリント(例 1GiB)で開始し、spill 発生時に
    一時的所有権を獲得する。リバランスは厳密に一方向: PrivateCache は SharedCache の
    遊休セグメントを preempt できるが、逆方向は不要(借りたセグメントは中間データが
    消費され次第自動返却されるため)。
  - 拡張トリガ: PrivateCache のローカルアロケータが空き < 閾値(例 20%)を検出すると
    RDMA RPC で MS に非同期拡張要求を送り、残容量で割当を続行。割当先が尽きたら
    拡張充足まで割当パスがブロック。MS は3段階で充足: ①グローバル free-segment
    list → ②SharedCache の遊休セグメントを内容 evict して転用 → ③それでも不足なら
    DMP の Resize にエスカレート。
  - 回収: クライアントの background スレッドが free セグメントを定期スキャンし、
    一定時間(例 >1s)遊休のものを共有プールに返却。スキャン間隔は適応的
    (大クエリ完了などで利用率が急落すると短縮、安定時は延長)。
  - Inter-pool resizing: MS が region リサイズの唯一のコーディネータ。cluster-level 拡張は
    SharedCache の遊休セグメントを回収し尽くしても足りない場合の last resort。縮小は
    MS がグローバル free list を監視し、遊休率が閾値(例 プール容量の 20%)を一定期間
    超えたら余剰を DMP へ返却。
- [paper] **障害処理 (§5.4)**: 上記 System model の故障モデル参照(クエリ失敗時の明示
  cleanup / ノードクラッシュ時の lease 回収 / MS の leader-follower 同期複製 / DM 層
  ポーリングと選択的無効化)。中間データにはクロスクエリの復旧が不要という性質を
  そのまま設計に使っている。

## Evaluation
- Setup [paper] (§6.1): パブリッククラウドの管理されたクラスタ。各マシン
  2× Intel Xeon Platinum 8369B (2.90GHz) / 1TB DDR4 / 4TB Intel DC P4510 SSD /
  CentOS 7 / 100Gbps Mellanox ConnectX-6、通信は RoCE。データは専用ストレージ
  ノード上の MinIO(S3 互換)に永続化。DuckLake をカタログに DuckDB compute
  node (CN) 4台。LakeMem は DuckDB の temporary block manager をクライアント
  ライブラリで置き換える形の external cache として統合。DMP は HN 1台 + SN 2台。
- Baselines [paper] (§6.1): ①disk-based cache(従来型2層ハイブリッド: ローカルメモリ →
  溢れたらローカルディスク)、②local-memory cache(LakeMem の総キャッシュ容量と
  同容量のローカルメモリ。実運用では通常非現実的な、分離オーバーヘッド計測用の
  理想上界)。著者ら自身が「評価は従来型ローカルキャッシュ基線に焦点を当てており、
  DM キャッシュの設計空間全体はカバーしない」と明記 (§6.1)。
- Workloads [paper] (§6.1): TPC-H SF300(公式ジェネレータ、全テーブル Parquet
  1ファイル/テーブル)、GraySort 100GiB(spill-heavy な前処理ワークロードの代表)。
- Headline numbers:
  - [paper] TPC-H 22 クエリ(warm-up 後に各1回実行): I/O-intensive(Q1, Q3, Q4, Q5,
    Q7, Q8, Q17)で disk-based 比 1.2–2.6×(SharedCache が base table をリモートメモリに
    保持し、SSD でなく RDMA でスキャンを捌く)。memory-bound(Q9, Q10, Q13, Q18,
    Q21)で 2.0–5.9×(one-sided RDMA での spill によりディスク spill を回避)。Q6, Q11,
    Q16, Q22 はワーキングセットがローカル DRAM に収まるため同等 (§6.2, Fig. 7)。
  - [paper] 理想上界(全量ローカルメモリキャッシュ)との比較: 選抜クエリで
    「highly comparable」、最大オーバーヘッドは Q8 の 20% と Q9 の 27%(メタデータ
    解決の追加ラウンドトリップとリモート転送が主因)(§6.2, Fig. 8)。
  - [paper] ローカルメモリ感度(メモリ% = ローカル DRAM / クエリ所要データ総量):
    disk-based は 20% 容量時に Q3/Q4 で 2.9–3.2× 劣化、memory-bound (Q13/Q18) は
    6.7–9.8× 劣化。LakeMem はほぼ一定で、ローカルメモリ 20% でもピーク近傍
    (§6.3, Fig. 9)。
  - [paper] Elasticity: Private-only / Shared-only / Static (1:1) / LakeMem の4構成比較。
    I/O-intensive ワークロードでは Shared-only ≈ LakeMem が最良、Static は
    PrivateCache 予約分が遊休で実質半減、Private-only が最悪。memory-bound では
    LakeMem が最良、Static は大きい中間データを収容できず部分 spill、Shared-only は
    全中間データがディスク spill して最悪。mixed では切替直後の transient miss による
    小さいオーバーヘッドはあるが全構成に勝つ (§6.4, Fig. 10)。メモリ配分のタイム
    ラインでは、workload が memory-bound に振れると PrivateCache が急拡張し、
    I/O-intensive に戻ると SharedCache に返る往復が観測される (Fig. 11)。
  - [paper] コスト内訳(100Gbps を飽和させる並行度、PrivateCache 64KiB /
    SharedCache 1MiB 要求): SharedCache は read/write ともデータ転送が支配的で、
    MS への RPC は read 16% / write 17%。PrivateCache もデータ転送支配。write の
    「remote write」時間は実際には foreground スレッドの空きバッファ待ち
    (実 RDMA write は background が非同期実行)(§6.5, Fig. 12)。
  - [paper] ML データ前処理: smallpond(AI ワークロード向け軽量データ処理
    フレームワーク)の DuckDB 実行を LakeMem 化し、GraySort 100GiB を DuckDB
    4並列でソート。spill 先をローカルディスク → LakeMem にすると sort phase
    122.83s→73.81s(1.7×)、全体 154.8s→104.6s(1.5×)(§6.6, Table 2)。
- [inference] 評価がカバーしていないもの:
  - DM ベースのキャッシュ基線(Ditto / Redy / Alluxio 的な外部共有キャッシュ)との
    比較が無い(§6.1 で明示的にスコープ外宣言)。「byte-uniform な DM キャッシュは
    遅い」という §3.5 の主張は、汎用 DM キャッシュとの直接対決では実証されていない。
  - §4.1 の「ms〜µs 級のリバランス」の直接計測が無い。Fig. 11 は秒スケールの
    タイムラインで、拡張要求 1 回のレイテンシや preemption(SharedCache eviction を
    伴う)のコストは分解されていない。
  - §5.4 の障害処理は設計記述のみで、故障注入(MS フェイルオーバ、SN 喪失時の
    クエリ再実行コスト、lease 回収の遅延)の実験は無い。
  - スケールは CN 4 / SN 2 / HN 1 固定。CN 台数を増やした際の MS スループット
    (クリティカル操作は同期複製付き)や、複数 CN の PrivateCache 拡張要求が競合する
    状況は未測定。
  - 各クエリ 1 回実行 (§6.2) で分散・分位点の報告が無い。マルチテナントや同時
    多クエリでの共有プール争奪も未評価。
  - §3.2 の経済性(大メモリインスタンス過剰確保のコスト)を動機にしながら、
    コスト効率(例: $ あたり性能)の定量化は無い。

## Limitations
- Stated [paper]:
  - 評価は従来型ローカルキャッシュ基線が対象で、disaggregated-memory キャッシュの
    設計空間全体との比較はしていない (§6.1)。
  - 理想上界(全量ローカルメモリ)比で Q8 20% / Q9 27% のオーバーヘッド。メタデータ
    解決の追加ネットワークラウンドトリップとリモートデータ転送が原因 (§6.2, Fig. 8)。
  - mixed ワークロードではリバランス適応中の transient cache miss による小さい
    オーバーヘッドが出る (§6.4)。
  - DM 層の耐障害性は「高可用メタデータサービス + 故障メモリの自動補充」を仮定
    (LakeMem 自身はメタデータ監視と結果的データ喪失の処理のみ担当)(§5.4)。
  - メモリノード喪失時、揮発 PrivateCache エントリに依存するクエリはアボート・再実行
    される (§5.4)。
- Inferred [inference]:
  - MS の中央集権性: SharedCache アクセスの 16–17% が MS RPC (Fig. 12) で、かつ
    クリティカル操作は全 follower への同期複製後 ACK (§5.4)。CN 数・エントリ数の
    増加や follower 追加でこの割合がどう伸びるかが設計上の急所だが、シャーディング等の
    緩和策は SharedCache のメタデータ構造(lock-free 化)の話に留まり、MS 自体の
    水平分割は論じられていない。
  - 一方向リバランス (§5.3) は「中間データは速やかに消費される」前提に立つ。
    長時間クエリが PrivateCache セグメントを保持し続けるケース(遅い consumer、
    多段パイプライン)では SharedCache が痩せたまま戻らず、逆方向の preemption 手段が
    無いため I/O-intensive な同居クエリが割を食う可能性がある。
  - spill の実効スループットは 1GiB(デフォルト)の staging バッファに律速される。
    §6.5 が示すとおり write レイテンシの実体はバッファ待ちなので、中間データ生成
    レートが RDMA 帯域を超えるバーストではエンジンが結局ブロックする。バッファ
    サイズと帯域のトレードオフの掃引は無い。
  - LakeMem は internal prototype で、DMP も Alibaba の先行内部基盤 [21, 48](PolarDB
    系)に依存する。アーティファクト URL は本文に無く、外部再現は困難。
  - 中間データの「ノード私有」前提は分散 shuffle と緊張関係にある(§2.2 と §1 の
    shuffle buffer 例示、および GraySort で shuffle フェーズを測定除外している点)。
    ノード間で消費される中間データは SharedCache と PrivateCache のどちらの意味論にも
    きれいに収まらない第3クラスに見える。

## Relations
- [[2026-edbt-krause-disaggregated-survey.md]](分離システムのサーベイ/チュートリアル):
  Krause らの整理でいう RDMA-Split 型メモリ分離の、OLAP キャッシュ層に特化した
  産業界インスタンスが LakeMem。サーベイが挙げる「メモリ分離の何をアプリ意味論に
  合わせて特殊化するか」という論点に対する一つの具体回答(control plane のみ特殊化、
  data plane は one-sided RDMA のまま)として対照できる。
- [[2026-eurosys-hombal-disagg-cache.md]](Ldc: 論理的に分離されたレプリカキャッシュ):
  どちらも「キャッシュを一様に扱うと損」という主張だが、軸が違う — Ldc は
  レプリカ間の内容重複(read/write の汚染)、LakeMem は共有 vs 私有の意味的非対称性。
  「キャッシュ分離の際に何の非一様性を第一級にするか」の比較材料。
- [[2026-edbt-lee-cxl-pools.md]](CXL メモリプール + SAP HANA): ユースケースが直接
  重なる — Lee らの③(SQLScript 中間結果のプール配置)は LakeMem の PrivateCache と
  同じ「中間データをプールメモリへ」を CXL load/store で行う。RDMA(明示的 spill +
  非同期化)と CXL(透過アクセス)で中間データ配置の設計がどう変わるかの対照軸。
- [[2026-fast-wei-dmtree.md]](DMTree: DM 上の range index): 同じく one-sided RDMA の
  DM 上で「調整コストをどこに置くか」を設計する論文。DMTree はロック・位置特定を
  compute 側に移して memory 側 NIC の IOPS を節約し、LakeMem は私有データから
  調整そのものを消す。DM 上のコーディネーション削減の2つの流儀として対になる。
- [[2026-eurosys-cai-rdma-locks.md]](StreamLock: RDMA 分散ロック): LakeMem が §3.5 で
  「私有データには RDMA ロックは不要コスト」と切り捨てた当のプリミティブを高速化する
  研究。共有が本当に必要なデータパス(LakeMem では SharedCache 側)にのみロック
  最適化を投じる、という役割分担の構図で読める。
- [[2026-pvldb-zhao-sidle.md]](SIDLE: CXL ヘテロメモリ上の索引配置): 旧 abstract-only
  ノート時点からの関連。全文読解後の整理では、SIDLE はノード粒度(構造内)の配置、
  LakeMem はデータクラス粒度(キャッシュプール間)の配置で、「分離メモリ上に何を
  どの粒度で置くか」の粒度スペクトラムの両端に近い。
- [[2026-edbt-ye-adcache.md]](AdCache: RL による LSM キャッシュ分割): 「2種類の
  キャッシュプール間のメモリ分割を動的に調整する」問題設定が同型(AdCache は
  block/range cache を RL で、LakeMem は Shared/Private を閾値駆動 + 所有権モデルで)。
  閾値ヒューリスティクス vs 学習ベースという制御方式の対照。

## Idea seeds
- [inference] 中間データの耐障害性はコスト便益で決められるはず: LakeMem はメモリ
  ノード喪失時に依存クエリを全アボート・再実行する (§5.4) が、Q9 のように中間データ
  113.7GiB (Table 1) を作る長時間クエリでは再実行コストが大きい。「再計算コストが
  閾値を超えた中間データにだけ選択的に複製/erasure coding を張る cost-based spill
  durability」は dual-path の自然な第3ポリシーになる。最初の検証: TPC-H Q9/Q18 で
  SN kill を注入し、再実行時間 vs 複製書込みオーバーヘッドの損益分岐を測る
  シミュレーション。
- [question] 一方向リバランス (§5.3) が破れる条件は何か。長寿命の中間データ(多段
  ETL、carry-over される build 側 hash table)が PrivateCache を占有し続けるとき、
  SharedCache 側に preemption 権が無い設計はどの程度性能を落とすか。検証:
  mixed ワークロードに人工的な long-running spill クエリを混ぜ、Fig. 10 の Static /
  LakeMem 比較を再現しつつ SharedCache ヒット率の劣化を観測する。
- [question] ノード間で消費される shuffle 中間データ(生産者 ≠ 消費者)は
  PrivateCache の単一所有意味論に収まらない。所有権移転(producer→consumer への
  メタデータ/rkey の手渡し)を足せば、MS を介さない「private-to-private 転送パス」が
  作れるのではないか。Magnet / Pocket 系の外部 shuffle サービス (§7) との中間形態と
  して面白い。検証: smallpond の shuffle フェーズ(§6.6 では測定除外)を LakeMem
  経由に載せ替えたときの挙動確認から。
- [inference] LakeMem の semantic asymmetry は「共有/私有」の2値だが、EDBT の
  AdCache が示すように分割制御自体を学習で置き換える余地がある。中間データ量が
  クエリプランからある程度予測可能(Table 1 のようにクエリ毎に安定)なら、
  プラン特徴から PrivateCache 需要を先読みして proactive にセグメントを確保する
  「plan-aware pre-rebalancing」は、mixed ワークロードで観測された transient miss
  (§6.4) を削れる可能性がある。検証: TPC-H の optimizer 推定中間サイズと Table 1 の
  実測の相関を取るところから。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: full-text 格上げ(status: abstract-only → read。手動取得した PDF 全文を読解し全節を執筆)
