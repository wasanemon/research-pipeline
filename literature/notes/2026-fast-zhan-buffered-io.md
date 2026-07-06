---
title: "Rearchitecting Buffered I/O in the Era of High-Bandwidth SSDs"
authors: [Yekang Zhan, Tianze Wang, Zheng Peng, Haichuan Hu, Jiahao Wu, Xiangrui Yang, Qiang Cao, Hong Jiang, Jie Yao]
venue: "FAST '26 (24th USENIX Conference on File and Storage Technologies)"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/fast/ZhanWPHW000026"}
urls: {paper: "https://www.usenix.org/conference/fast26/presentation/zhan", pdf: "literature/pdfs/2026-fast-zhan-buffered-io.pdf", code: ""}
status: read
read_date: 2026-07-06
tags: [buffered-io, page-cache, ssd, file-systems, linux-kernel, write-buffering, partial-page-write, lock-contention, dirty-page-flushing, xfs]
---

## TL;DR
高帯域 NVMe SSD 時代には「全書き込みをページキャッシュ経由でバッファする」従来の
buffered I/O アーキテクチャ自体が書き込みボトルネック、という診断に基づき、書き込み
バッファリングをページキャッシュから分離する WSBuffer を提案。小さい/非整列な書き込み
だけを専用の scrap buffer(部分ページを header 付きで管理)に置き、大きく整列した部分は
SSD に直接書き、read-before-write は非同期の二段フラッシュ(OTflush)に追い出す。
ページキャッシュは read 専用(常に clean)に純化。XFS 上のカーネル実装で EXT4/F2FS/
BTRFS/XFS/ScaleCache に対しスループット最大 3.91×、レイテンシ最大 82.80× 改善。

## Problem & motivation
- [paper] buffered I/O の write は高帯域 SSD の性能を引き出せない。根本原因は3つ:
  C1 = 全書き込みを write critical path 上でページキャッシュにバッファする設計のコスト、
  C2 = ページ管理の並行性不足によるメモリ非効率、C3 = partial-page write の
  read-before-write ペナルティ (abstract, §1, §2.4)。
- [paper] PCIe 3.0 → 5.0 で SSD の write 帯域は 3GB/s 未満から 10GB/s 超に拡大し、
  メモリとの帯域差は1桁以内に縮小 (§2.1, §2.2)。
- [paper] 理想条件(メモリ無制限・flush 無効・2MB sequential write)ですら direct I/O が
  buffered I/O を全ケースで 1.10×–4.46× 上回る。8× PCIe4.0 SSD の RAID0(計約 55GB/s)
  対 8× DDR4 DRAM(計約 200GB/s)であり、メモリの帯域優位はページキャッシュ管理コスト
  (allocation / lookup / page-state / LRU)を相殺できない (§2.3.1, Fig. 1)。
- [paper] flush 有効・16 スレッド・4KB full-page write では、供給メモリが書き込みデータ量の
  70% のときスループットが 100% ケースより最大 54.0% 低下 = 高いメモリ依存性 (§2.3.2, Fig. 2)。
  主因は XArray の非スケーラブルな spinlock (xa_lock):free page 挿入・clean page 削除・
  page-state 更新が競合し、さらに flush はタグ遷移 dirty → writeback → clean のたびに
  ロック取得が必要。flusher を増やしても根本解決にならない (§2.3.2)。
- [paper] キャッシュミスした partial-page write は page fault → 低速な SSD-read で
  ページを埋めてから更新する。partial-page write のレイテンシは full-page write の
  1.51×–84.37×(4FS 比較、ほぼ全て SSD-read 起因)(§2.3.3, Fig. 3)。
- [paper] 既存解の二分類と限界: ①ページキャッシュ最適化(ScaleCache の ccXArray、
  StreamCache、uncached buffered I/O)は full-buffering 設計自体は変えないので効果に上限。
  ②部分/完全バイパス(BeeGFS のモード切替、Lustre AutoIO、OrchFS、SPDK)は buffered I/O
  の利点を捨て、プログラム修正・保守コストを課す (§2.4)。
- [paper] 設計目標: G1 = バッファする user-write の最小化、G2 = 途切れない dirty-data
  flushing、G3 = 効率的な partial-page write。POSIX の I/O インターフェースは変えず、
  アプリ修正も不要。既存ページキャッシュ最適化とは直交で統合可能 (§2.4)。

