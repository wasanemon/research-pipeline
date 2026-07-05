---
title: "How to Write to SSDs"
authors: [Bohyun Lee, Tobias Ziegler, Viktor Leis]
venue: "PVLDB 19(7):1469-1483"
year: 2026
ids: {doi: "10.14778/3801059.3801063", arxiv: "", dblp: "journals/pvldb/LeeZL26"}
urls: {paper: "https://www.vldb.org/pvldb/vol19/p1469-lee.pdf", pdf: "literature/pdfs/2026-pvldb-lee-how-to-write-to-ssds.pdf", code: "https://github.com/LeeBohyun/ZLeanStore"}
status: read
read_date: 2026-07-06
tags: [ssd, write-amplification, storage-engine, buffer-management, garbage-collection, zns, fdp, b-tree, leanstore]
---

## TL;DR
DBMS の書き込みは DB 層(doublewrite 等)と SSD 内部(GC)で乗算的に増幅される
(Total WAF = DB WAF × SSD WAF)。in-place 書き込みを捨てて out-of-place に移行し、
圧縮+ページパッキング、deathtime によるグルーピング、DB/SSD の GC 単位整合、NoWA
パターン(または FDP ヒント)を併用すると、コモディティ SSD でも SSD WAF=1 を達成できる
ことを LeanStore 拡張(ZLeanStore)で実証。YCSB-A でスループット 1.65–2.24×、
フラッシュ書き込み 6.2–9.8× 削減。TPC-C 15,000WH で 2.45×。

## Problem & motivation
- [paper] in-place LeanStore は 4KiB ページ1回の書き込みあたり 18.85KiB をフラッシュに
  書く(期待の4.7×)。MySQL は 70.22KiB、PostgreSQL は 37.06KiB (Fig. 1)。
- [paper] 原因1: DWB(doublewrite buffering)で DBMS 発行書き込みが約2倍 (DB WAF 2.0)。
  原因2: SSD 内部 GC による増幅 (SSD WAF 2.36, PM9A3 90% full) (§1)。
- [paper] 寿命影響: PM9A3 の保証は 1 DWPD×5年 ≈ 平均 11MB/s 相当。実験中の LeanStore は
  約 400MB/s 書き込み → 約1.5ヶ月で寿命到達 (§1)。
- [paper] 主張: ワークロード知識を持つ最上位層 = DBMS が DB/SSD 両層の WA を統合管理
  すべきで、そのためには out-of-place 書き込みが必須(配置の自由 + DWB 除去)(§2)。
- [paper] 片層だけの最適化は逆効果になり得る(LSM の size-tiering で DB WAF を下げると
  空間消費増で SSD WAF が上がる例)(§2)。

## System model & assumptions
- [paper] B-tree ベースのページ型エンジン(LeanStore + vmcache で 1:N の PID→offset
  マッピング)。ファイルシステム無しでブロックデバイス直書きを想定 (§2, §6)。
- [paper] SSD の内部構造(superblock 追記、ベンダ固有 GC 粒度)をモデル化して推定する。
  ZNS / FDP / 標準 SSD の3種に対応 (§5)。
- [paper] WAL 書き込みは「扱いが容易」として分析から除外 (§1)。
- [inference] 実験は enterprise SSD 8機種。コンシューマ SSD や、SSD 内部圧縮を持つ
  デバイスでの挙動は別議論(§8 で SSD 内部圧縮に言及あり)。

## Approach
- [paper] **out-of-place 化**: 旧ページは新版が durable になるまで有効なので DWB 不要に
  (WAL replay で回復)。代償として DB レベル GC が必要になる (§2, §4.1)。
  ※ 素朴な out-of-place はむしろ Total WAF を 1.66× 悪化させる(DB GC 支配)(§7.2, Fig. 13b)
  — 以降の最適化とセットで初めて効く、が本論文の核心的な注意点。
- [paper] **圧縮+ページパッキング** (§3): ページ単位 LZ4 圧縮(圧縮率 25–49%、ZSTD なら
  14.5–36.5%)+ best-fit ビンパッキングで 4KiB 境界に整列 → 1 PID = 1回の 4KiB 読み。
  4KiB がレイテンシ/IOPS 最良の読み単位であることを4機種の FIO 実測で確認。
- [paper] **GDT(deathtime グルーピング)** (§4): ページヘッダに書き込みタイムスタンプ
  履歴(直近 n=4)を持ち、EDT = current_lsn + (WHn−WH1)/(n−1) で次回無効化時刻を外挿。
  類似 EDT のページを同一ゾーンに配置し、GC も EDT 順で再配置。初回書き込みは
  B-tree index ID でグループ化。
- [paper] **DB と SSD の GC 単位整合** (§5.3): FDP なら Reclaim Unit サイズを直接取得、
  無ければ ZNS 様パターンで「WAF が 1 に到達するゾーンサイズ」を実測推定(4機種で
  4–8GB、安全側は 32GB)。
