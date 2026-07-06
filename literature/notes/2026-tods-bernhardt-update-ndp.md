---
title: "Update NDP: On Offloading Modifications to Smart Storage with Transactional Guarantees in Near-Data Processing DBMS"
authors: [Arthur Bernhardt, Sajjad Tamimi, Florian Stock, Andreas Koch, Ilia Petrov]
venue: "ACM Trans. Database Syst. 51(2), Article 11 (March 2026)"
year: 2026
ids: {doi: "10.1145/3774753", arxiv: "", dblp: "journals/tods/BernhardtTSKP26"}
urls: {paper: "https://doi.org/10.1145/3774753", pdf: "literature/pdfs/2026-tods-bernhardt-update-ndp.pdf", code: ""}
status: read
read_date: 2026-07-06
tags: [ndp, computational-storage, smart-storage, transactions, locking, lock-violation, logging, recovery, mvcc, ccix, cxl, cache-coherence, fpga, postgresql]
---

著者・誌名は PDF ヘッダで確認: p.1 に著者5名と所属(Reutlingen Univ. / TU Darmstadt)、
"ACM Trans. Datab. Syst., Vol. 51, No. 2, Article 11. Publication date: March 2026"、
doi:10.1145/3774753 の自己記載あり (p.1–2)。Received 2024-05-29 / revised 2025-06-12 /
accepted 2025-10-06 (p.45)。本文中にコード・artifact URL の記載は無し(NVM エミュレータ
NVMulator [86] と TaPaSCo [39] は外部 OSS として引用されるのみ)。

## TL;DR
NDP はこれまで実質 read-only に限られていた。本論文は、更新操作を smart storage に
トランザクション保証付きでオフロードする「update NDP」を、PostgreSQL ベースの NDP DBMS
neoDBMS(著者らの先行研究 [14, 89] の拡張)上で実現する (§1)。核は3つ: ① CCIX/CXL 系
cache-coherent interconnect 上の共有仮想メモリ (ccSVM) に置く tuple 粒度の Shared Lock
Table (SLT) と、それを host lock table (HLT) と論理チェーン化する統合ロックプロトコル
(host-shared lock + lock ownership) (§5)、② 新版を専有割当ページに out-of-place 生成し
ΔL2P/ΔVID マップだけを host にアトミック適用する shadow-paging 的な更新方式 — これにより
NDP 部分には undo/redo ログ自体が不要になる (§5.4.5, §6)、③ メディア回復用の overflow log
転送を controlled lock violation で有効な仕事とオーバーラップさせる拡張ロック/ロギング
(§5.4, §6.2)。ARM N1-SDP + CCIX 接続 Alveo U280 FPGA(MicroBlaze PE ×8, NVM エミュレータ)
の実機で、mixed workload の更新が host-only (PostgreSQL) 比 ≥6.52×(19s vs 124s)、更新単体
で選択率 100% 時 ≥4.67× (Fig. 1, Fig. 19)。

## Problem & motivation
- [paper] 大規模データの更新操作は大量のデータ移動を引き起こす(hot と cold の混在、
  更新対象の特定自体に大きな転送が要る)にもかかわらず、NDP は read-only 設定と静的
  データセットに主に使われてきた (§1, p.2)。
- [paper] 更新オフロードの動機: (i) 大規模プロダクションで write-intensive 化が進行 —
  Twitter/X では調査対象ワークロードの 35% 超が write/read 比 ≥30%、20% は書き込みが
  読みより多い; Facebook/Meta のソーシャルグラフでは更新が約 15–30%、ML 設定では 92%
  (§1, p.2, refs [23, 98])。(ii) GDPR / right-to-be-forgotten のような規制で更新が
  データセットの大部分に及ぶ (§1)。(iii) 読み書き混在のシーケンス(NDP-Pipeline)を
  丸ごとオフロードしないとデータ移動は減らないケースがある (§1)。
- [paper] **Problem 1(同期・無効化)**: host と NDP 更新の write/write 競合で版分岐が
  異常生成される/host キャッシュの旧版無効化が必要 (Fig. 1(B))。粗粒度(テーブル)ロックは
  並行性を殺し、OCC は (a) reader 飢餓、(b) commit 時の遅い abort による資源損失、
  (c) read/write set の追加転送を招く。tuple 粒度ロックが本命だが、数キャッシュラインの
  小転送は帯域最適化された PCIe では非実用的に遅く、PCIe は非 cache-coherent なので
  細粒度コヒーレンスの手動実装も非現実的(手動 cacheline flush か OS ページ移動が必要)
  (§1 Problem 1, p.3, refs [20, 32, 63, 87])。
