---
title: "Accelerating Transactional Execution via Processing-In-Memory"
authors: [André Lopes, Daniel Castro, Paolo Romano]
venue: "EuroSys"
year: 2026
ids: {doi: "10.1145/3767295.3803621", arxiv: "", dblp: "conf/eurosys/LopesCR26"}
urls: {paper: "https://doi.org/10.1145/3767295.3803621", pdf: "literature/pdfs/2026-eurosys-lopes-pim-txn.pdf", code: "https://github.com/Andre12Lopes/PIM-TIDE"}
status: read
read_date: 2026-07-06
tags: [pim, upmem, oltp, transaction-processing, deterministic, stm, opacity, epoch-batching, energy-efficiency, hardware]
---

## TL;DR
実 PIM ハードウェア (UPMEM) 上で **cross-DPU トランザクション**をサポートする初の
in-memory datastore、**PIM-TIDE** (Processing-in-Memory with Transactional Isolation via
Deterministic Execution) の提案 (§1)。エポック単位のバッチ実行で、CPU がバッチ構築時に
distributed トランザクションへ commit timestamp を事前割当し、各 DPU 内では
TinySTM 系 STM(opacity 保証)を拡張した決定的 CC がその順序を強制する。これにより
DPU 間通信も分散コミットプロトコル(2PC)も分散ロックも使わずに強い整合性を達成する
(§1, §3)。local トランザクションは非決定的 STM で流す混合実行方式 (§3.2)。TPC-C
3プロファイルで CPU ベースライン(Xeon Gold 5320 + TinySTM)比で最大 6.75×(§1。
§4.2.1 の記述では 2000 DPU 時に最大 10×)、エネルギー効率 2.24–3.52× を報告 (§4.2)。

## Problem & motivation
- [paper] PIM はメモリモジュール内に計算能力を統合してデータ移動を削減する。ML・グラフ
  解析・科学計算・datastore などメモリバウンドな分析系では強い効果が示されてきた (§1)。
- [paper] 商用 PIM の UPMEM は DRAM モジュール内に数千の軽量 DPU(合計 2 万超の
  ハードウェアスレッド)を持ち、性能を引き出すには大規模並列性が必須 (§1)。
- [paper] UPMEM(および PIM 全般)の鍵となる制約は **DPU 間直接通信の不在**。DPU 間の
  あらゆる交換はホスト CPU の仲介が必要で、高レイテンシとシリアライズコストを伴う。
  数千 DPU にスケールするほど、分散データへの並行アクセス + 強整合性を要する
  トランザクショナル in-memory datastore にとって深刻なボトルネックになる (§1)。
- [paper] 定量例: CPU 仲介の DPU 間 64-bit word read は 331µs、ローカル MRAM read は
  231ns — 3桁の差 (§3.1)。さらに UPMEM では DPU 上の計算と CPU–DPU 通信が排他で
  重ね合わせ不可 (§2.1)。
- [paper] 既存研究は (a) 並列化しやすい OLAP に集中するか、(b) トランザクションのスコープを
  単一 DPU に制限してきた(PIM-STM)。後者は atomicity の範囲を 1 DPU に収まるデータ
  (現行 UPMEM で最大 64MB)に限定してしまう (§1, §2.2)。
- [paper] PIM-TIDE は分散トランザクションの speculative 実行と決定的 CC の系譜
  (Calvin, Epic, Sparkle 等 §2.3)に着想を得て、グローバルなトランザクション順序を
  事前計算し、分散トランザクションを各 DPU でローカル実行される subtransaction に
  分解することで、DPU 間通信を最小化しつつ数千 DPU 規模の並行性を狙う (§1)。

## System model & assumptions
- [paper] ハードウェア (UPMEM, §2.1, Fig. 1): 標準 DIMM 形状のモジュール、チップあたり
  8 DPU。各 DPU = 64MB DRAM バンク (MRAM) + 24KB 命令メモリ (IRAM) + 64KB
  スクラッチパッド (WRAM) + 350MHz in-order 32-bit RISC コア(最大 24 ハードウェア
  スレッド = tasklet)。実効的な命令スループットのピークは 11 tasklet(パイプライン深度)。
  フル構成で 2560 DPU / 160GB / 最大 28,160 tasklet 並行 (§2.1)。
- [paper] DPU 間直接通信なし(CPU 仲介のみ)。DPU 上では計算と CPU–DPU データ転送が
  相互排他(DPU がアイドルの時のみ転送可)で、計算と通信のオーバーラップ不可 (§2.1)。
