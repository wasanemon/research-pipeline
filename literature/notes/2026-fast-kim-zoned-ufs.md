---
title: "Unleashing Zoned UFS: Cross-Layer Optimizations for Next-Generation Mobile Storage"
authors: [Jungae Kim, Jaegeuk Kim, Kyu-Jin Cho, Sungjin Park, Jinwoo Kim, Jieun Kim, Iksung Oh, Chul Lee, Bart Van Assche, Daeho Jeong, Konstantin Vyshetsky, Jin-Soo Kim]
venue: "FAST '26 (24th USENIX Conference on File and Storage Technologies)"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/fast/KimKCPKKOLAJVK26"}
urls: {paper: "https://www.usenix.org/conference/fast26/presentation/kim-jungae", pdf: "literature/pdfs/2026-fast-kim-zoned-ufs.pdf", code: ""}
status: read
read_date: 2026-07-06
tags: [zoned-storage, ufs, mobile-storage, ftl, l2p-mapping, f2fs, log-structured, garbage-collection, write-buffer, write-ordering, io-scheduling, fragmentation, flash, write-amplification]
---

## TL;DR
モバイルストレージ標準 UFS の L2P マッピングは SRAM 予算(~1MB)に収まらず、
map cache miss と device GC が性能を不安定化する。JEDEC 標準化された Zoned UFS
(ZUFS) はゾーン単位マッピングでこれを解消するが、商用スマートフォンへの実配備には
①複数 open zone での SRAM 書き込みバッファ管理、②電源管理(clock gating)下での
end-to-end 書き込み順序保証、③巨大ゾーンが誘発する F2FS GC 負荷、の3課題がある。
本論文は device firmware / SCSI・UFS ドライバ / block layer / F2FS / Android
framework を跨ぐ最適化(ZABM 動的バッファ管理、順序保証修正、proactive GC)で
これを解き、Pixel 10 Pro に商用搭載。断片化下で CUFS 比 2 倍超の書き込み
スループットとゲームロード 14% 短縮を示す。SK hynix + Google + SNU の産学連携。

## Problem & motivation
- [paper] page-level L2P マッピングはエントリ 4B 以上で全容量の ~0.1%、1TB デバイス
  なら約 1GB 必要 (§2.2, Fig. 2)。一方 UFS コントローラの SRAM は数 MB で、L2P 用
  SRAM は 2017 年以降 1MB 前後で停滞、容量は 32GB→1TB へ指数的に成長 (§2.1–2.2, Fig. 1)。
- [paper] このため UFS は 2 段階マップ + map cache(計約 1MB)で運用され、random I/O
  でアクセスパターンがキャッシュ容量を超えると NAND からのマップ読みが頻発する
  (§2.2)。圧縮マッピング(4MB 連続域を L1 エントリで直接指す)は論理-物理連続性が
  前提で、random write による断片化で階層マップへフォールバックする (§2.2)。
- [paper] 実機調査: 前世代フラッグシップ(128GB UFS、発売約 1 年)1 万台の統計を収集。
  利用率は 3–86%(平均 ~32%)、約半数は 27%(35GB)未満 (§3.1)。fragmentation level
  = dirty segments / (dirty + free segments) と定義すると、約 30% のデバイスが 0.7 超の
  深刻な断片化 (§3.1, Fig. 4a)。利用率との相関は r≈0.74 だが低利用率でも高断片化の
  デバイスが存在(容量圧迫の副産物ではなく本質的課題)(Fig. 4b)。
- [paper] 断片化の性能影響(block layer で /sys/block/<dev>/stat から測定): read は
  平均 66ms/MB・最悪 344ms/MB で、fragmentation level 0.4 超から分散が急増。write は
  平均 175ms/MB・p99 678ms/MB・最悪約 2s/MB で、0.8 超から急劣化 (§3.1, Fig. 4c, 4d)。
- [paper] ZUFS(2023 年 11 月 JEDEC 批准、UFS 3.1/4.0 + ZBC 拡張)はゾーン 1 個に
  つき 1 エントリのマッピングで表サイズを数桁削減し、SRAM に全載せして map cache
  miss を排除。ゾーンサイズを NAND erase block(の倍数)に揃えれば device-level GC が
  不要になり WAF が下がる(GC 責務はホストへ移る)(§2.3)。
