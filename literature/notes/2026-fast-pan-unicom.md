---
title: "UnICom: A Universally High-Performant I/O Completion Mechanism for Modern Computer Systems"
authors: [Riwei Pan, Yu Liang, Sam H. Noh, Lei Li, Nan Guan, Tei-Wei Kuo, Chun Jason Xue]
venue: "FAST '26 (24th USENIX Conference on File and Storage Technologies)"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/fast/Pan0NLGKX26"}
urls: {paper: "https://www.usenix.org/conference/fast26/presentation/pan", pdf: "literature/pdfs/2026-fast-pan-unicom.pdf", code: "https://github.com/MIoTLab/UnICom"}
status: read
read_date: 2026-07-06
tags: [io-completion, polling, interrupt, nvme, ssd, kernel-bypass, direct-io, cpu-scheduling, linux, io_uring, ext4]
---

## TL;DR
既存の I/O 完了機構は、polling は低 CPU 利用率でのみ速く(高負荷では busy-wait が
compute スレッドと衝突)、interrupt は割り込み処理コストで低負荷時に遅い、という
「シナリオ限定の強さ」しか持たない。UnICom は「syscall のモード切替 ~150ns はディスク
I/O に比べ無視できる」という観察に基づき、カーネル内で①スケジューラのタグ更新だけで
sleep/wake する TagSched、②全スレッド・全プロセスの完了を一括 polling する集中完了
スレッド TagPoll、③カーネルモジュールで NVMe キューと per-file extent tree を管理し
I/O スタックの大半をバイパスする SKIP、を組み合わせる。ext4 / BypassD / io_uring
(SQ_POLL) に対し、CPU 利用率の高低を問わず最良水準の同期 I/O 性能を主張。

## Problem & motivation
- [paper] 高性能 SSD(数百万 IOPS・10µs 未満のレイテンシ、PCIe 5.0 NVMe は最大 14GB
  帯域)に対し、I/O スタックのソフトウェアオーバーヘッドが総 I/O レイテンシの最大
  50% 程度を占める(低レイテンシ SSD 上の 4KB read で約 50% という先行研究 [37,45] を
  引用)(abstract, §1, §2)。
- [paper] 先行研究は完了機構を「I/O だけの視点」で研究し、I/O スレッドに十分な CPU が
  あると仮定して、同時に走る非 I/O スレッド(compute スレッド、C-thread)への影響を
  見落としてきた。実運用では I/O 集約と計算集約のワークロードが単一アプリ内または
  co-running アプリ間で混在する (§1)。
- [paper] motivation 実験(4KB / 128KB random read、C-thread 16 本 = 16 コア占有)から:
  - Interrupt(ext4)の限界: 低 CPU 利用率(I/O スレッドのみ)では頻繁な割り込み処理の
    per-I/O オーバーヘッドで、I/O スレッド ≤8 のとき ext4 の IOPS は BypassD の平均
    62.9%。SSD 飽和(4KB で 1550k IOPS、128KB は ≥4 スレッドで 55k IOPS)に達すると
    差は縮む (§3.1, Fig. 1)。一方 C-thread 混在時の ext4 は CPU 使用が効率的で、128KB
    では I/O スレッドを増やしても C-thread 性能が安定 (§3.1, Fig. 2b)。
  - Polling(BypassD)の限界: 低利用率の小 I/O では最速だが、デバイス飽和時は
    busy-wait 時間が 1 スレッド 36µs → 32 スレッド 587µs に急増(in-device 完了待ちの
    queueing)。C-thread 混在時は CPU サイクルの奪い合いで両者が劣化し、32 スレッドでは
    BypassD 下の C-thread 性能が ext4 の 39.1% まで落ちる (§3.1, Fig. 1, Fig. 2)。
  - io_uring(SQ_POLL)の限界: ①同期 I/O 依存のアプリはソース大改修が必要、
    ②per-instance インターフェースのためプロセス間で polling を統合できない(32
    プロセス → 32 submission thread が I/O スレッドと干渉し io-uring-proc は劣化、
    C-thread も巻き添え)、③submission thread は要求を転送するだけで下層の完了機構に
    依存するため、instance を共有しても(io-uring-shared)ext4 並みのスループットに
    留まる (§3.1, Fig. 1, Fig. 2)。
