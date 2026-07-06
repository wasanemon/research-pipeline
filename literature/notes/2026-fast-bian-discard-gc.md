---
title: "Discard-Based Garbage Collection for Distributed Log-Structured Storage Systems in ByteDance"
authors: [Runhua Bian, Liqiang Zhang, Jinxin Liu, Jiacheng Zhang, Jianong Zhong, Jiahao Gu, Hao Guo, Zhihong Guo, Yunhao Li, Fenghao Zhang, Jiangkun Zhao, Yangming Chen, Guojun Li, Ruwen Fan, Haijia Shen, Chengyu Dong, Yao Wang, Rui Shi, Jiwu Shu, Youyou Lu]
venue: "FAST '26 (24th USENIX Conference on File and Storage Technologies)"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/fast/BianZLZZGGGLZZC26"}
urls: {paper: "https://www.usenix.org/conference/fast26/presentation/bian", pdf: "literature/pdfs/2026-fast-bian-discard-gc.pdf", code: ""}
status: read
read_date: 2026-07-06
tags: [garbage-collection, log-structured, discard, trim, write-amplification, space-amplification, distributed-storage, ssd, erasure-coding, production-experience, tco]
---

## TL;DR
ByteDance の分散 append-only ストレージ(ByteStore)上のブロックサービス
(ByteDrive)では、compaction のみの GC が write amplification (WA) と
space amplification (SA) の負の相関トレードオフを生み、月数百万ドルの TCO 増を
招いていた。DisCoGC は「長く連続した stale 範囲」を valid データ移動なしに
in-place で回収する discard を GC の主役にし、低頻度 compaction を断片化・
メタデータ肥大の解消役に回す combined GC。多層スタック(EC stripe / cluster /
sector header)での boundary loss、メタデータ更新負荷、SSD の trim IOPS 制限を
境界拡張・バッチング・trim filter/merger で解決し、本番クラスタで SA 10% 減 +
総 WA 25% 減 = TCO 約 20% 減を性能劣化なしで達成した。

## Problem & motivation
- [paper] ByteStore は ByteDance 全ストレージサービス(ByteDrive/TOS/NAS/
  ByteGraph/ByteNDB)の基盤となる分散 SSD ベース append-only ストレージ。本論文は
  ByteDrive + ByteStore スタックに焦点 (§1, §2, Fig. 2)。
- [paper] 初期の ByteDrive は compaction ベース GC(valid データを新 LogFile に
  書き直して旧 LogFile を削除)を採用。compaction の最適化を試みた結果、WA と SA が
  負に相関する根本的トレードオフに直面: SA を下げる aggressive compaction は
  logical WA を上げ、SSD 摩耗を早め、フォアグラウンド I/O と競合する (§1, Fig. 1, §3.1)。
- [paper] WA は logical(compaction の valid データ再書込み)と physical(SSD 内部の
  GC・wear leveling)の積: WA = LWA × PWA (§3.1)。
- [paper] この WA/SA が ByteDance で月数百万ドルの追加 TCO を生んでいた (§1, §3.1)。
- [paper] トレース分析の動機付け: AI モデル DL/推論・転置インデックス構築更新・
  分散計算(Spark 等)のワークロードは書込みの過半が 256KiB 超の連続範囲を変更し、
  数秒以内の頻繁な overwrite を示す → LogFile 上に長く連続した stale 範囲ができる (§1)。

## System model & assumptions
- [paper] **階層スタック**: アプリ → ストレージサービス(ByteDrive 等)→ ByteStore。
  ByteDrive は compute-storage disaggregation 構成で仮想ディスク(volume)を提供し、
  数千クラスタ・エクサバイト規模を管理 (§2, Fig. 2, p.3)。
