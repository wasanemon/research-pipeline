---
title: "ByteGraph-Dione: An Adaptive Dual-Format Graph Engine with Hotspot Awareness and Transaction Efficiency for Production-Scale Workloads"
authors: ["Chao Chen et al."]
venue: "SIGMOD Companion"
year: 2026
ids: {doi: "10.1145/3788853.3803073", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3788853.3803073", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [graph-database, htap, mvcc, snapshot-isolation, hotspot, storage-format, replication, production-system]
---

> **ソース注記**: 本ノートは abstract のみに基づく(status: abstract-only)。
> abstract の取得元: https://doi.org/10.1145/3788853.3803073
> (メタデータは OpenAlex 経由: https://api.openalex.org/works/doi:10.1145/3788853.3803073)。
> さらに OpenAlex に収録されていたのは **abstract の第 1 段落のみ**であり、
> 手法・評価に触れる後続段落は未取得(S2 / Crossref には abstract 収録なし)。
> したがって本ノートの内容は「問題設定」の範囲にほぼ限られる。

## TL;DR
ByteDance のソーシャルプラットフォーム(例: Douyin)が生成する production 規模の
グラフデータを対象に、OLTP と OLAP の収斂(HTAP 化)が既存アーキテクチャ
(同社の先行システム ByteGraph 等)にもたらす新しい課題 — 過剰なバージョン保持、
硬直的なストレージフォーマット、ホットスポット — を提起する論文 (abstract)。
タイトルによればシステム名は ByteGraph-Dione で、「adaptive dual-format」
「hotspot awareness」「transaction efficiency」を掲げるが (title)、取得できた
abstract 断片には解決手法の記述が無く、アプローチの内容は未確認。

## Problem & motivation
- [paper] ByteDance のモダンなソーシャルプラットフォーム(例: Douyin、中国版
  TikTok)は前例のない規模でグラフデータを生成しており、コスト効率が高く
  低レイテンシなストレージソリューションを要求する (abstract)。
- [paper] 同社の先行システム(ByteGraph 等)は shared storage と workload-aware な
  garbage collection でこれらの課題に対処してきたが、OLTP と OLAP の収斂が進み、
  既存アーキテクチャに新しい課題が生じている (abstract)。
- [paper] 具体的な緊張関係: OLTP 操作は最新のデータバージョンへの継続的な更新を
  要求する一方、OLAP クエリ(例: Snapshot Isolation 下)は分析の一貫性のために
  安定したバージョンに依存する。この本質的な緊張により、従来のトランザクション
  機構は過剰な数のデータバージョンを保持せざるを得ず、追加のアクセス
  オーバーヘッドが生じる (abstract)。
- [paper] 硬直的なストレージフォーマットは、乖離したアクセスパターン
  (exact query と analytical scan)に適応できない (abstract)。
- [paper] バイラルイベントや高負荷なグラフ分析タスクに起因するホットスポットが、
  従来の粗粒度レプリカアーキテクチャの性能をさらに劣化させる (abstract)。
- [inference] 以上はすべて問題提起(abstract 第 1 段落)であり、Dione がこれらに
  どう対処するかは取得済みソースからは一切確認できない。タイトルの
  「dual-format」はフォーマット硬直性への、「hotspot awareness」はホットスポット
  への、「transaction efficiency」はバージョン過剰保持への対応を示唆するが、
  これは推測に過ぎない。

## System model & assumptions
(abstract-only のため未記載)

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

## Limitations
(abstract-only のため未記載)

## Relations
- [[2026-pvldb-ding-jasper-htap.md]](Jasper: HTAP レイアウト): [inference] 本論文の
  abstract が挙げる「硬直的ストレージフォーマットが exact query と analytical scan
  という乖離したアクセスパターンに適応できない」(abstract) という問題は、HTAP 向け
  ストレージレイアウトを扱う Jasper と同じ問題領域(こちらはグラフエンジン文脈)。
  full text 読解後にフォーマット適応のアプローチを比較する価値がある。
- [[2026-pvldb-wu-aqd.md]](AQD: HTAP ディスパッチ): [inference] OLTP(最新
  バージョンへの更新)と OLAP(SI 下の安定バージョン読み)の緊張 (abstract) は、
  HTAP ワークロードの振り分けを扱う AQD と接続する問題設定。関連はいまのところ
  問題領域レベルであり、手法上の関係は full text で確認が必要。

## Idea seeds
- [question] 「OLTP は最新版、OLAP は安定版」という緊張が「過剰なバージョン保持」
  を強いる (abstract) とされるが、Dione がバージョン数をどう抑えるのか
  (GC 方針か、バージョン表現か、dual-format との連動か)は不明。full text 入手後の
  最優先確認事項。
- [question] 「粗粒度レプリカアーキテクチャ」がホットスポットで劣化する (abstract)
  のに対し、hotspot awareness(タイトル)が細粒度レプリケーションを意味するのか、
  それとも別機構なのかは未確認。バイラルイベント由来のホットスポットという
  production 特有のワークロード特性の記述自体が、full text を読む価値の根拠になる。

## Changelog
- 2026-07-06: created (status: abstract-only)