- [paper] **Problem 2(ロギング)**: NDP 更新はロールバック・システム回復・メディア回復
  (smart storage 自体が故障しうる)のための新しいロギングを要する。undo/redo +
  physiological の既存流儀を素朴に適用するとログのデータ移動が増える。ログをデバイス内に
  置くとデバイス故障でデータとログが同時消失。ログを host へ転送すると、転送・flush の
  遅延がロック保持期間を不必要に延ばし、lock contention と commit レイテンシ増を招く
  (§1 Problem 2, p.3)。
- [paper] 先行の更新オフロードは特殊ケースのみ: in-storage 常駐 DBMS(SaS [71]、同期なし
  バッチ更新前提)、KV ストアの in-storage compaction([60, 82]、既定アドレス範囲への
  out-of-place で ad-hoc 同期不要)(§1, §10)。KV 系 NDP(Caribou/Willow/PapyrusKV/Kanzi)は
  単一 KV ペア操作でトランザクション支援なし (Table 3, §10)。
- [paper] 「我々の知る限り、smart storage 上の細粒度ロックでトランザクショナルな一貫性を
  実証した最初のシステム」と主張 (§10, p.41)。

## System model & assumptions
- [paper] **ハードウェア**: host は ARM Neoverse N1 SDP(N1 コア ×4 @2.6GHz、RAM 16GB)。
  smart storage は CCIX 対応 Xilinx Alveo U280 FPGA を CCIX-enabled PCIe Gen3 x16 で
  直結 (direct-attached topology)。host が CCIX Home Agent(自分のメモリを共有)、
  デバイスが Request Agent。ccSVM/PCIe 転送/NDP 呼び出しは TaPaSCo [39] 経由 (§8.1)。
- [paper] **インターコネクト選択**: 研究実施時点で CXL Type 2 対応の FPGA ボード・host が
  商用入手不能だったため CCIX を採用(N1-SDP は FPGA-CPU ccSVM が実際に qualify された
  唯一の商用サーバ)。CCIX は deprecated だが、CXL.cache/HDM-D では coherence roundtrip
  増でレイテンシは約2倍になると推測しつつ、PCIe 5.0 の CXL Type 2 は PCIe 3.0/4.0 の
  CCIX を上回るはずで提案の妥当性は保たれると主張 (§2.2.3, p.9)。update NDP の対象は
  CXL Type 2 デバイス(一部技術は Type 1 にも適用可) (§2.2.2, Fig. 3)。
- [paper] CCIX アクセスレイテンシ(64B cacheline): local 60ns / cached remote 100ns
  (read)・80ns (write) / remote no-ATS 686–699ns / ATS 込み full remote 約 2400ns。
  連続 pinned 共有メモリ範囲に限定すれば ATS を回避して約 680ns (Fig. 2(B), §2.2.1,
  ref [87])。CCIX atomics は最大 128b の Load/Store/Compare/Swap (§2.2.1)。
- [paper] 実 CXL Type 2 デバイスの評価 [45] は device→host アクセスの方が host→device
  より低レイテンシと示しており、「host メモリを device と共有する」という neoDBMS の
  設計選択と整合する (§2.2.2, p.9)。
- [paper] **ハイブリッドインターコネクト**: 同一 PCIe レーン上で PCIe DMA(大容量転送)と
  CCIX エージェント(低レイテンシ coherence)を切り替える統一 HW 設計。CXL の
  CXL.io / CXL.cache 分担に対応づく (§3.1, p.15)。
- [paper] **デバイス内計算**: 最大 8 個の MicroBlaze soft-core PE @180MHz。各 PE に
  1-cycle の BRAM scratchpad と preloader/unloader HW モジュール(NVM への非同期
  byte-addressable DMA)、SLT アクセスは専用 HW locking module。NVM は NVMulator [86] で
  DRAM 上にエミュレート(Optane 系レイテンシセットで較正、システム実験は middle-ground:
  read 350ns / write 170ns)(Fig. 8, §3.1, §8.2.2, §8.3)。PE アレイは host ARM 比 26× 以上
  遅い(CoreMark: 8PE 合計 2,992 vs N1 4コア 79,417 it/s。参考: Xeon Silver 4110 16コア
  207,630)(Table 1, §8.2.1)。
- [paper] **Software-NDP**: NDP 操作・visibility checker・layout accessor・format parser は
  C で書かれた小さな事前コンパイル済みバイナリで、NDP 呼び出し時に各 PE にロードされる。
  現行設計が NDP 操作としてサポートするのは scan / selection / projection / update のみ
  (§3.1, §4.1.3)。PE の種類は MicroBlaze に限定されない(RISC-V/ARM/カスタムロジックへ
  置換可能な設計)と主張 (§3.1, p.15)。