## System model & assumptions
- [paper] ハードウェア前提: 高帯域 NVMe SSD(複数台の RAID0 で帯域集約)。評価環境は
  8× PCIe4.0 Samsung 990 PRO(read 7GB/s / write 6.9GB/s)を mdRAID RAID0
  (stripe 512KB)で構成、計約 55GB/s (§4.1)。メモリと SSD の帯域差は1桁以内 (§2.2)。
- [paper] SSD の内部並列性前提: scrap-page の data-zone サイズは「チャネル数 × SSD-page
  サイズ」の整数倍にすべきで、評価 SSD(8 チャネル・16KB SSD-page)では 256KB がデフォルト
  (§3.2)。SSD-write サイズを常に data-zone サイズの倍数にすることで SSD 上の最小格納単位を
  data-zone 化し、file fragmentation を構造的に防ぐ (§3.3)。
- [paper] プラットフォーム依存パラメータ: request-size 閾値 1MB(これ以上は SSD 直書きが
  scrap buffer より速い、評価環境での実測に基づく)(§3.3)。SSD busy 判定の Bcount 閾値は
  4MB(4MB write で SSD 帯域がほぼ飽和)(§3.4)。scrap-page は 32 ページずつバッチ確保し
  「4KB header 領域 + 8MB data-zone 領域」のレイアウト (§3.2)。
- [paper] 一貫性の不変条件: scrap buffer 内のデータは常に最新。残りは SSD 上にあり、
  ページキャッシュは SSD データの一部を read 用にキャッシュするのみ。memory-page は
  常に clean で read 専用 = dirty な scrap-page と clean な memory-page を分離することで
  3ソース間の整合性を単純化 (§3.3)。
- [paper] 耐久性・クラッシュ一貫性: 従来ページキャッシュ同様、下層ファイルシステムの
  journaling 等に委譲(WSBuffer 自身は保証を追加しない)(§3.6)。fsync() は関連
  scrap-page のみ検索し(memory-page は見ない)、専用 fsync スレッドで OTflush 同様に
  flush。高帯域 SSD と OTflush により大半の scrap-page は既に flush 済みのことが多い (§3.6)。
- [paper] ストレージ割当: 新規 scrap-page の SSD 空間は delayed allocation。SSD-id=0 の
  ページは writeback 時に最も暇な SSD を選んで割当 (§3.4 Stage-2)。
- [paper] 実装前提: Linux kernel 6.8 の XFS 上に ~4500 LoC のカーネル FS モジュールとして
  実装。アーキテクチャは XFS 非依存で、scrap buffer 構造と concurrent page management は
  他 FS にも直接適用可能だが、data-access 機構と OTflush の統合は FS ごとの
  エンジニアリングを要する (§3.6)。
- [paper] リソース前提: OTflush はデフォルトで queue-thread ペア2組のみ(Stage-1/2 各1、
  公平比較のため)。サブキュー分割で並行 flush 可能だが CPU コストと引き換え (§3.4)。
- [inference] 暗黙の前提として、ワークロードは write() / read() システムコール経由
  (Algo. 1 は read/write 関数に実装、§3.6)。mmap 経由の書き込みの扱いは本文に記述が
  見当たらない。また RAID0 前提の評価であり、冗長性のある構成(RAID5 等の
  read-modify-write を伴う配列)での挙動は論じられていない。

## Approach
- [paper] **全体構成 (§3.1, Fig. 4)**: buffered I/O インターフェースの下に、write を
  scrap buffer + SSD 直書きで処理し、read はページキャッシュ(read 専用)+ scrap buffer で
  処理する。構成要素は ①scrap buffer (§3.2)、②buffer-minimized data access (§3.3)、
  ③OTflush (§3.4)、④concurrent page management (§3.5)。
- [paper] **scrap-page 構造 (§3.2)**: 常に「満杯」であるページキャッシュのページと異なり、
  部分的データを持てる。128B header に、有効バイト数 counter (4B)、data-segment 数 (1B)、
  対応 SSD を示す SSD-id (2B)、flush 状態 tag (1B)、および data-segment の
  (offset 4B, size 4B) を記録する index entry 群を持つ。評価では 95% 超のケースで
  使用 index entry 数は 15 未満。header と data-zone は分離配置(32 ページバッチ確保、
  4KB header 領域 + 8MB data-zone 領域)でフラグメンテーションと分散アクセスを回避。
- [paper] **scrap buffer write (§3.2, Fig. 5)**: write は offset に従い scrap-page 単位に
  分割され、read-before-write なしでそのまま部分書きし、既存の address-overlapping な
  data-segment と header 更新でマージ(merge-friendly 配置)。ページ状態が変われば
  (unfilled → full 等)tag を更新し、header アドレスを OTflush のキューに挿入して通知。
