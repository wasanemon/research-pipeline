---
title: "Scalable and Resilient Storage Tier for Azure SQL Hyperscale"
authors: [Alejandro Hernandez Saenz, Krystyna Reisteter, Sarika Iyer, Yu Wang, Shweta Raje, Swati Roy, Bhupesh Chawda, Kashish Goyal, Vishnu Das, Kinshuk Chopra, Rishita Chauhan, Prashanth Purnananda, Hanuma Kodavalla]
venue: "SIGMOD Companion"
year: 2026
ids: {doi: "10.1145/3788853.3803083", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3788853.3803083", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [disaggregated-storage, cloud-native, oltp, storage-tier, resiliency]
---

<!-- ソース: https://api.openalex.org/works/doi:10.1145/3788853.3803083?mailto=miyayu@keio.jp
     (2026-07-06 取得)。abstract は OpenAlex の abstract_inverted_index からの再構成
     (語順はインデックスで保存)。dl.acm.org の PDF は自動取得に HTTP 403 のため本文未読。
     OpenAlex メタデータ: pp.426-436、出版日 2026-05-26、ライセンス CC-BY (gold OA)、
     著者所属は Microsoft Corporation (Redmond, USA / Bengaluru, India)。
     DBLP 未確認のため dblp id は空欄(収載確認後に BibTeX を DBLP から機械取得すること)。 -->

## TL;DR
Azure SQL Database Hyperscale は compute / log / storage を分離(disaggregate)して
最大 128TB のデータベースを独立スケールさせるが、Page Server と Azure Storage の間の
remote IO がレイテンシと resiliency の課題を生む。本論文はこの storage tier を再設計し、
OLTP ワークロード向けに performance・scalability・resiliency を高めたと主張する
産業システム報告 (abstract)。

## Problem & motivation
- [paper] Hyperscale アーキテクチャは compute, log, storage を分離し、最大 128TB までの
  データベースの independent scaling を可能にする (abstract)。
- [paper] この設計は elasticity をもたらす一方で、Page Servers と Azure Storage の間の
  remote IO に起因する latency と resiliency の課題を導入する (abstract)。
- [paper] これらの課題への対処として、OLTP ワークロード向けに performance・scalability・
  resiliency を強化する再設計された storage tier を提案する (abstract)。

## System model & assumptions
(abstract-only のため未記載)

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

## Limitations
(abstract-only のため未記載)

## Relations
- [inference] [[2026-sigmod-arkhangelskiy-aurora-limitless]]: 同じ SIGMOD Companion の
  クラウドベンダによる production OLTP システム報告(あちらは AWS の水平スケール、
  こちらは Azure の storage tier 再設計)。クラウド OLTP のスケーラビリティ課題への
  ベンダ別アプローチとして対で読む価値がある。abstract 同士の主題レベルの関連であり、
  技術的な直接比較は本文読解後に行う。
- [inference] [[2026-pvldb-kuschewski-btrlog]]: BtrLog が問題視した「クラウド DB の
  ストレージ/ログのリモート化に伴うレイテンシ」と、本 abstract の「Page Server と
  Azure Storage 間の remote IO によるレイテンシ課題」は同じ問題系に見える。
  ただし本論文がログ側・ページ側のどちらをどう再設計したかは abstract からは不明。
- [inference] [[2026-pvldb-zhang-terark-ds]]: compute-storage 分離環境でのリモート IO 起因の
  性能劣化への産業側の対処という点で主題が重なる(あちらは LSM/KV 分離エンジン、
  こちらは page-based な SQL DBMS の storage tier)。

## Idea seeds
- [question] 「redesigned storage tier」が具体的に何を変えたのか — Page Server と
  Azure Storage の役割分担の変更なのか、IO パスの短縮(キャッシュ階層・ローカル SSD 活用)
  なのか、複製/耐障害機構の変更なのか — は abstract から判別できない。本文入手
  (dl.acm.org は CC-BY・gold OA なのでブラウザ経由で取得可能なはず)が最優先。
- [inference] 「remote IO が latency と resiliency の両方の課題を生む」という問題設定は、
  BtrLog(ログ)・Terark-DS(LSM)と合わせると、分離アーキテクチャの IO パス再設計が
  2026 年時点の産業側共通課題であることを示す材料になる。検証: 本文読解後、
  各システムが「どの IO をどこに残し、何をローカル化/非同期化したか」の比較表を
  ideas/ に起こし、未カバーの IO パス(候補領域)を洗い出す。

## Changelog
- 2026-07-06: created (status: abstract-only)
