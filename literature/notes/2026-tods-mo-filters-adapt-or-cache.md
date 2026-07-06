---
title: "Mitigating False Positives in Filters: To Adapt or to Cache?"
authors: [Tianchi Mo, "et al.(全著者リストは未確認)"]
venue: "ACM Trans. Database Syst. (TODS)"
year: 2026
ids: {doi: "10.1145/3786324", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3786324", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [filters, false-positive, adaptive-filter, quotient-filter, caching, zipfian, skewed-workload]
---

> **ソース注記**: 本ノートは abstract のみを情報源とする(status: abstract-only)。
> abstract は OpenAlex API 経由で取得
> (https://api.openalex.org/works/doi:10.1145/3786324、対象 DOI:
> https://doi.org/10.1145/3786324)。PDF 本文は未読。本文由来の技術的詳細・
> 実験数値は一切記載しない。

## TL;DR
偽陽性を返したクエリに応じて内部表現を変える adaptive filter について、
「強い適応性(strongly adaptive)を持つフィルタ」対「非適応フィルタ+最近の
偽陽性のキャッシュ(CAF)」という対立軸を、(敵対的でない)Zipfian に偏った
クエリ分布の下で理論・実験の両面から比較した論文 [paper] (abstract)。
adaptive 系フィルタはいずれも非適応フィルタより偽陽性率が 1〜2 桁低く、
strongly adaptive な broom filter / TAF が CAF に勝るのは「distinct な負クエリ数の
positive set サイズに対する比が高い」場合に限られる、と主張する [paper] (abstract)。

## Problem & motivation
- [paper] 近年の研究は adaptive filter(偽陽性を出したクエリに応じて内部表現を
  変えるフィルタ)を調べてきた。その分類として (1) strongly adaptive filter:
  過去のクエリ履歴に依らず(適応的な敵対者に対しても)任意のクエリで偽陽性確率
  ≤ ε を保証、(2) support-optimal filter: 敵対者が oblivious のとき十分長いクエリ列に
  対する平均偽陽性確率 ≤ ε を保証、(3) 表現を変えて経験的には性能が良いが static
  filter を超える証明可能な保証を持たないその他の adaptive filter、がある (abstract)。
- [paper] 本論文が調べるのは、データベース応用で一般的な(非敵対的な)偏った
  クエリ分布の下で strongly adaptive filter が持つ性能上の利点である。偏りは
  パラメータ z の Zipfian 分布でモデル化する (abstract)。
- [paper] 比較対象: strongly adaptive filter として broom filter と telescoping
  adaptive filter (TAF)。adaptive だが strongly adaptive でないものとして adaptive
  cuckoo filter (ACF)、および非適応の rank-and-select quotient filter に最近の
  偽陽性のキャッシュを付加した cache-augmented filter (CAF、本論文の命名)
  (abstract)。
- [paper] 理論面: broom filter・TAF・CAF の偽陽性率について、クエリ列長 → ∞ の
  極限での Zipfian パラメータ z の関数としての上界を証明する (abstract)。
- [paper] 実装・実験面: (非適応の)rank-and-select quotient filter に基づく broom
  filter の実装を提供し、合成 Zipfian クエリ列上で broom filter・TAF・CAF の上界を
  実験的に検証。さらに強い偏りを持つ実世界のネットワークトレースデータ上で
  broom filter・TAF・CAF・ACF の観測偽陽性率を測定する (abstract)。
- [paper] 主結果: すべての adaptive filter が非適応フィルタより 1〜2 桁低い
  偽陽性率を達成した。broom filter と TAF が CAF に勝るのは distinct な負クエリの
  数の positive set サイズに対する比が高いときのみで、それ以外では CAF と
  strongly adaptive filter の偽陽性率は同程度である (abstract)。
- [inference] タイトルの「To Adapt or to Cache?」は、理論保証の強い適応機構が
  実際のスキュー下でどこまで単純なキャッシュ増強に対して優位かを問う構図と
  読める。abstract の主結果は「多くの場合キャッシュで十分、優位性が出る条件は
  限定的」という含意に見えるが、条件の正確な定式化は本文未読のため未確認。

## System model & assumptions
(abstract-only のため未記載)

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

## Limitations
(abstract-only のため未記載)

## Relations
- 既存の 42 ノートの中に、フィルタ(Bloom/quotient/cuckoo 系)の偽陽性や
  adaptive filter を直接扱うノートは確認できず(Bloom filter 等を LSM の一部品と
  して言及するノートは複数あるが、フィルタ自体が主題のものは無い)。現時点で
  確度をもって張れる関連リンクは無し。
- [question] LSM-tree 系ノート(ArceKV、Ren LSM-scheduling、Liu learned-index-LSM
  など)の本文がフィルタの偽陽性を論じているかは各ノートからは未確認。本論文を
  deep-read した際に、LSM の point lookup フィルタという文脈が本文にあれば
  リンクを追記する。

## Idea seeds
- [question] 「distinct な負クエリ数 / positive set サイズの比が高いときのみ
  strongly adaptive が CAF に勝つ」(abstract) という境界条件は、DB ワークロード
  (例: LSM-tree の point lookup)で実際にどちら側に落ちるのか。本文の理論上界と
  実験設定を読んだ上で、代表的な KV ワークロードのトレースでこの比を測るのが
  最初の検証になる。
- [inference] 「adaptive 機構 vs 単純なキャッシュ増強」という比較の枠組み自体は、
  フィルタ以外の適応的データ構造(適応的インデックスなど)にも移植できる可能性が
  ある。ただしこれは abstract の構図からの類推であり、本文の主張ではない。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: 検証パスによる修正(Relations の既存ノート数 49→42 に訂正)