- [paper] 同期プリミティブは acquire / release のみ(256-bit atomic register 上で動作し、
  アドレスをハードウェアハッシュでビットに写像 → 別アドレスが同一ビットに写像される
  aliasing あり)。CAS も read-write lock も無い。複雑な浮動小数点演算はソフトウェア
  エミュレーション。
  24KB IRAM が DPU プログラムサイズを制約 (§2.1, §3.3)。
- [paper] 整合性基準: **opacity**(abort するトランザクションも一貫した状態のみを観測)。
  DPU 上のコードはサンドボックス化されない C であり、不整合状態の観測はクラッシュや
  無限ループを招き得るため、DBMS 流の strict serializability ではなく TM 流の opacity を
  採用 (§2.2, §3.2)。
- [paper] トランザクションモデル: トランザクション = 1 個以上の subtransaction。各
  subtransaction は異なる DPU を対象とし、stored procedure 的な C ルーチン(PIM-TIDE
  API で begin/commit と read/write を記述)。入出力パラメータはパック化された bit array。
  read/write は MRAM への word(4 バイト)粒度 (§3 Batching/Execution, p.4–5)。
  1 DPU のみアクセスするトランザクションを local、複数なら distributed と呼ぶ (§3, p.4)。
- [paper] **read/write set の事前知識は不要**(Calvin 系の多くの決定的 CC と異なる)。
  reconnaissance query も不要で、speculative に実行される (§3, p.4)。
- [paper] 中核となる制約: **subtransaction は自分のターゲット DPU のローカルデータのみ
  アクセス可**。リモートアクセス自体は(依存 subtransaction の実行同期という形で)
  サポートし得るが、331µs の仲介 read と通信/計算の非オーバーラップにより不利益が
  大きく、表現力を犠牲に効率を最大化する意図的トレードオフとして採らない。cross-DPU
  トランザクションは複数 subtransaction の組で表現する (§3.1)。
- [paper] パーティショニングはプログラマ定義。細粒度分割はロジック改変と入力分配・結果
  集約コストを増やすため、DPU の 64MB に揃えた粗粒度分割を推奨 (§3.1)。評価では
  TPC-C の 1 warehouse(付随レコード込み)= 1 DPU (§4.1)。
- [paper] 実行はエポック(batching → communication → execution の3フェーズ)単位 (§3,
  Fig. 2)。バッチは DPU ごとの subtransaction 集合で構成され、distributed トランザクションの
  subtransaction にはバッチ構築時に CPU が commit timestamp を割り当てる (§3, p.5)。
  バッチを大きくすると CPU–DPU 帯域とカーネル起動固定費が償却されるが、個々の
  トランザクションのレイテンシは延びる(アプリ依存のチューニング事項)(§3, p.5)。
- [paper] エポック内の同一 DPU 上では、決定的(= distributed)subtransaction を先に実行し、
  完了後に local を並列実行する (§3.2)。脚注 1: local 群 G_L と distributed 群 G_D の間の
  conflict graph のエッジが G_L → G_D に向くことを保証すれば(G_L・G_D 各々が acyclic で
  ある前提の下で)全体が acyclic、と述べる (§3, footnote 1, p.6)。
  - [question] 「決定的を先に実行」なら local は distributed の書き込みを読むはずで、
    直感的には エッジは G_D → G_L に向きそうに見える。抽出テキストの乱れか、
    serializability 論証の取り違い(自分の)か、原文の誤植か。組版 PDF で要再確認。
- [paper] 故障モデル: **現実装は fault tolerance を保証しない**。決定的順序を活かした
  SMR ベースの複製で拡張可能という設計スケッチのみ (§3.4)。
- [inference] durability は完全にスコープ外。abstract も consistency / atomicity / isolation
  のみを謳い(D が無い)、ログ・永続化機構の記述は皆無。MRAM は DRAM であり、
  §3.4 の SMR スケッチが唯一の可用性の話。OLTP「datastore」としては ACI(D 抜き)。

