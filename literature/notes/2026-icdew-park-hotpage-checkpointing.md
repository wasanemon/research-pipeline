---
title: "Hot-Page-Aware Checkpointing for Flash SSDs"
authors: [Geunhyun Park, Sang-Won Lee]
venue: "ICDEW (2026 IEEE 42nd International Conference on Data Engineering Workshops)"
year: 2026
ids: {doi: "10.1109/ICDEW71238.2026.00007", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1109/ICDEW71238.2026.00007", pdf: "literature/pdfs/2026-icdew-park-hotpage-checkpointing.pdf", code: ""}
status: read
read_date: 2026-07-06
tags: [checkpointing, flash-ssd, buffer-management, recovery, oltp, mysql-innodb, write-amplification, tpc-c]
---

著者・所属は PDF 冒頭で確認: Geunhyun Park / Sang-Won Lee(責任著者)、いずれも
Seoul National University, Graduate School of Data Science (p.1)。DOI は PDF 掲載の
10.1109/ICDEW71238.2026.00007 と queue メタデータが一致 (p.1)。

## TL;DR
OLTP の skew により、少数の hot page が dirty のまま多数の checkpoint interval に
居座り checkpoint flush に繰り返し選ばれる — TPC-C 実測では「5 回以上連続で
checkpoint に選ばれ続けた page」が checkpoint write の約 51% を占める (Fig. 2)。
提案は page ごとの `checkpoint_count`(deferral の連続回数)と上限
`max_checkpoint_count` だけで checkpoint 起因の flush を有界に先送りする軽量機構
(Algorithm 1)。MySQL/InnoDB に実装し TPC-C(54GB, buffer 50%)で Vanilla 比
1.58× のスループット、write/tx 49% 減 (Fig. 3, Table I)。代償は crash recovery
時間 +30.2%(redo が約 3 倍。Table II)で、著者自身が明示的トレードオフとして提示。

## Problem & motivation
- [paper] SSD は現代 DBMS の事実上の標準ストレージだが、read-write 非対称がある:
  erase-before-write 制約・out-of-place 更新・FTL・GC・write amplification により、
  持続書き込みはコントローラ帯域とデバイス内並列性を消費して read を妨げる。
  read IOPS は write IOPS を数倍〜1 桁以上(例: 13× 超)上回り得る (§II-A)。
- [paper] OLTP の更新は強く skew し、少数の hot page が書き込みの不均衡な割合を
  吸収する。An et al. の引用: write working set(時間窓内に 2 回以上書かれた page)は
  平均でアクセス page 全体のわずか 0.54%(300MB)(§I)。
- [paper] checkpoint は recovery 時間の制限と log 成長の制御に必須だが、
  write-intensive OLTP では大量の background write を注入し、SSD 上で read と競合
  して bottleneck 化する。現行の checkpoint ロジックは「flash-agnostic」で、メモリ
  管理と recovery 境界だけを見て flash への書き込みコストを考慮しない (§I, §II-D)。
- [paper] 実測による問題定量化(TPC-C 2 時間、500 warehouses = 54GB、32 クライアント、
  buffer cache 50%、4KB page、計測用に InnoDB を改造)(§II-C):
  - 大半の page は checkpoint に長く晒されない: 約 62% はちょうど 1 回だけ
    checkpoint を経験し、3 回目までの累積で約 81% (Fig. 1)。
  - 一方で長期滞在する少数派が書き込みを支配: 5 回以上連続で checkpoint に選ばれた
    page が checkpoint write の約 51%、10 回以上が約 20% を占める (Fig. 2)。
    つまり checkpoint 起因の write traffic は少数の long-resident page に強く偏る。
- [paper] hot page の即時 flush は「すぐ再 dirty 化されるのに storage write の
  フルコストを払う」ため durable progress をほとんど生まず、write 量増加 → SSD 摩耗と
  write 起因干渉 → read 遅延 → スループット低下、という経路で全体を劣化させる
  (§I, §II-D)。狙いは checkpoint コストの消去ではなく checkpoint I/O の効率化 (§II-D)。

## System model & assumptions
- [paper] DBMS モデル: buffer pool + WAL の伝統的構成。トランザクションは buffer pool
  内の page を更新して dirty 化し、WAL が update を先に永続化する (§II-B)。
  checkpoint は dirty page を定期 flush して「そこまでの update の回復が保証される
  log 位置」= recovery point を前進させる (§II-B)。
- [paper] recovery 不変条件: update を記述する log record が対応する data page より
  先に安定ストレージへ到達する(WAL invariant)。crash 後は最後の checkpoint された
  recovery point から log replay で再構成する。提案はこの不変条件と WAL プロトコルを
  一切変更しない (§III-C)。
- [paper] ストレージ仮定: flash SSD(NVMe)。read が write より速く・低破壊的で
  あることが前提の最適化(§II-A)。評価は DB 用と log 用で物理的に別の SSD (§IV-A)。
- [paper] ワークロード仮定: 更新が skew した write-intensive OLTP。少数 page 集合が
  dirty 生成の大半を占め、buffer pool がそれらを複数 checkpoint interval にわたり
  保持できることが前提 (§I, §II-D)。実際、buffer が DB の 10–20% しかないと dirty page
  は checkpoint 滞在前に evict され、deferral の機会自体が消える (§IV-D)。
- [paper] hotness の定義: write アクセス回数では**なく**、「dirty のまま連続する
  checkpoint interval を跨ぎ、繰り返し checkpoint flush 対象に選ばれること」。
  これが冗長 writeback を最も起こしやすい page だから、という理由付け (§III-A)。
- [paper] deferral の適用範囲: checkpoint 起因の flush のみ。LRU flush・eviction・
  明示的 single-page flush は無制限に従来通り動き、メモリ圧下ではいつでも page を
  書ける(既存 buffer 管理との互換性を維持)(§III-A, §III-B)。
- [paper] 有界性: deferral は `max_checkpoint_count` で必ず打ち切られ、上限到達で
  強制 flush → eventual persistence と checkpoint 前進を保証。「わずかに遅れた
  persistence と引き換えに checkpoint I/O 効率を得る」トレード (§III-B, p.4)。
- [paper] 実装対象: MySQL/InnoDB、トランザクション意味論は不変更と主張(貢献の列挙で
  「transactional semantics を変えずに組み込めることを実証」)(§I, §III-D)。
- [inference] 単一ノード DBMS・単一デバイス障害なし(crash-restart のみ)のモデル。
  レプリケーションやクラウド分離ストレージは扱っていない。また checkpoint は
  「cycle(候補選定の周期)」を持つ interval ベースの実装が暗黙の前提で、
  incremental/fuzzy checkpoint の変種間の違いは論じられていない。
- [inference] 効果の前提条件として「flush 時間の大半が checkpoint 起因」であることが
  効いている(Vanilla は buffer 50% で flush 時間の 99.1% が checkpoint。Table I)。
  この比率が小さい構成(小 buffer)では §IV-D の通り逆効果になる。

## Approach
- [paper] **データ構造**: 各 dirty page に `checkpoint_count` フィールドを 1 個追加。
  意味は「連続して checkpoint に選ばれ、flush でなく deferral に終わった回数」。
  グローバル設定 `max_checkpoint_count` が deferral 回数の上限 (§III-B)。
- [paper] **Algorithm 1**(checkpoint 時): flush list 上の各 page について、
  `ckpt_count < max_ckpt_count` なら count を +1 して page をその cycle の
  checkpoint 候補集合から外し、write を発行しない。上限に達していれば FLUSH する
  (Algorithm 1, §III-B)。flush 到達時に counter はリセット (§III-B)。
- [paper] **counter のリセット規則**: page が(どの経路でも)正常に flush された時、
  または evict された時に `checkpoint_count` をリセットし stale 状態を防ぐ (p.4)。
- [paper] **介入点の局所性**: dirty page の flush list 挿入や通常の候補管理は不変更。
  hot-page 判定は「checkpoint サブシステムが page を flush 対象に選んだ瞬間」だけで
  発動し、InnoDB では候補選定直後・I/O サブシステムへの dispatch 直前に介入する
  (§III-B, §III-D)。foreground の update ロジックと WAL プロトコルは触らない (§III-A)。
- [paper] **オーバーヘッド**: counter 更新は checkpoint 選定時のみ発生するため、
  コストは read/write 毎ではなく checkpoint 選定頻度に比例。同期も flush 判断に
  既存する同期をそのまま使う (§III-B)。per-page メタデータとリスト操作の最小限の
  追加のみ、と主張 (§III-D)。
- [paper] **効果の理屈**: すぐ再 dirty 化される page への write は一時的な進捗しか
  生まないので、deferral により checkpoint の労力を「writeback 後 clean に留まり
  やすい page」へ振り向け、checkpoint I/O の効率を上げる (§III-B)。
- [paper] **recovery への影響設計**: 有界 deferral 予算により eventual persistence を
  保証し、checkpoint 前進は引き続き log 成長と redo 範囲を制約する。recovery は
  通常通り進行 (§III-C)。
- [inference] 機構は本質的に「checkpoint 候補フィルタ」1 段であり、hot 判定に
  アクセス頻度・再 dirty 化予測などの状態を一切持たない。この単純さ(page あたり
  counter 1 個)が売りだが、裏返すと deferral 判断は page の将来の更新確率とは
  無相関で、`max_checkpoint_count` の静的チューニングに全てを負わせている。

## Evaluation
- Setup [paper]: Linux サーバ、Intel Xeon Silver 4216(2.10GHz, 16 cores / 32
  threads)、128GB DRAM。DB 用 Samsung SSD 970 EVO Plus 250GB + log 用 Samsung SSD
  970 EVO 1TB(いずれも NVMe/PCIe)、ext4 + direct I/O。page size 4KB、クライアント
  32 スレッド、tpcc-mysql で TPC-C、DB は 54GB(500 warehouses)(§IV-A)。
  ベースラインは Vanilla MySQL のみ。
- Headline(buffer 50%, 1 時間実行)[paper]: warm-up 後の定常状態で一貫して優位、
  平均スループット 1.58×。差は持続的で、短期バーストでなく checkpoint 干渉の
  持続的削減を反映と主張 (Fig. 3, §IV-B)。
- Table I(buffer 50%)[paper]:
  - TPS 630 → 995。write/tx 67.3KB → 34.3KB(49% 減)、read/tx 19.1KB → 16.6KB。
  - デバイスレベル: 持続 write 帯域 41.4 → 33.3 MB/s(20% 減)、持続 read 帯域
    11.7 → 16.1 MB/s(38% 増)= write 起因干渉の減少と整合。
  - User CPU 26.5% → 40.6%(I/O 律速から有用作業へシフト)。
  - flush 構成: checkpoint flush の時間比 99.1% → 43%、LRU flush 0.9% → 56.9%
    (hot page の checkpoint flush を遅延させ cache 管理駆動の flush に委ねる設計意図
    と整合)。
- Buffer size 掃引(10–50%)[paper]: 30% 以上で一貫して Vanilla に勝ち、メモリが
  増えるほど差が拡大。**10–20% では逆に Vanilla を下回る**: 小 buffer では eviction
  支配で(checkpoint flush は write traffic の 30% buffer 時 64% に対し 20% buffer 時
  22% のみ)、dirty page が複数 checkpoint を跨ぐ前に evict され deferral の機会が
  ない。加えて deferral は clean frame を減らし緊急 eviction flush を増やす (Fig. 4, §IV-D)。
- `max_checkpoint_count` 掃引 {3,4,6,8,10}(buffer 50%)[paper]:
  - checkpoint flush 比率は単調減少: 約 43% (3) → 28% (4) → 21% (6) → 18% (8) →
    17% (10) (Fig. 5, §IV-E)。
  - TPS は非単調: 約 1,000 (3) → 約 1,250 (4, 6) → 最大約 1,340 (8, 3 比で約 +35%)
    → 約 1,260 (10)。checkpoint flush 比率の最小化 ≠ 性能最大化で、過剰 deferral は
    delayed writeback や buffer replacement 側へ圧力を移すと考察 (Fig. 5, §IV-E)。
- Recovery(`max_checkpoint_count` = 3、redo log 15GB)[paper]: 総 recovery 時間
  1,895.6s → 2,467.3s(+30.2%)。内訳は analysis 1,655 → 1,761s、redo 240 → 706s
  (約 3 倍)、undo 0.6 → 0.3s。ペナルティは rollback 増でなく redo 範囲の拡大で、
  両システムとも analysis 支配のため総時間は redo ほどは伸びない (Table II, §IV-F)。
- [inference] 評価がカバーしていないもの:
  - ベースラインが Vanilla MySQL 1 点のみ。flush/checkpoint ポリシー系の先行最適化
    (自引用されている read 優先 I/O スケジューリング [7][8] や LRU-C [10] を含む)
    との比較がなく、「checkpoint 側をいじる」アプローチ内での相対的位置が不明。
  - ワークロードは TPC-C 1 種・skew 1 点・32 クライアント固定。skew 度や
    クライアント数への感度は無い。
  - SSD endurance 改善は主張されるが、測定はホスト観測の write 量のみで、
    デバイス内 WAF・GC 活動の直接測定は無い。DB 54GB / 250GB SSD(約 22% 充填)+
    log 別デバイスという、GC 圧・干渉が出にくい構成である点にも注意。
  - Table I の Ours(995 TPS)は Fig. 5 の count=3(約 1,000 TPS)と整合するので、
    headline の 1.58× はおそらく count=3(最も保守的な deferral)の数値。一方
    recovery 測定(+30.2%)も count=3 のみで、TPS 最良の count=8 における recovery
    コストは未測定 — 「1.58×」と「+30.2%」は同一設定だが、性能を最大化した場合の
    recovery 代償は本文から読めない。
  - deferral が checkpoint age / log 消費に与える影響の直接測定(log 量の時系列や
    checkpoint LSN の進み)は無く、recovery 時間 1 点で代理されている。
  - tail latency の測定が無い(motivation は latency-sensitive read の遅延なのに、
    報告はスループットと帯域のみ)。

## Limitations
- Stated [paper]:
  - recovery 時間が +30.2%(redo は約 3 倍)。「定常性能の改善は、より多くの dirty
    状態を checkpoint interval を跨いで保持することで得ており、crash recovery に残る
    仕事を増やす」と明示的トレードオフとして提示 (Table II, §IV-F)。
  - runtime スループットと recovery 時間を同時最適化する adaptive checkpoint deferral
    control は future work (§IV-F)。
  - buffer が小さい(DB の 10–20%)と Vanilla を下回る(deferral 機会が無いのに
    追跡・再考のオーバーヘッドと clean frame 減少だけ払う)(§IV-D)。
  - deferral 予算を上げすぎる(count=10)と TPS がわずかに低下(圧力が delayed
    writeback / buffer replacement へ移る)(§IV-E)。
- Inferred [inference]:
  - §I には「our proposed method ensures recovery-time objectives remain intact,
    reassuring risk-averse stakeholders」(p.1) とあるが、Table II の実測は総 recovery
    時間 +30.2%。「有界の deferral だから eventual persistence は保たれる」(§III-C)
    という主張と読み替えれば整合するが、「recovery-time objectives が intact」は
    実測と緊張関係にあり、intro の表現は過大。recovery SLO が厳しい運用では
    count の選択自体が SLO 制約問題になる。
  - `max_checkpoint_count` は静的なグローバル 1 パラメータで、最適値(この設定では 8)
    は buffer サイズ・skew・checkpoint 頻度に依存するはず。設定間での可搬性は
    示されていない(著者も adaptive 制御を future work とする)。
  - flush 構成が checkpoint 99.1% → LRU 56.9% へ大きくシフトしており (Table I)、
    削減効果の一部は「checkpoint 経路から LRU 経路への write の付け替え」を含む。
    write/tx が半減しているので純減はあるが、経路別の page 単位 write 帰属
    (deferral で本当に消えた write vs 移動した write)は分解されていない。
  - counter は「どの経路でも flush されたらリセット」(p.4) なので、LRU flush が
    活発な領域では hot page が deferral 上限に達する前にリセットされ続け、機構が
    意図した「hot page の write 削減」から外れる可能性がある(§IV-D の小 buffer での
    逆転はこの現象の極端例と読める)。
  - デバイス側の検証が単一のコンシューマ SSD(970 EVO Plus 250GB)1 台・低充填率。
    endurance / WA の主張をエンタープライズ SSD や高充填率で支える測定は無い。

## Relations
- [[2026-pvldb-lee-how-to-write-to-ssds.md]]: 同じ「flash への書き込み削減」軸の
  相補関係。あちらは Total WAF = DB WAF × SSD WAF という乗算構造を踏まえ
  out-of-place 化とデバイス協調で SSD WAF≈1 を狙う。本論文はその乗算の上流、
  ホストが発行する write 量そのもの(write/tx 67.3 → 34.3KB, Table I)を checkpoint
  ポリシーで削る。[inference] 両者は層が異なり原理的に併用可能で、掛け算で効くはず。
  なお旧ノートの [question](第一著者 Lee が本論文の Sang-Won Lee と同一人物か)は
  解消: あちらの第一著者は Bohyun Lee で別人。ただし本論文 ref [10](LRU-C)の著者は
  「B. Lee, M. An, and S.-W. Lee」(p.6) であり、[question] この B. Lee が同一人物か
  (= 両グループに人的連続性があるか)は未確認。
- [[2026-pvldb-kuschewski-btrlog.md]]: checkpoint は「log 成長の制御」機構 (§II-B)
  であり、WAL サービス側(BtrLog)と checkpoint 側(本論文)は log 管理コストの二面。
  本論文の deferral は recovery point の前進を保守化し redo 範囲を広げる (§IV-F) ので、
  [inference] log 保持コストが高いクラウド WAL(BtrLog の設定)では deferral の
  「log を長く保持する」副作用が本論文のローカル構成より高くつく可能性がある。
- [[2026-fast-bian-discard-gc.md]]: 接点は「冗長 write の削減を endurance / TCO に
  結びつける」評価軸だが、あちらは分散 log-structured ストレージの GC 層、本論文は
  DBMS の checkpoint 層で、直接の競合・依存関係はない。

## Idea seeds
- [inference] 著者が future work とする adaptive deferral control (§IV-F) は、
  「redo 範囲(checkpoint age)を制約、deferral を決定変数」とする制約付き最適化として
  素直に定式化できる。Fig. 5 の TPS 非単調性と Table II の redo 3 倍が示す通り、
  count は性能と recovery の両方に非線形に効く。最初の検証: 本論文と同じ InnoDB 設定で
  count ∈ {3..10} の各点について TPS と recovery 時間の両方を測り(本文は recovery を
  count=3 でしか測っていない)、パレート前線を描く。
- [inference] `checkpoint_count` はホスト側の安価な「dirty 滞在時間」シグナルで、
  デバイス側の hot/cold 配置制御(multi-stream / FDP)と直交する。deferral で残った
  hot page write を専用 stream に隔離すれば、how-to-write-to-ssds 系の乗算 WAF 削減と
  重ねられるはず。検証: deferral 単体 / 配置制御単体 / 併用で、ホスト write 量と
  デバイス WAF を分解測定する。
- [question] counter が「任意経路の flush でリセット」される設計 (p.4) は、LRU flush が
  支配的な構成(Table I の Ours 側ですでに flush 時間の 56.9%)で deferral の効果を
  どれだけ食い潰すのか。page 単位で「checkpoint deferral 中に LRU flush された回数」を
  計測すれば、checkpoint ポリシーと replacement ポリシーを統合設計すべきか(例:
  deferral 中 page の eviction 優先度を下げる)が判断できる。
- [inference] 小 buffer での逆転 (§IV-D) は、checkpoint flush の write traffic 比
  (20% buffer で 22%、30% で 64%)という観測可能な指標で予測できる。この比率を
  オンラインで監視して deferral を自動 on/off するだけの適応策は実装が数十行で済み、
  本手法の「設定を誤ると悪化する」欠点を消せる可能性がある。最初の検証: buffer 10–50%
  掃引で閾値ベースの gating を入れた版と Fig. 4 を再現比較する。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: full-text 格上げ(status: abstract-only → read。手動取得した PDF 全文を読解し全節を執筆)