- [paper] **buffer-minimized data access (§3.3, Algo. 1)**: write は request-size 閾値
  (デフォルト 1MB)未満なら全て scrap buffer へ。以上なら partial-scrap-page 部分
  (scrap buffer へ)と data-zone 整列部分(SSD へ直接)に分割。整列粒度は memory-page
  (4KB)ではなく data-zone(256KB)。SSD-write 完了後、範囲が重なる既存 scrap-page /
  memory-page は obsolete としてバックグラウンドで回収(scrap-buffer write の範囲と重なる
  read キャッシュページも同様)。read はまず scrap buffer を検索し(常に最新)、
  不足分をページキャッシュ+page fault 経由の SSD read で読む = 成熟した read 最適化を
  そのまま享受 (Fig. 6)。
- [paper] **OTflush (§3.4, Algo. 2)**: 二段の opportunistic flush。**Stage-1** は
  unfilled scrap-page を SSD-read で非同期に充填(= read-before-write の critical path
  からの追い出し)。専用 ring queue (Queue-1) から取り出し、既に foreground write で
  full になっていれば破棄、対応 SSD が busy なら末尾に再挿入して後回し。**Stage-2** は
  full scrap-page の writeback (Queue-2)。obsolete で無効なら破棄、未割当 (SSD-id=0)
  なら最も暇な SSD に delayed allocation して書き戻し、busy なら再挿入。writeback 完了後は
  即座にページ回収してメモリ使用を削減。SSD busyness は per-SSD の未完了書き込みバイト数
  Bcount(submit_bio 前に加算、bi_end_io で減算)を閾値 4MB と比較する粗粒度・低コストな
  帯域認識で判定。scrap-page 間に依存が無いのでキュー分割による並行 flush も可能。
- [paper] **concurrent page management (§3.5, Fig. 7)**: memory-page は read 専用に
  なったため、XArray は page state 維持が不要になり置換管理のみ(page-fault 起因の
  tree 更新は当該スレッドしか妨げない)。scrap-page は SXArray(XArray の軽微な改変)で
  管理: 挿入は通常通り、削除は index-entry レベルの軽量ロックで NULL 化のみ行い、
  tree 構造更新(カスケード削除等)はファイルが暇か close 時に遅延実行(opportunistic)。
  page state は per-scrap-page ロックで管理し、scrap buffer write と OTflush Stage-1 は
  SXArray ロック不要。Stage-2 も flush 後の index entry 修正に entry レベルロックのみ。
  挿入には依然 xa_lock が要るが、scrap-page は粒度が大きく数が少ないため競合は小さく、
  flush とのロック競合はゼロ。ccXArray 等の既存 XArray 最適化とも併用可能。

## Evaluation
- Setup [paper]: 2× Intel Xeon Gold 6348 (2.60GHz, 28 CPU)、256GB DDR4、8× PCIe4.0
  Samsung 990 PRO の mdRAID RAID0 (stripe 512KB)。Ubuntu 22.04 / kernel 6.8
  (ScaleCache のみ kernel 5.4 実装)。ベースライン: EXT4 / F2FS / BTRFS / XFS /
  ScaleCache-XFS、および AutoIO 原理をユーザ空間で XFS 上に再実装した XFS-AutoIO。
  StreamCache は非公開のため除外。スレッドを core に pin、周波数スケーリング無効、
  各実行前にカーネルキャッシュをクリア、5回以上の平均 (§4.1)。
- [paper] full-page write(1スレッド・flush 無効・十分なメモリ): ベースライン比
  1.03×–3.29×。<1MB は scrap buffer で全バッファ(1.03×–2.84×、バッチ確保・レイアウト・
  大粒度管理が効く)、≥1MB は全て SSD 直書き (1.14×–3.29×) (§4.2, Fig. 8a)。
- [paper] partial-page write: 1.70×–82.80×。<1MB では read-before-write 除去により
  2.11×–82.80×。1MB/2MB/4MB write ではそれぞれデータの 32.4%/82.3%/91.1% が SSD 直書きで
  1.70×–4.06× (§4.2, Fig. 8b)。
- [paper] direct I/O・hybrid I/O 比較: XFS-direct I/O(RMW 実行)と XFS-AutoIO
  (閾値 1MB)に対し 1.59×–231.28×。direct I/O は全ケースで遅い RMW、AutoIO は小書きで
  partial-page write・大書きで RMW に苦しむ (§4.2, Fig. 9)。
