---
title: "ScaleSwap: A Scalable OS Swap System for All-Flash Swap Arrays"
authors: [Taehwan Ahn, Chanhyeong Yu, Sangjin Lee, Yongseok Son]
venue: "FAST '26 (24th USENIX Conference on File and Storage Technologies)"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/fast/AhnY0S26"}
urls: {paper: "https://www.usenix.org/conference/fast26/presentation/ahn", pdf: "literature/pdfs/2026-fast-ahn-scaleswap.pdf", code: "https://github.com/syslab-CAU/ScaleSwap"}
status: read
read_date: 2026-07-06
tags: [os-swap, linux-kernel, all-flash-array, nvme-ssd, many-core, scalability, lock-contention, lru, per-core, delegation, larger-than-memory, memory-tiering, tco]
---

## TL;DR
Linux swap は「全コアが全 swap 資源を共有ロック越しに触る」all-to-all モデルのため、
複数 NVMe SSD の swap array でも SSD 数・コア数に対してスケールしない(lru_lock と
si_lock の競合)。ScaleSwap は ①コアごとに swap metadata / swap cache / 専用 swap
space を割り当てる core-centric 資源管理(swap entry の type field を 5→8 bit に拡張し
最大 247 swap space)、②他コアの swap space が必要な時だけ per-core delegator に
メタデータ操作を委譲する opportunistic inter-core swap assistance(平均 29.99ns)、
③page flag にコア番号を記録する per-core LRU、の3戦略で swap を one-to-one モデル化。
Linux kernel 6.6.8 実装、128 コア + 8 NVMe SSD で Linux swap 比最大 3.4× スループット・
11.5× 低平均レイテンシ・27.2× 低テールレイテンシ、TMO 比最大 64%・ExtMEM 比最大 5×
を主張。

## Problem & motivation
- [paper] OS swap は anonymous page を回収して OOM によるアプリ失敗を防ぐ基幹要素。
  ML・ビッグデータ・グラフ処理・VM・コンテナ等の memory-intensive アプリが swap に
  強い圧力をかけており、Alibaba Cloud の memcg 非同期 reclaim や Meta の kernel
  コンポーネント(アプリのメモリ遅延感度計測)など産業側でも再注目されている (§1)。
- [paper] DRAM 増設は TCO で制約される: クラウドサーバコストに占めるメモリは Meta で
  約 37%、Microsoft Azure で 50%。DDR4 DRAM 単価($4.22/GB)は PCIe 4.0 NVMe SSD
  ($0.16/GB)の約 26 倍。よって複数 SSD を swap space にする「all-flash swap array」
  が容量・コスト両面で実用的、と主張 (§2)。
- [paper] 実運用例: Google Cloud は VM あたり 375GB ローカル SSD ×8 = 計 3TB を
  swap space として提供し π 計算等の科学計算で約 82PB を処理。あるストレージラボは
  Solidigm SSD 30 台(計 921.6TB)を swap にして π 計算の世界記録を出しており、
  「swap 性能がこれらの計算の単一最大ボトルネック」と報告 (§2)。
- [paper] Apache Spark のケーススタディ: Spark 自体は spill で任意サイズを処理する
  建て付けだが、CommonCrawl データセットの PySpark 前処理(読み込み・パース)では
  Spark の spill 管理が始まる前に OOM が発生。1 ファイルあたり 20,000 レコードの処理で
  約 300GB を要し、128 ファイルでは TB 級のメモリ需要になる。この場面で all-flash swap
  array による OS swap が必須になる (§2, §5.4)。
- [paper] スケーラビリティの実測 (§3): 8 SSD 構成で raw デバイス(FIO の random
  read/write mix)は 1→2→4→8 SSD で 3.4→5.8→9.4→11.2 GB/s とほぼ線形にスケール
  するのに対し、Linux swap は SSD 数によらず約 4 GB/s で頭打ち (Fig. 3a)。コア数では
  32 コアまでは Linux swap が raw の mixed 性能を上回る(swap は out/in を交互に行い
  FIO は常時 read+write のため)が、64 / 128 コアでは raw より 1.5× / 2.6× 低い
  (Fig. 3b)。
