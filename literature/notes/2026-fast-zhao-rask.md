---
title: "\"Range as a Key\" is the Key! Fast and Compact Cloud Block Store Index with RASK"
authors: [Haoru Zhao, Mingkai Dong, Erci Xu, Zhongyu Wang, Haibo Chen]
venue: "FAST '26 (24th USENIX Conference on File and Storage Technologies)"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/fast/Zhao0XW026"}
urls: {paper: "https://www.usenix.org/conference/fast26/presentation/zhao", pdf: "literature/pdfs/2026-fast-zhao-rask.pdf", code: "https://ipads.se.sjtu.edu.cn:1312/opensource/rask-index"}
status: read
read_date: 2026-07-06
tags: [range-index, cloud-block-store, ebs, in-memory-index, log-structured, art, garbage-collection, memory-efficiency, trace-analysis]
---

## TL;DR
クラウドブロックストア(EBS)の LBA→物理位置索引が DRAM の主要消費者になっている
問題に対し、「書き込みは連続ブロック範囲(Consecutive Write, CW)を狙う」という
プロダクショントレースの観測から、ブロック単位でなく**範囲そのものをキーにする**
(range-as-a-key, RKey)木索引 RASK を提案。ART 内部ノード + log-structured 葉で、
range overlap は「2段 GC + ablation-based search」、range fragmentation は
「range-conscious split + workload-aware merge/resplit」で処理する。Alibaba /
Tencent / Meta / Google の4社トレースで、10 の SOTA 索引比でメモリ最大 98.9% 削減・
スループット最大 31.0×(abstract)。

## Problem & motivation
- [paper] EBS-index は I/O クリティカルパス上にあり全量メモリ常駐が必要。ユーザ増と
  高密度メディア(QLC SSD)でエントリ数が増え、Alibaba Cloud では EBS-index が
  ノードメモリの ~57.1% を消費、最悪ケースでは ~10% のクラスタが物理ストレージの
  ~35% を無駄にするリスク(索引できないデータは使えない)(§1 p.2, §2.2 p.4)。
- [paper] 内訳: LBAIndex(LSM 風: page-table 形式 MemTable → 書き込み要求単位の
  sorted SSTable)が ~17.2%、CompressIndex(4ブロック圧縮単位 CU ごとの配列)が
  ~39.9% のメモリを消費。前者は書き込み要求数に、後者はデータ量に比例して伸びる
  (§2.1, §2.2 p.4)。
- [paper] 代替案の棄却: (1) アーキテクチャ変更やメモリ増設は索引対象データ量という
  根本原因を解決しない (§2.3)。(2) 索引構造の置換 — LBAIndex は既に B-tree / ART /
  PGM-Index よりメモリ・性能とも優る (Fig. 2, §2.3)。(3) CU 拡大 — LZ4 系ストリーム
  圧縮は先頭からの逐次伸長が必要で、random-access 圧縮(FSST)は辞書構築 ~1ms・
  圧縮速度 LZ4 比 9.78× 遅く、可変長圧縮ブロックのオフセット記録も必要になるため
  メモリ利益が消える (§2.3 p.4)。
- [paper] トレース観測: 観測窓 36 リクエスト内で LBA が連続する long CW に属する
  書き込みが 8 ワークロード全てで 65.0–81.5%(Alibaba EBS; Tencent トレースでも同傾向)
  (§3.1, Fig. 3(a) p.5)。Google では 51.6%、Meta では 90.3% の書き込みが 4 ブロック超
  の範囲に及ぶ (Fig. 5, §3.3 p.6)。根本原因は FS/アプリの sequential write 志向と、
  マルチアプリ干渉による分断(blktrace の white-box 分析: MySQL/TPC-C と Redis/YCSB
  で long CW 比率 29.0–99.0%、主因は FS ジャーナリングとアプリのログ書き)(§3.3 p.5)。
- [paper] 前段最適化の余地: I/O compaction(SegmentCache 内で CW に並べ替え・結合、
  窓 = キャッシュサイズ 128 ブロック ≈ 35.2 リクエスト)で LBAIndex 書き込み数
  58.4–77.0% 減 (§3.1, Fig. 3(b))。読みの >85.4% が CW 先頭に整列し 95.7% が先頭
  4 ブロック以内から始まるため、CU を CW に整列させても read amplification は僅少で、
  索引すべき CU 数は 69.1–91.1% 減、残りの読みのレイテンシ増も 0.477–2.60% (§3.2, Fig. 4)。
