---
title: "Hot-Page-Aware Checkpointing for Flash SSDs"
authors: [Geunhyun Park, Sang-Won Lee]
venue: "ICDEW (2026 IEEE 42nd International Conference on Data Engineering Workshops)"
year: 2026
ids: {doi: "10.1109/ICDEW71238.2026.00007", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1109/ICDEW71238.2026.00007", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [checkpointing, flash-ssd, buffer-management, recovery, oltp]
---

> **ソース**: abstract のみ(PDF は IEEE Xplore で paywall)。
> Semantic Scholar API から取得:
> https://api.semanticscholar.org/graph/v1/paper/DOI:10.1109/ICDEW71238.2026.00007?fields=title,abstract,authors,year,venue,externalIds

## TL;DR
SSD 上の DBMS では、少数の hot page が多数の checkpoint interval にわたり dirty の
まま残って繰り返し flush 対象に選ばれ、durable progress をほとんど生まない冗長な
writeback がデバイス帯域を消費する — この問題に対し、page ごとに「連続して checkpoint
に選択された回数」を追跡して不要な flush を遅延させる軽量機構を提案 (abstract)。
MySQL/InnoDB に実装し TPC-C で評価、Vanilla MySQL 比 1.58× のトランザクション
スループット向上を主張 (abstract)。

## Problem & motivation
- [paper] Flash SSD は現代 DBMS の支配的ストレージ媒体。random read スループットは
  高いが、持続的な書き込みは flash 管理活動(flash management activities)により
  read より大きな内部デバイスオーバーヘッドを生む — 個々の write 要求の応答が速くても
  (abstract)。
- [paper] この read/write 非対称性が checkpointing(crash recovery 時間を制限し
  log 成長を抑える DBMS の中核機構)に性能課題を生む。write-intensive な OLTP
  ワークロードでは checkpoint が大量の background write traffic を発生させ、SSD 上で
  ボトルネックになり得る (abstract)。
- [paper] さらに、少数の hot page が多くの checkpoint interval を跨いで dirty のまま
  残り、繰り返し checkpoint flush に選択される。これは durable progress をほとんど
  生まない冗長 writeback となり、デバイス帯域を消費し write 起因の干渉を増大させ、
  顕著なレイテンシによりトランザクションスループットとシステム効率を劣化させる
  (abstract)。
- [paper] 目標は checkpointing を SSD の特性に整合させること: 冗長書き込みの削減に
  より SSD endurance と DBMS 全体性能を改善する (abstract)。

## System model & assumptions
(abstract-only のため未記載)

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

## Limitations
(abstract-only のため未記載)

## Relations
- [[2026-pvldb-lee-how-to-write-to-ssds.md]]: 同じく「flash SSD への書き込みを
  どう減らす/整形するか」という軸のノート。本論文は DBMS の checkpoint flush 側から、
  あちらは WA 最適化 / out-of-place 書き込み側から同じデバイス特性に取り組んでいる。
  [question] ファイル名から第一著者が Lee であり、本論文の共著者 Sang-Won Lee と
  同一人物の可能性がある — フルテキスト入手時に確認。
- [[2026-pvldb-kuschewski-btrlog.md]]: checkpoint は「log 成長の制御」機構として
  abstract で位置付けられており (abstract)、WAL サービス側(BtrLog)と checkpoint 側
  (本論文)は log 管理コストの二面。直接の競合ではない。

## Idea seeds
- [question] hot page の flush を遅延させることは、checkpoint の本来の目的である
  「recovery 時間の上限保証」(abstract で明言) と原理的にトレードオフのはず —
  deferral が redo 距離 / checkpoint age をどこまで伸ばすか、論文がどうバウンドして
  いるかはフルテキストで要確認。最初の検証: InnoDB で flush 遅延量と recovery 時間の
  関係を実測する。
- [inference] 「連続 checkpoint 選択回数の per-page 追跡」はホスト(buffer manager)側の
  hot/cold 判定であり、デバイス側の hot-cold 分離(multi-stream / FDP のような
  placement 制御)と直交して組み合わせられる可能性がある。検証: deferral 単体 vs.
  deferral + 書き込みストリーム分離で WA と endurance への寄与を分解測定する。
- [question] 1.58× という数値の条件(TPC-C の規模、SSD の機種・充填率、checkpoint
  間隔の設定)は abstract からは不明。フルテキスト入手後に評価設定と、fuzzy
  checkpointing 系のベースラインが比較に含まれるかを確認する。

## Changelog
- 2026-07-06: created (status: abstract-only)