- [paper] まとめ: polling は低 CPU 利用率で強く高利用率で弱い、interrupt は利用率に
  鈍感だが割り込み処理が高コスト、という相補的な限界がある(概念図 Fig. 3)。目標は
  「全 CPU 利用率シナリオで高 I/O 性能 + 主流アプリ向け同期 I/O サポート」(§3.1)。
- [paper] 3 つの技術課題: ①同期 I/O に必須の sleep/wake-up 自体が重い — ext4 の 4KB
  read では interrupt handling(deactivation 710ns 8% + context switch 980ns 11% +
  reactivation 1240ns 14%)が総レイテンシ 8730ns の約 33% を占める(storage device
  自体は 4010ns 46%)(§3.2, Table 1)。②busy-wait の統合はプロセス間ではアドレス空間
  分離のため IPC 中継が必要になり難しい (§3.2)。③これらの解決策を direct-access
  方式と統合すること (§3.2)。
- [paper] 鍵となる洞察: user-kernel モード切替の syscall は ~150ns(実験プラットフォーム)
  でディスク I/O レイテンシに対し無視できる。ゆえにカーネル空間内に完了機構を置き、
  カーネルの既存インフラ(スケジューラ、権限チェック)を活用しつつカーネル I/O
  スタックの大半をバイパスできる (§3.2, Table 1)。

## System model & assumptions
- [paper] 対象は同期(synchronous)I/O を使う主流アプリケーション。io_uring 的な
  非同期パラダイムへの改修を求めない (§1, §3.1)。
- [paper] direct I/O のみサポート。伝統的な Linux I/O スタックをバイパスするため
  ページキャッシュは使えず、buffered I/O 等の未サポート操作は従来の POSIX
  インターフェースにフォールバックする (§5, p.10)。
- [paper] ハードウェア: NVMe SSD。設計目標は将来の高帯域・低レイテンシ flash デバイスの
  サポートで、評価は latency 最適化 SSD(Intel Optane P5801x)が主、consumer SSD
  (Kingston NV3)は一般性確認用 (§6.1)。NVMe ハードウェアキュー数は実デバイスでは
  有限(P5800x で 135、NV3 で 31)という制約を設計が前提にする (§4.3)。
- [paper] OS: Linux カーネル(実装は 6.5.1)+ ext4。CFS スケジューラを 71 LOC 改変
  (§5, §6.1)。スレッドは I/O 実行の有無で動的に I/O スレッド / C-thread に分類される
  (§4.1)。TagSched は OS 内の全タスクに適用されるが、IO-WAIT タグ付きタスクが選択
  されたときのみ発動する (§5)。
- [paper] セキュリティ/保護モデル: ファイル権限チェックはカーネルモジュール(UnIDrv)が
  カーネル空間で実施。BypassD(拡張 IOMMU ハードウェア要)や XRP(eBPF 要)と異なり、
  user-space の権限管理やハードウェア改変なしに安全なバイパスを実現すると主張 (§4.3)。
- [paper] 故障モデル: メタデータ操作(open/close/unlink 等)は従来 POSIX 経由のため、
  writeback ジャーナルモードの ext4 や BypassD と同様のメタデータ crash consistency を
  保証 (§5, p.10)。
- [paper] 資源モデル: 専用のカーネルレベル完了スレッドに CPU 1 コアを固定的に割り当てる
  (評価では 16 E-core 中 1 個を予約)(§6.1)。完了スレッドは 1 I/O を約 550ns で処理し、
  単一スレッドの最大完了レートは約 1820 KIOPS (§5, p.10)。
- [inference] データ(非メタデータ)の crash consistency / 永続化順序(fsync 相当)の
  扱いは本文に記述がない。writeback ジャーナル相当と明言されるのはメタデータのみで、
  SKIP 経由の書き込みとジャーナリングの関係は読み取れない。
- [inference] ページキャッシュを使うプロセス(従来 POSIX の buffered I/O)と SKIP の
  direct path が同一ファイルを共有した場合のキャッシュ一貫性は論じられていない。
  「未サポート操作は POSIX へ」という記述 (§5, p.10) は同一ファイル内での混在を
  排除していないように読める。

## Approach
- [paper] **全体構成 (§4, Fig. 4)**: カーネル内 I/O 完了機構。TagSched(スケジューラ内の
  タグ制御)+ TagPoll(集中完了スレッド)+ SKIP(direct I/O submission)の 3 スキーム。
