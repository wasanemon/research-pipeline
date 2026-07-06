---
title: "A Logically Disaggregated Cache for Replicated Storage Systems"
authors: [Kiranaraddi M. Hombal, Henry Zhu, S. G. Bhat, Neil Kaushikkar, Ramnatthan Alagappan, Aishwarya Ganesan]
venue: "EuroSys"
year: 2026
ids: {doi: "10.1145/3767295.3803608", arxiv: "", dblp: "conf/eurosys/HombalZBKAG26"}
urls: {paper: "https://doi.org/10.1145/3767295.3803608", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [caching, replication, disaggregation, key-value-store, storage]
---

ソース: Semantic Scholar API (https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3767295.3803608?fields=title,abstract,authors,year,venue,externalIds, 2026-07-06 取得)。
PDF は dl.acm.org が自動取得に HTTP 403 を返したため未読。本ノートは abstract のみに基づく。

## TL;DR
[paper] レプリケートされたストレージシステムでは、各レプリカに埋め込まれたキャッシュが
サイロ的に管理されるため、レプリカ間でキャッシュ内容が大きく重複し性能が落ちる、という
観察から出発する (abstract)。提案の Ldc (logically disaggregated cache) は、各レプリカの
埋め込みキャッシュを論理的に分離して単一の論理キャッシュとみなし、どのレプリカからでも
論理キャッシュの任意の部分にアクセスできるようにして読みによる重複を削減する。書きは
全キャッシュを汚染するため、書かれたオブジェクトを素早く demote して書きによる重複も
抑える。ただし重複削減が性能を害するケースがあるため、online analyzer で重複と
カバレッジのバランスを取る (abstract)。eventually-consistent KV ストア・
strongly-consistent KV ストア・プロダクション DB の3システムに実装し、YCSB 下の
eventually-consistent KV ストアで 2.6×〜5.4× のスループット向上を報告 (abstract)。

## Problem & motivation
- [paper] 既存のレプリケートストレージシステムは、各レプリカ内の埋め込みキャッシュを
  サイロで(レプリカごとに独立に)管理しており、レプリカ間で顕著な cache redundancy が
  生じ、結果として性能が低い (abstract)。
- [paper] 読みだけでなく書きも問題で、書きは全レプリカのキャッシュを汚染 (pollute) し、
  書き起因の重複を生む (abstract)。
- [paper] 一方で、重複を減らすこと自体が性能を害するケースもある(だから online analyzer
  によるバランス調整が要る、という構図)(abstract)。
- [inference] 「重複=悪」ではなく「重複 vs カバレッジのトレードオフ」として定式化して
  いる点がこの論文のフレーミングの核に見える。重複はキャッシュ実効容量を減らすが、
  ローカルヒットを増やす、という緊張関係を指していると読める(ただし abstract からの
  推測であり、本文の定式化は未確認)。

## System model & assumptions
(abstract-only のため未記載)

- [question] 「any replica が logical cache の any part にアクセスできる」の実現手段
  (リモートキャッシュ読みのネットワーク経路、レイテンシ前提)は本文確認が必要。
- [question] strongly-consistent KV ストアに適用した際、他レプリカのキャッシュから
  読むことと一貫性保証(stale read の扱い)をどう両立させているかは abstract からは
  不明。deep-read 時の最重要確認点。

## Approach
(abstract-only のため未記載)

abstract に現れる構成要素のみ列挙(詳細動作は未確認):
- [paper] 埋め込みキャッシュ群の論理的分離 → 単一論理キャッシュ化 (abstract)。
- [paper] 書かれたオブジェクトの quick demotion (abstract)。
- [paper] 重複とカバレッジのバランスを取る online analyzer (abstract)。

## Evaluation
(abstract-only のため未記載)

- [paper] 実装対象は3システム: eventually-consistent KV ストア、strongly-consistent
  KV ストア、production database。評価はマイクロベンチ・マクロベンチ・実トレースで、
  例として eventually-consistent KV ストアの YCSB で 2.6×〜5.4× のスループット向上
  (abstract)。具体的なシステム名・ハードウェア・ベースライン設定は abstract に無い。

## Limitations
(abstract-only のため未記載)

## Relations
- [inference] [[2025-tpctc-gao-distash]](DiStash: FoundationDB の多階層 KV キャッシュ/
  ストレージ階層)とテーマが近い可能性: どちらも「レプリケートされた KV ストアの
  キャッシュ階層の使い方」を扱う。ただし本ノートは abstract-only であり、比較軸
  (階層 vs レプリカ横断)は本文読解後に確定させる。
- [inference] [[2026-pvldb-zhang-terark-ds]](Terark-DS: 分離ストレージ上の KV 分離)とは
  「disaggregation」の語を共有するが、Ldc の分離は物理分離ではなく論理分離
  (embedded cache を論理的に一つに見せる)である点で方向が異なるように読める
  (abstract)。関連づけは暫定。

## Idea seeds
- [question] strongly-consistent 構成で他レプリカのキャッシュエントリを読む場合、
  そのエントリの新しさ(バージョン)をどう保証するのか。もし読みのたびに
  リーダー/クォーラム確認が要るなら利得はネットワーク往復とのトレードオフになる。
  本文入手後、consistency 保証の節と strongly-consistent KV での性能利得幅を最初に
  確認する。DB 側の CC(MVCC 等)との相互作用があれば Phase 2 の課題候補になり得る。
- [inference] 「書きが全レプリカのキャッシュを汚染するので quick demotion する」
  (abstract) という設計は、write-heavy な HTAP 的ワークロードではキャッシュヒット率を
  下げる方向に働き得る。検証案: read/write 比率を振ったときに Ldc の利得が反転する点が
  あるか(本文の評価がこれをカバーしているかをまず確認)。
- [inference] online analyzer による「redundancy vs coverage」の動的バランスは、
  larger-than-memory DB の buffer management(単一ノード内の admission/eviction policy)
  と構造的に相似に見える。レプリカ横断のキャッシュ配置問題を buffer pool の政策問題
  として定式化し直せるかは考える価値がある(abstract からの類推であり、本文が既に
  そう定式化している可能性もある)。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: 検証パスによる修正(Problem & motivation の [paper] 行から abstract に無い「静的な重複排除ではなく」「動的な」の対比表現を削除)