- [paper] **DBMS モデル**: MVCC。版レコードは new-to-old の単方向リスト+ one-point
  invalidation(生成タイムスタンプのみ保持、後続版の存在で暗黙に無効化)。VID_map が
  各タプルの最新版 RecID を保持する版インデックス、L2P_map が論理→物理マッピング
  (§2.3.4, Fig. 5)。snapshot-based NDP: 可視性判定とスナップショット構築はデバイス上で
  実行 (§2.3.2, §2.3.5, Fig. 6)。host の最新更新は shared-state(delta-buffer + マップ差分、
  数百 KB〜数 MB)として NDP 呼び出しごとに伝播 (§2.3.3)。PostgreSQL ベース
  (serializability は PostgreSQL の SSI [74] に依存、リカバリ実験では PostgreSQL の
  Custom WAL resource manager を利用)(§5.4.4, §8.3.8)。
- [paper] **並行性制御**: SLT による悲観的 tuple ロック。conflict 解決は
  First-Updater-Wins [12, 19](NDP 開始後に始まった host TX が先にロック・更新・commit
  したら NDP 側が abort)(§4.1.8)。分離レベルは SI 系(READ COMMITTED / REPEATABLE READ /
  SERIALIZABLE)を lock-violation と両立させる (§5.4.4, Fig. 13)。
- [paper] **故障モデル**: トランザクションロールバックとシステム(クラッシュ)回復は
  basic logging で常に可能。メディア回復(smart storage デバイス故障)は extended logging
  (overflow log の host 転送)を有効にした場合のみ (§6)。basic のみの運用は「メディア
  非回復性の窓を許容できるアプリ向け」と明示 (§6.1)。
- [paper] NDP 用ストレージ空間管理は host 側 DBMS エンジンが専任。NDP 実行中に空間が
  尽きると追加ページ要求のラウンドトリップ(実測 2–10ms、起動 PE 数依存)が発生 (§4.1.2)。
- [paper] SLT は host 側の物理連続 pinned メモリに配置(host はキャッシュされたローカル
  アクセス、低速なデバイス側はアクセス頻度が低く ATC で ATS を回避)。SLT を意図的に
  小さく設計し remote アクセスのキャッシュヒットを助ける (§5.1)。
- [inference] 評価構成は smart storage 1台・direct-attached のみ。§2.2.1 は「host が
  メモリを共有すれば ccSVM で複数デバイスへのパーティショニングが可能」と述べるが、
  マルチデバイス構成の実装・実験は無い。また NVM は DRAM 上のエミュレーションであり、
  実フラッシュ/実 Optane の耐久性・GC 由来の遅延変動は含まれない。

## Approach
- [paper] **実行フロー** (Fig. 9, §4): ① host の NDP plan optimizer(hybridNDP [53] の
  コストモデル拡張。推定選択率から相対更新コストを注入)が、対象特定コストが低く少数
  タプルを触る更新は host に、bulk 更新や対象特定が高コストな更新は NDP に割当 (§4.1.1)。
  ② NDP 呼び出し: TxID + 並行 TX リスト(スナップショット情報)+ shared-state の
  スナップショットを添えて push down。ストレージ(新規 DB ページの専有割当)と PE 資源を
  事前見積り・事前割当 (§4.1.2)。③ in-storage engine が呼び出しパラメータのログエントリを
  作成後、VID_map をパーティションして PE 群に NDP job を分配。各 job は自パーティションの
  VID_map エントリごとに visibility check → フィルタ → 更新 (§4.1.3)。④ 更新前に必ず
  SLT tuple ロックを取得。新版レコードは BRAM 上の DB ページに生成し、満杯で L2P_map の
  指す物理位置へ flush。Δ(VID_map, L2P_map) は BRAM ページ flush の一部として継続的に
  ログ・永続化されるが、**マッピング本体には適用しない**(abort 検証のためデバイス上に
  保持のみ)(§4.1.4)。⑤ 完了後、ΔMaps のサイズとアドレスを host に返し、PCIe DMA で
  回収 (§4.1.4–4.1.5)。⑥ host 側で ΔVID_map の各エントリの「先行版 RecID」を現在の host
  VID_map と突き合わせて更新競合を検証。競合が無ければ ΔL2P_map(専有ページのみ参照
  なので常に安全)→ ΔVID_map の順にアトミック適用し、旧 host 側版を無効化 (§4.1.5, §5.3,
  Fig. 11)。⑦ commit は常に host 側。未使用の事前割当ページは返却、デバイスログは
  非同期転送、SLT/HLT ロック解放 (§4.1.7)。abort 時は ΔMaps もログも転送不要で、専有
  割当空間の解放・回収だけで呼び出し前の状態に戻る (§4.1.8)。