- [paper] しかし既存索引は可変長範囲キーを扱えない: 時制 DB 系の range-aware 索引
  (interval tree / segment tree / HINT 等)は二次索引前提で covered range を削除しない
  ためメモリ・読み性能とも悪い。点索引の RKey 適応(Eager: 挿入時に重複除去 / Lazy:
  シーケンス番号で読み時解決)はいずれも overlap 処理コストで性能が出ない
  (§3.4, Fig. 6, Fig. 7 p.6)。

## System model & assumptions
- [paper] 対象アーキテクチャ: Alibaba Cloud EBS 3層(BlockClient / BlockServer / DFS)。
  書き込みは JournalFile 永続化→ACK、SegmentCache に非圧縮キャッシュ、閾値
  (例 512KiB)で DataFile へ圧縮書き出し。CU = 4 ブロック (§2.1, Fig. 1 p.3)。
- [paper] キーの定義: range key = 範囲の左端 LBA、range length = 右端 − 左端 + 1
  (両端 inclusive)(p.2 脚注1, p.7 脚注4)。値はユーザ定義で、それ自体が範囲を表し得る
  (EBS では DFS 上の連続物理ブロック位置)(§5.3 p.9)。
- [paper] 意味論の前提: 新しい範囲書き込みに完全被覆された旧範囲は**ゴミ**であり
  削除してよい(last-writer-wins な一次索引)。これが時制 DB の二次索引(被覆されても
  旧レコードは有効)と決定的に異なる前提 (§3.4 p.6)。
- [paper] ユーザ登録関数が2つ必要: DivideValue(範囲分割時に部分範囲の値を導出)と
  MergeRange(2エントリの範囲・値が結合可能か判定し結合値を返す)(Fig. 12, §5.3–5.4 p.9)。
- [paper] RASK は純粋な in-memory 索引で、永続化はアプリケーション(EBS 等)の責務
  (§6.2 末尾 p.10)。
- [paper] 並行制御: 標準的な optimistic lock(ノード単位 write lock + version number)。
  内部ノードは ART の optimistic lock 機構をそのまま使用。葉ヘッダに V_GC /
  V_split / V_merge(各4bit)と deleted bit を持ち、読みは version 検査+リトライ。
  跨り挿入は lock handover、削除ノードは epoch-based GC で回収 (§6.2 p.10)。
- [paper] 一貫性の前提: 読みは葉単位ではスナップショットを得るが、**葉を跨ぐ読みは
  非アトミック**(範囲の部分読み、または後の挿入は見えるのに先の挿入を見逃す)。
  既存の点索引(Masstree / ART / Cuckoo-Trie / HydraList)でも範囲読みは同じ性質で
  あり応用側は既に許容している、実測でも不整合遭遇は ~0.0394%、として妥当性を主張。
  全葉スナップショットは future work (§6.2 p.10)。
- [paper] 運用前提: クラウドブロックストアの内部ロジックは single-threaded であり、
  評価も §7.3 と §7.6 case 3 以外は単一スレッドで実施 (§7.1 p.10)。
- [inference] 上記を裏返すと、RASK の適用条件は「(a) 書き込みが範囲に強く偏る、
  (b) 被覆された旧値を捨ててよい(バージョン保持不要)、(c) 範囲読みのアトミック性を
  要求しない、(d) 永続化・回復は外側で面倒を見る」の4点であり、DBMS の汎用索引と
  してはかなり強い前提。特に (b) は MVCC 系ストレージエンジンへの直接流用を阻む。

## Approach
- [paper] **構造 (§4.1, Fig. 8)**: 内部ノードは ART(path compression とノードリサイズで
  メモリ効率が良い trie)、葉は log-structured leaf — 葉間は全順序、葉内は append-only。
  各葉は anchor key(その葉の最小左端)で内部ノードから索引され、葉の range space は
  「左端 ≥ 自 anchor かつ右端 < 次葉 anchor」で互いに素。葉は Range Array + Value Array
  + 8B ヘッダ(エントリ数と並行制御情報)を持ち doubly-linked (p.7)。
- [paper] **書き込み (Put, Fig. 14 §6.1)**: 対象葉(anchor ≤ 左端の最後の葉)に追記。
  満杯なら GC → それでも満杯なら split して挿入。葉の range space に収まらない残余
  (fragmented range)は連結リスト経由で後続の葉へ反復挿入 (p.9)。