- [paper] swap space の形態比較 (§3.1, Fig. 2): 8 devices より 128 swap files/partitions の
  方が高速(round-robin 割当で並列アクセス範囲が広がる)。ただし swap space 数の効果は
  デフォルト上限の 23 を超えると飽和する。file と partition の性能は同等で、柔軟性から
  本論文は swap file 構成に焦点を当てる。
- [paper] 根本原因の特定 (§3.4):
  - Insight #1: per-node LRU list の lru_lock 競合。direct reclaim 時にアプリスレッドが
    LRU lock を奪い合い、レイテンシスパイクとスループット低下が発生 (§3.3, §3.4.1,
    Fig. 4)。実測で lru_lock は Linux swap の総実行時間の 53.27% を占める (Table 5)。
  - Insight #2: swap metadata(swap_info、swap map 等)を守る si_lock。swap space を
    複数にしても全コアが全 space にアクセスできる all-to-all モデル+グローバルロックの
    ため高並行にならない (§3.4.2)。LRU 側だけ直した ScaleSwap(LRU) ではボトルネックが
    si_lock(5.03%)に移動することが示される (Table 5, §5.6)。

## System model & assumptions
- [paper] ハードウェアモデル: 単一サーバの many-core マシン + NVMe SSD 複数台の
  all-flash swap array。評価機は 2×AMD EPYC 7713(64 コア)= 128 コア、96GB DRAM、
  Seagate FireCuda 530 2TB ×8(random write/read/mix = 4.5/3.2/3.5 GB/s、raw RAID-0 で
  mix 11.4GB/s)(§5.1)。
- [paper] ソフトウェア: Linux kernel 6.6.8 への実装。swap space は EXT4 上の 128 swap
  files(§3.1 の比較に基づき file 構成を採用)(§5.1)。per-node kswapd は既存 Linux と
  同様に維持 (§4.5, Fig. 8)。
- [paper] 対象は anonymous page の swap(§1)。file-backed page cache は対象外
  [inference](§6 で ScaleCache を「file-backed page cache のスケーリング」として
  対比しており、本論文のスコープは swap パスに限定されている)。
- [paper] 設計上の資源上限(ビットフィールドのトレードオフ):
  - swap entry (swp_entry_t, 64bit) の type field を 5→8 bit に拡張(9 値は
    hardware-poisoned page 等のため予約)して swap space 数 23 → 247。代わりに
    offset が 50→47 bit になり per-core swap file は最大 128TB(現行最大デバイス容量が
    128TB、多くは 15TB 未満なので妥当と主張)(§4.4.2, Fig. 7)。
  - page flag の未使用 4bit + 3bit 拡張で 7bit の cpuid を記録(128 コアまで)。
    node bit は 10→7 bit に縮小(64 node まで。単一サーバには十分と主張)(§4.6, Fig. 9)。
- [paper] 一貫性モデル: 委譲は「他コアの swap metadata の読み書き」のみを対象とする
  メモリ操作で、コアごとに単一の delegator だけがそのコアの metadata を更新できる
  (multiple-producer / single-consumer の task queue、FIFO 処理)ため一貫性問題を
  防ぐ (§4.5)。swap-in 委譲の非同期性により「実際には空きがあるのに一時的に不足と
  報告される」ことはあるが、「無いのに有ると報告する」ことはない。Linux swap も
  swap-in 完了後に metadata を更新するため、一貫性レベルは既存 Linux swap と同等と
  主張 (§4.7.2)。
- [paper] I/O は委譲しない: 要求スレッド自身が委譲で決まった swap 位置に直接
  read/write する。各 swap space は自身のロック(例: file lock)で守られるため
  スレッド間の一貫性は損なわれない (§4.5, §4.7.2)。