- [paper] **アトミシティ = shadow paging 的**: 新版は専有割当ページに out-of-place、host に
  渡るのはマップ差分のみ、適用はアトミック。よって部分的な NDP 更新も部分適用も起こらず、
  NDP 部分にはトランザクションロールバック・システム回復用の undo も redo も不要
  (host 側操作の分だけ従来 WAL が残る)(§1 p.4, §5.4.5, §6)。
- [paper] **SLT の構造** (§5.1): (DB オブジェクト番号, VID) をキーとするハッシュ表。
  各エントリ(バケット)は 16B 固定のキューで、2B スロット ×8 または 1B スロット ×16
  (16B の CCIX/ARM atomics、または 8B の x86 atomics に整合)。head スロット = 現在の
  ロック保持者、残り = 待ちキュー、解放時は全体を1スロットシフト。配置・解放は atomic CAS
  で race-free。**最後のスロットは常に host 用に予約**。2B 構成で「同一タプルに同時に
  並べる NDP TX は最大 4/7」だが host TX 数は無制限(後述の host-shared lock による)。
  スロットには 8B の TxID ではなく JobID を格納(1 JobID = 1 NDP TxID に対応)(§5.1 脚注3)。
  先行研究の SLT [16] はキューあたり 8 リクエスト固定・128-bit atomics 必須・DBMS 統合
  なしで、これらを解消したのが本設計 (§2.3.6)。
- [paper] **統合ロックテーブル (ILT)** (§5.2, Fig. 10): SLT を論理 head、既存 HLT を論理
  tail とするチェーン。host lock manager は両方を、in-storage engine は SLT のみを見る。
  **host-shared lock (TxID_HOST)**: 同一タプル待ちの host TX 群は SLT 上では1個の汎用
  TxID_HOST を共有し、実際の順序管理は HLT が担う。並行 NDP のロック要求が来ると再利用
  チェーンが切れて2個目の TxID_HOST が積まれる。**lock ownership**: TxID_HOST の解放権は
  その TxID_HOST に対応する最後の host TX が持つ(先行所有者の解放を防ぐ)。コストは
  host 側のルックアップ2回(SLT + HLT)で、host 並列度を制限しない (§5.2)。
- [paper] **基本プロトコル** (§5.3, Fig. 11): NDP は SLT エントリを atomic load →
  head 空なら CAS で JobID を挿入し即時取得。host TX はロック不可なら TxID_HOST を
  enqueue しつつ HLT にも自 TxID を置き、先行ロックの commit/abort 通知に登録して
  sleep-wait(ポーリング不要)。NDP commit 時に ΔVID_map 検証 → アトミック適用 →
  commit ログ → SLT 解放。起床した host TX は自分が読んだ RecordID を現在の VID_map と
  照合し、無効化されていれば abort(TxID_HOST は所有者のみが解放)(§5.3)。
- [paper] **拡張ロックプロトコル = controlled lock violation の応用** (§5.4): NDP TX が
  検証を通過して commit レコードをログバッファに割り当てた時点(通常状況ではもう abort
  しない)で「lock-violation 許可」状態に遷移。待ち TX はロックを violate して有効な
  仕事を進められるが、NDP TX の EOT まで commit を acknowledge されない
  commit-dependency(commit-chain)を負う。システム故障時は依存 TX 全員がロールバック
  (Graefe らの CLV [36] に着想)(§5.4.2)。効果: (a) 早期 abort 検出と高速リトライ、
  (b) log 転送・flush 中の有効仕事、(c) hot tuple が host⇔device 間・NDP TX 間を
  「バウンス」できる (§5.4.2–5.4.3, Fig. 12)。並行 NDP TX にも拡張され、lock-violation
  状態は shared-state と共にデバイスへ伝播し、後続 NDP はより新しいスナップショットを
  計算しつつ発見した commit-dependency を host に通知する (§5.4.3, p.24–25)。
- [paper] **分離レベルとの整合** (§5.4.4, Fig. 13): RR/SERIALIZABLE はスナップショットが
  最初の read で固定されるため、violation 許可前に開始した TX は変更が見えず、violate は
  early-abort 判定に使える。許可後に開始した TX には新版が見え、commit-dependency 付きで
  仕事を進められる。READ COMMITTED も同様(古いスナップショットなら早期 abort、新しい
  スナップショットなら依存解決待ち)。serializability の競合検出は PostgreSQL SSI [74]。
