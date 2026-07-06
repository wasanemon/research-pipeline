---
title: "Milliscale: Fast Commit on Low-Latency Object Storage"
authors: [Jiatang Zhou, Kaisong Huang, Tianzheng Wang]
venue: "arXiv"
year: 2026
ids: {doi: "", arxiv: "2603.02108", dblp: ""}
urls: {paper: "http://arxiv.org/abs/2603.02108v1", pdf: "https://arxiv.org/pdf/2603.02108v1", code: "https://github.com/sfu-dis/milliscale"}
status: read
read_date: 2026-07-06
tags: [object-storage, commit-protocol, logging, oltp, s3-express, tail-latency, decentralized-logging]
---

読んだ版: arXiv v1 (`2603.02108v1`)。HTML 版と arXiv metadata から著者・タイトル・日付を確認した。

## TL;DR
Milliscale は、S3 Express One Zone のような **low-latency mutable object storage** を WAL の永続先として直接使う memory-optimized OLTP engine である。[paper] 核となるのは、object append 回数を減らす **restricted decentralized logging** と、不要な commit wait を減らす **record-level dependency tracking** で、S3X の素朴実装より tail latency を大きく下げつつ高 throughput を維持する (§1.2, §4, §5)。
特に、write-intensive workload では unoptimized S3X に対して最大 `51.9%` の tail-latency 改善を報告し、99.99 percentile を gp3 に近い水準へ引き下げると主張する (§1.2, §5.3, §5.6)。

## Problem & motivation
- [paper] 近年の low-latency object storage、特に S3 Express One Zone は、single-digit ms latency と mutable object append を提供し、OLTP engine が直接 commit / persist する先として魅力的になってきた (§1.1, §2.2).
- [paper] しかし、単純に decentralized logging を object storage に載せ替えるだけでは、S3 Express One Zone 特有の append cost と dependency delay によって commit latency がなお高い (§1.1, §1.2).
- [paper] 素朴な S3 Express One Zone 利用では、commit latency は gp3 に近いコスト帯へ寄る一方で、依然として高くなりうるため、専用の commit/logging 設計が必要だと位置付ける (§1.1, Fig. 1).

## System model & assumptions
- [paper] 対象は ERMIA を土台にした memory-optimized OLTP engine で、log records を block storage ではなく object storage に flush する設計である (§1.1, §5.1).
- [paper] S3 Express One Zone は single-digit ms latency と mutable append を持つ一方、S3 Standard より availability が低く、DBMS 側で必要なら replication を補う必要がある (§2.2, §4.5).
- [paper] append latency は 128–512KB でほぼ `~8ms`、512KB を超えると線形増加するため、request size の選定が commit latency を左右する (§2.2, Fig. 2).
- [paper] object あたり append 回数は最大 10,000 回で、512KB append なら最大 object size は 4.88GB になる (§2.2).
- [paper] 既存の pipelined group commit / decentralized logging は throughput には有利だが、cross-log dependency と straggler により tail latency が悪化しうる (§2.4, §3).
- [paper] Milliscale は read committed / snapshot isolation / serializability を、ERMIA の既存 concurrency control を継承して提供する (§5.1).
- [inference] 本論文は object storage を primary persistence target に据えることで durability / elasticity を得る代わりに、commit latency を storage-interface-aware な logging で詰める方向の設計である。

## Approach
### Overview
- [paper] Milliscale は active object per log を持ち、log buffer が満杯または timeout に達したら S3 append で flush する (§4.1, Fig. 3).
- [paper] intermediate NVMe SSD には依存せず、low-cost compute instance 上でも deploy できることを意図している (§4.1).

### Restricted decentralized logging
- [paper] per-thread logging は append request 数と straggler を増やし performance を悪化させることがあるため、Milliscale は log を thread group 単位で共有する **restricted decentralized logging (RDL)** を導入する (§4.2).
- [paper] S3 Express One Zone では 512KB と 1MB append の latency が近いため、1MB log buffer を 2 threads で共有すれば、per-thread 512KB logging と近い commit latency を保ちつつ append request 数を減らせる (§2.2, §4.2).
- [paper] TPC-C 上の tradeoff から、sharing ratio `2:1` と `1MB` log buffer が high throughput と low latency の両立点として採用される (§4.2, Fig. 4).

### Record-level dependency tracking
- [paper] Milliscale は record-level dependency tracking を用いて、commit timestamp ベースで fine-grained に dependency を追跡し、false positive dependency を減らす (§1.2, §4).
- [paper] これにより、modern decentralized logging 上で不要な dependency-induced delays を抑える (§1.2, §3, §4).
- [paper] commit timestamp は多くの CC protocol が既に持つため、tracking 自体は lightweight だと述べる (§1.2).