- [paper] マルチスレッド: FIO random write (bsrange=4k–4m) で 1.21×–3.91×。ピークは
  総 SSD 帯域 (~55GB/s) と、非整列ユーザバッファから submit_bio() 用の整列カーネル
  メモリへの不可避なメモリコピーで制約される (§4.2, Fig. 10a)。
- [paper] read-only ワークロードでは WSBuffer と XFS はほぼ同一性能(read パスは
  ページキャッシュのまま)(§4.2)。
- [paper] Filebench(十分メモリ・flush 無効): Fileserver (R/W=1:2) 1.23×–2.51×、
  Webproxy (R/W=5:1) は XFS にわずかに劣り他には 1.08×–1.65×(flush 無効で scrap-page が
  溜まり SXArray → XArray の二重検索・二重 tree 更新が発生。OTflush 有効化で緩和)、
  Varmail は 1.06×–2.84×(fsync が時間の 60% 超を占め、大粒度 scrap-page による高速な
  page locating / bio assembly / flush が効く)(§4.3.1, Fig. 11, Table 1)。
- [paper] メモリ制限下(flush 有効、OTflush スレッドは2つのみ): Fileserver 1.23×–4.48×、
  Webproxy 1.07×–4.37×。Webproxy では write 用メモリの節約分が read キャッシュに回ることが
  10–20% メモリ供給時に特に効く。ScaleCache-XFS は厳しいメモリ制限下では実行不能
  (§4.3.2, Fig. 12)。
- [paper] 実アプリ: LevelDB+YCSB(SSTable 64MB、1KB レコード、1M/3M/5M ops、RunA/RunF、
  flush 無効・十分メモリ)で 1.32×–2.02×。小アクセスは scrap buffer が吸収し、少数の大きな
  compaction write は SSD 直書き (§4.4, Fig. 13)。GridGraph PageRank
  (LiveJournal/Twitter/Friendster、20 iter)で 1.09×–4.37×。read も SSD 上の大きく整列した
  write パターンの間接効果で改善 (§4.4, Fig. 14, Table 2)。Nek5000(CFD、1,000 timestep
  ≈130分、~585GB 書き込み、256GB 全メモリ供給・flush 有効)で 1.74×–3.09×。
  ScaleCache-XFS が2位だが C1(全書き込みバッファ)が上限を規定 (§4.4, Fig. 15)。
- [paper] CPU 使用率: XFS/ScaleCache-XFS 比 3.2%–28.4% 低い。書き込みデータの 80% 超が
  SSD 直行で DMA 転送になるため。追加オーバーヘッド(header・キュー維持)は小さい
  (§4.5, Table 3)。
- [paper] メモリ消費: 閾値 1MB のとき partial-page write でメモリに書かれるデータは
  1MB=67.6% / 2MB=17.7% / 4MB=8.9%(ベースラインは常に 100%)(§4.6, Table 4)。実アプリでは
  write メモリ消費 0.34%–1.67%(graph/HPC)。小書きも後続の大きな上書きで obsolete 化され
  回収されるため (§4.6, Table 5)。KV store は全 foreground write がメモリバッファされる
  (小アクセスのため)(§4.6)。
- [paper] 感度: RAID stripe サイズに非依存。SSD 台数 4→8 でスループットが伸びる
  (XFS は伸びない)(§4.7, Fig. 16)。
- [inference] 評価がカバーしないもの: (1) マイクロベンチ・Filebench(十分メモリ)・
  KV/graph 実験は page flushing 無効で実施されており(§4.2, §4.3.1, §4.4)、flush 有効の
  総合評価は Filebench 2種と Nek5000 に限られる。(2) fsync レイテンシ自体の
  マイクロベンチマークは無い(Varmail の集約 OPS のみ)。(3) 単一 SSD での評価が無い
  (感度分析も 4–8 台)。閾値 1MB / 4MB は 8-SSD RAID0 での実測に基づくため、構成が
  変われば再チューニングが要る。(4) クラッシュ後の一貫性・回復の実験は無い(委譲の主張のみ、
  §3.6)。(5) DBMS 系は LevelDB のみで、fsync/WAL 頻度の高い RDBMS 的ワークロードは無い。

## Limitations
- Stated [paper]:
  - flush 無効時に scrap-page が滞留すると SXArray + XArray の二重インデックス検索・
    二重 tree 更新が発生し、read-heavy Webproxy では XFS にわずかに劣る (§4.3.1)。
  - ピークスループットは総 SSD 帯域と、ユーザバッファ→整列カーネルメモリのコピーで
    制約される (§4.2)。
  - data-access 機構と OTflush の他 FS への移植は FS 固有のデータ構造・処理ロジックへの
    慎重な統合エンジニアリングを要する (§3.6)。
  - buffered I/O 性能が最良の XFS でこの改善幅であり、逆に言えば効果は下層 FS に依存する
    (低性能な FS ほど利得が大きい)(§3.6)。
  - SXArray の遅延 tree 更新は tree 構造を一時的に肥大させ得る(scrap-page 数が少ないので
    許容、削除済みノードは再利用)(§3.5)。
