---
title: "LakeMem: An Elastic Disaggregated-Memory Caching Layer for Analytical Processing Systems"
authors: [Xinyi Yu, Yingqiang Zhang, Hao Chen, Zhaoxiang Huang, Xinjun Yang, Feifei Li, Chuan Sun, Jing Geng, Jiong Xie, Ninglong Weng, Yiming Zhang]
venue: "SIGMOD Companion"
year: 2026
ids: {doi: "10.1145/3788853.3803100", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3788853.3803100", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [disaggregated-memory, caching, analytical-processing, lakehouse]
---

ソース: OpenAlex API レスポンス
(https://api.openalex.org/works/doi:10.1145/3788853.3803100?mailto=miyayu@keio.jp、
2026-07-06 取得)。abstract は OpenAlex の abstract_inverted_index からの再構成。
ACM DL の PDF は自動取得に HTTP 403 のため未読。
**注意**: 取得できた abstract は問題提起の文で終わっており(手法・結果の記述なし)、
OpenAlex 側で abstract が途中で切れている可能性が高い [inference]。

## TL;DR
分析処理システム(lakehouse/lakebase)向けの、elastic な disaggregated-memory (DM)
キャッシング層 "LakeMem" の提案 (title)。動機は、分析ワークロードが memory-bound に
なりがちな一方、既存の DM キャッシュの多くが byte-uniform で、「共有される base-table
データ」と「ノード私有の中間データ」の意味的非対称性を無視している点 (abstract)。
[inference] タイトルと問題提起から、この非対称性を活用するキャッシュ設計と推測されるが、
手法・結果は取得済みテキストに含まれず未確認。

## Problem & motivation
- [paper] lakehouse/lakebase アーキテクチャの普及に伴い、shared storage +
  open table format 上で走る分析処理ワークロードは頻繁に memory-bound になる:
  エンジンはスループットのために大きな base table をキャッシュし、かつ大量の
  中間状態(hash table、shuffle buffer 等)を保持する (abstract)。
- [paper] このメモリ圧力に対し、disaggregated memory (DM) はノード単位の
  overprovisioning なしに elastic な容量を提供できる自然な選択肢である (abstract)。
- [paper] しかし既存の DM キャッシュの多くは byte-uniform、すなわち全データを
  一様に扱い、「共有される base-table データ」と「ノード私有の中間データ」の間の
  意味的非対称性 (semantic asymmetry) を無視している (abstract)。

## System model & assumptions
(abstract-only のため未記載)

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

## Limitations
(abstract-only のため未記載)

## Relations
- [inference] [[2026-pvldb-zhao-sidle.md]](CXL/分離メモリ上へのデータ配置)と
  テーマが近接: どちらも「分離メモリ上に何をどう置くか」の問題。ただし本ノートは
  abstract-only のため、技術的な関係(競合か補完か)は本文読解まで未確定。
- [inference] [[2026-pvldb-zhang-terark-ds.md]](分離ストレージ上の KV)とは
  「分離リソース上のデータサービス」という広い括りで隣接するが、階層(メモリ vs
  ストレージ)が異なる。関係性の主張はしない。

## Idea seeds
- [inference] 「共有 base-table データ vs ノード私有中間データ」という二分は、
  キャッシュの一貫性・耐障害性・退避 (eviction) 方針をデータ種別ごとに分けられる
  ことを示唆する(共有データは複数ノードから再利用可能、中間データは所有ノード
  消滅で無価値になり得る)。検証: DM キャッシュシミュレータで、単一 LRU と
  「種別別プール + 種別別 eviction」を TPC-H 系ワークロードで比較。
- [question] 中間状態(hash table、shuffle buffer)を DM に置く場合、ローカル DRAM
  比のレイテンシ増がハッシュ join/シャッフルの実行時間に与える影響はどの程度で、
  LakeMem はそれをどう吸収しているのか。本文 (§設計・評価) で要確認。
- [question] "elastic" が意味するのは容量の動的伸縮か、ノード数の伸縮か、両方か。
  課金/リソース管理モデルとの接続も含めて本文で要確認。

## Changelog
- 2026-07-06: created (status: abstract-only)