## Approach
- [paper] **Batching** (§3, p.4–5): アプリは CPU 側 API でトランザクション/subtransaction
  オブジェクトを構築(ターゲット DPU・ストアドプロシージャ種別・パラメータを指定。
  Alg. 1 は TPC-C Payment 例: リモート支払いなら 2 subtransaction)。エポック末に受領
  トランザクション群を 1 バッチに編成(2048 DPU なら 2048 個の subtransaction 集合)。
  distributed トランザクションへ commit timestamp を付与し、これが実行フェーズで
  決定的 CC により強制されるため、**2PC 等の追加コミットプロトコルが不要**になる (p.5)。
- [paper] **Communication** (§3, p.5): バッチを DPU 群へ一括転送。バッチ転送が必須の理由は
  ①CPU–DPU 帯域はデータサイズと共に(ある点まで)増える、②エポック毎の DPU カーネル
  起動に固定費がある、の2点。通信と計算は重ねられないため前バッチの処理完了を待つが、
  CPU 上でのバッチ i+1 構築と UPMEM 上のバッチ i 処理はオーバーラップさせる。
- [paper] **Execution — 混合実行戦略** (§3, §3.2): local トランザクションはグローバル順序の
  制約を受ける必要がないため、DPU 内競合のみで順序が決まる軽量な非決定的 CC
  (PIM-STM 由来の TinySTM 変種: fine-grained encounter-time locking + write-through)で
  実行。distributed は決定的 CC で speculative に実行し、CPU が定めた順序と等価な
  serialization order を強制。コミット判断に DPU 間通信が不要で、競合はエポック内の
  retry で解決されるため**全トランザクションが自エポック内でコミット**する (§3, p.6)。
  local 処理では非決定的 CC が決定的比で最大 1.5× 速い (§3 p.6, §4.3)。
- [paper] **CC アルゴリズム** (Alg. 3, §3.2, p.7–8):
  - DPU ごとに共有のグローバル CLOCK(コミット毎にインクリメント)と、全 word を
    写像するグローバル lock table。エントリは locked(LSB=1、値は所有者の write-log
    エントリへのポインタ)か unlocked(値 = 最終更新 subtransaction のタイムスタンプ =
    version。TL2 由来の設計)。lock table サイズはコンパイル時固定で、メモリ消費と
    aliasing(偽共有による不要 abort)のトレードオフ (§3.2)。
  - subtransaction ローカル状態: 開始時 CLOCK 値 ts、(決定的のみ)commit_ts、モード
    (DET/NON_DET)、read log、write log(旧値を保持し undo log を兼ねる)(Alg. 3)。
  - Read: 自分がロック所有者なら直接読み。さもなくば version → 値 → version の
    再読で原子性を確認し、unlocked かつ version ≤ ts なら read log に追加(opacity 保証)。
    ロック中なら contention manager に問い合わせ、待つか rollback (Alg. 3, ll.14–27)。
  - Write: encounter-time locking。CAS で lock に write-log エントリのポインタを格納して
    獲得し、version > ts なら rollback。所有済みならメモリへ直接書く(write-through)
    (Alg. 3, ll.28–47)。
  - Commit: DET は CLOCK が自分の commit_ts に達するまで待機(その間 abort 検査)。
    CLOCK を atomic increment して serialization timestamp t を取得。read-only は即
    コミット。それ以外は開始後に CLOCK が動いていれば read log を再検証し、成功なら
    書き込み対象 lock エントリに version t を書いて解放 (Alg. 3, ll.48–59)。
  - Contention management: NON_DET は競合したら常に自分を abort(デッドロック
    フリーで軽量)。DET は commit_ts が大きい(= 後に序列化されるべき)側が abort
    (Alg. 3, ll.60–66)。並行 subtransaction から abort させられ得るのは決定的
    subtransaction のみ (§3.2, p.8)。
- [paper] **UPMEM 固有の最適化** (§3.3):
  - CAS 不在 → acquire/release で CAS をソフトウェア実装。256-bit レジスタのビット
    aliasing による不要なシリアライズは、共有データの参照・更新の短時間に限られ、
    レジスタ操作自体は WRAM/MRAM に触れないため実害は小さいと主張。
  - メモリ配置: lock table(静的サイズ・毎アクセス参照)は高速な WRAM、サイズが
    読めない read/write log は MRAM。MRAM アクセスは DMA 経由で 1KB 超の粒度で
    帯域が出るため、subtransaction 群をチャンク単位で WRAM に取り込みキャッシュ。
    PIM-TIDE のデータ構造はデフォルトで WRAM の約 75% を占有(縮小可)。
  - Pipelining: エポック i の PIM 計算とエポック i+1 のホスト側 batching を重ね、
    高負荷時(実行フェーズ > バッチングの時)は batching レイテンシをクリティカル
    パスから完全に除去。
