---
title: "FicusDB: Scalable Multi-Versioned Authenticated Archival Storage"
authors: ["Hongbo Zhang et al."]
venue: "EuroSys"
year: 2026
ids: {doi: "10.1145/3767295.3803601", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3767295.3803601", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [blockchain, authenticated-data-structure, archival-storage, multi-versioning, log-structured, copy-on-write, write-amplification, caching]
---

> **ソース注記**: 本ノートは abstract のみに基づく(status: abstract-only)。
> abstract は Semantic Scholar API
> (https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3767295.3803601?fields=abstract)
> 経由で取得。論文本体の URL: https://doi.org/10.1145/3767295.3803601
> 本文 PDF は未読のため、abstract に書かれていない技術的詳細・実験数値は一切記載しない。

## TL;DR
ブロックチェーンではコンセンサスのスケールに伴いストレージが支配的ボトルネックに
なっており、従来研究は authenticated data structure (ADS) 自体を再設計するため互換性を
犠牲にし hard fork を要していた。FicusDB は逆に ADS インターフェースを維持したまま
ストレージ層を再設計する log-structured なアーカイバルストレージで、①compaction を
不要にする location-based identifier 付き append-only log、②LRU thrashing を避ける
CoW-aware な木構造キャッシュ、③proof の正しさと storage durability を分離する
Aggregated Hash Array (AHA) の 3 点を導入し、Ethereum 1,150 万ブロック(約 10 億キー)で
Geth 比 3.7× のストレージスループットと 66% 小さいフットプリントを完全互換のまま
達成したと主張する (abstract)。

## Problem & motivation
- [paper] コンセンサスプロトコルがスケールするにつれ、ストレージが現代ブロックチェーンの
  支配的ボトルネックになっている。システムは state が成長する中で、歴史バージョンの保持・
  integrity proof の生成・高スループットの維持を同時に求められる (abstract)。
- [paper] 従来研究はしばしば ADS(authenticated data structure)自体を再設計するが、
  その変更は互換性を犠牲にし、破壊的な hard fork を必要とする (abstract)。
- [paper] 本論文は補完的アプローチを取る: 既存の ADS インターフェースを保存したまま、
  ストレージ層(copy-on-write trie 向けの log-structured archival storage)を再設計する
  (abstract)。
- [paper] 提案手法群は write amplification の削減・read locality の改善・proof 計算の
  高速化をもたらし、ADS のセマンティクスを変えずに大幅な性能向上が可能であることを示して、
  「永続化層そのもの」をブロックチェーンスケーラビリティのイノベーション対象として
  再定位すると主張する (abstract)。

## System model & assumptions
(abstract-only のため未記載)

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

## Limitations
(abstract-only のため未記載)

## Relations
- [inference] [[2026-pvldb-liu-arcekv.md]](ArceKV: LSM compaction): FicusDB は
  「compaction を不要にする append-only log + location-based identifier」を主張しており
  (abstract)、log-structured ストレージにおける compaction コストというテーマで接点が
  ある。具体的な機構の比較は本文読解後でないとできない。
- [inference] [[2026-pvldb-lee-how-to-write-to-ssds.md]](write amplification /
  out-of-place write): FicusDB は write amplification 削減を効果として掲げており
  (abstract)、WA という評価軸を共有する。層は異なる(FicusDB はストレージエンジン層、
  こちらは SSD 書き込み経路)ため、関連の深さは本文確認待ち。
- [inference] [[2026-sigmod-webber-riot.md]](RIOT: DAG consensus): FicusDB の動機は
  「コンセンサスがスケールした結果、ボトルネックがストレージに移った」こと (abstract)。
  コンセンサス側のスケーリングを扱う RIOT とは、ブロックチェーンのボトルネック所在という
  問題設定レベルで補完関係にある。

## Idea seeds
- [question] 「ADS インターフェースを保ったままストレージ層だけを差し替える」という
  分離 (abstract) は、ブロックチェーン以外の multi-version ストレージ(MVCC の
  バージョンアーカイブ、time-travel クエリ用ストア)にも移植可能か。CoW trie 前提の
  設計がどこまで一般の CoW インデックスに一般化するかは、本文の設計詳細を読んでから
  判断する必要がある。
- [question] 「proof の正しさと storage durability の分離」(AHA、abstract)が具体的に
  どんな整合性・故障モデルの下で成立するのかは abstract からは不明。deep-read 候補。

## Changelog
- 2026-07-06: created (status: abstract-only)
