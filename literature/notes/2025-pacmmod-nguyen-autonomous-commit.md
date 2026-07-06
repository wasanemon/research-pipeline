---
title: "Moving on From Group Commit: Autonomous Commit Enables High Throughput and Low Latency on NVMe SSDs"
authors: [Lam-Duy Nguyen, Adnan Alhomssi, Tobias Ziegler, Viktor Leis]
venue: "Proc. ACM Manag. Data 3(3):191"
year: 2025
ids: {doi: "10.1145/3725328", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3725328", pdf: "https://www.cs.cit.tum.de/fileadmin/w00cfj/dis/papers/latency.pdf", code: "https://github.com/leanstore/leanstore/tree/latency"}
status: read
read_date: 2026-07-06
tags: [commit-protocol, logging, nvme, wal, latency, throughput, decentralized-logging]
---

読んだ版: 公開 PDF (`https://www.cs.cit.tum.de/fileadmin/w00cfj/dis/papers/latency.pdf`)。
ACM Reference Format から DOI `10.1145/3725328`、会場 `Proc. ACM Manag. Data 3(3)`、
Article 191, June 2025 を確認した (p.1)。

## TL;DR
modern NVMe SSD の「小さく・ランダムで・並列な durable write が速い」という性質を前提に、
従来の group commit を捨てて worker ごとに小さな log flush を並列実行する
**autonomous commit** を提案する。[paper] さらに、single-threaded な commit acknowledgment
も並列化し、GSN-based decentralized logging の straggler 問題に barrier transaction で対処する
ことで、high throughput と low commit latency を同時に狙う (§1, §2.2, §5)。
YCSB / TPC-C / TATP では、90p / 99p latency で group-commit 系より大幅に改善しつつ、
throughput も競合を上回るケースが多い (Fig. 9, Fig. 10, Fig. 12, Fig. 13)。

## Problem & motivation
- [paper] 磁気ディスク時代の group commit は throughput 改善には効くが、commit latency を悪化させる (§1).
- [paper] 既存の DBMS / commit protocol は、modern NVMe SSD 上でも high throughput と low-latency durable commit を同時に達成できていない (Fig. 1, §1).
- [paper] 著者らの分析では、high-throughput decentralized logging with group commit における主要ボトルネックは SSD への flush そのものだけではなく、queuing と commit acknowledgment にもある (§2.3, Fig. 4).
- [paper] したがって問題は「group commit をよりうまくする」ことではなく、NVMe SSD の特性に合わせて commit path 自体を作り直すことだと位置付ける (§1, §2.2).

## System model & assumptions
- [paper] enterprise NVMe SSD は 4KB random write で約 11µs の低レイテンシを持ち、16 threads 程度の concurrent random writes でもその低レイテンシをほぼ維持できる (Fig. 3a-b, §2.2).
- [paper] O_DIRECT を用いる高性能 DBMS では write は storage block size (典型的には 4KB) に align する必要がある (§3).
- [paper] 対象は decentralized logging を用いる in-memory / out-of-memory DBMS で、worker ごとの log buffer と dependency tracking を前提にしている (§2.3, §5).
- [paper] 依存関係追跡には precise causality-tracking と total ordering の両系統があるが、後者の GSN-based 方式には straggler 問題がある (§5.1, Fig. 8).
- [paper] 既存方式の単一 background thread による commit acknowledgment は、高 throughput 時に commit latency を押し上げる (§2.3, Fig. 4).
- [inference] 本論文の中心は単機 NVMe 上の durable commit path であり、replicated logging や remote log service のような分散耐障害構成は設計対象外である。

## Approach
- [paper] autonomous commit の第一原則は、large batched flush ではなく **all workers should flush logs** であり、worker が local log buffer を小さな単位で durable write する (§3).
- [paper] ただし transaction 単位の極小 flush は I/O amplification を招くため、worker local log buffer がしきい値に達したら flush する **log flush unit** を導入する (§3).
- [paper] modern NVMe SSD では small random parallel writes が速いため、従来の group commit のように single thread で大きな batch を流す必要はない (§1, §2.2, §3).
- [paper] second stage では commit acknowledgment を parallelize し、transaction の commit state を検査する手続きを単一 thread から解放する (§1, Fig. 5).
- [paper] batch が十分に埋まらないときの excessive delay を抑えるため、著者らは **log stealing** を導入する (§4).
- [paper] inter-die communication は高価なので、log stealing は CPU core pinning と組み合わせ、同一 die 内に制限する (§4, p.10 footnote 2).
- [paper] GSN-based decentralized logging の straggler 問題に対しては **barrier transaction** を使い、遅れている worker の min GSN を押し上げて dependent transaction の commit を前進させる (§5.1, Fig. 8).
- [paper] acknowledgment grouping も導入し、複数 transaction object をまとめて dequeue / inspect することで cache coherence traffic も減らす (§4, §6.6).

## Evaluation
- Setup [paper]: close-loop と open-loop の両方で、YCSB / TATP / TPC-C を用いて throughput と latency を比較する (Fig. 9, Fig. 10).
- [paper] YCSB では `Our4KB` の 90p latency は `175µs` で、best competitor の `FlushQueue` より `12431×` 低い (Fig. 9a, §6.2).
- [paper] 同 YCSB では、最も throughput が低い autonomous variant である `Our4KB` でも、best competitor `TradQueue` より `26.1%` 高 throughput を示す (Fig. 9a, §6.2).
- [paper] TPC-C では `Our4KB` と `Our16KB` の 90p latency は、それぞれ best competitor `FlushQueue` より `283×`、`265×` 低い (Fig. 9c, §6.2).
- [paper] open-loop 実験では autonomous commit の 99p latency は通常、YCSB で `100µs` 未満、TPC-C で `1ms` 未満に収まる (Fig. 10, §6.3).
- [paper] scalability 実験では `Our16KB` が 192 worker threads で `11 million transactions/s` に達する (Fig. 12, §6.4).
- [paper] log flush unit の比較では `4KB` が lowest latency を与える一方、`16KB` は throughput / latency の all-around solution とされる (Fig. 13, §6.5).
- [paper] acknowledgment group size は 2 または 4 が広い workload で低レイテンシに有効で、8 は throughput を 10% 改善する場合がある (§6.6, Fig. 14).
- [inference] 著者らの一番強いメッセージは「SSD はもう遅くないので、commit path の律速は I/O バッチングの古い常識そのもの」という点にある。
- [inference] 特に Fig. 4 で latency の主因が queuing と acknowledgment に移っていることは、ストレージデバイス改善後の DBMS ボトルネックの重心移動を示していて興味深い。

## Limitations
- Stated [paper]: `Our4KB` は lowest latency だが、TPC-C のような複雑な workload では `Our16KB` の方が throughput に優れることがある (Fig. 9c, §6.2, §6.5).
- Stated [paper]: smaller log flush unit は latency に有利だが、flush / acknowledgment の頻度が増え、overhead を償却しづらくなる (§6.2, §6.5).
- Inferred [inference]: 評価は単機 NVMe SSD と LeanStore 系の commit path に集中しており、replication, network failures, remote durability を含む cloud-native logging への外挿はそのままではできない。
- Inferred [inference]: barrier transaction による straggler 緩和は GSN-based decentralized logging の弱点を補うが、依存関係の意味論自体を単純化するわけではない。高 skew / heterogeneous workloads での tail behavior はなお設計の敏感点に見える。

## Relations
- [[2026-pvldb-kuschewski-btrlog.md]] — BtrLog は remote WAL service を前提に 1 RTT durable append を狙うが、本論文は単機 NVMe 上で commit protocol 自体を組み替える。どちらも「storage latency が十分低いなら古い commit engineering を捨てられる」という問題意識を共有する。
- [[2021-sigmod-zhou-foundationdb.md]] — FoundationDB は Sequencer / Proxy / LogServer を含む分散 transaction architecture を示す古典的基準点であり、本論文はよりローカルな durable commit critical path の最適化に集中している。

## Idea seeds
- [inference] autonomous commit の考え方を remote durable medium (たとえば low-latency object store や remote log service) に持ち込むと、worker-local flush の並列性と network tail のどちらが支配的になるかを切り分けられる。BtrLog / Milliscale との比較軸として有効そうである。
- [question] barrier transaction は straggler 解消に効くが、read-mostly ではなく write-heavy / skewed dependency graph でどこまで tail を抑えられるか。混合 workload で barrier 発火頻度と tail latency を相関させる実験を見たい。
- [inference] commit acknowledgment の並列化が throughput も改善するという結果は、近年の DBMS で「I/O 最適化」と思われがちな話が実は CPU scheduling / queue design の問題に転化していることを示す。NUMA-aware な commit acknowledgment 設計はまだ掘りがいがある。

## Changelog
- 2026-07-06: created (status: read)
