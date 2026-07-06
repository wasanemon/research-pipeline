---
title: "Accelerating Transactional Execution via Processing-In-Memory"
authors: [André Lopes, Daniel Castro, Paolo Romano]
venue: "EuroSys"
year: 2026
ids: {doi: "10.1145/3767295.3803621", arxiv: "", dblp: "conf/eurosys/LopesCR26"}
urls: {paper: "https://doi.org/10.1145/3767295.3803621", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [pim, oltp, transaction-processing, deterministic, hardware]
---

Source: https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3767295.3803621?fields=title,abstract,authors,year,venue,externalIds (fetched 2026-07-06)
※ dl.acm.org の PDF は自動取得で HTTP 403。abstract のみに基づくノート。

## TL;DR
Processing-in-Memory (PIM) アーキテクチャ上で OLTP トランザクションを実行する
プラットフォーム **PIM-TIDE** (Processing-in-Memory with Transactional Isolation via
Deterministic Execution) の提案 (abstract)。[paper] 複数 DPU (Data Processing Unit) に
跨るトランザクションを、CPU を「選択的に」コーディネーションに使う軽量な
ソフトウェアベース協調機構で実行し、consistency / atomicity / isolation を保証しつつ
頻繁な DPU 間通信のペナルティを回避する (abstract)。[paper] 実 PIM ハードウェア
(UPMEM) 上の TPC-C ベースワークロードで、性能・エネルギー効率の両面で
低オーバーヘッドかつスケーラブルなトランザクション処理を達成と主張 (abstract)。

## Problem & motivation
- [paper] PIM はメモリモジュール内に計算能力(メモリバンク近傍に埋め込まれた小型
  プロセッサ = DPU)を統合し、コストの高いデータ移動を削減する。分析系タスクでは
  強い効果が示されている (abstract)。
- [paper] 一方 OLTP のようなトランザクショナルワークロードの支援は、DPU が
  非集中的 (decentralized) であることと、効率的なハードウェア協調機構が欠如している
  ことにより、依然として困難 (abstract)。
- [paper] PIM-TIDE はこのギャップを、ハードウェア協調に頼らない軽量な
  ソフトウェアベースの協調機構(CPU をトランザクション協調に選択的に使用)で
  埋めると主張 (abstract)。
- [inference] システム名に "Deterministic Execution" を含むこと (abstract) から、
  協調機構の中核は何らかの決定的実行スキームだと推測されるが、その具体的な
  仕組み(順序付けの方法、abort の扱い等)は abstract からは一切読み取れない。

## System model & assumptions
(abstract-only のため未記載)

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

- [paper] abstract レベルで分かるのは「実 PIM ハードウェア (UPMEM) 上で、TPC-C
  ベースのワークロードを用いて性能とエネルギー効率を評価した」ことのみ (abstract)。
  具体的な数値・ベースライン・スケール条件は不明。

## Limitations
(abstract-only のため未記載)

## Relations
- 直接に関連する既存ノートはなし。
- [inference] 弱い主題的隣接: [[2026-pvldb-zhao-sidle]](CXL メモリ上の索引配置)と同じく
  「新しいメモリハードウェア × DBMS ワークロード」の系譜だが、SIDLE はメモリ拡張
  (容量・階層)、本論文は memory 内計算(データ移動削減)と軸が異なる。深読み前に
  これ以上の関係付けはしない。

## Idea seeds
- [question] "Deterministic Execution" が具体的にどの種の決定的実行
  (事前順序付け型か、それ以外か)なのか、既存の deterministic database 系
  プロトコルとどう違うのかは abstract から不明。深読み時の最優先確認事項。
  検証: PDF §Approach 相当を読み、トランザクションの順序決定タイミングと
  abort/retry の有無を既存決定的プロトコルの分類軸で整理する。
- [question] 「CPU を選択的に協調へ使う」設計 (abstract) では、CPU 側協調が
  DPU 数の増加に対してボトルネック(集中シリアライズ点)にならないかが焦点。
  検証: 評価節で DPU 数スケーリング時の CPU 協調コストの内訳が測られているか確認し、
  無ければ再現実験の候補にする。
- [question] エネルギー効率の主張 (abstract) の測定方法とベースライン
  (CPU-only 実行か、他の PIM 上実行方式か)は abstract に記載がない。
  比較対象次第で主張の強さが大きく変わるため、深読み時に評価設定を精査する。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: 検証パスによる修正(「CPU を協調にのみ使用」の「のみ」を削除 — abstract は "using the CPU selectively for transaction coordination" であり排他性は主張していない)