- [paper] メモリ確保の前提: swap task 構造体(96B)は事前確保プール(設定可能、
  デフォルト 1,500 個/コア)から割り当て、高メモリ圧下での確保失敗を回避。プールが
  尽きたらメモリが空くまで待つ (§4.5, §5.2)。
- [inference] core-affinity LRU は「ページを確保したスレッドが同じコアで再アクセスする
  可能性が高い」(§4.6 の主張)ことを暗黙の前提にしている。スレッドがコア間を頻繁に
  マイグレートするワークロードではこの前提が崩れ、swap-in 時の「元のコアの LRU に
  戻す」動作 (§4.6) がリモートコアの LRU lock 取得を増やしうる(正しさは委譲機構で
  保たれるが、性能面の評価は無い)。
- [inference] 耐久性・故障モデルは論じられていない(swap の対象は anonymous page で
  再起動後の内容保持を要しないため、クラッシュ一貫性の議論が無いこと自体は自然)。
  SSD 側の摩耗(swap は書き込み集約的)も本文では扱われない。

## Approach
- [paper] 設計目標 (§4.1): ①コアごとに排他的・独立な swap 資源アクセス、②必要時のみの
  効率的なコア間協調(メモリ一貫性を保つ)、③swap 中の LRU lock 競合の最小化。
- [paper] **Strategy 1: Core-centric swap resource management (§4.4)**:
  - Linux swap の割当: コアは自分の swap slot(64 swap entry を保持)が空になると
    グローバルな available swap space list から round-robin で swap space を選び、その
    swap info の si_lock を取って cluster(512 swap entry)を確保する。space の
    round-robin とグローバルロックで si_lock 競合が発生(cluster は SSD 内部チャネルの
    並列性を最大化するため stride 32 で取得)(§4.4.1, Fig. 6a)。
  - ScaleSwap の割当: 各コアが自分専用の swap space(= swap file)内の自分の swap info
    から直接 cluster を確保して swap slot を充填する。available swap space list も
    si_lock も経由しない (§4.4.1, Fig. 6b)。
  - 専用 swap space の実現: 前述の swap entry type field 拡張(23 → 247 swap space)に
    より、コア数 > 23 の many-core でもコアごとに専用 swap space を割当可能にする
    (§4.4.2, Fig. 7)。
- [paper] **Strategy 2: Opportunistic inter-core swap assistance (§4.5)**:
  - 委譲が起きるのは2ケースのみ: 1) swap-out 時に自コアの専用 swap space が満杯で
    他コアの space を使う場合、2) swap-in 時にページが他コアの swap space にある場合
    (共有ページ・プロセスマイグレーション)。
  - per-core delegator スレッドが自コアの swap metadata への委譲要求を処理する。
    委譲はメタデータの読み書き(メモリ操作)のみで、ページ I/O は要求スレッドが
    委譲で確定した位置に直接行う(委譲時間の最小化)。
  - swap task(96B、要求種別・swap 位置情報等)+ per-core task queue(concurrent list
    実装)で通信。複数 producer / 単一 consumer(delegator)の FIFO 処理で順序と
    一貫性を保証 (§4.5, Fig. 8)。
  - Cooperative swapping: 委譲は I/O を含まないため要求スレッドは busy waiting
    (平均委譲時間 29.99ns)。ただし delegator が sleep 中だと待ち時間が伸びるため、
    待っている間に要求スレッドは自コアの task queue に溜まったタスクを自コアの
    delegator の代わりに処理する。spinning による CPU 浪費と blocking による context
    switch の両方を回避 (§4.5)。
  - 委譲先の探索: まず同一 node 内のコアを round-robin で探し、無ければ次の node を
    探す(NUMA オーバーヘッド最小化)(§4.5)。