- [paper] **TagSched: tag-guided in-queue scheduling (§4.1, Fig. 5)**:
  - PCB にスケジューリングタグを追加: IO-WAIT(=-1)/ IO-NORMAL(=0)。I/O 発行時に
    IO-WAIT に落として CPU を明け渡し、スケジューラは pick-next で IO-WAIT スレッドを
    スキップ。完了時に IO-NORMAL へ戻すだけで再スケジュール可能になる。核心は
    「I/O 中もスレッドを run queue から出し入れせず留め置く」ことで、既存の
    deactivation / reactivation のコストを消すこと。
  - 非原子的タグ更新の競合(タグを IO-WAIT にする前に I/O が完了 → 永久スリープ)は、
    IO-WAIT 更新をデクリメント、IO-NORMAL 更新をインクリメントとして設計し、順序が
    逆転しても合計が 0(NORMAL)に戻ることで解決。タグ ≥0 は通常タスク扱い (§4.1, Fig. 5)。
  - C-thread preemption: I/O スレッドは submit 後 CPU を譲るため、C-thread 実行中だと
    完了済み I/O スレッドが C-thread の ms 級タイムスライス満了まで待つ head-of-line
    blocking が起きる。そこで I/O 完了時に対象 CPU へ IPI を送り、即時の pick-next-task を
    強制する。従来の I/O 割り込みと違い enqueue/dequeue が不要 (§4.1, Fig. 6)。
  - 公平性: vruntime 計算は元のまま(busy-wait ループ内で sched_yield するタスクと同様の
    振る舞い)。run queue のタスク数増加のコストは小さい(red-black tree のタスク選択
    レイテンシはタスク 1→100 で +28ns)(§4.1 Discussion)。
- [paper] **TagPoll: tag-notify polling (§4.2, Fig. 7)**:
  - カーネル内に専用の集中 polling 完了スレッドを 1 本置き、全 I/O スレッド・全プロセスの
    要求を代行処理する。カーネル空間で動くため multi-process 対応が自然に得られる。
  - ワークフロー: I/O スレッドは自分の PCB へのポインタを I/O 要求に埋め込んで NVMe
    キューに直接 submit(➊)→ タグを IO-WAIT にして CPU を明け渡す(➋)→ 完了スレッドが
    NVMe キューを poll し、完了検出でタグを IO-NORMAL に更新、対象 CPU 上の実行中タスクの
    種別(I/O / C-thread)に応じて IPI を送る(➌)→ 要求を completed にマークし、I/O
    スレッドが後で処理(➍)。wake-up は低コストなタグ更新 + C-thread preemption のみ。
  - Adaptive I/O completion policy: I/O 要求メタデータに「次の I/O で希望する完了機構」を
    示すフラグを追加。完了スレッドは要求受領時に当該 I/O スレッドの run queue のタスク数を
    確認し、その I/O スレッドが CPU を占有しているなら本人 polling を指示(context switch
    を消す)、そうでなければ TagSched+TagPoll の既定動作。ワークロードに応じて完了機構を
    スレッド単位で自動切替し、sleep 時間予測が難しい既存 hybrid polling の限界を回避すると
    主張 (§4.2)。
- [paper] **SKIP: Shortcut Kernel I/O Path (§4.3, Fig. 8)**: カーネルドライバモジュール
  UnIDrv + ユーザ空間ライブラリ Ulib。
  - UnIDrv がハードウェア NVMe キューを確保・管理し(TagPoll の作業環境)、per-file
    extent tree でファイルオフセット → 物理ブロックアドレス(PBA)の対応を保持。これで
    ファイル操作をブロック I/O に翻訳して NVMe キューへ直接 submit できる。権限チェックは
    カーネル内で実施 (§4.3)。
  - Ulib は LD_PRELOAD でアプリのファイル操作を横取りし、ioctl(user_io_submit; fd,
    offset, user buffer, length)で UnIDrv に転送 (§4.3)。
  - BypassD(full user-space 方式)との差分①: NVMe キューをプロセスのアドレス空間に
    直接マップしない。キュー数は有限なので、静的マッピングは過剰割当(浪費)か過少割当
    (キュー競合・プロセス間同期)のトレードオフを生む。UnIDrv はカーネル内に NVMe
    キュープールを持ち、PID のハッシュで I/O スレッドにキューを動的に割り当てる (§4.3, Fig. 8)。
  - 差分②: BypassD の fmap(offset→PBA をページテーブルに静的格納しユーザ空間で索引)は
    カスタム IOMMU ハードウェアが必要で、PCIe 往復 + IOMMU 変換のレイテンシと、ファイル
    サイズの ~0.2% のメモリ + fmap ロードレイテンシを伴う。extent tree は 12B の extent
    (block-aligned offset 4B + PBA 4B + block length 4B)1 個で大きな連続範囲を表現でき、
    索引・メモリ両面で効率的 (§4.3)。
