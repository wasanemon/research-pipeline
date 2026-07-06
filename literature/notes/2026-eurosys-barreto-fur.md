---
title: "FUR: Fast and Unlimited Reads on Persistent Memory Transactions"
authors: [João Barreto, Daniel Castro, Paolo Romano, Alexandro Baldassin]
venue: "EuroSys"
year: 2026
ids: {doi: "10.1145/3767295.3769343", arxiv: "", dblp: "conf/eurosys/BarretoCRB26"}
urls: {paper: "https://doi.org/10.1145/3767295.3769343", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [persistent-memory, htm, read-only-transactions, transaction-processing]
---

> 取得ソース: Semantic Scholar API
> (https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3767295.3769343?fields=title,abstract,authors,year,venue,externalIds、
> 2026-07-06 取得)。dl.acm.org の PDF は自動取得に対して HTTP 403 のため abstract のみ。
> API レスポンス上は openAccessPdf が GOLD / CC-BY と表示されており、後日 PDF 取得を再試行する価値あり。

## TL;DR
[paper] Persistent Memory (PM) 上の Persistent Hardware Transactions (PHT) において、
Read-Only (RO) トランザクションが被る2つのボトルネック — ①並行 update トランザクション
との一貫性確保のための post-commit delay、②商用 HTM 実装の厳しい read capacity 制限 —
を解消する新しい PHT 設計 FUR を提案。核となるのは、一部の現代 HTM が提供する
「transactional access tracking を suspend / resume する高度な命令」の活用 (abstract)。
[paper] IBM POWER9 上の TPC-C 評価で、100% update トランザクションのワークロードを除き、
state-of-the-art の persistent hardware transaction 設計 (SPHT) および software memory
transaction 設計(Pisces または SpecPMT ベース)を最大 6.17× 上回る (abstract)。

## Problem & motivation
- [paper] 新興 PM 上での PHT サポートは近年改善されてきたが、RO トランザクションの
  低性能はほぼ見過ごされてきた (abstract)。
- [paper] RO トランザクションのボトルネックは2つ: i) 並行 update トランザクションとの
  一貫性を保証するために必要な「相当な post-commit delay」、ii) 商用 HTM 実装の
  よく知られた厳しい read capacity 制限 (abstract)。
- [paper] FUR はこの「state-of-the-art PHT で RO トランザクションを阻害する2大
  ボトルネック」の両方を排除する設計であると主張 (abstract)。
- [inference] タイトルの "Fast and Unlimited Reads" は上記2ボトルネックにそれぞれ対応
  している(Fast = post-commit delay の排除、Unlimited = HTM read capacity 制限の回避)
  と読めるが、対応関係の明示は本文未確認。

## System model & assumptions
(abstract-only のため未記載)

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

## Limitations
(abstract-only のため未記載)

## Relations
- [inference] [[2026-arxiv-egorov-flintkv]](NVM スキップリスト)と同じ PM/NVM 永続化
  領域の論文だが、FUR は HTM ベースのトランザクション実行層、FlintKV はデータ構造層で
  レイヤが異なる。深読後に関係を精査。
- 注意: abstract 中の比較対象 "Pisces"(software memory transactions)は、既存ノート
  [[2026-pvldb-weng-pisco]](分離バグ縮約フレームワーク Pisco)とは**無関係の別システム**。
  名前が酷似しているため将来の検索・参照時に混同しないこと。

## Idea seeds
- [question] "advanced instructions that some contemporary HTMs provide to suspend (and
  resume) transactional access tracking" (abstract) を提供する HTM はどの程度存在するのか。
  評価は IBM POWER9 のみ (abstract) であり、この命令への依存が FUR の可搬性をどこまで
  制約するかは本文で要確認。PDF 読解時の最優先チェックポイント。
- [question] "With the exception of workloads comprised of 100% update transactions"
  (abstract) — 100% update 時に FUR が既存法と同等になるのか劣化するのか、abstract からは
  判別できない。RO 最適化が update 側に課すコストの有無は、DBMS 文脈への転用可否を
  左右するので本文で確認する。
- [inference] 「RO トランザクションだけ access tracking を一時停止する」という発想は、
  ソフトウェア CC における read validation の選択的省略(read-only snapshot 読みの
  検証コスト削減)と構造が似ている可能性がある。PM+HTM 固有の技法なのか、より一般の
  CC 設計に移植可能な原理なのか、深読後に切り分けたい。最初の検証は、本文の設計が
  HTM の機能のどこに本質的に依存しているかの棚卸し。

## Changelog
- 2026-07-06: created (status: abstract-only)
