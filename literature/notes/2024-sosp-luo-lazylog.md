---
title: "LazyLog: A New Shared Log Abstraction for Low-Latency Applications"
authors: [Xuhao Luo, "et al.(完全な著者リストは未取得。メタデータ表記は 'Xuhao Luo et al.')"]
venue: "SOSP"
year: 2024
ids: {doi: "10.1145/3694715.3695983", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3694715.3695983", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [shared-log, linearizability, total-order, low-latency, sharding, log-abstraction]
---

> **ソース注記**: 本ノートは abstract のみに基づく(status: abstract-only)。
> abstract は OpenAlex API 経由で取得
> (https://api.openalex.org/works/doi:10.1145/3694715.3695983)。
> 論文本体の URL: https://doi.org/10.1145/3694715.3695983(PDF 未取得)。
> abstract を超える技術的詳細(アルゴリズムの動作、実験数値)は本ノートに書かない。

## TL;DR
Shared log はストレージシャードを跨ぐ linearizable な全順序を提供するが、従来は
ingestion 時に順序を eager に確定するため書き込みレイテンシが高い。LazyLog は
「順序は消費(read)時までに確定していればよく、reader は writer と時間的に
分離されている」という観察に基づき、レコードの global position への束縛を lazy に
行い read 前に順序を強制する新しい shared log 抽象である。著者らは 2 つの LazyLog
システムを構築し、eager-ordering な従来型 shared log より大幅に低いレイテンシを
示したと主張する(いずれも abstract に基づく)。

## Problem & motivation
- [paper] Shared log はストレージシャードを跨ぐ linearizable な全順序を提供するが、
  この順序を ingestion 時に eager に強制するため、高いレイテンシにつながる (abstract)。
- [paper] 観察: 現代の多くの shared-log アプリケーションでは、linearizable ordering は
  必要だが、データ取り込み時に eager に必要なのではなく、データが消費される時点で
  初めて必要になる (abstract)。
- [paper] さらに、これらのアプリケーションでは reader は writer から自然に時間的に
  分離(decoupled in time)されている (abstract)。
- [paper] 提案: LazyLog はレコードを(シャードを跨いで)linearizable な global
  position へ lazy に束縛し、そのログ位置が読まれる前に順序を強制する。この lazy
  ordering により低い ingestion レイテンシが可能になる (abstract)。
- [paper] 時間的分離があるため、LazyLog は read が到着するより十分前に順序を確定でき、
  read 時のオーバーヘッドを最小化できる (abstract)。
- [paper] シャードを跨ぐ linearizable な全順序を提供する 2 つの LazyLog システムを
  構築した。実験では、従来の eager-ordering な shared log より大幅に低いレイテンシを
  示した (abstract)。

## System model & assumptions
(abstract-only のため未記載)

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

## Limitations
(abstract-only のため未記載)

## Relations
- [inference] [[2026-pvldb-kuschewski-btrlog.md]](BtrLog: クラウド DB 向け低レイテンシ
  ログサービス): どちらも「ログへの append レイテンシの最小化」を狙うログ基盤である
  点で接続する。ただし BtrLog は single-writer WAL を前提にシーケンサ自体を不要化する
  アプローチ(BtrLog ノート参照)なのに対し、LazyLog は abstract を読む限り
  multi-shard な shared log の全順序確定を read 側に遅延させるアプローチであり、
  「順序付けコストをいつ・どこで払うか」という軸で対照的。詳細比較は本文読解後。
- [inference] [[2026-sigmod-webber-riot.md]](RIOT: leaderless 一般化コンセンサス):
  RIOT は「全順序ログをそもそも作らない(可換なら順序不要)」方向、LazyLog は
  「全順序は作るが束縛を遅延する」方向で、eager な全順序確定のコストを回避するという
  問題意識を共有しているように見える。この対応付けは abstract のみからの推論であり、
  本文読解で検証が必要。

## Idea seeds
- [question] 「linearizable ordering は消費時にのみ必要」という観察がどのクラスの
  アプリケーションで成立するのか、abstract からは具体例が分からない。DB 文脈
  (WAL 複製、log-structured なストレージエンジン、CDC/ストリーム消費)のどこまで
  この仮定が刺さるかは、本文 §導入/motivation の読解で確認すべき点。検証の第一歩は
  PDF を取得して対象アプリケーションの列挙と要件分析を読むこと。
- [question] read が「順序確定より先に」到着した場合(reader と writer の時間的分離が
  成立しないワークロード)のレイテンシ挙動は abstract からは不明。read 時に順序強制の
  コストを払うことになるのか、その最悪ケースの評価があるかは本文で確認する。

## Changelog
- 2026-07-06: created (status: abstract-only)
