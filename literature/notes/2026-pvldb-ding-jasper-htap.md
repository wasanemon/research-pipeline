---
title: "Breaking the Isolation-Freshness Trade-off: Joint Adaptive Storage Optimization for HTAP Systems"
authors: [Zhenghao Ding, Xinyi Zhang, Chao Zhang, Yishen Sun, Kai Xu, Wei Lu, Xiaoyong Du]
venue: "PVLDB 19(6):1142-1155"
year: 2026
ids: {doi: "10.14778/3797919.3797924", arxiv: "", dblp: "journals/pvldb/DingZZSXLD26"}
urls: {paper: "https://www.vldb.org/pvldb/vol19/p1142-ding.pdf", pdf: "literature/pdfs/2026-pvldb-ding-isolation-freshness-htap.pdf", code: "https://github.com/DBXAI/Jasper"}
status: read
read_date: 2026-07-06
tags: [htap, storage-layout, partitioning, column-store, freshness, tidb, mcts]
---

注意: 本論文の "isolation" は**ワークロード分離**(OLTP/OLAP の資源干渉)であり、
トランザクションの isolation level ではない。

## TL;DR
HTAP の「行×列の二重ストアは同期コストで freshness を失い、単一ストアは分離を失う」
というトレードオフに対し、ワークロードに応じた細粒度パーティショニング+**選択的**
列ストアレプリカ(update が少なく query が多いパーティションのみ列化)を MCTS 系探索で
共同最適化する機構 Jasper を TiDB 上に実装。完了時間を 20.43–40.59% 短縮。

## Problem & motivation
- [paper] TiDB で同期(TiKV→TiFlash)を有効にすると CH-Benchmark のクエリレイテンシが
  16.5–74.4% 増加(TP が重いほど悪化)。TiDB は読み時に最新データを取得するため、列側に
  未反映の更新が読みを遅らせる (§1, Fig. 1b)。
- [paper] 既存は全テーブル二重化(TiDB, ByteHTAP)か単一モデル(Peloton のタイル)か
  ハイブリッドだが同期コスト非考慮(Proteus)で、粗すぎるか分離を失う (§1, §2.3, Table 1)。
- [paper] JORC 問題: 分割 P と列レプリカ選択 C ⊆ P を共同で選び実行時間を最小化。
  設計空間は O([2(m/p)!]^{np}) で組合せ爆発、分割問題自体 NP-hard (§1, §2.2, Example 4.1)。

## System model & assumptions
- [paper] 対象アーキテクチャは「行ストアが主、列ストアレプリカを追加」型。TiDB v8.1.0
  (TiKV 3ノード + TiFlash 1ノード)上に実装。CC には手を入れず TiDB の MVCC + Raft に
  依存し、再構成はオンライン・非ブロッキングで背景同期→一貫性到達後に原子的スイッチ (§2.1, §3, §6.1)。
- [paper] isolation/freshness の直接定量化は難しいとして、実行時間 T(W) を統一プロキシ
  指標に採用 (§2.2)。
- [paper] 「劇的なワークロード変化やスキーマ変更はスコープ外」(§4.4)。
- [inference] 評価ハードは Seagate Exos X18(HDD)+ 1Gbps ネットワークと控えめ (§6.1)。
  同期・変換コストの相対的重みは NVMe/高速NW では変わり得るので、改善幅の絶対値は
  環境依存と見るべき。

## Approach
- [paper] 探索: MCTS-HTAP。状態=部分的ストレージ構成、行動=垂直分割/水平分割
  (パーティションキー選択)/列ストア付与。列の優先度 p(c)=Σ(読み頻度−書き頻度) を
  正規化し、行動優先度=関与列の優先度比 (Eq. 4-5)。ノードの utility=残り行動の平均優先度
  (Eq. 3)。選択は utility 閾値 θ(漸減)+ UCB1、展開は優先度比例の確率的選択 (§4.2-4.3, Alg. 1)。
- [paper] 評価モデル: optimizer 非依存の「実行コストツリー」= 演算子コスト
  (式ベース、例 Cost_scan = rows·log(rowsize)·scanfactor)+ **同期コスト**
  (TP 更新列と AP アクセス列の交差データ量×並行度、Eq. 9)+ **変換コスト**(列→行変換、
  Eq. 10)。論理プランをキャッシュし、パーティション枝刈りでカーディナリティを再導出。
  パラメタは演算子レベル実測レイテンシに最小二乗フィット(軽量・オフライン)(§5)。
  ※ 既存チューニング研究では総時間の75%超が optimizer の what-if 呼び出し (§2.3.2)。