- [paper] **Fault-tolerance スケッチ** (§3.4): 決定的 CC は SMR と好相性。multi-DPU
  トランザクションの順序は CPU が既に割当済みで、そのままレプリカへ配布できる。唯一の
  非決定性は local トランザクションの順序 → master が混合戦略で実行し、エポック末に
  local 分も含む serialization order をバックアップへ配布、バックアップは全トランザクションを
  決定的に再実行する構成を提案。レプリカは別 UPMEM システムにも、同一システム内の
  別 DIMM の DPU にも置ける(後者は実効容量を犠牲に部分故障へ耐性)。serialization
  timestamp の追加は既存メタデータ比で無視できるオーバーヘッドと主張(実装・評価なし)。

## Evaluation
- Setup [paper] (§4.1): PIM 側 = Xeon Silver 4215 ×2 + 256GB DRAM + 160GB PIM メモリ
  (2560 DPU)。CPU ベースライン = 別マシンの Xeon Gold 5320(52 ハードウェア
  スレッド)+ 250GB DRAM 上で、オリジナル TinySTM を使う TPC-C の TM ポート
  (SPHT 等の先行研究 [5, 19] のポートに基づく)。Gold 5320 は Silver 4215 より高性能で
  「より均衡した比較」と説明。各点 10 回平均。コードとベンチマークは公開
  (github.com/Andre12Lopes/PIM-TIDE, §4.1 fn.2)。
- Workload [paper] (§4.1): IRAM 24KB の制約から TPC-C は Payment / NewOrder /
  OrderStatus の 3 プロファイルに限定。ミックスは STD = 44/43/13、CUST = 25/25/50。
  Payment が複数 DPU に跨る確率を 0/15/45/75% で変化(15% が仕様標準値)。
  1 warehouse = 1 DPU。ほかに合成ベンチ Bank(20 万口座から一様選択した 2–100 口座間
  送金)。全実験で lock table 32KB(WRAM に入る最大)、バッチ = 128 トランザクション。
- Headline [paper]:
  - TPC-C ミックス全体: 全構成で CPU ベースラインを上回り、DPU 数と共に差が拡大
    (Fig. 3)。ピークは distributed 比率が低い構成での 6.75×。75% distributed でも
    STD75 で 6.82×、CUST75 で 4.78× (§4.2.1)。§4.2.1 本文は「2000 DPU で最大 10× の
    スループット向上」とも記述し、§5 も 10× を再掲。
    - [question] §1 は「up to 6.75×」(abstract 自体は数値を示さない)、§4.2.1/§5 は
      「up to 10×」、さらに本文の
      STD75 = 6.82× は 6.75× を上回る。10× は Fig. 4 の OrderStatus 単体プロファイルの
      speedup を指すようにも読めるが、本文の数値主張は相互に微妙に不整合。
  - プロファイル別(0% distributed, Fig. 4): OrderStatus は 2048 DPU で 10× 超
    (read-mostly・低競合)、NewOrder は約 9×、Payment は 2× 未満(書き込み集中と
    競合で intra-DPU 並列の利得が消える)(§4.2.1)。
  - CUST(read-only の OrderStatus 50%)は STD より絶対スループットが高い(競合減)
    (Fig. 3b, §4.2.1)。
  - エネルギー (§4.2.2, Fig. 5): 全構成で 2.24–3.52× の効率向上。UPMEM 側はエネルギー
    カウンタが無いため TDP 370W × 実行時間で過大見積り(→ 報告値は保守的下限と主張)、
    CPU 側は RAPL で CPU+メモリを実測。
  - 決定性のコスト (§4.3): 単一 DPU の Bank で、非決定的 CC が決定的比 1.1×(最小
    トランザクション)〜1.5×(最大)で常に優位 (Fig. 6)。決定的の低スループットの主因は
    strict order のためのコミット待ち。TPC-C 単一 DPU (Fig. 7): OrderStatus は tasklet 数に
    ほぼ線形スケールし両 CC 同等・abort ほぼゼロ。Payment は非決定的で横ばい、決定的で
    低下し、高 tasklet 数で abort 率 90% 超(全 Payment が同一 warehouse の残高
    フィールドを更新するため)。NewOrder は両モードとも abort 率 80% 超でスケールせず
    (長いトランザクション + 多数の insert)。総括: 非決定的は write-heavy に強く、
    決定的は read-mostly local でのみ拮抗。単一 DPU では高 abort 率が最大の障害 (§4.3)。