- [paper] **Strategy 3: Core-affinity page and LRU management (§4.6)**:
  - per-node LRU list を per-core LRU list(各々専用 spinlock)に置き換え、eviction を
    コアローカルに行う。
  - ページ確保時にそのコアの LRU list に挿入し、page flag(7bit cpuid, Fig. 9)にコア
    番号を記録。swap-in 時は flag からコア番号を認識して元のコアの LRU list に
    再挿入する。これによりコア/キャッシュ局所性が上がり page fault も減る(§5.2 で
    9.15% 削減)。
- [paper] **手続き(委譲なし)(§4.7.1, Fig. 10)**:
  - Swap-out: 自コア LRU からページを取得 → swap slot から swap entry を取得
    (Fig. 6b の流れ)→ swap map の使用ビットを 0→1 に更新 → swap cache に挿入 →
    swap space へフラッシュして cache から追い出し → PTE を swap entry (SWE) に置換。
  - Swap-in: page table の SWE から swap-out を認識 → swap cache を確認、無ければ
    swap entry の位置情報で swap space から読む → swap cache に挿入 → page flag の
    コア番号で自分の LRU list に再挿入 → swap map を 1→0 に更新 → swap entry を
    swap slot に返却 → SWE を PTE に置換。
- [paper] **手続き(委譲あり)(§4.7.2, Fig. 11)**:
  - Swap-out 委譲: 自 space が満杯で swap slot を充填できない場合、対象コアの task
    queue に swap-out task を投入して delegator を起床。待機中は cooperative swapping。
    delegator は swap slot 経由で entry を確保(そのコアも満杯なら失敗応答 → 要求側は
    round-robin で次のコアを探索)、swap map を更新し自分の swap cache にページを
    挿入して完了シグナルを返す。要求スレッドは PTE→SWE 更新後、対象 swap space へ
    ページを直接フラッシュする。
  - Swap-in 委譲: 要求スレッドが対象コアの swap cache(ヒット時)または swap space
    から直接ページを取得した後、metadata 更新のための swap-in task を対象コアの
    queue に投入。スレッドは自分の page table を PTE に戻し自分の LRU に挿入。
    delegator は後で swap map の使用カウントを減らし swap entry を swap slot に返す。
    この非同期性による見かけ上の空き容量過小報告は許容(前述の一貫性議論)。

## Evaluation
- Setup [paper] (§5.1): 128 コア(2×AMD EPYC 7713)、96GB DRAM、FireCuda 530 2TB ×8、
  Ubuntu 22.04 + kernel 6.6.8、EXT4 上の 128 swap files。micro-bench は stress tool
  (指定サイズのメモリを byte 単位で write/read)。各テスト 10 回実行の平均。
  micro-bench 既定構成: 128 スレッド・8 SSD・スレッドあたり 2.25GB(計 288GB、
  DRAM 96GB に対する過剰分が swap に落ちる)(§5.2)。
- SSD スケーラビリティ [paper]: 1/2/4/8 SSD で Linux swap 比 1.31× / 2.34× / 2.85× /
  3.41× のスループット、実行時間は 1.55×–2.49× 短縮 (Fig. 12a)。Linux swap は
  2 SSD 以降スケールしない。
- コアスケーラビリティ [paper]: スレッド数 = swap file 数 = コア数として 1→128 に増加。
  ScaleSwap はほぼ線形、Linux swap は 32 コア超で改善なし (Fig. 12b)。
- レイテンシ [paper]: 平均レイテンシ最大 11.5× 減 (Fig. 12c, 12d)。99.9th テールは
  8 SSD で Linux 2395.20µs vs ScaleSwap 87.94µs(27.2× 減)(Table 1)。
- CPU 使用率 [paper]: kernel (system) CPU を平均 25% 削減、idle は最大 16% 増
  (Table 2)。Linux もスレッド並列で swap するが lock 競合で system time を浪費して
  いる、という説明。