- [paper] **ablation-based search (§5.1, Fig. 9)**: 葉を新→旧の逆順に走査し、未発見部分
  範囲の順序付きリスト(Unfound List)を各エントリとの交差で「削り取る」。全て見つかれば
  早期終了。順序性により最初の重なりを見つけた後の交差除去は O(1)、線形探索コストも
  処理済みエントリ数で有界 (p.7–8)。
- [paper] **2段 GC (§5.2, Fig. 10)**: normal GC は逆順走査しつつ処理済み範囲の和集合を
  非重複範囲リスト(NonOverlapList)で保持し、複数新範囲の和に被覆された旧範囲も検出
  して一括削除。lightweight GC は「同じ左端を持つ新範囲による被覆」だけを O(1) の
  LT Map(左端→最大右端)で検出する軽量版 — Alibaba トレース再生では回収可能エントリの
  平均 73.8% がこのケース (p.8)。lightweight → 空きが出なければ normal、の2段で
  書き込みブロッキング時間を短縮 (p.8)。
- [paper] **range-conscious split (§5.3, Fig. 11)**: 分割点候補を GC で得た NonOverlapList
  の各エントリ左端(先頭以外)から取ることで「範囲を切らない」ことを保証しつつ、
  両葉のエントリ数が最も均衡する候補を選ぶ。候補が無い場合は範囲境界の中央値から選択
  (オーバーフローしない/しても再分割1回で解消できることを extended version [57]
  = arXiv:2601.14129 で証明)(p.8–9, p.18 ref [57])。分割点を跨ぐエントリは DivideValue
  で値も分割 (p.9)。
- [paper] **workload-aware merge/resplit (§5.4, Fig. 13)**: 葉ヘッダの N_frag で断片化
  挿入回数を計数し、閾値超過で左隣接葉と併合を試行(両葉 normal GC → 一時配列に併合 →
  容量に収まれば merge、収まらなければ新しいアクセスパターンに基づき resplit)。
  同一ユーザ書き込み由来の範囲は MergeRange で再結合 (p.9)。
- [paper] **Delete (§6.1)**: tombstone 付き Put として実装。normal GC 時に deleted list
  との重なりを除去して物理削除。Get は tombstone エントリを Unfound List に反映するが
  結果からは除外 (p.9–10)。

## Evaluation
- Setup [paper]: §7.6 は 2×Xeon Gold 5317 (12C) / 188GB DRAM / 7TB NVMe、他は
  1×Xeon Platinum 8369B (24C) / 96GB。既定パラメータ: 葉容量 16、merge/resplit 閾値 4
  (葉の 1/4)(§7.1 p.10–11)。トレース: Alibaba 1.5TB・1週(FullDataset = I/O compaction
  適用後の 1.8k VD・4クラスタ; SampledDataset = 100 VD)、Meta 150GB・3年、Google
  92GB・3ヶ月、Tencent 588GB・10日 (Table 1 p.10, §7.1 p.11)。リプレイは時系列順で
  時間間隔は省略 (§7.1 p.11)。
- Baselines [paper]: 9 の SOTA ordered index(Cuckoo Trie, HydraList, Wormhole, HOT,
  PGM-index, STX B-tree, ROWEX ART, segment tree, interval tree)+ EBS-index(Origin)。
  点索引には可能な範囲で Eager/Lazy RKey 変種を実装し最良版を採用(Table 2: Lazy
  B-tree, Lazy ART, original Wormhole, Eager HydraList, original PGM-index)。HINT は
  公開実装が更新をサポートしないため除外 (§7.1, Table 2, 脚注7 p.11)。
- [paper] 総合 (FullDataset): スループットは 9 ordered index の 2.76–37.8×、Origin の
  1.15–1.82× (Fig. 15(a) §7.2)。メモリは baselines の 1.15–54.7%、Origin の ~19.9%、
  segment/interval tree の 5.31–20.5% (Fig. 15(b) §7.2)。P99 レイテンシ 23.9–97.6% 減・
  P99.999 34.2–99.7% 減、対 Origin では P99.99/P99.999 を 90.9%/98.8% 減(LSM 風
  LBAIndex の write stall を回避)(Fig. 16 §7.2 p.12)。
- [paper] スケーラビリティ: 単一 VD トレースを順序保存でスレッド分配した合成マルチ
  スレッド負荷で、24 スレッド時に baselines の 3.08–21.5×、平均レイテンシ 85.9–98.3% 減・
  テール 82.3–99.9% 減。1–12 スレッドでよくスケールし、それ以上は書き込み偏重・高
  skew トレースで contention により鈍化。split/merge が並行書き込みをブロックするのは
  <0.01% ケース (§7.3, Fig. 17 p.12)。
