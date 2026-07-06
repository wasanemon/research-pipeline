---
title: "Scalable Leader Leases For Multi Consensus Groups in CockroachDB"
authors: [Ibrahim Kettaneh, Tsvetomira Radeva, Arul Ajmani, Sumeer Bhola, Nathan VanBenschoten, Alexander Shraer, Rebecca Taft]
venue: "SIGMOD Companion"
year: 2026
ids: {doi: "10.1145/3788853.3803081", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3788853.3803081", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [consensus, replication, leases, fault-tolerance, distributed-database]
---

## TL;DR
数百万規模の consensus group を持つ分散 DB では、read-only を quorum 通信なしで返すための
leaseholder lease の維持(頻繁な更新)がリソースを食い、lease を長くすると障害復旧が遅くなる。
本論文は CockroachDB の Raft に統合した leasing protocol「Leader Leases」を提案する。核は
ノード間の有向エッジ単位の新しい failure detector「Liveness Fabric」で、node 故障と
(対称・非対称の)ネットワーク故障を検知し、consensus group 数に依存しない liveness シグナルを
供給して強い Raft leadership 保証を与える。これにより per-consensus-group の lease 更新
トラフィックと Raft heartbeat を排除し、集中障害点を避けつつ迅速な故障検知・復旧を可能にする。
実験では、大規模時に従来の expiration-based lease と比べ CPU 使用量を大幅に削減しつつ、
同等の fault tolerance 保証を維持したと主張する。(abstract)

## Problem & motivation
- [paper] スケーラブルで resilient な分散 DB は複製に consensus protocol を用い、
  read-only リクエストを quorum 通信なしで捌くために一時的な leaseholder に依存する (abstract)。
- [paper] 大規模(例: 数百万 consensus group)では lease 維持が高コストになる:
  頻繁な lease 更新がシステムリソースを大きく消費し、逆に lease を長期化すると
  障害からの復旧時間が延びる、という二律背反がある (abstract)。
- [paper] この課題に対し、Raft に統合された scalable かつ fault-tolerant な
  leasing protocol「Leader Leases」を提示する (abstract)。

## System model & assumptions
(abstract-only のため未記載)

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

## Limitations
(abstract-only のため未記載)

## Relations
- (2026-07-06 改訂)コーパスには consensus / replication を直接扱う既存ノートが
  既にある: RIOT(2026-sigmod-webber-riot.md、tags: consensus / replication、
  Raft/Paxos 型 SMR に対する順序付けの緩和)と Rosé(2026-cidr-zarkadas-rose.md、
  tags: replication / primary-backup / failover。同ノートは比較対象として
  CockroachDB 等の consensus 複製にも言及している)。
  一方、lease protocol と failure detector(Liveness Fabric のような)を主題とする
  ノートは現時点でコーパスに無く、その点では本ノートが最初のエントリになる。

## Idea seeds
- [question] abstract は「有向エッジ単位の failure detector が strong Raft leadership
  guarantees を提供する」と述べるが (abstract)、lease の安全性(リーダー交代時に stale read を
  出さない保証)がどんな時刻同期・clock 仮定に依るのかは abstract からは読めない。
  本文精読で clock offset 仮定と安全性議論を確認するのが先決。
- [inference] 「group 数に独立な liveness シグナル」でグループ毎の heartbeat/lease 更新を
  排除するという構図 (abstract) は、多数の shard/ログストリームを持つ他のシステム
  (例: クラウド WAL サービスのような shared-storage 系)にも転用できる可能性がある。
  検証第一歩: 本文を入手して Liveness Fabric の適用条件(何をノード単位に集約できるか)を
  洗い出し、BtrLog(クラウド WAL サービス)の既存ノートのアーキテクチャ記述に
  当てはめてギャップを列挙する。
- [question] 「equivalent fault tolerance guarantees」(abstract) の「同等」が何を指すか
  (failover 時間の分布か、安全性の等価性か)は abstract の記述だけでは不明。
  評価節で recovery time がどう測られているかを確認したい。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: 検証パスによる修正(Relations の「consensus/replication を扱うノートはコーパスに無い」という誤った記述を訂正。RIOT・Rosé の既存ノートが該当するため、「lease protocol / failure detector を主題とする最初のノート」に範囲を狭めた)