- [paper] **ロギング** (§6): *Basic* (§6.1, Fig. 14(A)): NDP 呼び出し開始時に呼出パラメータ
  入りの Start-NDP レコードを host WAL に書き、その LSN を呼び出しと共に伝播。完了時に
  ΔMaps を含み Start-NDP を参照する End-NDP レコードを書く。システム回復の redo では
  ΔMaps をメインマップに再適用するだけ(デバイス上のページは無傷)。ΔMaps は全 I/O の
  0.7% 未満と小さい (§6.1, Table 2)。メディア回復は不可。*Extended* (§6.2, Fig. 14(B)):
  NDP 完了後、新規ページと ΔMaps から NDP redo-log をデバイス上で非同期構築し、commit
  前に host へ転送、End-NDP から参照される **overflow log ファイル**に格納(高価な
  log-merge を回避、DBMS 非依存のログ reader/writer を可能にする)。デバイス故障時は
  redo フェーズで overflow log を適用 (§6.2)。
- [paper] **最適化** (§7): byte-level preloader / page-level unloader(BRAM double
  buffering + 非同期 DMA)で計算と転送をインターリーブし、弱い PE と高い NVM レイテンシを
  相互にマスク。版レコード1件の検査は5転送・計約 20B で済み、ページ粒度転送比で
  read-amplification を大幅減 (§7.1, Fig. 15)。**in-storage SELECT FOR UPDATE**: 対象
  タプルのロックをデバイス内で先取りし、成功ロックを物理版アドレスのリストとして
  ΔVID_map に保持。後段の NDP pipeline 内 update は abort リスクも再 visibility check も
  不要。SQL 標準の SELECT FOR UPDATE 文をそのまま NDP へ割り当てるためアプリ変更不要
  (§7.2)。

## Evaluation
- Setup [paper]: 上記 N1-SDP + AU280 実機。ベースラインは PostgreSQL v12(ext4 +
  block storage)による host-only 実行。ワークロードは YCSB 系、scale factor 6000
  (初期 6.5GiB / 総計 14GiB)、NVM エミュレータは middle-ground(read 350ns / write
  170ns)(§8.1, §8.3)。
- Headline numbers(各 anchored):
  - 導入実験(YCSB-A 50/50 + NDP-able 更新の3フェーズ mixed workload): 更新は
    update NDP 19s vs host-only 124s で **≥6.52×**。host-only は MIXED フェーズで
    スループット約 36% 低下、neoDBMS は低下なし (Fig. 1(A), §1)。
  - SLT ロックレイテンシ: host 側 80–400ns、デバイス側 750–800ns(競合度依存)
    (Contributions, §1 p.5)。
  - preloader/unloader は NVM レイテンシを効果的にマスク: ロックなし全表更新で、
    有効時は DDR〜worst-case NVM 設定で 13.25–14.52s とほぼ一定、無効時は 44.05–84.2s
    (Fig. 16, §8.2.2)。DMA(sync/async)は MicroBlaze memcpy よりはるかに高帯域
    (Fig. 17, §8.2.3)。
  - Exp 1(選択率スイープ、YCSB-C + 更新注入): neoDBMS は選択率 >0% で一貫して優位、
    10% で 1.68× 〜 100% で ≥4.67×。0%(実質全表スキャン)は pgSQL の index scan 比
    0.94×(neoDBMS はデバイス上で索引未使用、VID_map 全走査)(Fig. 19(A), §8.3.1)。
    デバイス内帯域は scan/filter 段で約 92MiB/s read、更新段で最大 490MiB/s read +
    530MiB/s write — この時点で弱い MicroBlaze が compute-bound になり、デバイス内
    NVM 帯域 10GiB/s を使い切れない (Fig. 19(D), Fig. 17, §8.3.1)。
  - Exp 2(オーバーヘッド分解、選択率 100%): 総 I/O のうち SLT ロッキング 46MiB
    (0.34%)、ΔMaps 92MiB(0.69%)。ロック設定オーバーヘッドはデバイス側 6.4%
    (13.0s→13.9s)、解放は host 側 4.4%(1.4s→1.5s)(Table 2, §8.3.2)。
  - Exp 3(YCSB-A + 頻繁な小更新 10% 選択率): 並行 read TX 1.9×、write TX 5.9×
    (対 pgSQL)。host–storage 間平均帯域利用を 80× 削減(バッファ汚染・ページ追い出し
    減)(Fig. 20, §8.3.3)。
  - Exp 4(SELECT FOR UPDATE 単体): SFU のオーバーヘッドは host 実行 1.43× →
    in-storage 1.19× に低減、SFU+update をデバイス実行して 4.2× speedup (Fig. 21, §8.3.4)。
  - Exp 5(ロック方式比較、並行負荷なし): 全表ロックが最速だが並行性を殺す。SLT が
    僅差で追随。OCC は検証フェーズのコストで SLT より遅い (Fig. 22(A), §8.3.5)。
  - Exp 6(NDP pipeline): scan+update を丸ごとデバイス実行 (S3) は選択率 >17% で
    host scan + NDP update (S2) や host-only (S1) より高速 (Fig. 22(B), §8.3.6)。
  - Exp 7(abort 挙動): SLT は early-stop 条件を全 PE に通知でき ΔMaps が小さく
    version chain がクリーン。OCC は検証が更新後なので常に late abort となり、aborted
    版が version chain に残って visibility check と GC を圧迫、時間経過でスループットが
    劣化する (Fig. 23, §8.3.7)。
  - Exp 8(ロギング/回復、6M insert + 6M update の replay): 回復時間 pgSQL 226s /
    basic 96s / extended 106s — extended は pgSQL 比 2× 高速、basic 比 +10%。ログサイズは
    pgSQL 19.5GiB > extended 13.5GiB > basic 6.9GiB。更新実行への影響: no-logging 13.9s /
    basic 15.4s / extended 25.9s(extended 単体では 1.68× のオーバーヘッド)(Fig. 24,
    §8.3.8)。低競合(SF100)でも neoDBMS の回復は 24–43% 高速 (§8.3.8, p.37)。
  - Exp 9(lock-violation、SF4000、100% 選択率更新 + 20TX/s の OLTP): CLV 有効時は
    NDP の commit レコード割当時点(28s)で待ち TX が violate → 検証 → early-abort の
    スパイク、38s の NDP 完了時に commit-chain が一斉 commit して OLTP が 20TX/s に復帰。
    CLV 無効(overflow log のみ)では待ち TX は仕事ができず 38s に late-abort の山だけが
    出る。pgSQL は更新 commit が 71s (Fig. 25, §8.3.9)。「メディア回復のオーバーヘッドを
    ほぼゼロに抑えつつ basic logging 並みの性能」と総括 (§8.3.9 Insight)。