- [paper] 増分再構成: ワークロードウィンドウ間の偏差が閾値超過→変化の大きい列に限定した
  候補行動集合で高速再探索。利得=実行時間削減−データ移動コスト(I/O は
  T_IO = α·V/Bandwidth+β を回帰で学習)が正のときだけ適用 (§4.4, Eq. 6-7)。

## Evaluation
- Setup [paper]: CH-Benchmark 50GB(200WH)/ Twitter 20GB / HyBench / OSS(実運用、2TB・
  6テーブル・80億行超)。TP:AP = 10:1 / 1:1 / 1:10。ベースライン: Proteus、Peloton、
  Two-Stage(Redshift 分割+Oracle 列選択)、Greedy、TiDB デフォルト(全表二重化)(§6.1)。
- [paper] 完了時間: CH で平均 20.72–40.59% 短縮、Twitter で 20.43–33.28% 短縮。
  OLTP-Heavy で利得最大 (Fig. 6, §6.2)。
- [paper] OLAP レイテンシ(CH, balanced): TiDB 比 −39.7%、Proteus 比 −28.39%、
  Peloton 比 −19.9%、TSO 比 −37.11%。OLTP スループットは全手法ほぼ同等(垂直分割の
  insert/update オーバーヘッドで僅かに低下)(Fig. 7, §6.2)。
- [paper] OSS 実運用ワークロード: DBA 最適構成比で実行時間 16.67–21.16% 短縮 (Fig. 9)。
- [paper] 動的ワークロード(5分ごとに変動): 大きなパターンシフト時のみ再構成し(6/11/26/31
  分時点)、全フェーズで最低レイテンシ・最高スループット維持 (Fig. 10, §6.3)。
- [paper] 最適化オーバーヘッド: 初回探索 348s / 増分 6.7s(optimizer 依存版は 1432s / 40s)
  (Table 2)。
- [inference] カバーされないもの: freshness の直接測定(遅延秒数等)が H-Score 以外に無く、
  ほぼ完了時間ベース。TiFlash 1ノード構成なので列側資源が絞られており、TiDB デフォルト
  (全表列レプリカ)に不利な設定に見える。分離の直接指標(干渉時のテールレイテンシ等)も
  未報告。

## Limitations
- Stated [paper]: 劇的なワークロード/スキーマ変化は対象外 (§4.4)。詳細(他アーキテクチャ
  への一般性等)はテクニカルレポート送り (§6 冒頭)。
- Inferred [inference]:
  - 同期コストモデル (Eq. 9) は「交差データ量×並行度」の線形プロキシで、TiDB の Raft
    learner 同期という特定実装に較正されている。同期機構が異なる系(delta merge 系)への
    移植性は較正頼み。
  - MCTS の探索は優先度=読み書き頻度差というヒューリスティックに強く依存。頻度は同じでも
    レイテンシクリティカルさが違う列(例: 低頻度だが SLA が厳しい AP)には無力の可能性。

## Relations
- 比較対象: Proteus (adaptive HTAP)、Peloton (tile-based)。アーキテクチャ分類は §2.1
  (TiDB/ByteHTAP 型 vs Oracle/SQL Server/Heatwave/PolarDB-IMCI 型 vs HANA/Umbra 型)が
  簡潔なサーベイになっており、HTAP 系ノートの基準点として使える。
- キュー内関連: AQD(同じ PVLDB 19、HTAP ディスパッチ)、TiRex(HTAIP)。AQD はルーティング側、
  Jasper はレイアウト側で相補的 — 両ノート完成後に対比する。

## Idea seeds
- [inference] 本論文の freshness は「同期待ちの読みレイテンシ」に還元されているが、
  トランザクション的な意味での一貫した鮮度(スナップショットの stale 度合いの保証)とは
  別物。**レイアウト適応と isolation level/staleness bound(例: bounded staleness 読み)を
  共同設計する**余地がある — 検証: TiDB の stale read 機能と Jasper 的な選択的列化を
  組み合わせ、freshness SLA 下での完了時間を測る。
- [question] 選択的列レプリカの下で、AP クエリが行ストアに回されるパーティションの
  トランザクション競合(ロック/MVCC ガベージ)がどれだけ増えるか。分離の劣化を
  スループット以外(abort 率、GC 圧)で測ると別の絵が見えるかもしれない。

## Changelog
- 2026-07-06: created (status: read, PVLDB 公式 PDF を読解)
- 2026-07-06: 検証パスによる修正(アンカー精緻化 2 件: NP-hard の出典に §1 を追加、実装・構成 bullet のアンカーを §3 単独から §2.1/§3/§6.1 に修正。数値・主張は全数照合で相違なし)