### Design principles
- [paper] 設計原理は、(1) object operations を frugal にすること、(2) dependency-induced delay を短く保つこと、の2つに集約される (§3).
- [paper] RDL は前者を、record-level tracking は後者を主に担う (§3, §4).

## Evaluation
- Setup [paper]: 32-vCPU の Amazon EC2 `c6in.8xlarge` と S3 Express One Zone を使い、YCSB microbenchmarks と end-to-end TPC-C で評価する (§1.2, §5.1).
- [paper] S3 Express One Zone の append latency は 128–512KB で `~8ms`、2MB では `~22ms`、S3 Standard より `~71%` 低い (§2.2, Fig. 2).
- [paper] YCSB-A tail latency では、Milliscale は S3X に対し uniform / zipfian workload で 99.9 percentile を `62.4% / 51.8%`、99.99 percentile を `56.2% / 51.6%` 改善する (§5.3, Fig. 11).
- [paper] block storage への適用でも、Milliscale の techniques は gp3 / io2 の average latency を 16 threads で `26.8%` / `32.8%`、99.99 percentile latency を `42.2%` / `41.6%` 改善する (§5.5).
- [paper] TPC-C では、RDL の 2:1 sharing ratio により S3 append requests/sec を `~50%` 削減する (§5.6, Fig. 16).
- [paper] 同 TPC-C では、Milliscale の average latency は 16 threads で S3X より `3.8%` 高く、gp3 より `23%` 高いが、99.9 / 99.99 percentile では S3X より明確に低く、gp3 に近い tail latency を示す (§5.6, Fig. 17, Fig. 18).
- [paper] 論文冒頭の summary では、representative benchmarks 全体で baselines に対し最大 `51.9%` の tail-latency 改善を主張する (§1.2).
- [inference] average latency だけ見ると gp3 に完全勝利しているわけではないが、elasticity / consistency / durability の利点を維持したまま tail を圧縮するのが本当の売りである。
- [inference] S3 Express One Zone の素の tail spike を software-level logging redesign でかなり相殺している点が本論文の重要点で、storage backend の特性と log layout を強く co-design している。

## Limitations
- Stated [paper]: S3 Express One Zone は S3 Standard より low latency の代わりに高 availability を犠牲にしており、同等の可用性が必要なら DBMS が明示的に replication を行う必要がある (§2.2, §4.5).
- Stated [paper]: log buffer size は current S3 Express One Zone の latency characteristics に基づき決めており、runtime autotuning は将来課題である (§4.5).
- Inferred [inference]: object append latency がすでに ms オーダなので、NVMe SSD 向け commit protocol のような sub-ms commit をそのまま移植するだけでは効かず、request aggregation と dependency pruning の両立が必須になる。
- Inferred [inference]: 99 percentile ではなお gp3 / io2 より不利な場面があるため、「block storage を全面的に置き換える」より、「durability / elasticity を優先する workload で十分に competitive にする」設計として読むのが妥当である。

## Relations
- [[2025-pacmmod-nguyen-autonomous-commit.md]] — autonomous commit は local NVMe SSD 上で small parallel durable writes を活かす設計だが、Milliscale は object storage の ms-scale append 特性に合わせて request count と dependency delay を詰める。どちらも logging を hardware / backend aware に再設計する点で近い。
- [[2026-pvldb-kuschewski-btrlog.md]] — BtrLog は remote log service を用いて 1 RTT durable append を狙うのに対し、Milliscale は object storage を直接 persistent home に据える。remote durability の設計空間における別の極として読める。

## Idea seeds
- [inference] Milliscale と BtrLog / autonomous commit を並べると、「durability medium が NVMe / object storage / remote log service のどれか」で、最適な log-buffer sizing・dependency tracking・replication strategy がどう変わるかという比較軸が見える。commit path の媒体依存性を整理する survey 的まとめができそうである。
- [question] S3 Express One Zone の latency profile が変わったとき、固定 1MB・2:1 sharing の最適性はどこまで保たれるか。runtime autotuning を導入すると throughput / tail latency / request cost の三者トレードオフがどう動くかは未解明に見える。
- [inference] object storage を persistent home にしつつ tail latency を詰める発想は、larger-than-memory DB や disaggregated commit path にも広げられる。次の一歩は、read path や recovery path でも同じ設計哲学が通用するかを見ることだろう。

## Changelog
- 2026-07-06: created (status: read)