- メモリオーバーヘッド [paper]: swap task 事前確保 1,500 個/コア ×128 = 192,000 個 =
  17.57MB、実験中のピーク使用は 66,000–150,000 個(約 6.0–13.7MB)。ピーク総メモリ
  消費は Linux swap 367.79GB vs ScaleSwap 367.78GB でほぼ同一 (Table 3, §5.2)。
- Page fault [paper]: 100,827,862 → 92,280,466(9.15% 減)。per-core LRU がページを
  コアに局所化し、他コアからの干渉と頻繁アクセスページの追い出しを減らすため (§5.2)。
- 実アプリ [paper] (§5.3, Table 4, Fig. 13): BFS(184GB)、DNA visualization(640GB)、
  Python list(256GB)、image gray-scale / flip(各 384GB)。8 SSD で 2.4× / 2.57× /
  1.70× / 1.72× / 1.91×。1 SSD では Linux と同等(Linux も並列 swap 自体は行うため)。
  micro-bench より利得が小さいのはアプリ側の計算比率が高いため(user CPU: stress
  0.29% に対し各アプリ 2.91–45.21%)。
- Apache Spark [paper] (§5.4, Fig. 14): CommonCrawl CC-MAIN-2025-13 の WARC 128
  ファイル(各約 1GB)。コアあたり入力レコード数を変化させ全条件で Linux swap を
  上回る。最大負荷(100,000 records/core)で 6.3GB/s、1.75×。
- vs TMO [paper] (§5.5, Fig. 15): DNA + gray-scale + flip の3アプリ同時実行、zswap の
  圧縮率(10–80%)を変化。ScaleSwap が最大 64% 上回り、圧縮率が上がるほど差が拡大。
  TMO は圧縮/解凍の CPU オーバーヘッドがあり、圧縮上限到達後は結局 swap が発生する
  ため。TMO の主眼は DRAM コスト削減・PSI ベース監視であり、swap 性能最大化の
  ScaleSwap とは目的が異なるという整理。
- vs ExtMEM [paper] (§5.5, Fig. 16): ExtMEM 由来の mmapbench を使用。8 SSD で最大
  5.02× の ops/s。ExtMEM は SSD 追加でほぼ性能向上なし、32 スレッド超で飽和または
  低下。ScaleSwap は 128 スレッドまでスケール。
- 内訳 [paper] (§5.6, Table 5): Linux swap = 4.34GB/s・768.67µs・lru_lock 53.27%・
  si_lock 1.43%。LRU 対策のみの ScaleSwap(LRU) = 8.13GB/s・lru_lock 0.15% だが
  si_lock が 5.03% に浮上。フル ScaleSwap = 14.81GB/s・66.34µs・lru_lock 0.16%・
  si_lock 0%。
- 委譲オーバーヘッド [paper] (§5.7, Table 6): 128 swap file 中 0/16/32/64/96 個を故意に
  満杯化。96 個満杯(残り 32 file)でも委譲回数 202,714,836 回・平均委譲時間 81.76ns で
  ピークの約 84% のスループット(14.81→12.48GB/s)を維持、実行時間は 52→63 秒。
  委譲がメモリ操作のみだから、という説明。stress ワークロードは各スレッドが自分の
  書いたページを読み戻すため、この結果は swap-out / swap-in 双方の委譲を含む。
- [inference] 評価がカバーしていないもの:
  - コアスケーラビリティ実験はスレッド数・swap file 数・コア数を常に一致させて
    掃引しており (Fig. 12b)、「コア数 > swap file 数」「スレッド数 ≫ コア数
    (オーバーサブスクリプション)」の構成での挙動は示されていない。
  - スレッドのコア間マイグレーションや共有ページが支配的なワークロード(委譲ケース
    2 が高頻度化する状況)は Table 6 の「swap file 満杯化」でしか代理されていない。
  - SSD の摩耗・書き込み増幅への影響は未評価(288GB 級の swap トラフィックを
    consumer 向け FireCuda に反復書き込みする構成)。GC と swap I/O の干渉も
    測られていない。
  - マルチテナント(cgroup)環境での分離・公平性は論じられていない。per-core LRU が
    グローバル LRU の近似としてどれだけ eviction 品質を落とすかは、page fault 数
    (stress での 9.15% 減)以外の指標では評価されていない。
  - ZNSwap は related work で言及されるが比較対象ではない(ZNS SSD が前提のため
    と推測される。本文には理由の明記なし)。
  - baseline の TMO 比較は3アプリ同時実行の1構成のみで、TMO が得意とする
    「レイテンシ感度に応じた offload 制御」のシナリオでの比較は無い。
