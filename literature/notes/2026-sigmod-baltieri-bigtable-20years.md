---
title: "Twenty Years of Bigtable"
authors: [Fabio Baltieri, et al.]
venue: "SIGMOD Companion"
year: 2026
ids: {doi: "10.1145/3788853.3803095", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3788853.3803095", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [non-relational, storage-system, industrial-experience, scale]
---

> **ソース注記**: 本ノートは abstract のみに基づく(status: abstract-only)。
> abstract の取得元: https://doi.org/10.1145/3788853.3803095
> (OpenAlex API レコード https://api.openalex.org/works/doi:10.1145/3788853.3803095 経由で取得)。
> 本文 PDF は未取得。著者リストはメタデータ上 "Fabio Baltieri et al." としか
> 確認できておらず、共著者は未確認。

## TL;DR
Google の非リレーショナルデータベース Bigtable の、原論文以降 20 年間の歩みを
語る回顧・経験報告論文。この 20 年で追加された新機能と改善、および Google 内で
最大級のデータベースシステムとなった本システムを大規模に運用してきた経験を共有する、
と abstract は述べる。技術的な中身(何の機能が足され、何がボトルネックだったか)は
abstract からは読み取れない。

## Problem & motivation
- [paper] Bigtable は先駆的で影響力のある non-relational database system であり、
  原論文は広く引用され、HBase や Cassandra など多くのシステムに影響を与えた (abstract)。
- [paper] その後も Bigtable は成長を続け、Google 社内で最大級のデータベースシステムの
  一つになった (abstract)。
- [paper] 本論文は過去 20 年の Google 社内での Bigtable の歩みを語る: 追加された
  新機能と改善、およびユーザの増え続ける要求に応えるためにあらゆる側面を継続的に
  改善しながらこのストレージシステムを大規模運用してきた経験を共有する (abstract)。
- [inference] 位置付けとしては新規手法の提案ではなく、運用経験・システム進化の
  回顧型の industrial paper と読める(abstract に評価・新アルゴリズムへの言及がない)。

## System model & assumptions
(abstract-only のため未記載)

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

## Limitations
(abstract-only のため未記載)

## Relations
- abstract のみからは、既存ノート群との具体的な技術的関係(構造・プロトコル・
  ワークロードのレベル)は確立できない。本文読解後に追記する。
- [inference] ジャンルとしては、大規模商用システムの設計・運用経験を報告する系統
  ([[2026-sigmod-arkhangelskiy-aurora-limitless.md]]、
  [[2026-sigmod-saenz-hyperscale-storage.md]]、
  [[2026-cidr-arora-salesforce-oltp.md]] が扱う industrial 報告)に属する可能性が
  高いが、これは abstract の「running this storage system at scale ... share our
  experience」という記述からの推測であり、具体的な技術的接点は本文を読むまで書かない。

## Idea seeds
- [question] 「20 年間の新機能と改善」が具体的に何か(ストレージエンジン、
  レプリケーション、マルチテナンシー、HW 世代交代への追従など)は abstract からは
  不明。本文を読み、監視キーワード(LSM-tree / WAL / checkpoint / recovery /
  buffer management 等)との接点を確認するのが先決。deep-read 候補として
  優先度を人間に確認したい。
- [inference] HBase / Cassandra に影響を与えた原点システムの 20 年回顧は、
  「長期運用で当初の設計判断のうち何が生き残り何が捨てられたか」という、
  単発の性能論文からは得られない縦断的データを含む可能性がある。Phase 2 の
  課題発見(設計判断の寿命・技術的負債の類型化)の素材になりうる。最初の検証は
  本文入手と精読そのもの。

## Changelog
- 2026-07-06: created (status: abstract-only)