- [paper] 著者ら自身の測定上の限界: 使用ベンチマークスイート(OLTP-bench [27])が
  worker スレッド内で厳密逐次実行のため、高ロック競合下ではストールし、workaround
  (worker の連続 spawn)のコネクションプール欠如で持続スループットが 20TX/s に制限。
  より高い並行スループット下での log-movement / lock-violation の検証は未実施(その場合
  CLV の利点はさらに顕著になるはずと予想)(§8.3.9 Limitations)。
- [inference] 評価がカバーしていないもの:
  - 比較対象は host-only PostgreSQL v12 のみ。他の NDP システム(nKV、AIDE、Caribou 等、
    Table 3 に整理されている競合)との直接性能比較は無い。標準 OLTP ベンチ(TPC-C)も
    無く、YCSB 系のみ。
  - host が 4 コア ARM / 16GB RAM と小さく、host-only ベースラインが資源制約下にある。
    Table 1 が示すとおり enterprise Xeon は N1 の 2.6× の CoreMark を持ち、大メモリ host
    ならバッファ汚染の影響自体が縮む可能性があるが、host 資源のスケーリング実験は無い。
  - NVM はエミュレータ(DRAM 裏付け)であり、実デバイスの GC・摩耗・帯域変動は不在。
    smart storage の「デバイス故障」も実際に注入した実験は無い(overflow log からの回復
    時間は測定されているが、故障検出・切替のシナリオは扱われない)。
  - SLT のハッシュ衝突(異なるタプルが同一バケットに落ちた場合の偽競合)の頻度・影響の
    分析が見当たらない。
  - デバイス側で索引を使わないため 0% 選択率で pgSQL に負ける (Fig. 19(A)) が、
    on-device 索引を足した場合の比較は将来課題のまま。