- Inferred [inference]:
  - SSD 上の最小格納単位を 256KB data-zone にする設計 (§3.3) は、小ファイル多数の
    ワークロードでの内部フラグメンテーション(空間増幅)を生み得るが、空間効率の評価は
    本文に見当たらない。
  - 「SSD 直書き部分は write() 復帰時点で SSD 到達、scrap buffer 部分は揮発」という
    非対称な永続化タイミングになるはずだが、クラッシュ時に見える状態(直書き部分だけ
    残る等)と FS ジャーナルの整合の議論が無い。delayed allocation とも絡む点で、
    crash-consistency のテスト(dm-log-writes 的なもの)が欲しい。
  - Bcount による busyness 判定は自己申告の書き込みバイト数のみで、GC 等 SSD 内部起因の
    遅延は捉えない(著者らも粗粒度と明言、§3.4)。テールレイテンシの評価が無いため、
    busy 誤判定時の Queue 内 head-of-line 的な遅延の影響は不明。
  - ScaleCache が kernel 5.4 上という比較条件の非対称性は著者も注記しているが (§4.1)、
    ScaleCache との差のどこまでがカーネル世代差かは切り分けられていない。

## Relations
- 競合(本文中のベースライン/比較対象): ScaleCache (ccXArray)、StreamCache、
  uncached buffered I/O、Lustre AutoIO、OrchFS、SPDK (§2.4, §4.1)。
- [[2026-pvldb-lee-how-to-write-to-ssds.md]]: 相補的。あちらは DBMS 層から out-of-place
  書き込みで DB WAF × SSD WAF を最小化、こちらはカーネル buffered I/O 層で「大きく整列した
  SSD write の強制」によりフラグメンテーション起因の劣化を防ぐ (§3.3)。
  [inference] WSBuffer の 256KB 整列直書きが SSD 内部 WAF に与える効果は本文で測られて
  おらず、両者の観点を組み合わせる余地がある。
- [[2026-pvldb-liu-arcekv.md]]: [inference] 弱い関連。WSBuffer の LevelDB 評価 (§4.4) は
  「小さな foreground write は scrap buffer、大きな compaction write は SSD 直行」という
  分担を示しており、LSM compaction の I/O パターンがカーネル側最適化とよく噛み合う例。
  compaction スケジューリング(ArceKV)とカーネル側 flush スケジューリング(OTflush)の
  相互作用は未検討領域。

## Idea seeds
- [inference] WSBuffer は「buffered I/O のまま DBMS を速くする」路線で、O_DIRECT +
  自前バッファプール路線(多くの DBMS)への反例になり得る。検証: fsync/WAL 頻度が高い
  RDBMS 的ワークロード(例: SQLite/PostgreSQL 相当の fio 再現)で WSBuffer vs XFS vs
  O_DIRECT の fsync レイテンシ分布と WA を測る。§3.6 の fsync 設計(scrap-page のみ検索)が
  WAL の小さな追記 + fsync 連打でどう振る舞うかが焦点。
- [question] scrap buffer 部分(揮発)と SSD 直書き部分(即永続)の混在するクラッシュ状態は、
  アプリから見て従来ページキャッシュの「prefix でない部分永続化」と同型か? crash-consistency
  テスティング(FS ジャーナル + delayed allocation + 直書きの組合せ)は本文に無く (§3.6)、
  Pisco 的な「違反ケースの縮約」を FS 層に持ち込む余地がある。
- [inference] 「dirty ページを read キャッシュから構造的に分離し、状態管理ロックを消す」
  という §3.5 の発想は、DBMS バッファプール(dirty flag + latch + flush list)にもそのまま
  輸入できる可能性がある。検証: LeanStore 系バッファプールで clean/dirty をプール分離し、
  flush list ロックの競合プロファイルを before/after 比較する小実験。

## Changelog
- 2026-07-06: created (status: read, USENIX 公開 PDF の抽出テキスト全 18 ページを読解)
- 2026-07-06: 検証パスによる修正(Fig. 1 の DRAM 構成表記を原文どおり「8× DDR4 DRAM」に修正。「8ch」はチャネル数の解釈であり原文に無い)
