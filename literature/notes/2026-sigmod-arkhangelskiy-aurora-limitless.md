---
title: "Aurora PostgreSQL Limitless Database: Building a Highly Scalable OLTP Database"
authors: [Dmitry Arkhangelskiy, Saikiran Avula, Sachit Batra, Jin Chen, Radwan Deeb, Alexey Gotsman, Upendra Gowda, Haritabh Gupta, Benoit Hudzia, Rishabh Jain, Kaumudi Kaushik, Aravind Kumar Kumar, Sergey Melnik, Saleem Mohideen, Sharique Muhammed, Davor Prugovecki, Sanjay Shanthakumar, Sagar Shedge, Anand Kumar Thakur, David Wein]
venue: "SIGMOD Companion"
year: 2026
ids: {doi: "10.1145/3788853.3803089", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3788853.3803089", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [distributed-transactions, mvcc, two-phase-commit, oltp, cloud-native, sharding]
---

<!-- ソース: https://api.openalex.org/works/doi:10.1145/3788853.3803089?mailto=miyayu@keio.jp
     (2026-07-06 取得)。abstract は OpenAlex の abstract_inverted_index からの再構成。
     dl.acm.org の PDF は自動取得に HTTP 403 のため本文未読。 -->

## TL;DR
Amazon Aurora PostgreSQL を水平スケール可能にした cloud-native 分散 OLTP データベース
「Aurora Limitless Database」のシステム報告。router 層(クエリ分配)+ PostgreSQL シャード
群の storage 層でアプリ側シャーディングを不要にし、time-based MVCC と two-phase commit を
統合した分散トランザクションプロトコルで strong consistency を維持すると主張する (abstract)。

## Problem & motivation
- [paper] Amazon Aurora PostgreSQL に horizontal scaling 能力を加えつつ strong consistency
  保証を維持することが目標 (abstract)。
- [paper] router 層によるクエリ分配と PostgreSQL シャードの storage 層により
  「transparent scalability」を提供し、application-level sharding の必要性を排除する
  (abstract)。
- [paper] 主張される技術的貢献は3点: ① time-based multi-version concurrency control と
  two-phase commit を統合した分散トランザクションプロトコル、② vertical と horizontal の
  スケーリングを組み合わせる adaptive scaling framework、③ DML と DDL の両方にわたって
  strong consistency を維持する分散クエリ処理エンジン (abstract)。

## System model & assumptions
(abstract-only のため未記載)

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

## Limitations
(abstract-only のため未記載)

## Relations
- abstract-only の現段階では、既存ノート群との直接の技術的関係(build on / compete /
  contradict)は確認できない。本文精読後に再評価する。

## Idea seeds
- [question] 「time-based MVCC と 2PC の統合」(abstract) が、クロック同期の前提
  (誤差境界、コミットタイムスタンプの割り当て方式)に何を要求するかは abstract からは
  不明。本文精読で確認すべき第一の論点。
- [question] 「DML と DDL の両方で strong consistency を維持」(abstract) という主張は、
  分散環境での online schema change とトランザクションの相互作用をどう扱うかを含意する
  はずだが、機構は abstract に無い。DDL の一貫性保証は研究ノート横断で比較軸になり得る。
- [inference] 「vertical と horizontal を組み合わせる adaptive scaling framework」(abstract)
  は、スケーリング動作(シャードの分割・移動)中のトランザクション処理への影響という
  評価観点を示唆する。本文の評価がこの遷移中の性能を測っているかは要確認 — 測っていなければ
  再現実験の切り口になる。

## Changelog
- 2026-07-06: created (status: abstract-only)