- [paper] しかし実配備には 3 つの新課題がある (§1, §3):
  1. **Write buffer thrashing**: ZUFS 仕様は最低 6 open zones を要求し、F2FS も hotness
     分離のためデフォルト 6 open zones を使う。本デバイスで superpage(ゾーン内の
     全 die×plane を跨ぐプログラム単位)1 個のプログラムに 768KB のバッファが必要で、
     6 ゾーン分 4,608KB + conventional LU 用 1 本 = 7×768KB は SRAM に載らない (§3.2)。
  2. **書き込み順序違反**: モバイル UFS はアイドル時にクロックを止める clock gating を
     多用し、gated 中に到着した要求は requeue されて dispatch 順序が変わり得る。zoned
     の厳格な逐次性と根本的にミスマッチ (§3.3)。
  3. **巨大ゾーンの GC 負荷**: F2FS の section をゾーンに揃えると、victim section の
     valid データ移動量が増え、割当可能 section 数も減るため foreground GC が頻発する
     (§3.4)。
- [paper] 先行の ZMS はホスト側 IOTailor 層で superpage 整形するが、JEDEC ZUFS
  インターフェースが公開しないデバイスジオメトリ情報を要し、ホスト CPU/DRAM
  オーバーヘッドとキュー遅延を加え、Android のファイル別暗号化がファイル横断
  マージを阻む。ZMS の budget-based IPU は overwrite を禁じる JEDEC ZUFS 仕様に
  違反する (§2.5)。ホストに FTL を移す Yan et al. と対照的に、本論文は FTL を
  デバイス内に保ったまま UFS 級制約でゾーンマッピングを実用化する方針 (§2.5)。

## System model & assumptions
- [paper] ハードウェア: TLC NAND 複数 die、各 die 4 plane、ページ 16KB。ゾーンは
  die・plane を跨いでブロックを論理集約し、実効ゾーンサイズ 1,056MB(物理
  superblock 粒度に整合、逐次 I/O でデバイス並列性をフル活用)(§4.1, Fig. 5)。
- [paper] コントローラ SRAM の主用途: write buffer、Zone Mapping Table (ZMT)、
  Zone Mapping Log (ZML)、その他メタデータ (§4.1)。
- [paper] ホストスタック: Android framework(vold / fsmgr。unclean shutdown 後の
  fsck が open zone の write pointer 補正を含む)→ F2FS → block layer(mq-deadline、
  Zone Write Locking で 1 ゾーンにつき in-flight write 1 本)→ SCSI/UFS ドライバ →
  ZUFS デバイス (§2.4, Fig. 3)。公式サポートは Android 16 + Android Generic Kernel
  6.6/6.12 (§2.4 脚注 1)。
- [paper] F2FS は 2 種の LU を使う: random 更新が要るメタデータ領域は conventional
  LU、ユーザデータと逐次書きメタデータは zoned LU (§2.4)。zoned デバイスでは
  overwrite 禁止のため In-Place Update (IPU) は使えず、F2FS は厳格な LFS モードで
  動作する (§2.4)。
- [paper] ゾーン状態は EMPTY / OPEN / CLOSED / FULL。電源サイクルで OPEN は暗黙に
  CLOSED になり、次の write で OPEN に復帰。OPEN/CLOSED を合わせて open zones と
  数え、標準は最低 6 個の同時 open を要求 (§2.3)。
- [paper] ZMT エントリは 8B(開始物理アドレス 4B + ゾーン内 valid データ長 4B)。
  長さフィールドは 4KB 粒度でホスト可視の write pointer に対応し、バッファ内の
  未プログラムデータへの read 応答と、sudden power-off 時の回復情報を提供する。
  1TB ZUFS の ZMT は 8KB(CUFS の page-level なら約 1GB)で SRAM 全載せ可能 (§4.1)。
- [paper] ZMT は直接更新せず、ZML に変更をステージしてバッチで checkpoint。read
  reclaim や wear-leveling によるゾーン再マッピング中は ZML が移行先の情報を持ち、
  victim ゾーンの ZMT エントリを保持したまま read を継続提供する (§4.1)。