- [inference] 評価がカバーしていないもの:
  - **レイテンシが一切測られていない**。報告指標は throughput と abort rate のみ (§4.1)。
    §3 でバッチサイズとレイテンシのトレードオフを論じながら、バッチ 128 固定での
    end-to-end レイテンシ(エポック待ち込み)の数値が無い。バッチサイズ感度分析も無い。
  - CPU ベースラインは TinySTM ベースの TPC-C ポートであり、最適化された最新
    in-memory OLTP エンジンではない。ハードウェアも PIM ホストと別マシンで、
    コスト正規化($/txn 等)の比較軸は無い。speedup の絶対値はベースライン選定に
    強く依存する。
  - distributed トランザクションは Payment の multi-DPU 化のみで合成。NewOrder の
    remote stock アクセスのような他プロファイルの分散化は試されていない。
  - PIM-STM との直接比較実験は無い(§2.2 の「単一 DPU では PIM-STM と同等性能」は、
    非決定的 CC が PIM-STM 由来の TinySTM 変種であることによる暗黙の含意どまり)。
  - §3.4 の SMR 複製は設計スケッチのみで、実装・故障注入・複製オーバーヘッドの測定なし。
  - エネルギー推定(TDP × 時間)に、batching / コーディネーションを担う PIM 側ホスト
    CPU の消費が含まれるのかが読み取れない。
  - lock table aliasing の発生率や、それによる不要 abort の寄与は定量化されていない。

## Limitations
- Stated [paper]:
  - 現実装は fault tolerance を保証しない(SMR による拡張は将来課題)(§3.4, §5)。
  - IRAM 24KB のため TPC-C はトランザクション 3 種のサブセットに限定 (§4.1)。DPU
    プログラムサイズ自体が制約 (§2.1)。
  - バッチを大きくするとトランザクションのレイテンシが延びる。バッチ長はアプリ依存の
    チューニング事項 (§3, p.5)。
  - subtransaction のローカルアクセス制限はプログラミングモデルの表現力を削る意図的
    トレードオフ (§3.1)。word 粒度 API は低レベルで、KV や SQL 等の上位層は将来課題
    (§3, p.5)。
  - 決定的実行は commit 順の待機で並列性を阻害し、大きいトランザクションでは abort 率も
    非決定的より高い (§4.3)。
  - lock table の aliasing は不要 abort を生み、サイズ拡大は乏しい記憶容量と衝突 (§3.2)。
  - エネルギー利得は性能利得ほどには大きくない (§4.2.2)。
  - 将来課題として PIM 向け fault-tolerance と、distributed トランザクション頻度を下げる
    パーティショニングを明示 (§5)。
- Inferred [inference]:
  - durability の欠如(上記 System model 参照)。永続化・リカバリを足した場合、エポック
    バッチングとどう干渉するか(エポック単位の group commit になるはず)は白紙。
  - CPU は batching・timestamp 割当・全 DPU 間通信仲介を担う集中シーケンサであり、
    DPU 数をさらに増やした時のホスト側コストの内訳(構築時間、転送量)が分離計測されて
    いない。Fig. 3 は 2000 DPU まで伸びているが、頭打ちの位置は不明。
  - Payment/NewOrder の abort 率 80–90% 超 (Fig. 7b) は、DPU 単体の実行効率が低いまま
    DPU 数の暴力で勝っていることを示唆する。abort による無駄実行はエネルギー推定
    (実行時間 × TDP)にも乗るため、abort 削減はエネルギー面の伸び代でもある。
  - 1 warehouse = 1 DPU の分割は TPC-C の warehouse hotspot をそのまま DPU 内競合に
    変換する(Fig. 7b の Payment abort 90% 超はその帰結)。warehouse を跨ぐ細分割や
    ホットフィールド分離との相互作用は未検討。

## Relations
- 論文内の系譜 [paper]: 土台は PIM-STM [39](単一 DPU の STM。本論文はその TinySTM
  変種を local 用に採用し、決定的 CC を追加)(§2.2)。決定的 CC の先行は Calvin [56]、
  Epic [49]、Sparkle [37]、LiTM [59]、DeSTM [51] (§2.3)。versioned lock 設計は TL2 [11]
  由来 (§3.2)。