- [paper] **ByteDrive の2層構造** (§2.1, Fig. 3):
  - Volume Layer: 4KiB ブロック粒度の random read/write/**trim** インターフェース。
    volume の LBA 空間は segment に分割され複数 BlockServer に分散。segment→server の
    対応は BlockMaster が管理し BlockClient にキャッシュ。128KiB stripe を round-robin
    で segment に散布。
  - Segment Layer: random write を append-only 化。ブロック単位で圧縮(LZ4/deflate)し
    ヘッダを付けて ByteStore へ append。LBA→最新物理アドレスの索引を **LSM-Tree** で管理。
- [paper] **ByteStore**: LogFile(append/read/seal インターフェース)でデータ管理。
  LogFile は最大 2GiB に制限(GC 柔軟性のため)。segment は 1 個の active LogFile +
  0 個以上の sealed LogFile に対応。LogFile は chunk(数十〜数百 MiB、可変)で構成され、
  chunk は EC またはレプリカで冗長化され異なる ChunkServer に配置。MetaServer が
  LogFile 属性と chunk 属性を管理 (§2.2.1)。EC/replication プロトコルとエラー回復は
  heavyweight クライアント SDK 側で実装 (§2.2.1)。
- [paper] **ChunkServer 上の userspace filesystem (UFS)**: Ext4/XFS を置換。各 4KiB
  sector は先頭 32B ヘッダ(CRC・データ長)+ 4064B データの self-contained 単位。
  **cluster = 4 sector** が割当単位。MetaPage zone に cluster 割当と chunk→cluster
  対応を保持 (§2.2.2, Fig. 4)。BlockServer の圧縮のため ChunkServer 上での 4KiB
  データ整合は非現実的かつ不要(脚注2, p.5)。
- [paper] **SSD 仮定**: 評価に使う SSD は Model A(PCIe5.0, 7.68TiB, TLC, trim IOPS
  160K)と Model B(PCIe4.0, 7.5TiB, TLC, trim IOPS 6K)(Table 2)。SSD の trim は
  2 相実装(FTL が trim log を前景書き、write cache を無効化して即完了通知、
  LBA-PBA 表更新は背景)のため、閾値(Model A で例 128MiB)未満のサイズなら
  レイテンシは 1ms 未満で一定 (§4.5)。**trim IOPS の上限はモデル依存で、write IOPS
  よりはるかに低い場合がある**(Model B は write IOPS の 3%)(§4.5, Table 2)。
- [paper] **ワークロード仮定**: TCE(コンテナエンジン)が ByteDrive volume を Ext4 で
  フォーマットして使用 (§3.2, Fig. 7)。3 分類のトレース(Table 1):
  ➀ online(リアルタイム・频繁スケジューリング)、➁ SAR(検索・広告・推薦:転置
  インデックス構築更新 + AI モデル DL/推論)、➂ offline(長期分散計算)。
  - online: merge 後も断片的 — 60% 超が 4KiB 書込み、256KiB 超は 12% のみ (§3.2.2)。
  - SAR: 最良の逐次性 — merge 後 65% が 256KiB 超、4KiB は 15% (§3.2.2)。
  - offline: 55% が 256KiB 超 (§3.2.2)。
  - SAR/offline は局所ホットスポットへの频繁 overwrite を示す(Takeaway 2: 大きく
    連続した garbage を生む。online は断片 garbage)(§3.2.3, Fig. 10)。
  - SAR/offline には予測可能な日次サイクルがなく、夜間 GC 前提は成り立たない
    (Takeaway 1)(§3.2.1, Fig. 8)。
- [paper] **運用制約**: 本番の ByteDrive は突発大量書込みに備え SSD 空間の 20% 以上を
  予約(最大使用率 80%)(§6.5.1)。
- [paper] **障害モデル(discard メタデータ)**: discard 関連メタデータは BlockServer
  メモリ上にあり、クラッシュ整合性は per-segment の discard LogFile への WAL で保証。
  ByteStore 本体の整合性は元設計で担保 (§5)。
- [inference] 有効性の前提は「garbage が長く連続している」ことに尽きる。この性質は
  ゲスト側(コンテナ内 Ext4 上のアプリ)の書込みパターン由来であり、DisCoGC 自体は
  それを作り出せない。ワークロード適合判定をトレース分析に委ねるのはこのため
  (§7 の採用基準がそれを裏書きしている)。

## Approach
- [paper] **LogFile discard 機構** (§4.1, Fig. 11): 5 ステップの top-down 非同期処理。
  ➀ BlockServer が segment ごとの LSM-tree をスキャンし未 discard の invalid 範囲を
  特定 → ➁ SDK 経由で discard 要求発行 → ➂ SDK が LogFile 範囲を chunk 範囲へ写像し
  レプリカを特定 → ➃ 各 ChunkServer の UFS が cluster を特定し MetaPage を更新して
  解放 → ➄ BlockServer が成功範囲を記録(再 discard 防止)。valid データの読出し・
  再書込みが不要なので、WA を増やさずに SA を下げる (§4.1)。
- [paper] **課題1: boundary loss** (§4.2, Fig. 12): 層間の割当単位不整合により境界の
  garbage が回収できない。(1) EC loss — discard は完全な EC stripe 単位でしか実行
  できず、BlockServer の要求は任意サイズ(例: 36% 損失)。(2) cluster loss — EC stripe
  のパケットは 4KiB 倍数だが UFS の割当単位は 4×4064B cluster(例: 25.6% 損失)。
  例では境界損失合計 50% 超 (Fig. 12)。対策は2つ:
  - **境界拡張**: discard は同一範囲に対し再入可能(reentrant)なので、隣接する
    discard 済み範囲がある場合は現在の discard 範囲を数 MiB まで重ねて拡張し、
    前回の境界 garbage も回収しつつ新たな境界損失を防ぐ (§4.2, Fig. 13)。
  - **discard-friendly EC stripe**: stripe unit サイズを n×4×4064B に設定して cluster と
    整合させ、cluster loss を除去。LogFile は任意サイズ要求を許容するので書込み・
    discard 効率に影響しない (§4.2, Fig. 14)。
- [paper] **課題2: メタデータ更新負荷** (§4.3): discard 1 件ごとに MetaPage 更新
  (SSD 書込み + CPU)が要る。対策:
  - **バッチング**: 同一 LogFile の複数範囲を 1 discard 要求に集約(最大範囲数は
    1〜64 で設定可能)。
  - **並列度制御スケジューラ**: discard タスクは segment 粒度で生成し並列度を P で
    上限。周期的に discard 範囲が最大の top-k segment を選択(k は P と実行中タスク数
    から算出)。
  - **フロー制御**: 最大 discard IOPS を制限してバースト時の性能変動を抑制。
- [paper] **課題3: 断片化と compaction の協調** (§4.4): discard は LogFile/chunk を
  疎・断片化させ、BlockServer の LogFile 索引・MetaServer の chunk 索引・UFS の
  MetaPage のメタデータを肥大させる。compaction と discard は相補的(compaction は
  断片化を防ぐが WA を生む、discard は逆)なので、**軽量高頻度の discard を主回収
  機構、低頻度 compaction を断片化・メタデータ圧縮役**とする協調戦略を採る。
  - garbage ratio (GR) 計算は boundary loss を組み込み補正: 境界あたり損失 LPB を
    EC stripe 長の半分と推定し GR = 1 − ValidData / (TotalData + LPB × Boundaries) (§4.4)。
  - compaction は dual-mode スケジューリング(分オーダーの間隔): 通常は GR 最大の
    top-k segment を選ぶが、LogFile 数が閾値を超えたら LogFile 数最大の top-k segment
    選択に切替えてメタデータ負荷を緩和 (§4.4)。
  - DisCoGC は断片化により PWA を 2%〜10% 増やすが、データ移動削減により NAND への
    総書込みバイトは減り、寿命はむしろ延びる (§4.4)。
- [paper] **課題4: SSD trim IOPS 不足** (§4.5): trim が遅れると UFS 空間枯渇や
  aggressive な SSD GC による前景品質低下を招く。UFS 内に **trim filter**(大きい
  範囲のみ trim、例: 128KiB 以上)と **trim merger**(LBA 隣接の小範囲を併合して 1 コマンド
  で trim)を実装し、限られた trim IOPS を有効活用。代償はわずかな PWA 増 (§4.5)。
- [paper] **デプロイと実装** (§5):
  - 段階的展開: 重要度の低い offline クラスタから開始、volume 単位で有効化。canary
    段階では実データを解放しない **mock discard**(メモリ上でステータスのみ記録)で
    ソフトウェア正当性を検証してから大規模展開。
  - クラッシュ整合性: "issued" 範囲を §4.1 ステップ➀後、"successfully discarded"
    範囲をステップ➄後に per-segment discard LogFile へ WAL 永続化。再起動時に両者を
    突き合わせ、中断された discard をリトライ。
  - メモリ管理: LogFile ごとに issued/成功の 2 bitmap(1 bit = 非圧縮データ 4KiB)。
    garbage 範囲が長く連続する性質を利用し roaring bitmap で半減。さらに成功 bitmap の
    代わりに疎な "failed bitmap" を保持し S = I & (~F) で導出、合計サイズをさらに
    25%〜45% 削減。

## Evaluation
- Setup [paper]: 本番クラスタ(サーバ = dual 24C48T CPU、256GiB DRAM、200Gbps NW、
  SSD 16 台)+ 同一構成 10 台の offline テストベッド。§3.2 の 3 トレースと FIO を
  使用。SSD は Table 2 の Model A/B(既定は A)(§6.1)。ベースラインは compaction-only
  GC (§6.4)。
- [paper] **本番(mixed workload)**: SA をベースライン 1.37 / DisCoGC 1.23 に維持した
  状態で、invalid 範囲の 90% 超が 128KiB 超・70% 超が 1MiB 超(mixed でも discard 適性
  あり)(Fig. 16)。LWA は **32% 減**、SA 10% 減、PWA は最大 10% 増、**総 WA 25% 減**、
  **TCO 約 20% 減** (§6.2, Fig. 15a)。レイテンシと per-TiB-volume 帯域への影響は無視
  できる (Fig. 15b,c)。
- [paper] **ワークロード横断**: SA–LWA 曲線が 4 ワークロード全てで左下にシフト
  (Fig. 17)。SAR が最大の恩恵(TCO 25% 超削減と推定)、online は断片 garbage のため
  最小だが、最悪でも compaction-only にフォールバックして 2%〜5% の TCO 節約 (§6.3)。
  前景書込みレイテンシへの影響は全ワークロードで無視できる (Fig. 18)。
- [paper] **要因分析**(SA 固定: online 1.2 / SAR 1.05 / offline 1.2)(§6.4, Fig. 19):
  +Discard(+フロー制御)で LWA 8.4%〜13.9% 減(discard ratio 0.45〜0.88 = フロー制御
  が一部要求を絞る)。+Batch(バッチサイズ 64)でさらに 2.7%〜11.7% 減、discard ratio
  はほぼ 1 に。+BoundExt でさらに 5.5%〜16.1% 減。前景帯域・レイテンシは全構成で安定。
- [paper] **SSD 使用率感度**(offline トレース、SA=1.2): 使用率が高いほど PWA 増
  (SSD GC が aggressive 化)だが LWA と前景レイテンシは不変 (§6.5.1, Fig. 20)。
- [paper] **フロー制御感度**(FIO 8MiB random write / 64KiB ブロック、SA=1.5):
  discard IOPS 上限が高いほど LWA は下がるが、CPU 競合により前景レイテンシは悪化
  (0 IOPS = compaction-only)(§6.5.2, Fig. 21)。
- [paper] **trim 最適化**(FIO、境界拡張等は有効)(§6.6, Fig. 22):
  - Model A(trim IOPS 160K): trim 有効化で PWA 1.4→1.3(delete latency +600µs は許容)。
    +Filter は PWA 1.35 に微増(元々 trim IOPS 5K/s で上限に達しておらず、filter は
    むしろ劣化)。+Merge で 1.33。
  - Model B(trim IOPS 6K): trim のみでは上限到達で PWA・delete latency とも非常に高い。
    +Filter(128KiB)で PWA 1.74 / trim IOPS 2.8K / delete latency 34ms、+Merge で
    PWA 1.65。trim なしは SSD GC 能力も低くシステムがより早く破綻するため未評価 (§6.6.2)。
- [paper] **CPU/メモリ**(offline トレース、使用率 60%、SA=1.25): CPU は
  compaction-only の 82.9%(compaction 削減のため)、メモリは 102.9%(bitmap 分)(§6.7)。
- [paper] **運用知見** (§7): バッチサイズ上限 32〜64(チューニング後、多くの場合の実効
  バッチサイズは ~10)、最悪時 CPU
  増を 2% 未満・平均 1.2% に制御。trim filter サイズは trim IOPS が SSD 上限の 85%
  未満になるよう調整。監視は「SSD 使用率 85% 超かつ増加中に discard ratio が 10 分超
  80% 未満」で SRE にアラート。
- [inference] 評価の空白:
  - 比較対象は自社の compaction-only GC のみで、関連研究の GC 手法(§8 で言及される
    Slack Space Recycling、IPLFS 等)との定量比較はない。
  - TCO 20% 減の算出モデル(SSD コスト・電力・何を含むか)は本文に示されておらず、
    検証不能なヘッドライン数値である。
  - トレースは全て ByteDance 内部のもので、Table 1 の 3 本(1.7〜2.6 日分)に基づく。
    外部再現の手段(トレース公開・コード公開)は本文に記載がない。
  - read 性能への影響は「読み統計は今後の研究のために提示」(§3.2)とある一方、
    discard による LogFile 疎化が read パスに与える影響の測定は見当たらない。
  - SSD は TLC NVMe 2 モデルのみ。trim 閾値(128MiB 等)の一般性は「様々な SSD モデル
    での経験的観察とベンダーとの議論」(§4.5)に依拠しており系統的測定ではない。

## Limitations
- Stated [paper]:
  - random で断片化したワークロードでは利益が実装コストに見合わない(採用基準 (2))(§7)。
  - DisCoGC は断片化により PWA を 2%〜10% 増やす (§4.4)。
  - trim 最適化の有効性は SSD モデルの最大 trim IOPS に依存し、不足する SSD では
    filter/merger の追加最適化が必須 (§6.6, §7)。
  - バースト時は discard だけでは回収しきれず、compaction による回収に頼る (§7)。
- Inferred [inference]:
  - boundary loss の GR 補正は「LPB = EC stripe 長の半分」という推定であり(§4.4)、
    実測追跡はメモリコストを理由に放棄されている(§4.2 冒頭)。推定が外れると
    compaction 対象選択が歪む可能性があるが、その感度評価はない。
  - stale 範囲の特定は Segment Layer の LSM-tree スキャンに全面依存する(§4.1)。
    つまり「何が garbage か」を上位層が正確に知っているスタック(自前のブロック
    サービス)に閉じた設計で、ゲスト FS の削除を volume trim として受け取れない
    ケースや、索引を持たない append-only 利用者(TOS 等他サービス)への一般化は
    本文では示されていない(評価は ByteDrive のみ)。
  - bitmap は非圧縮データ 4KiB あたり 1 bit × 2 枚 / LogFile で、圧縮後も
    メモリ +2.9% (§6.7)。LogFile 数が閾値超過で compaction モードが切り替わる設計
    (§4.4)自体が、メタデータ肥大が実際に効いてくることの証左に見える。

## Relations
- [inference] [[2026-pvldb-lee-how-to-write-to-ssds]](WA 最適化 / out-of-place 書込み)
  と同じ問題圏: 本論文は WA = LWA × PWA の分解(§3.1)のうち、LWA をホスト側 GC 設計で
  削り、PWA を trim 活用で抑える具体例。
- [inference] [[2026-pvldb-liu-arcekv]](LSM compaction)と相補: ArceKV が扱う LSM
  compaction のコストと、本論文の LogFile compaction の WA/SA トレードオフ(§3.1)は
  同型の問題。ただし本論文の索引 LSM-Tree(§2.1)自体の compaction は本論文の
  スコープ外。
- [inference] [[2026-pvldb-kuschewski-btrlog]](クラウド WAL サービス)と同じ
  「クラウドの分散 append-only ログ基盤」レイヤの論文だが、BtrLog が書込みパス、
  本論文は回収パス(GC)を扱う。

## Idea seeds
- [inference] DisCoGC の「discard の再入可能性を利用した境界拡張」(§4.2)は、
  多層ストレージ一般で使える trick に見える。LSM ベース KV(圧縮ブロック単位と
  ファイルシステム割当単位の不整合)にも同じ boundary loss があるはずで、
  「compaction ではなく hole punch(FALLOC_FL_PUNCH_HOLE 相当)+ 境界拡張」で
  SSTable の部分無効化ができるか検証する価値がある。第一実験: RocksDB の
  DeleteFilesInRange 相当を範囲 punch に置き換えた際の SA/WA を fio + db_bench で測る。
- [question] trim IOPS がモデル間で 160K vs 6K と 26 倍超も違う(Table 2)なら、
  ストレージエンジンの GC 方式選択(discard 主体 vs compaction 主体)は SSD の
  trim 特性を入力とする適応制御にできるのではないか。論文は静的なチューニング指針
  (§7)に留まる。第一実験: trim IOPS をオンライン計測し filter 閾値を動的に調整する
  コントローラを模擬環境で比較。
- [question] GR 補正の LPB = EC stripe 長 / 2 という推定(§4.4)の妥当性は
  ワークロード依存のはず(境界の位置分布に依存)。boundary loss を安価に
  サンプリング推定する軽量スケッチ(例: 境界オフセットの mod 分布)で置き換えたら
  compaction 対象選択がどれだけ改善するか、トレース再生で検証できそう。

## Changelog
- 2026-07-06: created (status: read, USENIX 公式 PDF 抽出テキストを全文読解)
- 2026-07-06: 検証パスによる修正(バッチサイズ ~10 を「平均」→「多くの場合」に訂正 [§7]、トレース期間 2〜3 日分 → 1.7〜2.6 日分に訂正 [Table 1]、trim filter の 128KiB 閾値を例示 (e.g.) であることを明示 [§4.5])