- [inference] 対象はあくまで「FTL をデバイス内に残す」ZUFS で、ホスト管理 FTL
  (Yan et al.)や ZNS SSD の GB 級 DRAM 前提とは資源モデルが異なる (§2.5 の対比
  に基づく整理)。conventional LU(メタデータ用、random 更新可)側は依然 page-level
  マッピングを要するはずだが、その SRAM コストの定量は本文に無い。

## Approach
- [paper] **ZABM: Zone-Aware Buffer Management (§4.2, Fig. 6)**
  - 素朴に open zone 数より少ない固定バッファにすると premature なバッファ切替で
    unaligned flush が多発。SLC バッファで凌ぐ案は SLC 域への page-level マッピング
    追加と SLC→TLC 移行で WAF が悪化し、ZUFS の利点を打ち消す (§4.2)。
  - Scatter-Gather Buffer Manager (SGBM) という専用ハードウェアモジュールが、予約
    SRAM を 4KB スロットに分割して割当を追跡。ゾーン open 時に per-zone slot table を
    内部メモリに確保し、write 到着でデータを空きスロットに格納、スロット番号を
    テーブルに追記(ゾーン内は厳格逐次なので線形記録で足りる)(§4.2, Fig. 6)。
  - 単一 die の 1 ページ分が溜まり次第即 flush してスロットを解放。全 die 分が揃えば
    superpage 並列 flush で並列性をフル活用 (§4.2, Fig. 6)。
  - 各 open zone に最小フットプリントを保証しつつ、書き込みの重いゾーンへ動的に
    スロットを追加割当。superpage 境界とバッファ割当をデカップルすることで
    unaligned flush と WAF を抑え、SRAM を効率利用 (§4.2)。
  - ハードウェアコストはコントローラチップ面積の約 0.4% (§4.2)。ホスト側 IOTailor に
    頼る ZMS と違い、複雑さを UFS コントローラ内に閉じ込める (§4.2)。
- [paper] **End-to-end 書き込み順序保証 (§4.3)**
  - ベースライン Linux UFS スタックでは clock gated 中の I/O は一時 reject され SCSI
    mid-layer で requeue され、順序が崩れ得る。これを synchronous ungating に置換:
    新 I/O 到着時、ドライバはクロック完全復帰を待ってから dispatch し、ファイル
    システムの発行順を厳守する (§4.3)。
  - mq-deadline のコーナーケース 3 件を修正: ①requeue 後に next_rq ポインタが stale に
    なり別要求を dispatch する問題、②FUA フラグ付き要求が ordering path を迂回して
    zoned write と再順序化する問題、③ionice / blk-ioprio cgroup による I/O 優先度が
    zoned write を誤順序で submit し unaligned write エラーを起こす問題(優先度駆動の
    並べ替えと逐次制約の意味論的ミスマッチ)(§4.3)。修正は upstream 済み (§4.3)。
- [paper] **Proactive GC (§4.4, Table 1)**
  - F2FS background GC を 3 フェーズ化する kernel knob 群を追加(/sys/fs/f2fs/<dev>/
    経由、Android framework 変更不要): free section 比率 > gc_no_zoned_gc_percent
    (60%) で No-GC(background GC 停止)、下回ると Normal-GC(valid block 比率 <
    gc_valid_thresh_ratio (95%) の victim を選び、1 ラウンドに
    migration_window_granularity (3) セグメントを走査、cost-benefit アルゴリズム)、
    gc_boost_zoned_gc_percent (25%) を切ると Boosted-GC(窓を
    gc_boost_gc_multiple (5) 倍に拡大し greedy アルゴリズムで回収加速)(§4.4, Table 1)。
  - OP 空間の細粒度化: CUFS 時代の reserved_sections(section 粒度、ZUFS では 1
    section が 1GB 級で粗すぎる)に代え、segment 粒度の reserved_segments knob を
    導入(デフォルト 6336 = 6 open zones 収容に要する segment 数の 2 倍)(§4.4, Table 1)。
  - ZUFS では device-level GC が不要になるため、CUFS がデバイス内に確保していた OP
    空間を F2FS 側の GC 用 OP として開放 (§4.4)。
  - user read 到着時は background GC を即座に一時停止し read を常に優先 (§4.4–§5, p.11)。
    knob とポリシー変更は zoned デバイス向けに upstream Linux kernel へ取込済み (p.11)。