## Limitations
- Stated [paper]:
  - CCIX は deprecated であり、実験プラットフォーム(N1-SDP + AU280)は当時ほぼ唯一の
    選択肢。CXL.cache/HDM-D への外挿は「レイテンシ約2倍」という推測ベース (§2.2.3)。
  - basic logging はメディア回復不可(非回復性の窓を許容するアプリ向け)(§6.1, §8.3.8)。
  - extended logging はログサイズを増やし、単体では更新実行に 1.68× の影響
    (lock-violation で緩和されるという建付け)(§6.2, §8.3.8, Fig. 24)。
  - lock-violation はシステム故障時に commit-chain 上の依存 TX 全員のロールバックを
    強制する (§5.4.2)。
  - SLT キューは同一タプルへの並行 NDP TX を 4/7(2B)または 7/15(1B)に制限
    (host TX は無制限)(§5.1)。
  - 現行の NDP 操作は scan/selection/projection/update のみ (§4.1.3)。デバイス上で
    索引を使わない (§8.3.1)。
  - NDP 実行中のストレージ枯渇は 2–10ms の追加ラウンドトリップ (§4.1.2)。
  - ベンチマークハーネスの制約で持続 20TX/s までしか検証できていない (§8.3.9)。
- Inferred [inference]:
  - 速度向上の源泉は「データ移動と資源競合の削減」であり (§8.3.1 Insight)、PE 自体は
    26× 遅い (Table 1)。したがって、host が大バッファ・多コアで cold データ転送が
    ボトルネックにならない構成(あるいは選択率が低く索引が効く更新)では利得が縮む
    はず。Fig. 19(A) の 0% 選択率で既に pgSQL に負けていることはこの境界の存在を示す。
  - First-Updater-Wins + commit 時 ΔVID_map 検証という設計上、長時間 NDP 更新は host の
    hot 更新と衝突すると丸ごと破棄されうる(§8.3.7 の abort 実験が示す通り)。in-situ
    SELECT FOR UPDATE で緩和されるが、これはロック先取りなので host 側 OLTP を先に
    止める(Fig. 25 の第2フェーズで host スループットが 0 に落ちる)。「NDP 更新 vs
    host OLTP のどちらを待たせるか」のポリシー問題は未解決に見える。
  - SLT が host メモリ側にある設計は host-centric な競合には有利だが、§2.2.1 自身が
    「device-centric で高競合な更新 NDP には HA をデバイス側に置くのが正しい」と述べて
    いる。HA 配置の比較実験は無く、デバイス側配置での成立性は開いている。
  - 750–800ns/lock のデバイス側ロックコストは、PE が 180MHz と遅いから相対的に 6.4% で
    済んでいる面がある (Table 2)。デバイス側計算が高速化(hardwired FPGA ロジック化、
    §8.2.1 Insight が示唆)すると、ロック取得が新たなボトルネックとして顕在化しうる。
  - overflow log は「commit 前に host へ転送」される (§6.2) ため、メディア回復の保証は
    commit 済み TX に限られる。lock-violation 中の依存 TX はデバイス故障時にも(NDP TX の
    EOT 前なら)巻き添えで abort するはずだが、デバイス故障と commit-chain の相互作用は
    本文で明示的に論じられていない。

## Relations
- 本論文の直接の土台(著者ら自身の先行研究): neoDBMS ICDE demo [14]、update-aware
  read-only NDP [89]、CCIX 上の初代 SLT [16](本論文 §2.3.6 が限界を列挙して置換)、
  HW 詳細 DANSEN [85]、NVMulator [86]、hybridNDP コストモデル [53]、preloader/unloader
  [15] (§2.3, §4.1.1, §7.1)。
- [[2026-pvldb-zhao-sidle.md]] (SIDLE: CXL ヘテロメモリ索引): 本論文は cache-coherent
  interconnect を「ロック状態の共有」に使い、SIDLE は「索引ノードの配置」に使う。
  どちらも 64B cacheline 粒度の coherence を DBMS 内部構造に露出させる潮流で、
  本論文 §2.2.2 の CXL Type 2/3 の整理は SIDLE 側(Type 3 相当の memory expander)と
  ちょうど相補的。abstract-only 時代の推測リンクが本文で裏付けられた形。
- [[2026-fast-wei-dmtree.md]] (DMTree: DM 上の協調ロック): 「ロックをデータと別の、
  同期が安い場所に置く」という設計判断が共通。DMTree は lock を compute server 側に
  分散(RDMA_CAS を compute 間で実行)、本論文は lock を host pinned memory に集約して
  CCI atomics で共有。interconnect が RDMA(明示メッセージ)か CCI(load/store +
  coherence)かで、キュー設計(DMTree は embedded unlocking、本論文は 16B queue +
  host-shared lock)がどう変わるかの比較軸になる。
- [[2026-eurosys-cai-rdma-locks.md]] (StreamLock, abstract-only): RDMA NIC 上の分散
  ロックプリミティブ。本論文の SLT(CCI atomics + HW locking module)と「NIC/インター
  コネクト機能でロックを実装する」軸で正面から比較可能。StreamLock の PDF 入手後、
  順序付け機構(パケット受信順 vs SLT キュー+HLT)を対比する価値がある。