- [[2026-eurosys-barreto-fur.md]] (FUR: PM 上の PHT): 同じ EuroSys '26 で著者が重複
  (Castro / Romano。INESC-ID の TM 系譜)。「新種メモリハードウェア上でトランザクション
  抽象を再設計する」枠で対をなす — FUR は persistent memory + HTM の read-only
  トランザクション、本論文は PIM + STM の cross-DPU トランザクション。本論文の TPC-C
  ポートは SPHT [5](FUR のベースラインと同系)に基づく (§4.1)。FUR ノートは
  abstract-only なので詳細比較は FUR 深読み後。
- [[2026-tods-bernhardt-update-ndp.md]] (Update NDP): 「データ近傍計算 × トランザク
  ショナル更新」という同一問題への対照的な解。Update NDP は cache-coherent inter-
  connect 上の共有 lock table で host と computational storage を協調させる(ロック共有型)。
  PIM-TIDE は事前順序付けで実行ユニット間ロック・通信自体を回避する(協調回避型)。
  ハードウェアが提供する同期機構の強弱(coherent interconnect vs CPU 仲介のみ)が
  設計を分岐させている点は、新ハードウェア上の CC 設計の比較軸として有用。
- [[2026-pvldb-zhao-sidle.md]] (SIDLE: CXL 索引配置): 「新メモリハードウェア × DBMS」の
  弱い主題的隣接(旧ノートから維持)。SIDLE は容量・階層の拡張、本論文はメモリ内計算と
  軸が異なる。
- [inference] Epic [49](OSDI'24, GPU 加速の決定的 MVCC)は §2.3 で議論される最も近い
  「アクセラレータ × 決定的 CC」の先行だが、ノートコーパスに未収録。queue 追加候補。

## Idea seeds
- [inference] **ホスト側シーケンサのスケーリング限界の特定**: batching・timestamp 割当・
  バッチ転送は全て単一ホスト CPU 上にあり、pipelining (§3.3) は高負荷時の隠蔽しか
  主張していない。公開コードで DPU 数 / distributed 比率を掃引し、ホスト側フェーズの
  所要時間を分離計測すれば、「PIM 上 OLTP の Amdahl 境界」を示せる。Calvin の
  単一スレッドスケジューラボトルネック(Sparkle が指摘, §2.3)の PIM 版になり得る。
- [inference] **競合を考慮した commit timestamp 割当**: CPU はバッチ全体を見てから順序を
  決めるのに read/write set 知識を使っていない(§3, p.4)。パラメータ(warehouse id 等)
  から推定したホットキーで同一ホット対象の subtransaction を隣接順序に置けば、決定的
  実行の abort(Fig. 7b で 90% 超)を削れる可能性がある。検証: 公開コードのバッチ構築で
  Payment を warehouse 毎にソートし、abort 率とスループットの変化を測る。
- [question] §3 footnote 1 の conflict graph エッジ向き(G_L → G_D)は「決定的を先に
  実行」という本文と整合するのか。組版 PDF で原文確認の上、serializability 論証を
  自分で再構成してみる価値がある(もし誤植なら軽微だが、正しいなら自分の理解が
  欠けている部分で、混合 CC の正しさ条件として面白い)。
- [question] エポックバッチング + 決定的順序に durability を足す最小の設計は何か。
  write log は既に MRAM にある (§3.3) ので、エポック末に結果と一緒に write log を
  ホストへ引き揚げれば epoch 粒度の redo ログになる(通信と計算が排他な UPMEM では
  このコストが直接スループットを削る点が本質的制約)。検証: 公開コードで write log
  転送を追加した時のスループット低下率の測定。Update NDP(共有ロック + ログ移動)の
  アプローチとの定量比較軸にもなる。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: 検証パスによる修正(「CPU を協調にのみ使用」の「のみ」を削除 — abstract は "using the CPU selectively for transaction coordination" であり排他性は主張していない)
- 2026-07-06: full-text 格上げ(status: abstract-only → read。手動取得した PDF 全文を読解し全節を執筆)
- 2026-07-06: 検証パスによる修正(6.75× の出典を abstract/§1→§1 に訂正(abstract は数値なし)/浮動小数点エミュレーションを「複雑な」演算に限定/footnote 1 の所属節 §3.2→§3 と G_L・G_D acyclic 前提の追記/1.5× のアンカー §3.2→§3 p.6)