- [paper] 感度: merge 閾値を下げるとメモリ ~24.0% 減 / スループット ~1.67% 低下。
  葉容量はスループットのピークが 16(小さいと GC 頻発、大きいと overlap 処理コスト増)、
  メモリは 8→64 で 31.3% 減、128 で idle エントリにより 9.09% 増 (Fig. 18 §7.4.1)。
  範囲長 <10 で ordered index 比 1.84–12.71× / Origin 比 +11.1%、平均長 ≤2 の
  最悪スパース時は Origin に 6.64% 劣後(O(1) 更新の Origin が有利)、平均長 ≥100 では
  Origin の 16.10×・他の 17.2–312.97× (Fig. 19(a) §7.4.2 p.12–13)。read-heavy
  (write <5%) で +16.0%–37.3×、write-heavy (≥90%) で +39.1%–38.7× (Fig. 19(b))。
- [paper] 要因分析(optimistic lock 付き ART に順次追加, Fig. 20 §7.5): log-structured
  leaf で 1.50× / メモリ −90.3%(GC 頻度は書き込みの 5.08%)→ normal GC +70.6% →
  lightweight GC 追加で +24.1%(有効確率 59.1%)→ ablation-based search +12.6% →
  range-conscious split +7.56% / メモリ −26.0%(splits の 84.3% は範囲を一切分断せず、
  再分割 <0.01%、葉間エントリ差 <2.34)→ merge/resplit でメモリ −7.70%(性能
  オーバーヘッド 1.90%、発動頻度は書き込みの 0.87%)(p.13)。
- [paper] 一般性 (§7.6): Tencent EBS で 2.35–49.21× / メモリ 27.4–99.3% 減 /
  テール 46.4–98.8% 減 (Fig. 22)。Meta Tectonic の DFS メタデータ(RocksDB の
  MemTable を RASK に置換、3年トレース・7クラスタ)で最大 7.46×(skiplist 比で
  メモリ効率が高く、より多くのエントリがメモリに残るため)(Fig. 21 p.13–14; §1 p.3 では
  「6.46× higher」と表現)。Google flash cache シミュレーションで 1.52–37.52× /
  メモリ 3.2–99.9% 減 / テール 4.2–99.4% 減。唯一の例外は segment tree のテール
  レイテンシが RASK より低い(covered range 除去のコストを払わないため。ただし
  メモリは大きい)(Fig. 23, §7.6 p.14)。
- [inference] 評価がカバーしていないもの: (1) 大半の実験が単一スレッド(生産系が
  single-threaded という理由付けはあるが、マルチスレッド実験も単一 VD トレースの
  人工分配で、実アライバルパターンではない)。(2) リプレイは時間間隔を省略しており、
  レイテンシ数値は「索引操作そのものの」レイテンシであって到着率由来のキューイングを
  含まない。(3) 永続化・クラッシュ回復・索引再構築時間の評価は無い(in-memory 前提)。
  (4) FullDataset は I/O compaction 適用後のトレースなので、Origin を含む全索引が
  「前段最適化済み」の土俵で比較されている — I/O compaction / CU alignment 自体の
  end-to-end 効果(圧縮率・書き込みパス改変コスト)の単独評価は §3 の統計に留まる。
  (5) 範囲読みのアトミック性欠如がアプリ観測可能な異常につながるかの分析は不整合率
  0.0394% の報告のみ。
- [question] スループット向上の上限値が abstract は「up to 31.0×」(p.2)、§1 は
  「1.37–32.0×」(p.3)、§7.2 は「2.76–37.8×(対 9 ordered index)」(p.11) と揺れて
  いる。集計対象(10 baselines か 9 か、平均か最大か)の違いと思われるが本文からは
  確定できない。

## Limitations
- Stated [paper]:
  - 葉を跨ぐ読みの不整合(部分読み/先行挿入の見逃し)。全葉スナップショットによる
    解決は future work (§6.2 p.10)。
  - RASK は in-memory 索引であり永続化はアプリ側の責務 (§6.2 p.10)。
  - 平均書き込み長 ≤2 の最悪スパース負荷では Origin に 6.64% 劣る (§7.4.2 p.12–13)。
  - Google トレースでは segment tree のテールレイテンシが RASK を下回る (§7.6 p.14)。