- [[2026-eurosys-lopes-pim-txn.md]] (PIM-TIDE, abstract-only): 弱い near-data 計算資源
  (UPMEM DPU vs 180MHz MicroBlaze)上でトランザクション実行を成立させ、host CPU を
  選択的に協調に使うという問題設定が同型。あちらは deterministic execution、こちらは
  悲観ロック + shadow-paging 的アトミシティと、解が対照的。
- [[2026-pvldb-kuschewski-btrlog.md]] (BtrLog: クラウド WAL): 「commit クリティカル
  パス上のログ書き込みレイテンシ」への攻め方の対比。BtrLog は 1 RTT durable append で
  ログ書き込み自体を速くし、本論文は CLV でログ転送・flush を有効な仕事と重ねて
  「見かけ上」クリティカルパスから外す。両者は併用可能に見える(overflow log の
  受け側を BtrLog 型ログサービスにする等)。
- [[2026-edbt-lee-cxl-pools.md]] (SAP HANA + CXL プール): 実 CXL ハードウェアを DBMS に
  接続した実証という点で隣接。あちらは容量拡張(CXL.mem 系)でコヒーレンス共有は
  使わず、本論文が求める CXL.cache/Type 2 の実機評価はまだ産業側にも無い、という
  ギャップの確認に使える。
- [[2026-pvldb-lee-how-to-write-to-ssds.md]]: out-of-place 書き込みを前提にした DB/デバイス
  協調設計という広い軸で弱く関連(本論文の「新版を専有ページ範囲へ out-of-place 生成
  して write-atomicity を得る」(§1 Problem 2, §5.4.5) は、あちらの DB WAF 削減の議論と
  同じ物理的性質を別目的に使っている)。

## Idea seeds
- [inference] 「NDP 更新はアトミックだから undo/redo 不要」という観察 (§6) は、
  neoDBMS 固有ではなく「out-of-place 生成 + マップ差分のアトミック適用」を満たす任意の
  エンジン(shadow paging 系、あるいは LSM の SST 生成 + manifest 更新)に移植可能な
  抽象に見える。第一検証: LSM エンジンの remote compaction(ArceKV 系の文脈)を
  「ΔManifest のみ返す NDP 更新」とみなし、本論文の basic/extended logging の二層を
  そのまま適用してログ量と回復時間を測る。
- [question] CLV による commit-chain は「システム故障で依存 TX 全滅」(§5.4.2) という
  税を払う。overflow log の転送時間が長いほど chain が伸びる (Fig. 25) ので、
  chain 長(= 巻き添えロールバック量)と log 転送帯域のトレードオフが定量化できる
  はず。本文はこの分析をしていない。20TX/s 制限 (§8.3.9) を外したハーネスで chain 長
  分布を測るのが最初の実験。
- [question] SLT の host 側配置は host-centric 前提 (§5.1) で、§2.2.1 は device-centric
  なら HA をデバイス側に置くべきと述べる。ロックテーブルの配置(host / device / 分割)を
  ワークロードの host:NDP 更新比で動的に切り替える「ロック配置最適化」は、DMTree の
  compute-side 配置・StreamLock の NIC 配置と合わせて、統一フレームワークで論じられる
  余地がある。まず 3 ノートの配置決定要因(レイテンシ非対称性、atomics の可用性、
  故障ドメイン)を表にして比較する。
- [inference] 導入実験のベースラインが 4 コア ARM + 16GB の PostgreSQL v12 である点は、
  ≥6.52× の解釈に効く。host を多コア・大バッファにした場合に mixed workload の
  バッファ汚染がどこまで残るかは、本論文の Fig. 19(C)(I/O 経路別スループット)を
  コストモデル化すれば実機なしでも一次近似できる。NDP 論文の「host-only ベースライン
  の弱さ」を横断調査する素材として DMTree(memory server 1台構成)と対にできる。
- [question] CXL.cache/HDM-D でレイテンシが約2倍 (§2.2.3) になったとき、SLT の
  デバイス側ロック 750–800ns → 約 1.5–1.6μs で、Exp 2 の 6.4% オーバーヘッドが
  どこまで膨らむか。ロック回数は選択率に比例するので、選択率 × ロック単価の簡単な
  モデルで「CXL 実機で update NDP が成立する選択率レンジ」を予測できる。実 CXL Type 2
  デバイス評価 [45] の数値を使えば机上で検証可能。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: full-text 格上げ(status: abstract-only → read。手動取得した PDF 全文を読解し全節を執筆)