- [paper] **実装 (§5)**: Ulib 1,089 LOC、UnIDrv 3,250 LOC、CFS 改変 71 LOC。TagSched は
  sched_entity に 2-bit タグ + 1-bit I/O/C-thread フラグを追加し pick_next_entity に統合。
  NVMe キュースロットへの I/O スレッド / 完了スレッドの並行アクセスによる CPU キャッシュ
  false sharing は共有データ構造のキャッシュ整列で回避。extent tree は inode_operations に
  setup_extent_tree / mapping_lookup の 2 インターフェースを追加し、ext4 では on-disk
  extent の走査で構築、ext4_ext_map_blocks / ext4_truncate と既存ロックに統合して
  ファイルシステムとの写像一貫性を保証。fallocate / truncate / append は extent tree の
  即時更新でサポート (§5, p.9–10)。ソースコードは公開
  (https://github.com/MIoTLab/UnICom)(§5 脚注 1, p.9)。
- [paper] **スケーラビリティの見通し**: 完了スレッドは 1 I/O 約 550ns、最大 ~1820 KIOPS。
  SSD の IOPS 向上や複数 SSD 管理ではボトルネック化しうるので、SSD 毎 / ファイル毎に
  完了スレッドを割り当てる複数スレッド化を将来課題とする (§5, p.10)。

## Evaluation
- Setup [paper]: Ubuntu 20.04 + Linux 6.5.1、24-core Intel Core i9-14900K(8 P-core
  3.2GHz + 16 E-core 2.4GHz)、32GB RAM、400GB Intel Optane SSD P5801x(主)+ 1TB
  Kingston NV3(consumer)。16 E-core のみ使用、hyperthreading / turbo boost 無効。
  比較対象: ext4(interrupt)、BypassD(polling; 全 NVMe キュー割当、fmap のハードウェア
  オーバーヘッドは原論文のシミュレーション設定を再利用)、io_uring SQ_POLL(micro のみ。
  同期 I/O が主題のため macro / real-world からは除外)。UnICom は E-core 1 個を完了
  スレッド専用に予約し残り 15 個をアプリに、他方式は 16 個全部使用。全実験 direct I/O、
  5 回試行の平均 (§6.1)。C-thread はカウンタをインクリメントし続ける計算スレッド (§3.1)。
- Micro(C-thread なし、1GB ファイル random I/O)[paper]:
  - 4KB IOPS: read +43.5% / write +34.9%(対 ext4 平均)。BypassD よりわずかに高いのは
    per-file extent tree が fmap オーバーヘッドを改善するため (Fig. 9a, 9b, §6.2)。
    I/O サイズ掃引でも対 ext4 平均 +36.6% (Fig. 9c)。
  - レイテンシ: 1 スレッド(非飽和)では BypassD 同等で、ext4 の平均レイテンシを 4KB で
    42%、128KB で 17.4% 削減。飽和時(32 スレッド)は平均は各方式収束するが、4KB P99 は
    TagSched の sleep/wake 最適化で ext4 比 31.2% 改善(ただし multi-thread では context
    switch を消せないため BypassD よりは高い)。128KB P99 は BypassD の非プリエンプティブ
    polling が極端なテール(16175µs vs ext4/UnICom の ~593µs)を生み、io-uring-proc も
    16233µs (Fig. 10, §6.2)。
- Micro(C-thread 16 本固定)[paper]:
  - 4KB read IOPS: 対 ext4 +39.4%、対 BypassD +88.8%(平均)。代償として C-thread 性能は
    専用コア分 ext4 / BypassD 比約 -7.5%。ただし I/O が十分強い 32 I/O スレッドでは専用
    コアが使い切られ、C-thread 性能も ext4 +35.8% / BypassD +26.4% と逆転 (Fig. 11a, §6.2)。
  - 128KB read: 即飽和。TagSched が BypassD / io-uring-proc の C-thread 漸進劣化を防ぎ
    平均 +39.3% / +43.3%。ext4 / io-uring-shared に対しては一貫して約 15% 低い(コアが
    1 個少ない + 大 I/O 下では専用コアの利用効率が低い)(Fig. 11b, §6.2)。
  - write も同傾向(4KB write で ext4 超え、128KB で C-thread 性能が BypassD 比平均
    +44%)(Fig. 11c, 11d, §6.2)。
  - C-thread 数掃引(I/O 16 本固定、4KB): 対 ext4 平均 +33.2%。BypassD は C-thread 増で
    劣化し続け、32 C-thread では UnICom が +82.7% (Fig. 12, §6.2)。
  - 著者の総括: 固定 CPU 資源(専用コア)を捧げることで、(1) 小 I/O で ext4 を大きく
    上回りつつ同等の C-thread 効率を維持、(2) 大 I/O で BypassD が示す C-thread 劣化と
    CPU 浪費を防ぐ、というトレードオフ (§6.2)。
- Consumer SSD(Kingston NV3, 4KB)[paper]: ボトルネックがデバイスの I/O レイテンシ側に
  あるため対 ext4 は +5.3% に留まる。一方 I/O レイテンシが長いほど busy-wait が非効率に
  なるため対 BypassD は +79.4%。C-thread は ext4 / io-uring-shared に対し一定の差
  (専用コア分)だが、BypassD / io-uring-proc の持続的劣化は起きない (Fig. 13, §6.2)。
- Breakdown [paper]:
  - Adaptive completion: I/O スレッド ≤8(コア占有)では本人 polling に切り替わり
    UnICom-no-opt 比 平均 +13.8%。≥16 ではコア共有になり TagSched+TagPoll 経路 (Fig. 14a, §6.3)。
  - 動的 NVMe キュー管理: BypassD をキュー 1 本に制限すると peak IOPS 約 -20%(対
    Q-max)。増やせば他アプリのキューが減る、という静的割当のトレードオフを動的割当が
    解消 (Fig. 14b, §6.3)。
  - Extent tree: 4KB read のレイテンシ内訳で fmap の mapping レイテンシを 71.2% 削減
    (fmap は PCIe 往復 + IOMMU 変換が乗るため)。UnICom の mapping コストは syscall
    150ns + tree 検索 80ns。ただし完了スレッド経由のため I/O 時間自体はやや長い。cold
    open 時の extent ロードで open レイテンシが ~7µs → 28 / 57 / 146µs(extent 4 / 9 /
    186 個)に増える(hot open では消える)(Fig. 14c, §6.3)。
  - 公平性: 32 I/O + 16 C-thread で、IOPS 分布は BypassD 類似(どちらも run queue に
    留まり同様の vruntime 更新)、C-thread 分布は ext4 類似 (Fig. 15, §6.3)。
  - メモリ: タグはスレッドあたり 1B(最大 PID 4194304 で最悪 4MB)。extent tree は
    12B/extent で、1000 extent の断片化ファイルでも ~12KB、評価中で最も断片化した
    ファイル(1GB・9 extents)は 108B。同一ファイルで BypassD fmap 比 99.9% 超の
    メモリ削減 (§6.3)。
- Macro [paper]: destor(dedup バックアップのファイル復元、16KB chunk、multi-thread 化
  改造)を I/O 集約、stress-ng(128×128 行列計算、8 / 16 スレッド)を計算集約として同時
  実行 (§6.4, Fig. 16)。低負荷(stress-ng 8 本)では BypassD と UnICom の復元帯域は
  ほぼ同じで、飽和前は ext4 比最大 +32%。stress-ng 側は専用スレッドの分だけ
  BypassD / ext4 がやや優位。高負荷(stress-ng 16 本)では復元帯域で ext4 同等以上、
  BypassD には平均 +52.3%。stress-ng 側も BypassD 比 +22.5% / +45.7%(restore 16 / 32
  本)、ext4 にはわずかに劣る (§6.4)。
- Real-world [paper]: RocksDB(direct I/O 有効)+ YCSB。500M KV(32B key、value 64B /
  200B)、10M ops、1 / 8 / 32 スレッド。ext4 と BypassD は期待通りのトレードオフ
  (1 スレッドは BypassD 優位、32 スレッドは ext4 が逆転)を示す中、UnICom はほぼ全域で
  最良: 対 ext4 で 1 スレッド +24%(64B)/ +28%(200B)、32 スレッドでも +9% / +18%
  (DB 内部の競合で相対利得は縮小)。対 BypassD で 1 スレッド +3%、32 スレッドで
  +34%(64B)/ +56%(200B)(Fig. 17, §6.5)。
- [inference] 評価がカバーしていないもの:
  - CPU は 16 E-core(2.4GHz、単一ソケットのデスクトップ CPU)のみ。§1 の motivation は
    「数十〜数百コア」だが、多ソケット / NUMA / 高コア数サーバでの集中完了スレッド
    (単一スレッド上限 ~1820 KIOPS、§5)の挙動は未測定。完了スレッドが飽和する負荷での
    劣化カーブも示されていない。
  - 比較対象に Aeolia(user interrupt ベース、§2 で「Sapphire Rapids 以降限定」と紹介)や
    XRP、io_uring の I/O Passthru [14] は含まれない。polling 代表は BypassD のみ。
  - fmap のオーバーヘッドは「BypassD 原論文のシミュレーション設定を再利用」(§6.1) で
    あり、拡張 IOMMU の実ハードウェア測定ではない。extent tree の対 fmap 利得
    (71.2%、Fig. 14c)はこのシミュレーション前提に依存する。
  - 書き込みの永続性(flush / FUA / fsync 相当)とデータ crash consistency の実験は無い
    (crash 注入も無い)。
  - ファイルは 1GB(micro)等の固定構成で、深く断片化した大ファイルや多数ファイル同時
    open(cold open 146µs@186 extents の外挿)のストレスは限定的。
  - LD_PRELOAD ベースの Ulib で intercept できないアプリ(静的リンク等)の扱いは
    論じられていない。

## Limitations
- Stated [paper]:
  - 専用完了スレッドの上限は ~1820 KIOPS で、SSD の IOPS 増加や複数 SSD ではボトルネック
    になりうる。複数完了スレッド化(SSD 毎 / ファイル毎のルーティング)は将来課題 (§5, p.10)。
  - direct I/O のみ。ページキャッシュ不使用のため buffered I/O は従来 POSIX へ
    フォールバック (§5, p.10)。
  - CPU 1 コアを固定的に消費するため、I/O が軽いときは C-thread 性能が ext4 / BypassD 比
    約 7.5% 低下し、大 I/O では ext4 / io-uring-shared に約 15% 及ばない (§6.2, Fig. 11)。
    macro でも stress-ng は ext4 にわずかに劣る (§6.4)。
  - cold open 時の extent tree ロードで open レイテンシが増加(~7µs → 最大 146µs @186
    extents)(§6.3, Fig. 14c)。
  - multi-thread シナリオでは context switch を消しきれず、4KB P99 は BypassD より高い
    (§6.2, Fig. 10)。
  - crash consistency の保証はメタデータについてのみ明言(writeback ジャーナルモードの
    ext4 / BypassD と同等)(§5, p.10)。
- Inferred [inference]:
  - 「syscall 150ns は無視できる」という核心的洞察は µs 級 SSD の前提。CXL-SSD 等で
    デバイスレイテンシがさらに 1 桁下がる(§2 が展望として引く)と、150ns + 完了スレッド
    経由 550ns の相対コストは増し、洞察の成立範囲が狭まる可能性がある。
  - TagSched の C-thread preemption は IPI で C-thread のタイムスライスを強制中断する。
    Fig. 15 で公平性分布は示されるが、IPI レートが極端に高い(小 I/O 数百万 IOPS)場合の
    C-thread 側のキャッシュ汚染・中断コストの定量は無い。
  - PID ハッシュによる NVMe キュー割当 (§4.3) は、ハッシュ衝突で複数のホットな I/O
    スレッドが同一キューに載る偏りを排除しない。キュー競合時の挙動は評価されていない。
  - 完了スレッドは全プロセスの I/O を直列化する (§4.2)。single point of contention に
    なるだけでなく、悪意ある / バグのあるプロセスの大量 submit が他プロセスの完了
    レイテンシに直接波及する分離性の議論が無い。

## Relations
- 競合 baseline(本文): ext4(interrupt)、BypassD [37](user-space polling + 拡張
  IOMMU)、io_uring SQ_POLL [11]。関連手法として blk-switch / Cinterrupts /
  FlashShare / XRP / SPDK / DevFS / CrossFS / uFS / Aeolia / I/O Passthru が §2 で
  整理される。
- [[2026-cidr-houlborg-xnvme.md]](xNVMe/nvmefs): 同じ「DB/アプリと NVMe の間の I/O
  経路選択」問題を反対側から攻める関係。xNVMe は DuckDB 側が io_uring_cmd(I/O
  Passthru)/ SPDK 等のバックエンドを切り替えて速い経路を使う話で、UnICom はカーネル側に
  「同期 POSIX のまま速い」経路を新設する話 (§2, §4.3)。同期 I/O のままでよいという
  UnICom の主張 (§3.1 の io_uring 批判) は、xNVMe 系の非同期化アプローチの導入コストの
  裏返しであり、両ノートを跨ぐ比較軸になる。
- [[2026-fast-zhan-buffered-io.md]](WSBuffer): 同じ FAST '26 のカーネル I/O スタック
  改革だが分担が対照的。WSBuffer は buffered write path(ページキャッシュ)を再設計し、
  UnICom は direct I/O の完了機構を再設計してページキャッシュを完全に迂回する(buffered
  I/O は従来 POSIX へフォールバック、§5 p.10)。「高性能 NVMe 時代にカーネル I/O
  スタックのどこを残しどこを捨てるか」という共通の問いに対する二つの切り口。

## Idea seeds
- [inference] TagPoll の adaptive completion policy(スレッド単位で polling / sleep を
  切替、§4.2)は、DBMS 内部のスレッド役割(レイテンシ敏感なトランザクションワーカ vs
  スループット志向の compaction / checkpoint スレッド)と自然に対応する。DB 側から
  タグ/フラグにヒントを渡す co-design(WAL flush は本人 polling、compaction I/O は
  TagPoll 任せ等)は、RocksDB 評価 (§6.5) が示す 32 スレッド時の利得縮小(+9–18%)を
  押し上げられる可能性がある。最初の検証: 公開コード(github.com/MIoTLab/UnICom)で
  RocksDB の flush/compaction スレッドと foreground スレッドに異なる完了ポリシーを
  静的に固定し、YCSB のテールレイテンシを比較する。
- [question] 単一完了スレッドの上限 ~1820 KIOPS (§5, p.10) は、複数 NVMe SSD を束ねる
  ストレージエンジン(LSM の並列 compaction 等)では現実的な壁になるのではないか。
  複数完了スレッド化の際の「SSD 毎 / ファイル毎」ルーティング (§5) は DB のパーティション
  設計と干渉しうる。検証: SSD 2 台 + 完了スレッド 1 本で飽和カーブを取り、ボトルネックの
  所在(完了スレッド CPU vs デバイス)を確認するところから。
- [inference] UnICom は「ページキャッシュを使わない直接 I/O + 自前バッファ管理」という
  DBMS の伝統的構成 (direct I/O + buffer pool) と親和的で、逆に言えば buffer pool を持つ
  DB こそが Ulib/LD_PRELOAD を介さず user_io_submit ioctl を直接叩ける最短経路の
  クライアントになる。DB の buffer manager から SKIP を第一級 API として叩いたときの
  syscall あたりコスト(150ns + 80ns、§6.3)が read path の何 % になるかを LeanStore 系
  エンジンで測るのは小さく始められる実験。
- [question] メタデータのみ writeback 相当の crash consistency (§5, p.10) という保証で、
  WAL を SKIP 経由で書く DB は durability を自前で(write 完了 = デバイス到達の確認を
  どう取るかを含め)組み立てる必要があるはず。SKIP の write 完了通知がデバイスの持つ
  揮発キャッシュを考慮するのか(FUA/flush の扱い)は本文から読み取れず、公開コードで
  確認すべき点。

## Changelog
- 2026-07-06: created (status: read)