## Evaluation
- Setup [paper]: Google Pixel 10 Pro(12GB LPDDR5X、512GB ZUFS)。CUFS ベースラインは
  同一デバイスの conventional LU を全ボリュームに割り当てて構成(ストレージモード
  以外は同一ハードウェア)。Android 16 + カーネル 6.6、両者とも F2FS(ZUFS は純 LFS
  モード)(§5.1)。fio: 逐次 = 1 スレッド 512KB、random = 4 スレッド 4KB、4GB テスト
  ファイル。write は buffered + 末尾 fsync、read は libaio QD64 + direct I/O (§5.2)。
- クリーンデバイスでは ZUFS ≈ CUFS(seq/rand の read/write とも。断片化が無く GC も
  走らないため両者とも NAND 生帯域を出せる)(§5.2, Fig. 7a)。
- Map cache miss の影響 (§5.3): random read のアクセス範囲を 4GB→256GB に拡大すると、
  CUFS は page-level マップが SRAM に収まらず NAND からのマップ再読込で劣化、ZUFS は
  ZMT が SRAM 全載せのため全範囲で安定(4GB では CUFS が僅かに上回るが測定ノイズと
  説明)(Fig. 7b)。256GB ファイル上のブロックサイズ掃引では 128KB 未満で ZUFS が
  一貫して優位、128KB 超でマップ操作の相対コストが下がり差が縮小 (Fig. 7c)。
- ZABM vs ZMS (§5.4, Fig. 8): ZMS はソース非公開のため、IOTailor + バッファ方式を
  「バッファサイズ整列の固定長 write を直接発行」で模擬。chunk(flush 単位)768KB =
  ZMS 流の full superpage、192KB = 単一 die のプログラム単位。ZUFS(192KB)は
  ZMS(768KB)比 26% 高スループット(768KB 蓄積待ちの stall が無く、die 単位 flush で
  ホスト書き込みと NAND プログラムをパイプライン化)。ZUFS は 768KB chunk でも
  ZMS を上回る(SGBM が重負荷ゾーンへ動的にスロット追加)。ZUFS 内では 192KB と
  768KB の差はごく僅か = die 単位 flush に性能ペナルティ無し (§5.4, Fig. 8)。
- 断片化耐性 (§5.5): 128KB ファイル 32,768 個作成 → 1 つおきに削除 → 1GB テスト
  ファイルの書き/読みを測る、を空き 1GB 未満まで反復。CUFS は約 90 反復目で free
  segment が枯渇して foreground GC(ユーザスレッド文脈で実行)が発火し、write が
  ~100MB/s 近くまで急落、read も約 35% 低下 (Fig. 9a, 9b, Fig. 10a)。ZUFS は 40・80
  反復目付近に write の落ち込みはあるが常に 200MB/s 超を維持し、read は全反復で安定
  (Fig. 9c, 9d)。Fig. 10b では No-GC → Normal-GC(~40 反復目)→ Boosted-GC の遷移が
  観察され、Normal-GC で fragmentation 増加が鈍化、Boosted-GC で顕著に減少 (§5.5)。
  著者ら自身「background GC のオーバーヘッドは非無視だが、proactive な回収で
  コストを償却し write スループットの下限を CUFS より高く保つ」(§5.5, p.13)。
- アプリレベル (§5.6):
  - Genshin Impact(約 40GB のリソース検証 + ロード): 2 段階のエージング(1GB
    ファイルで容量半分まで充填し 1 つおき削除 → 64MB×16 ファイルに 4KiB random
    overwrite 各 ~12MB、空き 40GB 未満まで)後、ZUFS 30 秒 vs CUFS 35 秒(14% 短縮)
    (§5.6.1)。原因は read 要求サイズ分布: CUFS は F2FS の Selective Segment Reuse
    (SSR) がデータ配置を散らし read の 66.3% が 4–8KB、ZUFS は逐次書き強制で大半が
    512KB 超 (Fig. 11)。
  - フォトギャラリースクロール(写真 1,300 枚、平均 ~4.5MB、swipe-up 30 回・間隔
    100ms、§5.5 と同じエージング): jank 率 0.60%→0.26%、ファイルあたり平均
    フラグメント数 46.29→2.31(20 分の 1)、平均フラグメント長 99KB→1,979KB
    (20 倍)、p99 フレームタイム 16ms→11ms (§5.6.2, Table 2)。