- [question] p.10 (§5.1) は「six memory-intensive applications」と書くが、§5.3 と
  Table 4 は 5 アプリ(BFS / DNA / Python list / gray-scale / flip)のみ。§5.5 の
  mmapbench を含めて 6 と数えている可能性があるが本文からは確定できない。

## Limitations
- Stated [paper]:
  - swap entry の offset を 50→47 bit に縮小したため per-core swap file は最大 128TB
    (現行デバイス容量から妥当と主張)(§4.4.2)。
  - page flag の node bit を 10→7 bit に縮小したため最大 64 node(単一サーバには
    十分と主張)(§4.6)。cpuid 7bit なので core-affinity 管理は 128 コアまで (§4.6)。
  - swap task の事前確保プールが尽きた場合はメモリが空くまで待つ (§4.5)。
  - delegator が sleep 状態だと委譲時間が延びる(cooperative swapping で緩和)(§4.5)。
  - swap-in 委譲の非同期性により、一時的に空き容量を過小報告しうる (§4.7.2)。
  - 満杯 swap file が増えると平均委譲時間は 29.99→81.76ns に増加(それでもピークの
    約 84% を維持)(Table 6, §5.7)。
- Inferred [inference]:
  - 「1 コア = 1 swap file」の対応は静的で、コアごとの swap 需要の偏りには委譲で
    対処する設計。特定コアに swap-out が集中して自分の file だけ満杯になる偏った
    ワークロードでは、そのコアの全 swap-out が委譲経路(+リモート space への直接
    I/O)になる。Table 6 は「満杯 file 数」を変える実験であり、「特定コアへの需要
    集中」の実験ではない。
  - per-core LRU への分割は eviction のグローバルな recency 順序を放棄している。
    stress のような一様なアクセスでは page fault が減る (§5.2) が、コア間でページの
    ホットネスが大きく異なる場合に「あるコアのホットページが追い出され、別のコアの
    コールドページが残る」品質劣化が原理的に起こりうる。本文にこのトレードオフの
    分析は無い。
  - 評価はすべて swap 専有マシンでの実行であり、swap 対象アプリと非 swap アプリの
    混載時に per-core delegator スレッドや busy waiting が他アプリの CPU を奪う影響は
    不明(cooperative swapping は緩和策だが定量評価は Table 6 の委譲時間のみ)。
  - kernel のページ管理コア構造(page flag、swp_entry_t のビットレイアウト)を変更
    するため、既存の swap 周辺機能(例: 本文が type field 予約の例に挙げる
    hardware-poisoned page 処理以外のフラグ利用者)との互換性検証は本文に無い。

## Relations
- 競合 baseline(本文 §5.5): TMO(圧縮メモリ + PSI 監視による offload)、ExtMEM
  (user space へのメモリ管理委譲)。related work では ZNSwap / FlashVM / SSDAlloc
  (OS ベース swap)、ScaleCache / Falcon(all-flash array のスケーリング)、
  Infiniswap / AIFM / TeRM(disaggregated/remote memory)、NOMAD / Colloid
  (tiered memory)と対比 (§6)。
