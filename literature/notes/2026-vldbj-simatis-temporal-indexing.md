---
title: "Scalable lighting-fast temporal indexing"
authors: [Panagiotis Simatis, George Christodoulou, Panagiotis Bouros, Nikos Mamoulis]
venue: "The VLDB Journal"            # PDF 自己表記: "The VLDB Journal (2026) 35:17", REGULAR PAPER (p.1)
year: 2026
ids: {doi: "10.1007/s00778-026-00968-6", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1007/s00778-026-00968-6", pdf: "literature/pdfs/2026-vldbj-simatis-temporal-indexing.pdf", code: "https://github.com/GiorgosChristodoulou/LIT (LIT, p.17 脚注16) / https://github.com/psimatis/lit_fossils (LIT+, p.22 脚注20)"}
status: read
read_date: 2026-07-06
tags: [temporal-indexing, time-travel-query, multi-version, interval-index, hint, hybrid-index, larger-than-memory, memory-budget, r-tree, in-memory-index]
---

## TL;DR
時間発展するテーブルの全版(バージョン)を索引し time-travel クエリに答える問題で、
live(現在有効、終端未知)と dead(過去、区間確定)の版を単一構造で扱う従来方式を捨て、
両者を別構造に分離するハイブリッド索引 LIT を提案(LiveIndex = 分割付き enhanced
hashmap、DeadIndex = 成長ドメイン対応 HINT)。さらにメモリ予算 M の下で古い dead 版
(fossil)をディスク上の R-tree(FossilIndex)へ一括退避する LIT+ に拡張。in-memory の
SOTA(Timeline index、MVB-tree、te-HINT)比で桁違いの総時間短縮を主張し、空間は版数に
線形 (abstract, §9)。著者らの SIGMOD 版 LIT 論文 [19] の拡張版ジャーナル論文 (§1)。

- [question] 掲載タイトルは "lighting-fast" だが、先行版 [19] のタイトルは
  "LIT: lightning-fast in-memory temporal indexing" (p.25, ref 19)。掲載文字列を
  そのまま採用したが、おそらく "lightning-fast" の誤植。

## Problem & motivation
- [paper] temporal database は DB の進化を追跡し、過去時点(または期間)における DB
  インスタンス上でクエリを処理する time-travel クエリを支援する (§1)。時間旅行クエリは
  SQL 拡張 [27,34] に含まれ、PostgreSQL、Oracle Workspace Manager、IBM DB2、Microsoft
  SQL Server、Teradata、MariaDB に実装がある (§1, p.2 脚注1–3)。
- [paper] 既存の temporal 索引は2分類: (1) transaction-time / multi-version DB 向け
  (MVB-tree [4]、Timeline index [30])、(2) (時間)区間向けデータ構造 [6,8,17,22,33]。
  (2) は検索が速いが、①終端未知の live 版を実質的に支援できない、②静的ドメインの静的
  区間向け設計、という欠点を持つ (§1)。
- [paper] HINT [17] は in-memory 区間索引の SOTA(m+1 レベル階層、レベル ℓ がドメインを
  2^ℓ 分割、区間は全レベルから被覆する最小の partition 集合に割当・レベルあたり高々2、
  originals/replicas の2クラス分け、端点比較が必要な partition は期待高々4)だが、
  区間端点のドメインが事前既知でなければならない (§2.1, Fig. 2b)。ドメインが成長する
  temporal DB では partition 更新・割当変更が必要になる (§2.1 "Deficiencies")。
- [paper] transaction-time DB の索引付けは valid-time DB より難しい: 終端未知の live
  レコードが存在するため (§2.2)。
- [paper] MVB-tree [4] 系はディスク I/O 最小化指向で、main-memory 版は §2.1 の区間索引に
  比べ検索・更新とも相対的に遅い (§2.2)。Timeline index [30](SAP HANA)は Events
  Sequence Table(EST)+ Checkpoint Tables(CT)で更新は末尾追記のみと最小コストだが、
  クエリ評価は checkpoint 以降のイベント走査とアクティブ集合更新のため高価。稀な CT
  構築イベントも高コスト (§2.2)。
- [paper] 本論文の立場: live と dead を同一構造で索引する従来方式からの大きな離脱として、
  live/dead を別データ構造に分離し(死んだ版は前者から後者へ転送)、それぞれを最適化
  する (§2.2, §1)。
- [paper] ジャーナル版の追加要素: 索引の要求量が更新数とともに成長しメモリが枯渇する
  ため、指定タイムスタンプ t_f 以前に死んだ版(fossil)をディスク常駐 FossilIndex に
  周期的にオフロードする LIT+ を新規提案 (§1, abstract)。

## System model & assumptions
- [paper] 対象は更新され続けるテーブル T。更新イベントは (1) 挿入、(2) 削除、(3) 属性値
  変更で、(3) は削除直後の挿入としてモデル化 (§3)。live 版の終端は常に可変の t_now (§3)。
- [paper] クエリ2種 (§3): Query 1 [Pure Timeslice/Timerange] = 時点 q.t または区間
  [q.tstart, q.tend] に有効だった全版を有効区間ごと取得。Query 2 [Range
  Timeslice/Timerange] = 加えて属性 A の範囲述語 q.Astart ≤ r.A ≤ q.Aend を課す。
  Query 2 では非時間属性 A は単一を仮定(複数属性は §6.3 で議論)。索引属性 A 以外の
  属性のみ変わった更新は索引に影響せず、A 値が同じ連続版は同一版とみなす (§3)。
- [paper] 過去の版は temporal DB から削除されないため、(LIT の)DeadIndex は削除不要の
  insert-only で運用できる (§1, §5.3)。
- [paper] 並行性制御は DBMS のトランザクションマネージャが担い(SAP HANA [30] と同様)、
  索引からは独立。LIT はコミット済み更新を ingest する (§8)。time-travel クエリは過去
  参照であり、挿入は常に t_now で起きるためクエリと競合しない。削除とも競合しないが、
  「LiveIndex から削除後、DeadIndex へ挿入前」にクエリが走ると誤結果になり得るため、
  Live→Dead の移動は直列(クエリと非交錯)に行う。移動コストは約 150 ナノ秒と低いため
  性能影響はないと主張 (§8)。
- [paper] fossilization も直列化され、DeadIndex と FossilIndex への排他制御を取る。並列
  fossilization は並行アクセス管理が複雑になるため不採用。fossilization は稀なので影響は
  無視できると主張 (§8)。fossilization は単一のシステムトランザクションとして原子的に
  実行され、dead 版は DeadIndex か FossilIndex のどちらか一方のみに存在する (§8)。
- [paper] 永続化・リカバリ (§8, Fig. 12): 各更新イベントをログに書き、LIT のバックアップ
  (LiveIndex/DeadIndex のメモリ構造のダンプ)を周期的にディスクへ書く。時刻 t_B の
  バックアップから、ログ replay + 以降のイベント ingest で t_now まで復元。t_B 以前の
  ログは削除。FossilIndex は既にディスク上にあり、ディスク側の故障回復は RAID 等の別
  機構を仮定 (§8)。
- [paper] 評価は全て単一スレッドプロセス (§9.1, §9.3)。マルチスレッド処理は future work
  (§10)。
- [inference] 「クエリは過去のみ・挿入は常に t_now・CC は上位に委譲」という分業前提が
  §8 の軽量な整合性議論を成立させている。現在状態への読み書きと time-travel が混在する
  HTAP 的な設定や、複数 writer の索引内競合はこの論文のモデル外。
- [inference] リカバリはメモリ構造の全ダンプ+replay 方式で、索引サイズは GB 級
  (Table 11: TAXIS で 2 GB 超)なので、バックアップ頻度・復旧時間のトレードオフが
  実運用では効いてくるはずだが、その測定・分析は本文にない。

## Approach
### te-HINT: 素朴な拡張(比較用ベースライン)(§4)
- [paper] HINT を time-evolving 化した te-HINT を最初の試みとして定義: ①live/dead 両方を
  保持(originals/replicas をさらに live/dead に分け、P^OL, P^OD, P^RL, P^RD の
  sub-partition を導入。dead は不変、live は削除・移動され得る)(§4.1, Fig. 3)。
  ②成長する時間ドメインを支援 (§4)。
- [paper] 挿入: live 区間の終端を現ドメイン終端(horizon t_H)と仮定して HINT 挿入
  アルゴリズムを実行し、補助 KV 構造 H_{r.id→start} にも登録 (§4.2)。削除: H で
  s.start を引き、s′=[s.start, t_H) の挿入経路を再実行して live sub-partition から除去、
  s=[s.start, s.end) を dead として再挿入(挿入・削除で対象 partition 集合は異なり得る)
  (§4.2)。
- [paper] ドメイン拡張: t_now ≥ t_H の更新が来たらドメインと t_H を倍加。新レベル 0 を
  追加し既存レベル番号を +1(既存 partition の中身は不変)、旧 P_0,0 内を除く全 live
  区間を新 P_1,1 に live replica として移す(live の複製を減らし以後の更新を容易にする)
  (§4.2, Fig. 3c)。
- [paper] te-HINT はクエリは高速だが、版の生成・終了のたびに複数 partition への挿入・
  転送が起きるため更新が遅い、という欠点が LIT の動機 (§5 冒頭)。

### LIT: live/dead 分離ハイブリッド (§5, Fig. 4)
- [paper] LiveIndex I_L は live 版を start 時点のみで索引、DeadIndex I_D は dead 版を
  有効区間で索引。版の生成は I_L のみ、死亡は I_L から削除して I_D へ挿入。クエリ
  q=[q.tstart, q.tend] は両者を独立に probe(互いに素な集合なので重複結果なし)。
  I_L は q.tend のみで probe し、q.tend より前に始まった live 版は全て結果 (§5.1)。
- [paper] LiveIndex の内部 id `num`: 更新ストリームから start が読まれた順の連番。
  削除対象の特定と、start による暗黙の順序付けに使う。補助ハッシュ表 H_{r.id→num} を
  維持 (§5.2)。
- [paper] LiveIndex のデータ構造3案 (§5.2.1): ①append-only 配列(挿入 O(1) 追記、削除は
  tombstone、クエリは O(n) 走査)。②探索木(B+-tree 等、num がキー。更新・検索とも
  O(log n)、tombstone 不要)。③enhanced hashmap(Gapless hashmap [46] や Java
  LinkedHashMap 相当: 連続メモリ領域に格納、挿入は末尾追記、削除は末尾要素との swap で
  O(1)、走査は要素数線形)。③はクエリ O(|I_L|)(live 数)で、配列の O(n)(全更新数)
  より低い (§5.2.1)。
- [paper] LiveIndex の temporal partitioning (§5.2.2, Fig. 5): I_L を buffer のチェーンに
  分割し、num(すなわち start)がbuffer 間で単調になるよう維持。クエリは q.tend を含む
  B_end より前の buffer は無比較で全報告、B_end 内のみ比較。①duration-based(等幅
  D_L 時間単位。B_end は ⌊q.tend/D_L⌋ で O(1) 特定。削除には buffer ごとの最小 num と
  ポインタを持つ on-top 構造を二分探索)。②capacity-based(各 buffer 高々 C_L 件。
  削除は num/C_L 除算で buffer 特定。クエリには buffer ごとの最小 start を持つ on-top
  構造を二分探索)。分割は buffer 内データ構造と直交 (§5.2.2)。
- [paper] 最適化 (§5.2.3): live が死んで疎になった buffer の統合(duration-based は隣接
  疎 buffer をマージ、capacity-based は容量が例えば C_L の 50% を切ったら mark して
  隣接 marked buffer とマージ)。マージ後は除算による特定が効かなくなるため、最小
  start / 最小 num を持つ on-top 構造の追加が必要 (§5.2.3)。
- [paper] DeadIndex (§5.3): HINT を成長ドメイン対応化して使う。live 区間の転送が不要な分
  te-HINT より単純で、t_H 以降に端点を持つ区間が入ったらレベルを1つ追加して t_H を倍加
  (既存 partition の中身は改名のみで不変)。代替案の 2D 点変換([55]: 区間
  s=[s.start,s.end) を 2D 点にして空間索引)も検討 (§5.3, §2.1, Fig. 2a)。
- [paper] レベル数が過大になった場合のために HINT の最下層レベルを削除するアルゴリズムを
  提案: 削除レベル m の区間を、1 partition に収まるものは直接 P_{m-1,i÷2} へ、その他は
  temporary partition 経由で上位レベルへ段階的に propagate(HINT の最小被覆性を維持)
  (§5.3, Fig. 6)。
- [paper] 複雑性 (§5.4): n 更新後、LiveIndex の空間 O(n)、HINT DeadIndex の空間
  O(m·n)(m = レベル数)。挿入イベント消費は enhanced hashmap チェーンなら O(1)、
  削除は LiveIndex O(1) + DeadIndex O(m)、よって更新あたり O(m)。再構成操作(buffer
  マージ、レベル追加)は稀で償却コストは O(m) 未満。クエリは B_end で O(C_L)(または
  duration-based で O(|I_L|))の比較 + 期待定数(4)個の HINT partition 探索 (§5.4)。

### a-LIT: 属性 A の同時索引 (§6)
- [paper] live 版は時間-A 空間の 2D 点、dead 版は (start, end, A) の 3D 点として扱える
  (§6, Fig. 7)。
- [paper] LiveIndex 2案 (§6.1): ①2D 空間索引(kd-tree/quad-tree/R-tree)+
  H_{r.id→(start,A)}。②A ドメインを分割(equi-width 等)し、partition ごとに §5.2 の
  pure time LiveIndex を構築。クエリの A 範囲に完全被覆される partition は時間条件のみ、
  境界を含む高々2つの partition だけ A 述語を検証。H_{r.id→num} は A-partition id も
  保持する (§6.1, Fig. 8a)。ハッシュ主体の後者の方が更新が速いと予想 (§6.1)。
- [paper] DeadIndex 2案 (§6.2): ①(start,end,A) の 3D 点を 3D R-tree で索引(dead 版を
  線分のまま 2D R-tree に入れる案は long-lived 版の巨大 MBR で非効率)。②A-partition
  ごとにドメイン拡張対応 HINT を1本ずつ (§6.2, Fig. 8b)。
- [paper] 複数属性 A_1..A_m は (m+1) 次元索引か、結合ドメイン上の多次元グリッドで
  multiple pure time indices 方式を拡張 (§6.3)。

### LIT+: メモリ予算下のディスクオフロード (§7, Fig. 9)
- [paper] fossilization timestamp t_f がメモリ常駐とディスク常駐の境界。t_f 以前に死んだ
  dead 版 = fossil はディスク常駐 FossilIndex I_F へ、それ以外の dead は in-memory の
  DeadIndex に留まる (§7.1)。I_L + I_D の合計メモリフットプリントが予算 M を超えると
  fossilization イベントが発火: t_f を前進 → end < t_f の dead を I_D から除去
  (DeleteFossils)→ I_F へ挿入(InsertFossilIntervals)(§7.1, Fig. 9)。
- [paper] クエリ: q.tstart > t_f なら LIT と同一(I_L, I_D のみ)。q.tstart ≤ t_f なら
  3コンポーネント全部を probe。3つは互いに素なので重複なし (§7.1)。
- [paper] t_f の更新 (§7.2): 全 dead を fossil 化するとディスク行きクエリが増える
  space-time トレードオフがあるため、1回の fossilization で空にできるメモリ量の上限
  r·M をパラメータ化。候補 t_f を HINT 最下層 partition の end に限定して探索空間と
  走査を単純化し、I_D のドメイン中央から始めて CountFossilEntries(新 t_f 以前に終わる
  エントリの originals+replicas 総数)による二分探索で、r·M を超えない最大の解放量と
  なる t_f を決める。新 t_f が旧値と等しくなる極端なケースでは直後の partition の end に
  設定して最小量を必ず空ける (§7.2)。
- [paper] DeleteFossils 2案 (§7.3): 前提として [17] の subdivisions 最適化(originals を
  partition 内で終わる P^Oin と後で終わる P^Oaft に、replicas を P^Rin / P^Raft に分割。
  各 subdivision は end 昇順ソート済み)を有効化。①Reconstruct: 全 partition の
  P^Oin/P^Rin を走査して fossil を集め、残りで HINT を作り直す(重複除去は不要 — 各
  dead 版は O_in か R_in にちょうど1回格納されるため)。②Update in-situ: partition を
  3分類し(light gray: P.end < t_f、dark gray: P.end = t_f、white: P.end > t_f、
  Fig. 10)、light/dark gray の P^Oin/P^Rin は定義により全部 fossil なので比較なしで
  空にし、light gray の P^Oaft/P^Raft のみ end > t_f の最初のエントリを二分探索して
  それ以前を除去、white は触らない (§7.3)。t_f を最下層 partition の end に置く限り
  ①は比較不要だが index 全体の再構築が要る、というのが②の動機 (§7.3)。なお [17] の
  tombstone 削除は使えない(メモリを空けるには物理削除が必要)(§7.3)。
- [paper] FossilIndex (§7.4): fossil を (start, end) の 2D 点にマップしディスク上の
  R-tree [26] で索引。初回はSTR [35] でバルクロード。以降は新規のバッチ挿入: 到着
  fossil を start でソート(空間局所性向上)→ R-tree の leaf ノードサイズに合わせて
  バッチ分割 → バッチごとに新 leaf を作り、leaf 直上の internal ノードへ直接挿入
  (必要なら split)(§7.4, Fig. 11)。fossilization の I/O コストは挿入 leaf 数に有界
  (非 leaf は少数でメモリに収まる想定、特に 8KB 等の大ノード)。検索 I/O はアクセス
  される leaf 数 ≈ 結果数/ノード容量と見積る (§7.4)。
- [paper] a-LIT+ (§7.5): live と in-memory dead は a-LIT の A-partition 設計、fossil は
  単一の FossilIndex((start,end,A) の 3D R-tree)と単一の t_f。属性 A の分だけメモリ
  フットプリントが増え fossilization が頻発するため、t_f 更新ではメモリ使用量最大の
  DeadIndex を優先して選ぶ(dead 索引間のバランス維持と、t_f が新しくなりすぎることに
  よるクエリ劣化の防止)(§7.5)。

## Evaluation
- Setup [paper] (§9.1, Table 1, Table 2): 実データ6種 + 検索キー A。TAXIS-F/-P(NYC
  タクシー 2009、約 1.69 億件、A=運賃(実数/normal)・乗客数(整数/zipfian))、
  BIKES(NYC 自転車 2014–2021、約 1.01 億件、A=乗り手の生年、normal)、FLIGHTS
  (US フライト 2013–2022、約 6133 万件、A=出発遅延、zipfian)、WILDFIRES(US 山火事
  1992–2015、778,410 件、A=焼失面積、zipfian)、BOOKS(オーフス図書館 2013、
  2,050,707 件、A=貸出冊数、zipfian)。BOOKS/WILDFIRES は長い有効区間、TAXIS/BIKES は
  極端に短い区間、FLIGHTS は中間 (§9.1)。各区間を insert/delete イベントに分割し 10K
  クエリを一様に interleave。更新/クエリ比は TAXIS 34000/1、BIKES 20000/1、FLIGHTS
  13000/1、BOOKS 410/1、WILDFIRES 156/1 (§9.1)。全て C++、gcc -O3 -mavx
  -march=native (§9)。in-memory 実験: AMD Ryzen 9 3950X 3.5GHz、64GB DRAM、単一
  スレッド (§9.1)。LIT+ 実験: Intel Core i7-14700K 3.4GHz、64GB RAM、4TB NVMe SSD
  (PCIe 4.0)、on-disk R-tree のページは 8KB (§9.3)。
- LiveIndex チューニング [paper] (Table 3, §9.2.1): 更新は配列最速(TAXIS 9.92s vs 木
  47.9s vs hashmap 12.42s)だが、update-heavy な TAXIS では tombstone で配列のクエリが
  破綻(409s)。enhanced hashmap が常に競争的(TAXIS query 0.011s、BOOKS query
  ~6.4s)で総時間最小のため以後採用。partitioning は capacity-based が duration-based を
  平均 10% 上回り、C_L=10000 に設定 (Fig. 13, Table 4)。
- DeadIndex チューニング [paper] (Table 5, §9.2.1): HINT は pure time-travel クエリで
  2D R-tree(Boost.Geometry)比 1〜2桁高速(TAXIS: query 0.001s vs 3.21–59.2s)、
  挿入も update-heavy TAXIS で1桁高速(47.9s vs 69.7s、BOOKS のみ R-tree が競争的)。
  以後 HINT を採用。
- Pure time-travel [paper] (Fig. 14, Table 6, Table 7, §9.2.2): LIT が全ストリームで
  総時間最良、ほぼ全ケースで Timeline が2位、te-HINT が最下位(例外 WILDFIRES)。
  クエリは LIT・te-HINT が Timeline より常に低コスト(te-HINT は LIT より常に遅い)。
  更新は Timeline が最良で LIT が競争的(TAXIS: Timeline 12.3s、LIT 22.89s = Live 14.5 +
  Dead 8.43)、te-HINT はレベル間の区間移動コストで桁違いに遅い(TAXIS 1886s)(Table 6)。
- a-LIT チューニング [paper] (Table 8, Table 9, §9.2.3): LiveIndex の 2D R-tree は削除
  コストで実用外(TAXIS-F 更新 1163s vs 複数 pure time indices 19.7s)。単一 pure time
  index は更新最速(16.2s)だがクエリで1桁劣る。クエリ集約型(BOOKS)での得が
  update-heavy での損を上回るため、複数 pure time indices を採用 (§9.2.3)。DeadIndex も
  A-partition ごとの複数 HINT が最良(TAXIS-F: 挿入 9.48s / クエリ 0.40–0.51s vs 3D
  R-tree 81.9s / 40.6s)(Table 9)。A ドメインは equi-width で 6–7 分割(十分性は紙面外の
  テストによる)(§9.2, p.15 脚注15)。
- Range time-travel [paper] (Fig. 15, Table 10, §9.2.4): a-LIT と LIT(pure)(時間のみで
  索引し A は後検証)が MVB-tree(main-memory 再実装)に全テストで勝つ。主因は
  MVB-tree の更新コスト(TAXIS-F: 341s vs a-LIT 29.3s vs LIT(pure) 27.9s)。MVB-tree は
  更新最少の BOOKS でのみ競争的。a-LIT は A で探索空間を刈れるため LIT(pure) に常に勝ち、
  query-heavy ストリームではさらに差が開くと著者らは予想 (§9.2.4)。
- 索引サイズ [paper] (Table 11, Table 12, Fig. 16, §9.2.5): LIT は Timeline より小さい
  (TAXIS: 2042MB vs 3086MB)。te-HINT の最大フットプリントは LIT と同一(最終的に
  同一の HINT になるため)。a-LIT は MVB-tree より小さい(TAXIS-F: 3744MB vs 8522MB。
  LIT(pure) は 3404MB とさらに小)。サイズは更新数に線形に成長 (Fig. 16)。
- LIT+ チューニング [paper] (§9.3.1): DeleteFossils は Update in-situ が Reconstruct を
  全データセットで上回り、典型的に 6×–12× (Fig. 17)。FossilIndex 更新はバッチ挿入が
  R*-tree 逐次挿入に全ケースで勝つ(例外: WILDFIRES の 5% チャンク = 38,921 件と小さく、
  ソースのソート代が R*-tree の再構成代を上回る)(Fig. 18)。メモリ予算 M(データセット
  サイズ比 %)が大きいほど fossilization 頻度が減って更新時間が大きく減少、削減係数
  r は影響が小さく r=10% が全設定で最速 (Fig. 20)。a-LIT+ は A の分メモリ要求が高いので
  公平性のため M を +5% 調整 (§9.3.1)。
- LIT+ 内訳 [paper] (Fig. 21, §9.3.1): 更新時間は LiveIndex が支配的(全 insert/delete を
  処理するため)、DeadIndex > FossilIndex。例外 BOOKS は長寿区間で LiveIndex が肥大 →
  頻繁な fossilization → 小さく維持費の安い DeadIndex。a-LIT+ では全データセットで同じ
  「DeadIndex の落ち込み」が出る(A によるメモリ圧の増加と 3D R-tree FossilIndex の
  オーバーヘッドのため)(Fig. 21 右)。
- LIT+ クエリ [paper] (Fig. 22, Fig. 23, §9.3.2): M 増加でディスク行きクエリの割合が減り
  FossilIndex クエリ時間が減少(DeadIndex 側は増加)、LiveIndex は M に不感。a-LIT+ でも
  LiveIndex が最速、次いで DeadIndex、FossilIndex(例外 BOOKS では LiveIndex >
  DeadIndex)。
- LIT+ vs 競合 [paper] (Fig. 24, Fig. 26, §9.3.2): LIT+ はディスク常駐 Timeline と
  「in-memory LiveIndex + on-disk 2D R-tree(dead+fossil 一体、LRU キャッシュ利用)」
  ハイブリッドの両方に総時間・クエリ時間で勝つ(R-tree 解は TAXIS で極端に遅く実験
  打ち切り)。a-LIT+ はディスク常駐 MVB-tree と「LiveIndex + on-disk 3D R-tree」に
  総時間で全データセット勝利、MVB-tree が次点 (Fig. 26)。スケーラビリティ: TAXIS
  1〜3年分で総時間・クエリ時間とも滑らかに増加 (Fig. 25)。
- [inference] 評価がカバーしていないもの:
  - 全実験が単一スレッド。§8 の直列 migration(~150ns)や serialized fossilization が
    並行クエリ/更新の混在下でどれだけスループットを制限するかは未測定(マルチスレッドは
    §10 の future work)。
  - Timeline と MVB-tree は著者らの再実装(それぞれ「fully operate in main memory に
    再実装」「disk-resident」)であり (§9.2.2, §9.2.4, §9.3.2)、原実装との性能差は不明。
  - クエリは常に 10K 件・タイムライン上一様配置 (§9.1)。特定の古い期間へのクエリ集中
    (fossil ホットスポット)や、更新とクエリの比率を系統的に振った感度分析はない
    (query-heavy での a-LIT 優位は §9.2.4 で「予想」と明言)。
  - A-partition 数(6–7)の選定実験は「紙面の都合で非掲載」(p.15 脚注15)。
  - リカバリ(§8)の実測(バックアップ時間・復旧時間・ログ量)は無い。

## Limitations
- Stated [paper]:
  - t_f の更新は本質的に space-time トレードオフで、進めすぎるとディスク行きクエリが
    増える(そのための r パラメータ)(§7.2)。
  - a-LIT+ の fossil は単一 FossilIndex・単一 t_f に限定(in-memory 側の A-partition
    設計と非対称)(§7.5)。
  - 並列 fossilization は DeadIndex/FossilIndex への並行アクセス管理が複雑になるため
    見送り、直列化を選択 (§8)。
  - マルチスレッド処理、他の temporal クエリ(集約・結合)、オープンソース DBMS への
    統合は future work (§10)。
  - (LiveIndex の)2D R-tree 案は R-tree の維持コストの高さから実用外 (§9.2.3,
    p.18 脚注19)。
- Inferred [inference]:
  - LiveIndex のクエリコストは本質的に「q.tend までの live 版の列挙」であり、B_end 以前は
    無比較でも出力サイズ分の仕事は必ず発生する。live 集合が巨大で選択率の低い属性述語を
    伴うケース(a-LIT の A-partition 境界)では検証コストが残る。BOOKS(長寿区間)で
    LiveIndex がクエリ支配的になる Fig. 23 の挙動はその兆候と読める。
  - FossilIndex の検索 I/O 有界性は「結果数/ノード容量」という期待値ベースの見積り
    (§7.4)で、start ソートによる空間局所性が長寿区間混在時にどこまで保たれるか
    (leaf MBR の重なり)は分析されていない。
  - fossilization は「I_L+I_D が M を超えた時」に同期的に走る設計 (§7.1) で、その間
    更新・クエリと排他 (§8)。fossilization 1回の所要時間そのもの(テール遅延への影響)は
    Fig. 17 の累積時間でしか示されず、イベント単位のレイテンシスパイクは読み取れない。
  - 更新イベントは到着順 = 時間順(num が start 順の連番になる前提、§5.2)であり、
    遅延到着(out-of-order)イベントや過去時点への訂正(bitemporal 的更新)は扱えない
    設計に見える。
  - 属性 A の equi-width 分割は分布歪み(zipfian な TAXIS-P 等)で partition 間の負荷
    偏りを生むはずだが、動的再分割の議論はない(単一 index ケースが「極端に歪んだ分布の
    近似」として測られているのみ、§9.2.3)。

## Relations
- 本文内の系譜: 土台は HINT [17,18](in-memory 区間索引の SOTA、§2.1)。本論文は著者らの
  SIGMOD 2024 論文 [19]("LIT: lightning-fast in-memory temporal indexing")の拡張で、
  LIT+ / a-LIT+(メモリ予算・fossilization・FossilIndex)とそれに伴う §7–§8、§9.3 が
  主な新規部分 (§1, §10)。競合は Timeline index [30](SAP HANA)、MVB-tree [4]、
  te-HINT(本論文定義のベースライン、§4)。FossilIndex は R-tree [26] + STR バルク
  ロード [35]。
- 現行コーパス(49 ノート)には temporal / multi-version 索引や time-travel クエリを主題と
  するノートが無く、直接関連として挙げられるものはない。[inference] 「メモリ予算超過分を
  ディスクへ周期退避する」という larger-than-memory の構図はコーパスの階層ストレージ系
  ノートと緩く響き合うが、対象領域が異なるためリンクは張らない。

## Idea seeds
- [inference] LIT の live/dead 分離は、MVCC ストレージエンジンの「現行版 vs 版チェーン」
  分離と同型に見える。LIT を MVCC DBMS の版ストア上の二次索引として統合すれば、GC
  (不要版の破棄)と fossilization(古い版の退避)を単一の t_f 系ポリシーで統一できる
  可能性がある。最初の検証: 公開コード(2リポジトリ)の DeadIndex 移動パスに「保持期間を
  過ぎた fossil の破棄」を足し、時間旅行可能範囲とメモリ/ディスク消費のトレードオフを
  測る。
- [question] 更新イベントの到着が時間順でない場合(分散環境のコミット順 vs タイムスタンプ
  順の乖離、bitemporal 訂正)に LiveIndex の num 単調性と HINT の originals/replicas
  不変条件はどう壊れるか。out-of-order 耐性を持つ LIT 変種は開いた問題に見える。検証:
  ストリームに数%の遅延イベントを混ぜて公開実装の正しさ・性能劣化を観察する。
- [inference] fossilization は LSM-tree の compaction/tiering とアナロジーがある(メモリ
  予算駆動・バッチ書き出し・r=書き出し量制御)。LSM 系で蓄積された知見(書き出しの
  ペーシング、テールレイテンシ制御、並列 compaction)を fossilization に移植する余地が
  ある。§8 が並列 fossilization を「複雑さ」を理由に見送っている点は具体的な研究ギャップ。
  最初の検証: fossilization 中の更新停止時間をイベント単位で計測し、インクリメンタル
  (partition 単位)fossilization と比較する。
- [question] マルチスレッド化(§10 future work)で最初に衝突するのはどこか。候補は
  ①H_{r.id→num} ハッシュ表、②capacity-based buffer 末尾への追記、③HINT のドメイン
  倍加(全体構造の改名)。検証: 公開コードに read-write ロックを入れてスケーリング
  カーブを取るだけでボトルネックの一次切り分けはできるはず。

## Changelog
- 2026-07-06: created (status: read)