- [inference] 評価がカバーしていないもの:
  - **WAF そのものの測定が無い**。動機部は WAF 削減 → エネルギー・耐久性向上を
    主要便益に挙げる (§2.3) が、評価はスループット / レイテンシ / jank のみで、
    WAF・消費電力・NAND 摩耗の実測は示されない。
  - CUFS ベースラインは「同一 ZUFS デバイスを conventional LU モードで使う」構成
    (§5.1)。ハードウェア条件は揃うが、この CUFS モードのファームウェア(map cache
    方式・チューニング)が市販 CUFS 専用品と同等に最適化されているかは本文から
    確認できず、対 CUFS の倍率はこの構成に依存する。
  - ZMS 比較はバッファ flush 粒度のみの模擬 (§5.4)。IOTailor 実物のホスト CPU/DRAM
    コスト・キュー遅延・暗号化制約 (§2.5 で指摘) は再現されておらず、system-level の
    直接比較ではない。
  - §4.3 の synchronous ungating は「クロック完全復帰を待つ」設計だが、その待ち時間が
    I/O レイテンシ・消費電力に与える影響の定量が無い。順序保証修正群の性能コストは
    未報告。
  - sudden power-off 時の回復(ZMT length フィールドと fsck の write pointer 補正、
    §4.1, §2.4)は設計記述のみで、電源断注入実験は無い。
  - ゾーンサイズは 1,056MB 固定 (§4.1)。ゾーンサイズ感度、および Table 1 の knob
    デフォルト値(60%/25%/95%/×5 等)の感度分析は無い。
  - 断片化実機調査 (§3.1) は単一機種・128GB・F2FS 固有メトリクスに基づく。

## Limitations
- Stated [paper]:
  - 大ゾーンは逐次スループットと並列性に有利な一方、F2FS レベルの GC 移行コストと
    foreground GC 頻度を増やすトレードオフ(本論文の proactive GC はその緩和策)
    (§3.4)。
  - zoned では IPU が使えず F2FS は厳格 LFS モードを強制される(小さな同期更新の
    最適化パスを失う。atomic_write + WriteBooster が代替、§2.5)(§2.4)。
  - background GC のオーバーヘッドは非無視(proactive 実行で償却すると主張)
    (§5.5, p.13)。
  - 本研究は完成形ではなく、ZUFS の本番浸透に伴い追加の研究・エンジニアリング
    課題が出続けるとの位置付け (§6)。
- Inferred [inference]:
  - proactive GC は「空きに余裕があるうちに書き換え帯域と電力を先払いする」戦略で
    あり、バッテリー駆動デバイスでのアイドル時電力・NAND 書込み総量への影響が
    評価されていない(WAF・電力の実測欠如と同根)。バースト的な書込みが Boosted-GC
    と重なった場合の干渉も Fig. 9c の 40/80 反復目の dip 以上の分析は無い。
  - Zone Write Locking(1 ゾーン in-flight write 1 本、§2.4)+ synchronous ungating
    (クロック復帰待ち、§4.3)は正しさ優先の設計で、単一ゾーンへの書込み並列性を
    構造的に制限する。open zone 数が 6 のままアプリ側ストリームが増える将来
    (per-app 分離やマルチテナント)にスケールするかは未検証。
  - reserved_segments = 6336 のデフォルトはこのデバイス(zone 1,056MB・6 open zones)
    への調律であり、他容量・他ゾーンサイズへの移植規則は示されていない。
  - SGBM の slot table は「ゾーン内厳格逐次だから線形記録で足りる」(§4.2) 前提に
    立つ。ZUFS 仕様の範囲では妥当だが、将来 zone append 型の並行書込みが導入されると
    この単純化は成り立たなくなる。

