---
title: "Scalable RDMA-accelerated Distributed Locks with Shared Stream Abstraction"
authors: [Miao Cai, Junru Shen, Xiaojian Liao, Rong Gu, Yanchao Zhao, Hao Han, Bing Chen, Baoliu Ye]
venue: "EuroSys"
year: 2026
ids: {doi: "10.1145/3767295.3803598", arxiv: "", dblp: "conf/eurosys/CaiSLGZHCY26"}
urls: {paper: "https://doi.org/10.1145/3767295.3803598", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [distributed-locks, rdma, locking, networking]
---

ソース: https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3767295.3803598?fields=title,abstract,authors,year,venue,externalIds
(2026-07-06 取得。dl.acm.org の PDF は自動取得に対し HTTP 403 のため abstract のみ)

## TL;DR
[paper] RDMA でデータパスをオフロードする分散システムにおいて、スケールしない
分散ロックが主要な障壁だと指摘し、共有ストリーム(shared stream)抽象を核とする
ロックプリミティブ **StreamLock** を提案 (abstract)。[paper] 機構は2つ:
(i) 現代 NIC のラインスピードなパケット受信を転用したスケーラブルなリクエスト順序付け、
(ii) peer-to-peer 通知による 1 RTT でのロック所有権移転 (abstract)。
[paper] 市販(off-the-shelf)の RDMA NIC 上で実装し、最先端の分散ロック群と比較して
「大幅に上回る」と主張(具体的な数値は abstract に無し)(abstract)。

## Problem & motivation
- [paper] 高速な RDMA により、分散システムは性能クリティカルなデータパスを
  ネットワークファブリックへオフロードする方向にあるが、RDMA 最適化データパスの
  設計には「スケールしない分散ロック」という主要なハードルがある (abstract)。
- [paper] 既存ロック方式の性能分析(performance dissection)の結果、
  **ソフトウェアベースのロックリクエスト順序付け**と
  **ポーリングベースのロック所有権移転**がスケールせず、
  高い NIC 競合(NIC contention)と激しいネットワーク輻輳を招くと特定 (abstract)。
- [paper] 解決の方向性は、分散ロックプロトコルと高速 RDMA ネットワークの
  co-design であり、その核が novel な shared stream 抽象 (abstract)。

## System model & assumptions
(abstract-only のため未記載)

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

## Limitations
(abstract-only のため未記載)

## Relations
- 既存ノート(DiStash / BtrLog / FlintKV / Jasper / How-to-Write-to-SSDs / ArceKV /
  Terark-DS / SIDLE / Pisco / AQD)に RDMA ベースの分散ロックを直接扱うものは無く、
  現時点で確実に結び付けられる関係は無し。
- [question] disaggregated memory / 分散トランザクション系のノートが今後増えたときに、
  ロックプリミティブ層の関連としてここへ追記する(全文読解後に判断)。

## Idea seeds
- [question] 「NIC のラインスピードなパケット受信を順序付けに転用する」(abstract) とは
  具体的に NIC のどの機能・どの保証(受信キューの到着順?)に依存するのか。全文読解で
  確認すべき第一点。依存する保証が NIC ベンダ固有なら可搬性が論点になる。
- [inference] 1 RTT のロック所有権移転 (abstract) が本当に一般のロック競合下で成立する
  なら、分散トランザクション処理(2PL 系 CC のリモートロック取得)や disaggregated
  memory 上の索引の同期プリミティブとしてインパクトがあり得る。検証の第一歩:
  全文を読み、公平性(starvation)・ロック保持者障害時の回復がどう扱われるかを確認した
  上で、トランザクショナルなワークロード(TPC-C 的な hot-row 競合)での適用可能性を評価。
- [question] abstract は「大幅に上回る」としか述べず倍率・条件が不明。比較対象の
  「state-of-the-art distributed locks」が何かも abstract からは特定できないため、
  優位性の範囲(競合度・ノード数・ロック粒度)は全文で要確認。

## Changelog
- 2026-07-06: created (status: abstract-only)
