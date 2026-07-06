---
title: "SIDLE: Tree-structure Aware Indexes for CXL-based Heterogeneous Memory"
authors: [Haoru Zhao, Mingkai Dong, Fangnuo Wu, Haibo Chen]
venue: "PVLDB 19(7):1499-1515"
year: 2026
ids: {doi: "10.14778/3801059.3801065", arxiv: "", dblp: "journals/pvldb/ZhaoDWC26"}
urls: {paper: "https://www.vldb.org/pvldb/vol19/p1499-zhao.pdf", pdf: "literature/pdfs/2026-pvldb-zhao-sidle.pdf", code: "https://github.com/sidle-project/sidle"}
status: read
read_date: 2026-07-06
tags: [cxl, heterogeneous-memory, index, b-tree, radix-tree, data-placement, memory-tiering]
---

## TL;DR
CXL ヘテロメモリ(fast=CPU 直結 DRAM、slow=CXL メモリ、遅延 ~2×・帯域 ~60%)では、
NUMA/RDMA/PM 向けの既存インデックス配置最適化も、ページ粒度のティアリング(MEMTIS 等)も
効かない。木構造の3特性(ノード粒度・階層的ホットネス・パス型アクセス)を CXL の
キャッシュコヒーレントなメモリセマンティクスに合わせた**ノード粒度配置スキーム** SIDLE を
提案。leaf 中心の追跡+構造を考慮した移動+watermark 自動調整で、MEMTIS 比スループット
最大 +71%(YCSB)、P99 最大 −81%(実ワークロード)。既存の B+tree / radix tree への統合は
コード変更 3% 未満。

## Problem & motivation
- [paper] CXL slow memory は fast 比で遅延 ~2×、帯域 ~60%(CXL 1.1 実機、Intel MLC 計測)
  (Fig. 1c)。木の 75% を CXL 側に置くと性能 ~70% 低下 (Fig. 2)。
- [paper] 既存 HM 最適化が CXL で効かない理由 (§2.3):
  - NUMA 系(複製・分割・委譲)は CXL メモリにローカルプロセッサが無いので不可。
  - RDMA 系(SMART のローカルキャッシュ)は、CXL では fast/slow の差が小さく
    キャッシュ維持・照会コストが利得を上回る(スループットが素の ART の 50〜74%、
    オーバーヘッドの ~50% がキャッシュ起因)(Fig. 3-4)。
  - PM 系(PACTree の fat unordered leaf + async SMO)は、CXL DRAM に PM の
    読み書き非対称や高い永続化コストが無いため逆効果(leaf 書き込み時間の 99% が
    空きスロット探索、テール遅延 1.3〜1.9×)(Fig. 4b)。
  - 「internal を fast に固定」する静的配置は fast 容量と負荷変動に適応できない (PAC-L)。
- [paper] ページ粒度ティアリングは粒度ミスマッチ: 上位 1% のホットページでも大半の
  ノードはコールドで、ページ内最ホットノードがアクセスの 82〜85% を占める (Fig. 5)。

## System model & assumptions
- [paper] 対象は「値を leaf に持つ」木構造インデックス(B+tree、radix tree/ART、Masstree)
  (§1 footnote)。CXL 1.1 メモリ拡張カード、単一ソケット、32GiB DRAM + 32GiB CXL-DRAM、
  Xeon Platinum 8468V (§6.1)。
- [paper] 設計原理: **Layer Principle**(上位ノードを可能な限り fast に。上半分のレベルの
  ノードは全体の 1% 未満なのにアクセス頻度は3桁上)+ **Path Principle**(ホットパスを
  fast に)。配置の不変条件として **single-boundary structure**(fast ノードの祖先は必ず
  fast)を導入 (§3.1, Fig. 7)。

## Approach
- [paper] **軽量割当・追跡** (§4.1): クリティカルパス上は2つだけ — ①layer-aware allocation
  (現在の割当上限レベル L_fast と親の位置で新ノードの初期配置を決定、single-boundary を
  維持)、②leaf 中心のアクセス追跡(パス上の全ノードではなく leaf のみ更新。per-node
  追跡は 50% 超の性能低下という先行報告 (§3.2))。
- [paper] **構造対応の移動** (§4.2): promotion は leaf から祖先を再帰的に fast へ
  (ホットパス一括昇格)。demotion は「子が全て slow になってから親を遅延判定」する
  アルゴリズムで single-boundary とホットパス局所性を保つ(L_demote 以下は対象外)
  (Alg. 1, Fig. 10)。