## Relations
- 競合・先行(本文内): ZMS(ATC '24、IOTailor + budget-based IPU。§2.5, §3.2, §5.4 で
  比較)、Yan et al. のホスト側 FTL 化 ZUFS(§2.5)、ZNS 系(ZNS+ / eZNS / ZNSwap、
  §2.5)。ファイルシステム土台は F2FS (§2.4)。
- [[2026-pvldb-lee-how-to-write-to-ssds.md]]: 「Total WAF = DB WAF × SSD WAF」の枠組みと
  out-of-place 化・GC 単位整合・FDP の議論は、本論文の「ゾーンを erase block に揃えて
  device GC を消し、GC をホスト(F2FS)に一元化する」(§2.3) と同じ設計空間の
  モバイル版。あちらは DB エンジン側から、こちらはデバイス+FS 側から同じ増幅の
  乗算構造を潰しにいっている。
- [[2026-fast-bian-discard-gc.md]]: GC の WA/SA トレードオフを本番システムでどう
  制御するかという主題で接続。DisCoGC は分散ブロックサービス層で discard 主体の
  回収、本論文は F2FS の background GC を 3 フェーズの閾値制御で proactive 化 (§4.4)
  しており、「回収をいつ・どの強度で走らせるか」の設計判断を比較できる。
- [[2026-fast-ren-lsm-scheduling.md]]: foreground I/O とバックグラウンド回収
  (compaction / GC)の干渉制御という共通テーマ。HATS が分散 LSM で read と
  compaction を閉ループ co-scheduling するのに対し、本論文は「user read 到着で
  background GC を即停止」(§4.4–§5, p.11) という単純な優先則で、制御の洗練度の
  対極にある。

## Idea seeds
- [inference] モバイル DB(SQLite 系)への含意が大きい: ZUFS では IPU が禁止され
  F2FS は純 LFS モード、同期小書きは atomic_write + WriteBooster 頼み (§2.4, §2.5)。
  fsync 集約的なトランザクションワークロード(SQLite WAL / rollback journal)の
  コミットレイテンシが CUFS→ZUFS でどう変わるかは本論文が測っていない空白。
  最初の検証: Pixel 10 Pro 実機(CUFS/ZUFS 両モード構成可、§5.1)で SQLite
  ベンチ(挿入 + fsync)を走らせ、p99 コミットレイテンシと F2FS チェックポイント
  頻度を両モードで比較する。
- [inference] how-to-write-to-ssds の乗算 WAF の観点では、ZUFS 上の DBMS は
  「DB WAF × F2FS GC WAF」を払う(device WAF は ~1 に近づくが FS GC は残る、
  §2.3, §3.4)。F2FS を介さず zoned LU を直接扱う zone-aware なモバイル向け
  ストレージエンジン(ZLeanStore のモバイル版)なら FS 層の GC も消せる可能性が
  ある。最初の検証: §5.5 の断片化ワークロード下で F2FS の GC 移行バイト数
  (ホスト側 WAF)を実測し、DB を LFS 上に置く場合との増幅を分解する。
- [question] Table 1 の 3 フェーズ閾値 GC は静的 knob(60%/25%/×5)で、これが
  多様なゾーンサイズ・ワークロードに対し頑健かは開いた問題(著者らも system
  integrator による調律を想定、§4.4)。フィードバック制御(空き section の減少率や
  read 干渉率を入力に GC レートを連続調整)が Fig. 9c の dip を消せるかは検証可能な
  仮説。upstream 済み knob (p.11) が公開カーネルにあるため、実験は Pixel 実機 +
  mainline F2FS で再現できるはず。
- [question] 断片化調査 (§3.1) の fragmentation level(dirty/(dirty+free))は F2FS
  セグメント統計ベースの簡便な指標で、read 性能劣化の主因(SSR による配置散乱、
  §5.6.1)を直接測ってはいない。DB ファイルのエクステント断片化と論理的
  断片化(B-tree ページの論理順 vs 物理順)を区別する指標を立てれば、モバイル DB
  の性能予測指標として研究の余地がある。

## Changelog
- 2026-07-06: created (status: read)
