---
title: "PaCaR: Improved Buffered I/O Locality on NUMA Systems with Page Cache Replication"
authors: [Jérôme Coquisart, et al.]
venue: "EuroSys"
year: 2026
ids: {doi: "10.1145/3767295.3769359", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3767295.3769359", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [numa, page-cache, buffered-io, replication, locality, linux, os]
---

> **ソース注記**: 本ノートは abstract のみに基づく(status: abstract-only)。
> abstract は Semantic Scholar API
> (https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3767295.3769359)
> 経由で取得。論文本体の URL: https://doi.org/10.1145/3767295.3769359
> 本文 PDF は未取得のため、abstract を超える技術的詳細は一切記載しない。

## TL;DR
マルチソケット NUMA システムではリモートノードへのメモリアクセスがレイテンシ倍増・
帯域半減を招き、Linux ページキャッシュに依存する I/O 集約アプリケーションで特に
深刻になる (abstract)。PaCaR は、キャッシュされたページを NUMA ノード間で透過的に
複製するページキャッシュ複製機構であり、write の一貫性を保証し、メモリプレッシャーに
適応し、アプリケーション改変を要しないと主張する (abstract)。デュアルソケット NUMA
サーバでの評価により、synthetic ワークロードで最大 1.4×、実ワークロードで最大 25% の
性能向上を主張する (abstract)。

## Problem & motivation
- [paper] 複数ソケットを持つ現代のシステムは、メモリアクセス性能の非一様性に苦しむ。
  リモートノードのメモリアクセスはレイテンシが 2 倍、帯域が半分になりうる (abstract)。
- [paper] この問題は、Linux ページキャッシュに依存する I/O 集約アプリケーションで
  特に深刻であり、そこではローカリティが最重要となる (abstract)。
- [paper] スレッドやメモリをノード間で移動(migrate)する既存手法は、「小さな
  working set が複数ノードにまたがる多数スレッドから常時アクセスされる」高並列
  ワークロードでは問題を解決できない (abstract)。
- [paper] 提案する PaCaR は、キャッシュ済みページを NUMA ノード間で透過的に複製する
  ことでローカリティを高めるページキャッシュ複製機構である。write の一貫性を保証し、
  メモリプレッシャーに適応し、アプリケーション改変なしにシームレスに動作する
  (abstract)。

## System model & assumptions
(abstract-only のため未記載)

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

## Limitations
(abstract-only のため未記載)

## Relations
- [[2026-fast-zhan-buffered-io.md]](WSBuffer: 高帯域 SSD 時代の buffered I/O 再設計):
  [inference] 両者とも Linux ページキャッシュ / buffered I/O パスの性能問題を OS 側で
  攻める研究。ただし着眼が異なる — Zhan らは高帯域 SSD 下での write バッファリング
  経路のコスト、PaCaR は abstract によれば NUMA ノード間のアクセスローカリティ。
  「ページキャッシュのどの前提(単一コピー、write 経由)を崩すか」という比較軸で
  接続する。本文読解後に、複製がもたらす write 側コストと WSBuffer の診断
  (ページキャッシュ管理コスト)との関係を照合したい。

## Idea seeds
- [question] ページ複製の write 一貫性保証(abstract で主張)は具体的にどの機構か。
  複製維持のコストが write 集約ワークロードでどう振る舞うかは、DBMS のバッファ
  マネージャが direct I/O を選ぶ根拠と直結するため、本文読解時に最優先で確認する。
- [question] 「メモリプレッシャーへの適応」(abstract) が複製の縮退をどう行うかは、
  larger-than-memory な DB ワークロード(ページキャッシュと DB バッファプールの
  二重キャッシュ)にとって意味を持つ可能性がある。本文で評価ワークロードに DB 系が
  含まれるかを確認する。

## Changelog
- 2026-07-06: created (status: abstract-only)