- [paper] **NoWA パターン** (§5.4): 複数 open ゾーンの多重化が superblock 内で deathtime を
  混ぜるのが SSD WA の源。①現行ゾーン群が書き切られるまで新ゾーンを開かない、
  ②ゾーン間の無効化頻度不均衡を補償書き込みで矯正 → SSD GC 発火前に必ず全無効
  superblock を用意し SSD WAF=1。コモディティ SSD での SSD WAF=1 実証は初と主張 (§2)。
- [paper] **FDP ヒント** (§5.5): ゾーン→PlID(RUH 数で mod)で多重化自体を回避、NoWA 不要。
- [paper] 回復: PID2Offset 更新をログし「ページデータ→マッピング更新」の順序を強制。
  チェックポイントで PID2OffsetTable / ActiveGroupHistory のスナップショット (§6.2)。

## Evaluation
- Setup [paper]: enterprise SSD 8機種(5ベンダ)、YCSB-A (zipf 0.8) と TPC-C 15,000WH、
  バッファプールはデータセットの 5–20%、累積書き込み≥容量4×で定常状態化 (§7.1)。
- [paper] PM9A3 / 800GB: Total WAF 4.72→0.60(7.8×)。スループット 229K→535K OPS。
  内訳: DB WAF 2.00(in-place)→4.06(素朴 oop)→0.62(+圧縮)→0.59(+GDT)→0.60(+NoWA、
  補償書き込み分)、SSD WAF 2.36→1.94→1.07(+NoWA)→1.00(+GC単位整合)(Table 1, Fig. 13)。
- [paper] 機種横断: Total WAF 改善 6.2×(Solidigm)〜9.76×(Kioxia)。SSD WAF は
  Solidigm の 1.12 を除き全機種 ≈1 (Fig. 14, §7.4)。
- [paper] ZNS: 同一データセット 1,500GB で CNS 比 +31%(主因は OP 返還による実効容量増、
  同一 fill factor 比較では ~10%)(Table 2, §7.5)。FDP: NoWA 代替で DB WAF 0.57→0.54、
  スループット 541K→553K (Table 3)。
- [paper] TPC-C (1.6TB, FDP SSD A): 同一時間で 2.45× のトランザクション、同一
  トランザクション数で 7.2× 少ないフラッシュ書き込み (Fig. 16)。
- [paper] 副作用: バッファヒット率ほぼ不変(93.2→93.1%)、CPU 5%→8.3%、メタデータ
  メモリ最悪 10.9GB (§7.3)。
- [inference] カバーされないもの: 読み中心・スキャン中心ワークロード、レイテンシ
  (特にテール)への影響の系統的評価、WAL 書き込みとの統合的な配置(WAL は除外扱い)。

## Limitations
- Stated [paper]: NoWA は SSD の並べ替え・wear-leveling 等で完全でない場合がある (§5.4)。
  メタデータのディスク退避は future work (§7.3)。LSM への拡張・マルチデバイス・HM-SMR も
  future work (§9)。
- Inferred [inference]:
  - GC 単位推定(ZNS 様パターン)はデバイス挙動の安定性に依存。ファームウェア更新や
    マルチテナント(同一 SSD を他系と共有)で崩れる可能性は未検討(§9 が shared-device を
    future work とするのと整合)。
  - EDT 外挿は直近4回の線形外挿であり、周期的・バースト的なアクセスには誤る。GDT の
    誤予測時の感度分析は本文に見当たらない(GC 時の再配置で補正される、との定性説明のみ §4.2)。

## Relations
- [[2026-pvldb-kuschewski-btrlog]] — 同グループ。BtrLog はログノードの SSD 書き込みに
  本論文の out-of-place 書き込みを引用 [51]。WAL を除外した本論文と、WAL 専業の BtrLog は
  ちょうど相補対。
- LeanStore [63] / vmcache [64] 系譜。autonomous commit(Nguyen et al.)とも同系。
- 対比: LSM 系 WA 最適化(index レベル)とは直交で併用可能と主張 (§8)。
- キュー内関連: ArceKV(LSM コンパクション)、FAST の WARP(FDP SSD 特性評価)、
  Zhan らの buffered I/O 再設計 — SSD 書き込み経路クラスタとしてまとめて読む価値。

## Idea seeds
- [inference] 「Total WAF = DB WAF × SSD WAF を DBMS が一元管理する」という枠組みは、
  WAL・チェックポイント・インデックス構造まで含めた全書き込みソースに拡張できるはず。
  本論文は WAL を除外しており (§1)、BtrLog はリモート化を扱う — ローカル NVMe 上で
  WAL/ページ書き込み/GC を deathtime 統合配置する設計は空白に見える。
  検証: ZLeanStore(公開コード)で WAL を同一ゾーン機構に載せ、Total WAF を測る。
- [question] NoWA の補償書き込みはワークロード skew が時間変動するとき(hot set 移動)に
  どの程度増えるか。YCSB の静的 zipf のみで評価されており、動的 skew での挙動は開いている。
- [inference] checkpoint 研究(キューの Hot-Page-Aware Checkpointing 等)と GDT は
  「ページの将来の書き込み時刻予測」という同じ予測問題を解いている。予測器を共有する
  checkpoint×GC 共同設計はアイデア候補。

## Changelog
- 2026-07-06: created (status: read, PVLDB 公式 PDF を読解)