- [paper] ホット/コールド判定は対数スケールの頻度ヒストグラム+cooler(周期的に全 leaf の
  頻度を半減 = ビン左シフト)。閾値 T_hot / T_cold は目標比率 P_hot / P_cold から
  ヒストグラム走査で周期更新 (§4.2.3)。
- [paper] **Hyper watermark** (§4.3): ユーザは fast メモリ使用率の高低 watermark
  (U_high/U_low)だけ指定し、L_fast・L_demote・P_cold・P_hot は実使用率に基づき
  非対称に自動調整。静的閾値や手動調整を排除。
- [paper] B+tree と radix tree に統合(木の内部コード変更 <3%)(§1)。

## Evaluation
- Setup [paper]: 上記実機。比較対象: weighted allocation(ベースライン)、Caption、TPP、
  MEMTIS、Random、静的 internal-in-fast(Mass-L / PAC-L)、PACTree 最適化版 (§6.1-6.2)。
- [paper] マイクロベンチ(S-Masstree): ベースライン比 +50.4〜82.2%、Update Heavy の
  読み P90 −72.5%、平均読み書き遅延 <1µs (Fig. 14)。
- [paper] マクロベンチ: S-ART +31.7〜83.6%、S-Masstree +30.8〜56.6%(Short Ranges のみ
  +12.3% — fast 内 leaf 数に依存するため)(Fig. 15)。
- [paper] ヘッドライン: 対 MEMTIS 合成 +133%/P99 −67%、YCSB +71%(対 MEMTIS)/+60%
  (対 optimized PACTree)、実ワークロードで +66%/P99 −81% (§1)。
- [paper] 動的ワークロード(ホット領域を 60 秒ごとに移動): 2 秒で 84% 回復、最大 6 秒で
  完全回復 (Fig. 16a)。ワーカー起床間隔への感度 <5%。fast 割合 10→80% でスケールし、
  80% でほぼ全量 fast 相当 (Fig. 16b-c)。
- [inference] カバーされないもの: マルチソケット+CXL の複合階層(単一ソケット固定)、
  CXL 2.0/3.0 スイッチ経由のより大きい遅延ギャップでの検証(言及はあるが実験なし)、
  DBMS 全体(バッファプールやバージョン管理と共存する場合)への統合。

## Limitations
- Stated [paper]: 値を leaf に持つ木が対象 (§1)。Short Ranges ではベースラインに劣後する
  場合あり(fast 使用率 60% 超で CPU キャッシュ競合)(§6.3)。
- Inferred [inference]:
  - single-boundary 不変条件は「上が熱い」木には適合するが、二次インデックスからの
    leaf 直接参照や fingerprint 表など「途中から入る」アクセスには最適でない可能性。
  - ヒストグラム+cooler のホットネス時定数はワークロードの変化速度に依存し、
    秒オーダーより速いシフト(バースト)への追従性は評価外。

## Relations
- 比較系譜: MEMTIS/TPP/Caption(OS ページティアリング)、SMART(RDMA ART)、
  PACTree(PM ART)。「HM の種類が変わると最適化の前提が崩れる」ことを示す
  ケーススタディとしても価値が高い(§2.3 は良いサーベイ)。
- キュー内関連: EDBT の CXL メモリプール動的割当(Lee+、エンタープライズ in-memory
  DBMS)、CIDR の Hash Joins Meet CXL、FAST の DMTree(disaggregated memory 上の木)。
  CXL クラスタとしてまとめ読み推奨。DMTree は compute-side 協調設計でアプローチが
  対照的なはず — ノート化時に比較する。

## Idea seeds
- [inference] 「配置の不変条件(single-boundary)を決めてから、その下で割当・移動・
  閾値調整を自動化する」という設計は、バッファプール(ページ置換)と索引配置の統合にも
  一般化できそう。DBMS では索引と heap/バージョンチェーンが同じ fast メモリを奪い合う —
  SIDLE 的なノード粒度配置と buffer pool の協調は空白に見える。
  検証: vmcache 系バッファプールと S-B+tree を同一 fast メモリ予算で共存させ、
  watermark を共有した場合の挙動を測る。
- [question] MVCC のバージョンチェーンは「新しいほど熱い」という時間的ホットネスを持つ。
  木の「上ほど熱い」に相当する構造的事前知識としてバージョン方向の配置原理
  (version principle?)が立てられるか — CXL 上の MVCC ストレージ設計の切り口になり得る。

## Changelog
- 2026-07-06: created (status: read, PVLDB 公式 PDF を読解)