- Inferred [inference]:
  - last-writer-wins 前提のため、被覆された旧範囲を保持すべき用途(MVCC の版管理、
    時制/二次索引、スナップショット読み取り)にはそのまま使えない。§3.4 が二次索引を
    明示的にスコープ外としている裏返し。
  - 正しさが DivideValue / MergeRange というユーザ関数に依存する。値が「分割・結合
    可能な範囲様の構造」であることが暗黙の型制約で、非分割値(例: 単一オブジェクト
    ポインタ)では RKey の利点が縮む。
  - メモリ削減の主張(対 Origin ~19.9%)は「書き込みが CW に強く集約できる」
    ワークロード特性と前段の I/O compaction に依存しており、スパース書き込み主体の
    テナントが混在した場合のノードレベル効果は §7.4.2 の範囲長感度から外挿するしかない。
  - 12 スレッド超で write-heavy・高 skew 時に伸びが鈍る (§7.3) ので、単一 VD を超えて
    多テナント索引を1インスタンスに統合する設計には追加の分割(シャーディング)が
    要りそう。

## Relations
- [[2026-pvldb-zhao-sidle]]: 同じ「索引がメモリを圧迫する」問題への直交アプローチ。
  SIDLE は索引を CXL 階層へ配置して DRAM を空け、RASK はキー粒度を範囲に上げて
  エントリ数自体を減らす。[inference] 併用可能に見える(RASK の葉は append-only で
  cold 葉の tier 降格と相性が良いか、は要検討)。
- [[2026-arxiv-egorov-flintkv]]: KV ストアの in-memory コンポーネント(MemTable/
  skiplist)を置き換える点で RASK の §7.6 case 2(RocksDB MemTable → RASK, Fig. 21)と
  同じ挿入点を狙う。FlintKV は NVM 永続化、RASK は範囲キーによるメモリ削減と、
  最適化軸が異なる。
- [[2026-pvldb-lee-how-to-write-to-ssds]]: out-of-place 書き込み + GC のトレードオフ
  という設計語彙を共有する。[inference] RASK の log-structured leaf は同じ構図の
  in-memory 版(追記で書きを速くし、被覆エントリ回収を GC に先送り)であり、
  GC タイミング設計(2段 GC)の知見は SSD 側の議論と相互参照する価値がある。

## Idea seeds
- [inference] 「range-as-a-key + 可視性ウォーターマーク」で MVCC に拡張できないか。
  RASK の GC は「被覆 = 死」という LWW 前提 (§3.4) だが、被覆された旧範囲を
  「アクティブな最古スナップショット以前なら回収可」に緩めれば、範囲書き込みの多い
  MVCC ストレージ(bulk load、追記型テーブル)の版索引に使える可能性。検証: 公開
  コードの normal GC(NonOverlapList)に watermark 判定を足し、範囲書き込み比率を
  振った合成負荷で従来型バージョンチェーンとメモリ・スキャン性能を比較。
- [question] 葉跨ぎ読みの不整合率 ~0.0394% (§6.2) は EBS では許容でも、DBMS の
  範囲スキャン(例: 索引専用スキャンの結果整合性)では許容できない。著者が future work
  とする全葉スナップショットのコストはどの程度か — epoch + 葉 version の一括検証で
  実装した場合のスループット低下を実測する小実験は、公開コードで比較的すぐ組める。
- [inference] I/O compaction (§3.1) は「書き込みバッファ内で並べ替えて索引粒度を
  上げる」一般手法として、DBMS の WAL→ページ書き出しや LSM の memtable flush にも
  移植できそう(long CW 比率 29–99% の主因が FS ジャーナリングと DB ログ (§3.3) で
  ある以上、DB 側の書き込みは元々範囲性が高い)。検証: RocksDB の flush 経路で
  key-range 連続 run を1エントリに束ねる RASK 風 SSTable フォーマットを試作し、
  索引メモリと range scan 性能を測る。

## Changelog
- 2026-07-06: created (status: read, USENIX 公式 PDF 抽出テキストを全文読解)
- 2026-07-06: 検証パスによる修正(§6.2 並行制御の "(ROWEX)" 表記を削除(本文は「ART の optimistic lock 機構」とのみ記載、ROWEX はベースライン ART の呼称)、§7.3 スケーラビリティの "competition" を本文どおり "contention" に修正、extended version 参照のアンカーを p.17→p.18 に修正)
