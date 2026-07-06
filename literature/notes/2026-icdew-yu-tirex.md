---
title: "TiRex: An HTAIP Framework Beyond HTAP for Unified Transactional, Analytical, and AI Workloads"
authors: [Jane Yu, Yu Dong, Rossi Sun, Lucas Sun, Liu Tang, Ed Huang, Max Liu]
venue: "ICDEW"
year: 2026
ids: {doi: "10.1109/ICDEW71238.2026.00021", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1109/ICDEW71238.2026.00021", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [htap, retrieval, vector-search, full-text-search, mpp, consistency]
---

> **注意: abstract-only ノート。** IEEE Xplore で PDF がペイウォール内のため、
> Semantic Scholar API 経由の abstract のみを読んだ。技術詳細・実験数値は
> 本文未確認であり、本ノートには書かない。
> ソース: https://api.semanticscholar.org/graph/v1/paper/DOI:10.1109/ICDEW71238.2026.00021?fields=title,abstract,authors,year,venue,externalIds
> (取得日: 2026-07-06)

## TL;DR
[paper] HTAP システムは transactional + analytical を単一エンジンで統合するが、
AI アプリケーションを支える retrieval 中心ワークロード(keyword ベースの full-text
search、embedding ベースの vector similarity search)を効率的に扱う設計になっていない、
というのが出発点 (abstract)。TiRex(TiDB Retrieval Execution Engine)は HTAP を
HTAIP(Hybrid Transactional, Analytical, and AI Processing)へ拡張するフレームワークで、
retrieval 向けインデックス構築を DB ストレージから分離し、transactional log から
非同期に full-text / vector インデックスを構築・独立永続化し、クエリ時は analytical と
retrieval を MPP 実行エンジンで統一実行する。shard ベースの indexing / scheduling
モデルと、retrieval 向けの bounded-staleness 一貫性セマンティクスを導入し、実験では
スケーラブルな indexing スループット・低レイテンシ検索・混合ワークロード下の安定性能を
示したと主張する (abstract)。

## Problem & motivation
- [paper] HTAP システムは transactional / analytical の統合には対応するが、AI 対応
  アプリケーションで増大する retrieval 中心ワークロード(full-text search による
  keyword-relevance 検索、vector similarity search による embedding ベースの意味検索)を
  効率的にサポートする設計ではない (abstract)。
- [paper] 既存解は外部システムへの依存か、ストレージ層に密結合したインデックスに
  頼るのが典型で、データ重複・拡張性の制限・コア HTAP ワークロードへの干渉を招く
  (abstract)。
- [paper] 主張される貢献: (i) HTAP → HTAIP という抽象の拡張、(ii) retrieval 向け
  インデックス構築の DB ストレージからの decouple(transactional log からの非同期構築+
  独立永続化)、(iii) analytical と retrieval の MPP エンジンによる統一実行(共有
  スケジューリング・並列性、transactional 処理への影響なしと主張)、(iv) shard ベースの
  indexing / scheduling モデルと bounded-staleness 一貫性 (abstract)。
- [inference] abstract の書きぶりからは、位置づけは「新 CC プロトコル」ではなく
  「HTAP システム(TiDB 系)の実行モデル拡張のシステム設計論文」に見える。名称
  (TiDB Retrieval Execution Engine)は abstract 自身が明記している (abstract)。

## System model & assumptions
(abstract-only のため未記載)

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

- [inference] abstract は「scalable indexing throughput / low-latency full-text and
  vector search / stable performance under mixed workloads」と述べるのみで、比較対象・
  ベンチマーク・数値は一切不明。本文を読むまで評価の強さは判断できない。

## Limitations
(abstract-only のため未記載)

- [question] 「without impacting transactional processing」(abstract) がどの程度の
  分離を意味するか(リソース分離か、log 追従の遅延許容だけか)は本文確認が必要。
- [question] bounded-staleness の「bound」が何で規定されるか(時間か、log オフセットか、
  トランザクション境界か)は abstract からは不明。

## Relations
- [inference] HTAP の拡張という点で [[2026-pvldb-ding-jasper-htap]](HTAP 向け
  ストレージレイアウト)および [[2026-pvldb-wu-aqd]](HTAP クエリディスパッチ)と
  同じ問題圏。ただし TiRex は retrieval(full-text / vector)という第3のワークロード
  クラスを加える方向であり、比較軸は「AP との干渉回避」から「retrieval インデックスの
  鮮度と干渉回避」に移る。詳細な関係づけは本文読解後に行う。

## Idea seeds
- [inference] 「transactional log から非同期にインデックスを構築し、独立に永続化する」
  (abstract) という構図は、log を single source of truth とする派生データ構造の一種と
  読める。bounded-staleness の保証と log 追従(遅延・再構築・障害時回復)の関係は、
  HTAP のレプリカ鮮度問題の一般化として研究の切り口になり得る。検証の第一歩:
  本文を入手し、staleness bound の定義と障害時のインデックス回復手順を確認する。
- [question] retrieval を MPP エンジンで analytical と統一実行すると (abstract)、
  レイテンシ志向(point の類似検索)とスループット志向(スキャン系 AP)のスケジューリング
  要求が衝突しないか。shard ベースの scheduling モデルがこれをどう扱うかは本文確認事項。
- [question] 「HTAIP」という抽象がベンチマーク化可能か — mixed TX + AP + retrieval の
  標準ワークロードは(この abstract の範囲では)言及がない。存在しないなら、それ自体が
  空白の可能性。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: 検証パスによる修正(Evaluation 節の引用を原文どおり「low-latency full-text and vector search」に訂正)
