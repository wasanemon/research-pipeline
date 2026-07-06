---
title: "CloudJump III: Optimizing Cloud Databases for Tiered Storage"
authors: [Zongzhi Chen, Mo Sha, Feifei Li, Sheng Wang, Baolin Huang, Guoqing Ma, Huaxiong Song, Ke Yu, Xizhe Zhang, Yuan Wang]
venue: "SIGMOD Companion '26 (Companion of the International Conference on Management of Data, Bengaluru, India)"
year: 2026
ids: {doi: "10.1145/3788853.3803084", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3788853.3803084", pdf: "literature/pdfs/2026-sigmod-chen-cloudjump3.pdf", code: ""}
status: read
read_date: 2026-07-06
tags: [tiered-storage, cloud-database, buffer-management, disaggregation, object-storage, eviction, checkpoint, recovery, backup, snapshot, write-amplification, multi-tenancy, innodb, mysql]
---

## TL;DR
Alibaba Cloud の CloudJump 第3世代。クラウド DB のホット/コールド tiering を
ブロック層・FS 層の外部機構ではなく DB カーネル内に取り込み、buffer manager の
既存制御点(eviction と flush)で InnoDB 可視のメタデータ(ページ種別・age・
テーブル識別・一時テーブル判定・buffer-pool residency 等)を使って配置と書き込み
ルーティングを決める (§1, §2.3)。構成は DRAM buffer pool → ローカル SSD 上の
Buffer Pool Extension(BPE、揮発・クリーンページキャッシュ)→ ESSD 上の
OSS Buffer(耐久ステージング)→ OSS(2MB 版付きオブジェクト)の4層で、
snapshot-version プロトコルにより zero-downtime バックアップと crash-consistent
リカバリを両立する (§3, Fig. 1, §4.3)。プロダクションの MySQL 互換サービスに
展開済みで、fast tier がデータの 20–30% 程度でも all-ESSD に迫るスループットと
有界な tail を達成したと主張 (§5.2, §5.3, §7)。

## Problem & motivation
- [paper] クラウド DB は compute-storage 分離により、ローカル NVMe / RDMA 系
  リモートブロックボリューム / Ethernet 経由オブジェクトストレージという異種階層に
  またがる。DRAM を含むストレージ支出が TCO の支配的要因になっており、問題は
  「tiering するか」ではなく「動的 OLTP 下で性能とコストが安定するようにどう
  配置するか」である (§1)。
- [paper] 階層のコスト・レイテンシ幅は大きい: DRAM 80–100ns / $1.6/GB/月、
  instance-attached NVMe 10–100µs / $0.05、network block volume 200–500µs /
  $0.152、object storage 40–200ms / $0.016、archive tier 分〜時間 / $0.003 (Table 1)。
- [paper] 既存の tiering の大半はカーネル外(block / filesystem / gateway 層)で
  動く。I/O パターンは見えてもエンジン内部状態が見えないため、DRAM 上のホット
  ページがトレース上はコールドに見える、構造的に重要な index/メタデータページが
  早期に追い出される、などの誤配置が起きる。またカーネルの recovery/backup
  ロジックと分離された移動は LSN ベースの不変条件や snapshot プロトコルを尊重
  できず、zero-downtime の正しさを毀損する (§1, p.2)。
- [paper] 既存手法(dm-cache/bcache/LVMCache 系ホストキャッシュ、ILM/HSM、
  アレイ/クラウド auto-tiering、object-centric 設計)の共通限界: ワーキングセットの
  急変やスキャンでキャッシュ効率が崩れる、pollution/thrashing による tail 悪化、
  write-back の write amplification と不正終了後の長い回復、再起動/failover 後の
  warmup、粗粒度 recall(小さな読みが whole-file recall を誘発)、burst credit 枯渇や
  per-volume 上限、cross-AZ 起因の jitter、オブジェクト層の per-request オーバー
  ヘッド (§2.2)。
- [paper] 手動スキーム(時間ベースのパーティショニング、テーブル単位再編)は
  粗粒度かつ後追いで、分単位のワークロード変動に追随できない (§1)。
- [paper] 先行世代: CloudJump I はリモート分散ブロックストレージ向けに I/O パスを
  再構築(latency-bound / bandwidth-bound フローの分離)、CloudJump II は
  Multi-Version Data(MVD)により標準クラウドストレージ上でページ単位多版
  アクセスを RW/RO ノード間で実現。III は tiering をエンジン内に取り込む第3の
  マイルストーン (§1, §6)。

## System model & assumptions
- [paper] 対象エンジン: Alibaba Cloud のプロダクション MySQL 互換エンジン
  (InnoDB 系)。buffer manager・I/O サブシステム・メタデータカタログへの限定的な
  変更として統合 (§1)。ページは 16KB、OSS-backed テーブルは 2MB 単位
  (=128 ページ)のオブジェクトに分割され、2GB のテーブルなら 1024 オブジェクト
  (§3.1, §4.2.1)。オブジェクトは異なるテーブルや不連続領域のページを混在させない
  (§3.1)。
- [paper] 4層構成と揮発/耐久境界 (Fig. 1, §3): Cache Tier(揮発)= InnoDB Buffer
  Pool(DRAM)+ BPE(direct-attached SSD、クリーンページキャッシュ)。
  Storage Tier(耐久)= OSS Buffer(ESSD、network-attached block storage)+
  OSS object store + メタデータ/スナップショットサブシステム。DRAM/SSD の内容
  喪失は耐久性を損なわない。
- [paper] 耐久性モデル: dirty ページは OSS Buffer か OSS に flush された時点で
  初めて durable。それまでの耐久性は WAL が保証し、instance 故障時は WAL replay で
  復元。データが耐久層に到達すれば対応する WAL は trim できる。配置と flush 順序は
  redo ログから独立(placement は LSN ベースの版とは分離)(§3, §1)。
- [paper] メディアの前提: ESSD はブロック粒度の atomic visibility(atomic write
  またはポインタ間接、ESSD プロトコル定義)を持つ committed block storage。
  OSS は強整合な HTTP PUT/GET で、2MB の immutable な版付きオブジェクトを
  単調増加の version ID で保存し、旧版は非同期に回収 (§3.2/p.5)。
- [paper] OSS Buffer を instance-attached でなく network-attached(ESSD)に置くのは
  耐久性のための必須要件: instance storage 上ならノード故障で消え、OSS からの
  full replay なしには回復できない (§3.1)。
- [paper] ワークロード仮定: OLTP(トランザクショナル)対象。クエリセマンティクスや
  オプティマイザ変更に依存せず、アプリケーションヒント不要。使う信号はページ種別と
  age、テーブル識別と per-table quota、一時テーブル判定、ページの clean/dirty、
  buffer-pool residency のみ (§2.3)。
- [paper] 設計目標 (§2.3): (i) 有害な fast-tier miss の最小化と tail 影響の有界化、
  (ii) バックグラウンド移動の抑制(foreground I/O との競合回避)、(iii) 書き込み
  結合とルーティングによる write amplification 削減、(iv) 配置を MVCC/WAL と直交に
  保ちつつ snapshot プロトコルと協調して zero-downtime バックアップと crash-
  consistent リカバリを維持、(v) 小さい fast-tier フットプリントでのマルチテナント
  コスト効率。ローカル SSD は共有キャッシュなので per-table quota と帯域配分で
  テナントの独占を防ぐことも第一級の目標。
- [paper] 一時テーブルはデータ喪失を許容する(Single-Write で BPE のみに書き、
  recovery 対象外)(§4.1.2, §5.4/Fig. 8b)。
- [paper] 故障モデル: crash/restart 後は ESSD 上の OSS Buffer がテーブルメタデータと
  ブロック記述子のスキャンで状態を再構築し、InnoDB の crash recovery(redo replay)
  と版整合チェックで復元 (§4.2.1, §4.2.3, §4.3.4)。
- [inference] マルチノード(RW/RO 複数ノード)間での BPE/OSS Buffer の共有・整合は
  本文に記述がない。CloudJump II の MVD が RW/RO 間の多版アクセスを担う (§1) と
  述べられるのみで、III の tiering 状態がレプリカ間でどう見えるかは読み取れない。
- [question] BPE の書き込みポリシー既定値に本文内の不整合がある: §4.1.2 の箇条書きは
  Dual-Write を「persistent table の default」とするが、直後の decision rule は
  「persistent table は通常負荷では Clean-Write、dirty ページ永続化時に Dual-Write」
  とする。どちらが実運用の既定かは本文からは確定できない。

## Approach
- [paper] **中核方針**: 専用のマイグレーションスレッドやユーザ調整のパーティション
  ポリシーを持たず、buffer manager の自然な制御点(eviction / flush)を再利用して
  admission と書き込みルーティングを決める。eviction-centric 制御によりロックコストと
  運用複雑性を削減 (§1, §3)。
- [paper] **読みパス (§3.2, Fig. 2)**: R1 Buffer Pool hit(ns 級)→ R2 BPE hit
  (SSD レイテンシで DRAM に promote)→ R3 OSS Buffer hit(2MB ブロックから
  16KB ページを抽出して promote)→ R4 リモート OSS read(HTTP GET、range read 可。
  空間局所性のため 2MB オブジェクト全体を OSS Buffer に prefetch してもよい)。
  非 DRAM 層から取ったページは Buffer Pool に再挿入される。
- [paper] **BPE(§4.1, Fig. 3)**: InnoDB の young/old sublist に ghost sublist を加えた
  3リスト構成。ghost list は追い出されたページの識別子のみ(データなし)を保持する
  FIFO で、容量は BPE キャパシティで有界。BPE への admission は eviction パス限定の
  reuse-aware 方式: buffer pool 内で複数回アクセスされたページ、または ghost list に
  既載のページのみ BPE に書く。one-hit ページは識別子だけ ghost list に記録し、後の
  再アクセスで初めて BPE に入る(S3-FIFO の selective admission / second-chance 原理を
  明示的に踏襲)(§4.1, §4.1.1)。BPE 内の置換は per-page second-chance bit を持つ
  修正 CLOCK(リンクリスト同期を排し、SSD レイアウトに沿う順次書き込み)(§4.1.3)。
  BPE hit は old sublist に promote(young ではない)し、DRAM 内で再アクセスされて
  初めて young へ (§4.1.1)。
- [paper] **BPE 書き込みポリシー (§4.1.2)**: Clean-Write(flush 時に BPE コピーを
  無効化。SSD write amplification 削減、read-intensive 向け)/ Dual-Write(flush 時に
  storage 層と BPE を並行更新、書きたてのクリーンページを BPE に残して再利用性向上)/
  Single-Write(BPE のみに書く。一時・短命テーブル用、recovery 対象外)。エンジンが
  テーブル種別とチェックポイント状態から自動選択し、read-after-write 不整合を排除。
- [paper] **BPE の工学的機構 (§4.1.3)**: メタデータ圧縮(per-page ロック構造排除、
  64GB BPE で制御メタデータ約 184MB)、chunk-based resizing(64MB チャンク単位で
  数秒でのオンライン増減、テナント負荷に応じた弾力性)。
- [paper] **OSS Buffer(§4.2, Fig. 4)**: エンジンとリモートオブジェクトストレージの
  間の耐久ステージングキャッシュ。ブロック ID(OSS オブジェクトインデックスと整合)
  → エントリのハッシュディレクトリを持ち、各エントリは永続メタデータ(block ID、
  ページ ID 範囲、最新 snapshot version、dirty/valid/evictable/inflight フラグ、
  per-page の dirty マーカー・更新タイムスタンプ・validity)を保持。in-memory には
  page-to-block hash、LRU list、flush list を持ち、InnoDB buffer pool と並行する構造を
  ブロック粒度で運用する。再起動時はテーブルメタデータとブロック記述子のスキャンで
  最終コミット状態を復元 (§4.2.1)。2MB ブロックの全 128 ページをメモリに実体化せず、
  buffer pool から書かれたページと prefetch されたページのみ保持 (§4.2.2)。
- [paper] **書き込みパス (§3.3, Fig. 2)**: (1) Buffer Pool flush: dirty ページは OSS に
  直接書かず、対応する OSS Buffer ブロックに永続化(W1)し、atomic に dirty マークと
  block-local メタデータ更新(W2)。この時点で ESSD 上で durable になり、当該ページは
  WAL replay なしで回復可能。リモート PUT は発行せず、同一ブロックへの後続更新を
  吸収して遅延する。(2) OSS Buffer flush: ブロックの evict/明示 flush 時のみ、per-table
  メタデータを先に更新(W3: modification flag と新 object version ID)してから、
  2MB オブジェクト全体を新版として非同期 PUT(W4)。dirty ページのみでなくフル
  オブジェクトを append-only 版として書く。PUT 完了後にブロックを clean 化。BPE に
  同居するページには flush を伝搬(W5: 更新または無効化)。段階的耐久性モデル
  (Buffer Pool → OSS Buffer → OSS)。
- [paper] **flush スケジューリング (§4.2.4)**: ブロック内バッチング(ブロック跨ぎの
  集約はしない)、ホットブロックへの反復書き込みを避ける temporal deferral、飽和前に
  バックグラウンド flush する watermark 制御、OSS QPS とテナント公平性制約下の
  rate limiting。flush はバックグラウンドスレッド(アイドル時・スケジュールバッチ)
  または clean ブロック枯渇時に同期発行。clean ブロックは OSS 同期後にのみ eviction
  候補になる(永続化保証後にのみ領域回収)。
- [paper] **クラッシュ整合性 (§4.2.3, §4.3.4)**: 相補的順序付け — ローカル書き込みは
  metadata → data(意図の記録)、リモート flush は data → metadata-clean 化。これで
  replay が冪等になる: メタデータのみ先行なら redo replay、データのみ先行なら
  再 flush。両方永続した時のみ clean(Stage 3)。各ブロックは「旧版のまま」か
  「新版として完全」のどちらかに見え、部分書き込みや版ギャップが生じない (§3.3)。
- [paper] **snapshot/backup プロトコル (§4.3, Fig. 5)**: グローバルカウンタ
  next_snapshot_version が snapshot epoch を識別。バックアップ開始時にグローバル
  OSS ロックを取得(並行 DDL と OSS 書き込みをブロック)してカウンタを increment。
  以後の OSS 書き込みは現行 snapshot version でタグ付けされ、版が進んでいなければ
  in-place 上書き、進んでいれば新しい版付きオブジェクト(例: file_0002_v2)を書いて
  旧版をバックアップ用に保持。foreground は常に最新可視版を読み、バックアップは
  自分の epoch に対応する版を読むことで point-in-time 整合を得る (§4.3.1)。
  手順: ①version bump → ②ロック保持中に OSS Buffer(と任意で BPE)を含む
  ボリュームの ESSD スナップショット取得 → ③テーブルメタデータの dirty bit 走査で
  変更検出 → ④ロック解放(OSS write stall は数秒に収まる)→ ⑤OSS fast-copy API に
  よる intra-bucket shadow copy(メタデータのみ複製、データ移動なし、multi-TB でも
  秒単位)→ ⑥dirty bit クリアと invalid_snapshot_version 前進(旧版回収可能化)
  (§4.3.3)。増分バックアップは dirty-bit マップ誘導で差分のみコピー。
- [paper] **リカバリ (§4.3.4)**: ESSD スナップショットを attach → メタデータ走査で
  必要ブロックと版を特定 → 版付き OSS オブジェクトを取得(ブロックごとに版 k と
  <k が混在するのは正常)→ 再起動(OSS Buffer 制御構造の再構築 → InnoDB crash
  recovery)→ redo 適用(冪等)。
- [paper] **特殊経路**: 一時テーブルは OSS Buffer から除外して BPE ローカルに留める
  (§5.4, Fig. 8b)。DDL/BLOB の大きな書き込みは共有 log-flush キューから外して
  バイパスする (§5.4, Fig. 8c)。
- [question] バイパスの行き先が本文内で揺れている: §5.3 は「大きな書き込みを ESSD へ
  直接ルーティング」、§5.4 は「BLOB/DDL 書き込みを両方とも OSS へ直接送る」と
  記述する。2種類のバイパスが併存するのか、記述の不一致なのかは本文から確定
  できない。

## Evaluation
- Setup [paper] (§5.1): 2構成 — small: 8-core CPU / 1GB buffer pool / 50GB データ /
  16 クライアントスレッド。large: 64-core CPU / 100GB buffer pool / 5TB データ /
  128 スレッド。preload + スループットとキャッシュヒット率が安定するまで warmup。
  fast tier はデータセットの 5%–50% をカバーし、残りは OSS。ワークロードは
  Sysbench(OLTP マイクロベンチ)、YCSB(Zipfian α ∈ [0.8, 2.0])、Voter(短命
  セッション・厳しいレイテンシ目標)、Game(Alibaba のオンラインゲーム本番
  ワークロード。大 BLOB 更新とバースト)。比較対象は non-tiered の all-ESSD
  ベースライン(および §5.5 では OSS-only)。指標は TPS と CP(ストレージコスト
  あたりスループット)(§5.2)。
- 全体傾向 [paper] (Fig. 6, §5.2): TPS はキャッシュ比とスキューの両方に単調で、
  ホットセットが fast tier に収まると knee が現れる。YCSB-50GB では α≥1.4 で
  20–50% キャッシュ曲線が ESSD 上限近くに収束、α≤1.0 かつ ≤10% キャッシュでは
  ギャップが残る。CP はスキューが強いほど・中庸キャッシュ(典型 20–30%)ほど改善。
  read-write は write amplification の分だけ傾きが緩く、α≥1.4 なら 30–50% キャッシュで
  near-ESSD。write-only は α≥1.6 で 10–50% の曲線が密集(rate-limited なマージ
  writeback により remote PUT 圧が有界)。5TB でも定性は同じで knee が右シフトし、
  CP 改善はスケールでむしろ顕著。
- Voter [paper] (Fig. 7, §5.3): 1 スレッドで +17%(2727 vs 2321 RPS、p50 347µs vs
  419µs)、4 スレッドで同等(8554 vs 8589)、16 スレッドで ~10% 以内(16902 vs
  18583)だが p99 は 4861µs vs 3205µs(~1.5×)、64 スレッドで all-ESSD の 79–80%
  (17742 vs 22328)、p99 22145µs vs 14714µs(~1.5×)。制約要因は foreground stall
  ではなく paced な background 永続化と分析。
- Game [paper] (Fig. 7, §5.3): 全スレッド数で all-ESSD 比 ±5% 以内、4–16 スレッドでは
  +3–4%(2899 vs 2793、2913 vs 2820 RPS)。p99 は 16 スレッドで逆に低く(78.9ms vs
  90.8ms)、64 スレッドでやや高い(321ms vs 282ms、paced batching のトレードオフ)。
- Ablation [paper] (Fig. 8, §5.4, Sysbench 50GB):
  - BPE admission (Fig. 8a): ghost two-chance(本方式)36422 TPS で full-admit 比
    +12%、ヒット率 72.7% vs 63.4%(full-admit)vs 15.1%(one-hit discard、2945 TPS)。
    BPE IOPS は 22369 → 2082(約 91% 減)。
  - 一時テーブル除外 (Fig. 8b): 除外なしでは分析系バーストがリモートに漏れて帯域
    スパイクと高い時間変動。除外ありで一時ページは BPE 内に留まりピーク帯域低下。
  - DDL/BLOB バイパス (Fig. 8c): バイパスなしでは DDL フェーズごとに深い TPS 低下、
    バイパスありでほぼ定常 TPS を維持。
- Backup/recovery [paper] (Table 2, §5.5, 50GB): snapshot 作成 0.64s(ESSD-only
  0.52s、OSS-only 53.73s)。バックアップ所要 51.22s(49.58 / 53.73)。リカバリ
  52.26s(ESSD-only 1.15s、OSS-only 57.64s)。リカバリ時間はデータの大半が OSS に
  あるためリモート帯域律速で、階層追加による追加遅延はないと主張。
- [inference] 評価がカバーしていないもの:
  - 動機部 (§1, §2.2) の対立軸である block/FS レベル tiering(dm-cache 等)や
    ILM/HSM との直接比較実験がない。ベースラインは all-ESSD と OSS-only のみで、
    「engine-integrated が外部 tiering に勝つ」という中心主張は ablation(エンジン
    信号の有無)による間接的な裏付けに留まる。
  - マルチテナント公平性(per-table quota、IOPS 制御)は目標 (§2.3) かつ結論の
    主張 (§7) だが、テナント混在・quota 発動下の公平性実験は本文にない。
  - リモート write amplification の直接測定がない(2MB フルオブジェクト PUT の
    バイト増幅は §5.2 の CP と write-only 曲線から間接的に推測できるのみ)。
  - backup/recovery の測定は 50GB のみで、5TB 構成での snapshot/リカバリ時間は
    未報告。バックアップ中クラッシュ等の故障注入実験もない。
  - TPC-C 系のマルチステートメントトランザクションベンチがなく、Sysbench/YCSB/
    Voter/Game のみ。BPE warmup(failover 後のコールドキャッシュ)も、他手法の
    限界として指摘 (§2.2) しながら自システムでは測っていない。
  - CP の分母となるコストモデルの詳細(ESSD の IOPS 課金、OSS のリクエスト課金を
    含むか)は本文に明示がない。

## Limitations
- Stated [paper]:
  - 低スキュー + 小キャッシュのレジームは意図的に不利な設定であり、機能はするが
    CP は控えめ(BPE が再利用ページを確保する前に OSS Buffer がリモート書き込みを
    償却できない)(§5.2)。
  - 高並行時に tail が広がる(Voter p99 で all-ESSD 比 ~1.5×)。原因はリモート永続化の
    分散で、foreground stall ではないと位置づけ (§5.3, Fig. 7)。
  - バックアップ開始時はグローバル OSS ロックで並行 DDL と OSS 書き込みを
    ブロックする(write stall は数秒と主張)(§4.3.1, §4.3.3)。
  - スコープはストレージエンジンと OLTP に限定。クエリセマンティクスは使わない
    (§2.3)。
- Inferred [inference]:
  - リカバリ(バックアップからの復元)は 50GB で 52.26s と、all-ESSD の 1.15s に
    対し OSS-only(57.64s)側に張り付く (Table 2)。論文は「OSS 水準を維持しつつ
    コスト削減」と肯定的に書くが、tiering によって復元 RTO は fast-tier 水準には
    ならないことを意味し、データ量に対しリモート帯域でスケールするはず。
  - 制御点(InnoDB の eviction/flush、16KB ページ、2MB アライン)がエンジン固有で、
    ページベース buffer manager を持たないエンジン(LSM 系等)への一般化は自明で
    ない。論文自身、LSM 系は related work で別系統として扱う (§6)。
  - 2MB フルオブジェクト PUT 方式では、コールドブロック内の単一ホットページの
    反復更新が read-modify-write(現行オブジェクト取得 + マージ + フル PUT)を
    誘発する (§4.2.4 Stage 2)。temporal deferral で緩和されるが、スキューが極端な
    場合の増幅は定量化されていない。
  - 「production 展開済み」「multi-tenant scale での持続的安定性」(§1) の根拠として
    提示されるのは制御されたベンチマーク実験(+ 本番由来の Game トレース)であり、
    フリート規模の運用テレメトリは本文に含まれない。
  - BPE は揮発なので、ノード再配置・failover のたびにローカル SSD キャッシュは
    失われ、warmup は buffer pool eviction 経由でしか進まない(admission が eviction
    パス限定 (§3.1) のため、意図的なプリロード経路がない)。

## Relations
- 先行世代: CloudJump I(VLDB 2022, I/O パス再構築)と CloudJump II(SIGMOD
  Companion 2025, MVD による共有ストレージ多版化)の直系続編 (§1, §6 refs [19, 20])。
- [[2025-tpctc-gao-distash.md]](DiStash: FoundationDB 多階層 KV): 「階層配置を
  ストレージ外部でなく DB 側の知識で決める」という問題設定が共通。本論文はページ
  ベース buffer manager の eviction/flush を制御点にする RDBMS 側 (§1, §2.3)、
  DiStash は KV ストア側で、レイヤ差の比較軸は abstract-only 時の見立て通り成立。
- [[2026-pvldb-kuschewski-btrlog.md]](BtrLog: クラウド WAL): CloudJump III は
  「配置は WAL/LSN と直交、ただし耐久性はデータが耐久層に達するまで WAL が担い、
  到達後に trim」という分担 (§3) を取る。WAL サービス側の設計と、tiering 側からの
  WAL 依存の切り方(trim 条件)は相互に制約し合う関係で、クラウド OLTP の
  ログ/データ分離設計として突き合わせる価値がある。
- [[2026-pvldb-zhang-terark-ds.md]](Terark-DS: 分離ストレージ上の KV 分離):
  compute-storage 分離下でオブジェクトストレージを最終永続層に使う構成の隣接研究。
  本論文の 2MB 版付きオブジェクト + ESSD ステージング (§3.1, §4.2) は、分離環境で
  小書き込みをオブジェクト層から遮蔽する設計パターンとして比較できる。
- [[2026-sigmod-saenz-hyperscale-storage.md]](Azure Hyperscale storage): 本論文は
  Socrates / Azure SQL Hyperscale の remote page server + キャッシング構成を
  related work として明示引用する (§6)。ローカル SSD をエンジン統合の揮発
  キャッシュ(BPE)にする点は Hyperscale 系のローカルキャッシュ層と同型で、
  「キャッシュ admission をエンジン信号で絞る」部分が本論文の差分。
- [[2026-icdew-park-hotpage-checkpointing.md]](hotpage checkpointing): [inference]
  どちらも「dirty ページの flush をいつ・どこへ行うか」を制御点として扱う。本論文は
  flush 先の階層ルーティング (§3.3)、Park はチェックポイント時のホットページ扱いが
  主題で、flush ポリシー設計という共通軸で接続(詳細は各ノート参照)。
- [[2026-pvldb-lee-how-to-write-to-ssds.md]](How to Write to SSDs): [inference]
  BPE の CLOCK による SSD 順次書き込み・wear 削減 (§4.1.3) と Clean-Write による
  SSD WA 削減 (§4.1.2) は、SSD への書き方(WA/out-of-place)の一般論と接続する
  具体例。

## Idea seeds
- [inference] 「engine-aware tiering は block/FS tiering に勝つ」という中心主張が
  直接対決なしで残っている (§5 のベースラインは all-ESSD / OSS-only のみ)。
  オープンソース MySQL/InnoDB + dm-cache/bcache の2層構成と、buffer-pool 統計を
  使う簡易 engine-aware 配置を同一ワークロード(YCSB スキュー掃引)で比較すれば、
  「DB セマンティクスの可視性が配置品質に効く度合い」を初めて定量化できる。
  abstract-only 時の再現実験案は本文読了後も有効どころか、論文が残した空白そのもの。
- [question] バックアップ開始のグローバル OSS ロック (§4.3.1) は、OSS Buffer の
  clean ブロック枯渇時に flush が同期化する (§4.2.4) 状況と重なると、数秒では
  済まない foreground stall を生まないか。write-only 高負荷 + キャッシュ圧迫下で
  snapshot を開始する敵対的実験が設計の頑健性を切り分ける。
- [inference] CP(ストレージコストあたりスループット)を第一級の評価軸にした点は
  再利用価値が高い (§5.2, Fig. 6)。コストモデル(容量 + IOPS + リクエスト課金)を
  明示的に固定した「tiered-DB 向け CP ベンチマーク仕様」を定義し、DiStash 系
  (KV)・本論文系(ページベース)を横並びにする調査は Phase 2 の課題候補になる。
- [question] 2MB 固定オブジェクト粒度はスキューに対して最適か。ホットページが
  疎に散る場合、フルオブジェクト PUT のリモート WA(論理 dirty バイト比)は
  どこまで悪化するか (§4.2.4)。粒度可変(512KB–8MB)やホット/コールドでの
  粒度分離を InnoDB 外の簡易シミュレータで掃引するのが最初の一歩。
- [inference] BPE admission(ghost two-chance)の ablation 差(+12% TPS、IOPS 91%
  減、ヒット率 72.7% vs 15.1%)(Fig. 8a) は、S3-FIFO 系 admission が DB バッファ
  階層でも大きく効く証拠。CXL/disaggregated memory 上の中間キャッシュ層
  ([[2026-pvldb-zhao-sidle.md]] や [[2026-eurosys-hombal-disagg-cache.md]] の文脈)へ
  同じ reuse-validated admission を移植したときの利得は未検証の空白に見える。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: full-text 格上げ(status: abstract-only → read。手動取得した PDF 全文を読解し全節を執筆)
