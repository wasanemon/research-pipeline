---
title: "Update NDP: On Offloading Modifications to Smart Storage with Transactional Guarantees in Near-Data Processing DBMS"
authors: [Arthur Bernhardt, Sajjad Tamimi, Florian Stock, Andreas Koch, Ilia Petrov]
venue: "ACM Trans. Database Syst."
year: 2026
ids: {doi: "10.1145/3774753", arxiv: "", dblp: "journals/tods/BernhardtTSKP26"}
urls: {paper: "https://doi.org/10.1145/3774753", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [ndp, computational-storage, transactions, locking, logging, recovery]
---

## TL;DR
NDP(near-data processing)は現状ほぼ read-only 用途に限られており、更新系操作の
オフロードはトランザクショナルな一貫性と host–smart storage 間の低レイテンシ同期
機構の欠如により実現できていない、という問題に対し、「update NDP」— 更新操作を
computational storage にトランザクション保証付きでオフロードする方式 — を
neoDBMS という NDP DBMS 上で提案する (abstract)。cache-coherent interconnect に
基づく host / computational storage 間の共有ロックテーブルと、それを host 側
lock manager に統合する locking protocol、および log 移動中も host と storage の
双方が有効な仕事を継続できる拡張 locking / logging 機構(障害回復用)が構成要素で、
mixed workload において in-storage 更新は host-only 実行より ≥ 6.52× 高速と
報告されている (abstract)。

## Problem & motivation
- [paper] 大規模データを処理する data-intensive システムの性能とスケーラビリティは、
  不要なデータ移動により制限されている (abstract)。
- [paper] NDP はデータ転送を削減し性能を向上させることが示されているにもかかわらず、
  現在は主に read-only の設定でしか利用されていない (abstract)。
- [paper] 更新(modification)操作の near-data 実行が現状実現不可能な理由は、
  (1) トランザクショナルな一貫性の欠如、(2) host 側 database engine と smart storage 上の
  NDP-engine の間の実用的な低レイテンシ同期機構の不在、の2点 (abstract)。
- [paper] 提案は3点: ① cache-coherent interconnect に基づく host–computational storage 間の
  低レイテンシ共有ロックテーブル、② それを host NDP-engine の lock manager に統合する
  locking protocol、③ log 移動(log-movement)中に host と computational storage が
  有効な仕事を行える拡張 locking / logging 機構による障害回復対応 (abstract)。

## System model & assumptions
(abstract-only のため未記載)

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

- [paper] abstract に記載の唯一の数値: mixed workload 設定で neoDBMS の in-storage
  更新は host-only 実行比 ≥ 6.52× 高速で、データ移動の減少とリソース利用率の向上
  により robust な性能を示す (abstract)。設定・ベンチマーク・比較対象の詳細は本文
  未読のため不明。

## Limitations
(abstract-only のため未記載)

- [question] 比較対象は「host-only 実行」とだけ述べられている (abstract)。他の
  NDP / in-storage 処理方式との比較があるかは本文を読むまで不明。
- [question] "novel cache-coherent interconnects" が具体的にどのインターコネクト
  (CXL 等)を指すのか、実機かエミュレーションかは abstract からは判別できない。

## Relations
- [inference] [[2026-pvldb-zhao-sidle.md]] (SIDLE, CXL 索引配置): abstract が依拠する
  「cache-coherent interconnect 越しの host–デバイス間共有データ構造(本論文では
  ロックテーブル)」という設計軸で関連。SIDLE は索引の配置、本論文は同期機構という
  違いだが、coherent interconnect を DBMS 内部構造の共有に使う点で同じ潮流に見える。
- [inference] [[2026-pvldb-lee-how-to-write-to-ssds.md]]: SSD/ストレージデバイス側の
  書き込み経路を DBMS が意識して設計するという広い意味では隣接するが、本論文は
  デバイス内での更新「実行」のオフロードであり、階層はかなり異なる。弱い関連。

## Idea seeds
- [question] 共有ロックテーブルがデバイス側に(あるいは host 側に)置かれるとき、
  片側の障害(smart storage の障害・切断)時にロック状態と in-storage 更新の
  アトミシティがどう回復されるのか。abstract は「extended locking and logging」で
  障害回復に対応すると述べるのみ (abstract)。本文入手後、recovery プロトコルの
  failure model(デバイス障害を含むか、host 障害のみか)を最初に確認する価値がある。
- [inference] 「log-movement 中も双方が有効な仕事を継続できる」(abstract) という
  設計目標は、WAL 転送がボトルネック化する disaggregated / smart storage 構成一般に
  効く可能性がある。検証の第一歩は、本文の logging 機構が neoDBMS 固有か、既存の
  ARIES 系エンジンに移植可能な抽象かを読み分けること。
- [question] read-only NDP と update NDP が混在する mixed workload で ≥ 6.52× と
  される (abstract) が、更新のみ・高競合ワークロードでロックテーブル共有が
  ボトルネックにならないか。本文の評価軸(競合度のスイープの有無)を確認したい。

## Changelog
- 2026-07-06: created (status: abstract-only)