- [[2026-fast-zhan-buffered-io.md]](WSBuffer: buffered I/O の再設計): 同じ FAST '26 で、
  「高帯域 SSD 群の性能をカーネルのロック競合が殺す」という同型の診断を file-backed
  write パス(ページキャッシュ)側で行った論文。ScaleSwap は anonymous page の
  swap パス側で lru_lock / si_lock を攻めており、両者はカーネル内のボトルネック位置が
  相補的。両ノートとも ScaleCache(XArray lock 競合対策の page cache)を参照点に
  している(ScaleSwap 側は §6)。
- [[2026-eurosys-kumar-tierscape.md]](TierScape: 圧縮メモリ tier で TCO 削減):
  ScaleSwap §5.5 の TMO 比較は zswap の圧縮率を掃引しており、「圧縮メモリ tier vs
  flash swap tier」というまさに TierScape が扱う設計空間の一断面。[inference]
  ScaleSwap の主張(圧縮上限到達後は結局 swap が起き、圧縮 CPU コストが利得を
  食う)は、TierScape 型の多段圧縮 tier 構成の最下層に高スループット swap を置く
  ハイブリッドを示唆する。
- [[2026-edbt-krause-disaggregated-survey.md]](disaggregated systems チュートリアル):
  ScaleSwap §2 は disaggregated / tiered memory サーバでも遠隔・階層メモリ容量は
  有限であり、SSD ベース OS swap を「追加の最終メモリ tier」として個々のサーバの
  安定性に使えると位置付ける (§2, §6)。メモリ分離の設計空間を整理する survey 側と、
  その末端 tier の実装を担う本論文で階層が接続する。

## Idea seeds
- [inference] DB エンジンは伝統的に OS swap を避けて buffer manager で
  larger-than-memory を扱う(本論文が mmapbench の出典として引く Crotty らの
  mmap 批判 [24] も同じ文脈)。ScaleSwap は「OS swap がスケールしない」という
  前提側を直接攻撃しているので、「スケールする swap の上なら in-memory DB を
  そのまま over-commit する方が、buffer manager / anti-caching より単純で速い領域が
  あるか」を問い直せる。最初の検証: 公開コード(https://github.com/syslab-CAU/
  ScaleSwap)の kernel 上で、in-memory ハッシュ/ツリー索引ベースの KV を DRAM の
  2–4 倍のデータで動かし、同一ハードの buffer-managed ストレージエンジンと
  スループット・テール・CPU 消費を比較する。
- [inference] per-core LRU による eviction 品質のトレードオフは、DB の buffer pool
  研究(パーティション化 buffer pool、LRU 近似)と同型の問題。stress 以外の
  skewed / 共有アクセスワークロードで「per-core LRU vs per-node LRU の hit rate 差」を
  測る実験は、swap に限らず per-core 化一般の代償を定量化する小粒な貢献になる。
  検証: page fault 数と swap I/O 量を Zipfian アクセス + スレッドマイグレーション
  有無で比較。
- [question] swap は SSD にとってほぼ純粋な random write ストリームであり、247 個の
  swap file を 8 SSD に載せる構成が SSD 内部の GC・書き込み増幅に何をするかは
  本文で扱われない。cluster stride 32 のチャネル並列化 (§4.4.1) は Linux 由来の
  ヒューリスティックのままで良いのか。FDP / placement hint と per-core swap space を
  対応付ける co-design は開いた問題に見える(SSD 側の書き込み経路の一般論は
  [[2026-pvldb-lee-how-to-write-to-ssds.md]] が整理しており、接続先になる)。
  検証: swap 集中負荷での SSD SMART 統計(WAF 代理指標)を Linux swap /
  ScaleSwap で比較するところから。
- [question] 委譲(平均 29.99ns、満杯時 81.76ns)は単一マシンの共有メモリ上の
  MPSC queue だから安い。この core-centric + delegation パターンを CXL メモリプール
  越しの swap(遠隔 swap space)に持ち出したとき、どこまで成立するか。§2 は
  disaggregated/tiered サーバへの適用可能性を主張するが実験は無い。

## Changelog
- 2026-07-06: created (status: read, USENIX 公式 PDF を読解)
