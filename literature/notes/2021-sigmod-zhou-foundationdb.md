---
title: "FoundationDB: A Distributed Unbundled Transactional Key Value Store"
authors: [Jingyu Zhou, Meng Xu, Alexander Shraer, Bala Namasivayam, Alex Miller, Evan Tschannen, Steve Atherton, Andrew J. Beamon, Rusty Sears, John Leach, Dave Rosenthal, Xin Dong, Will Wilson, Ben Collins, David Scherer, Alec Grieser, Young Liu, Alvin Moore, Bhaskar Muppana, Xiaoge Su, Vishesh Yadav]
venue: "SIGMOD Conference"
year: 2021
ids: {doi: "10.1145/3448016.3457559", arxiv: "", dblp: "conf/sigmod/ZhouXSNMTABSLRD21"}
urls: {paper: "https://doi.org/10.1145/3448016.3457559", pdf: "https://www.foundationdb.org/files/fdb-paper.pdf", code: "https://github.com/apple/foundationdb"}
status: read
read_date: 2026-07-06
tags: [transactional-kv, strict-serializability, occ, mvcc, unbundled, simulation, recovery]
---

読んだ版: SIGMOD'21 論文 PDF (`https://www.foundationdb.org/files/fdb-paper.pdf`)。
ACM Reference Format から DOI `10.1145/3448016.3457559` と会場 `SIGMOD '21` を確認した。

## TL;DR
FoundationDB は、トランザクション処理系・ログ系・分散ストレージ系を分離した
**unbundled** な分散トランザクショナル KV ストアで、strict serializability を
OCC+MVCC で実現する。[paper] さらに、実装そのものを deterministic simulation で
継続的に検証する点を中核的な差別化要素としている (abstract, §1)。
評価では、読みは StorageServer 直読でスケールし、書きも Proxy / Resolver /
LogServer の追加で水平スケールする構成を示す (Fig. 1, §2.3.2, Fig. 8)。

## Problem & motivation
- [paper] FoundationDB は、NoSQL 的な柔軟性・スケーラビリティと ACID トランザクションを両立する初期のシステム群の1つとして位置付けられている (abstract, §1)。
- [paper] 中心的な設計思想は、transaction processing・logging・storage を分離して、それぞれ独立にスケール可能にすることにある (§1, §2.3.2, §8)。
- [paper] 著者らは、分散 DB の信頼性確保において「モデルではなく実装コードそのもの」を deterministic simulation で検証することを重視している (abstract, §1, §6.2)。

## System model & assumptions
- [paper] FDB は cluster metadata を扱う control plane と、transaction management / logging / storage を担う data plane から成る (§2.3.2, Fig. 1)。
- [paper] data plane の transaction system は stateless な Sequencer / Proxies / Resolvers からなり、log system は LogServers、storage system は StorageServers からなる (§2.3.2, Fig. 1)。
- [paper] 想定ワークロードは read-mostly で、少数キーを読む/書く低競合 OLTP である (§2.3.2)。
- [paper] strict serializability は OCC と MVCC の組み合わせで実現される (§2.3.2, §2.4.2)。
- [paper] OCC の競合履歴は Resolvers が保持し、false positive はあり得るが、MVCC window が短いため実運用では問題化しにくいとしている (§2.4.2)。
- [paper] 論文中で MVCC window は 5 秒に設定され、transaction system と storage servers のメモリ使用量を抑えるための実装上の制約にもなっている (§6.4)。
- [paper] FDB は障害を quorum でマスクするより、障害を積極検出して reconfiguration で回復する設計をとる (§1, §2.3.2)。
- [inference] 低競合前提と 5 秒 MVCC window の組み合わせは、FDB の lock-free OCC がうまく動く範囲を暗に規定している。高競合・長大トランザクション中心の設定は、この論文の得意領域ではなさそうである。

## Approach
- [paper] クライアントはまず Proxy 経由で read version を取得し、その version で StorageServers に直接 read を投げ、commit 時に read/write set を Proxy へ送る (§2.4.1)。
- [paper] Proxy は Sequencer から commit version を取得し、range-partitioned Resolvers に read-write conflict チェックを依頼し、成功した transaction を LogServers に永続化する (§2.4.1)。
- [paper] Sequencer は read version / commit version を与え、Proxy / Resolver / LogServer の recruit も担う singleton role である (§2.3.2, Fig. 1)。
- [paper] strict serializability の鍵は、Sequencer が単調な commit version を配り、Resolvers と LogServers と StorageServers がその順序に従って処理する点にある (§2.4.1, §2.4.2)。
- [paper] logging では Proxy が mutation を対応する StorageServer tag 付きで LogServers に書き、すべての replica LogServers が durable reply を返した時点で commit とみなす (§2.4.3, Fig. 2)。
- [paper] StorageServers は redo log を LogServers から順次 pull し、ログが LogServers 上で durable であることを前提に、データ本体のディスク反映を遅らせて I/O を coalesce できる (§2.4.3)。
- [paper] recovery では Sequencer が old LogServers を停止し、Recovery Version (RV) を決め、それより後ろを切り戻して新しい transaction system を起動する (§2.4.3, Fig. 4)。
- [paper] deterministic simulation は、ネットワーク・ディスク・プロセス障害や recoveries を単一物理プロセス内で再現し、同一実装コードに対して repeatable にテストできる (§1, §6.2)。

## Evaluation
- Setup [paper]: production cluster 1か月計測では、平均 read / write / keys-read はそれぞれ 390.4K / 138.5K / 1.467M ops で、read は多くが range read を含む (Fig. 7)。
- [paper] 同 production cluster では、read latency の平均/99.9p は約 1ms / 19ms、commit latency の平均/99.9p は約 22ms / 281ms だった (Fig. 7b)。
- [paper] 4→24 machines の scalability test では、90/10 read-write workload の operations/s は 593k から 2,779k へ 4.69× 増加した (Fig. 8b)。
- [paper] 24-machine 構成で 90/10 load の operation rate を上げる実験では、100k Ops 未満なら read 約 0.35ms、commit 約 2ms、GRV 約 1ms で安定するが、2m Ops では Resolvers と Proxies が飽和し、commit latency は 368ms まで跳ね上がる (Fig. 9b)。
- [paper] write throughput は T100 で 67→391 MBps (5.84×)、T500 で 73→467 MBps (6.40×) に伸び、read throughput も T100 で 2,946→10,096 MBps、T500 で 5,055→21,830 MBps に伸びる (Fig. 8a)。
- [inference] 著者らは production と synthetic の両面から示しているが、commit latency は read に比べて一桁以上重く、log durability と複数ホップの代償をかなり率直に見せている。
- [inference] 飽和時の commit latency の悪化は顕著で、FDB の価値は「低レイテンシ単体」よりも、厳密な整合性・運用安定性・回復性込みの総合設計にあると読むのが自然である。

## Limitations
- Stated [paper]: OCC は transaction が必ず commit できることを保証しないが、production workload では conflict rate は 1% 未満で問題になっていない (§2.4.2)。
- Stated [paper]: false positive conflicts は起こり得るが、modified keys は MVCC window 内にしか残らず、Resolver key ranges も動的調整される (§2.4.2)。
- Inferred [inference]: Sequencer が単一の順序源である設計は回復や reasoning を単純化する一方、書き込み順序付けの柔軟性は犠牲にしている。後年の leaderless / decentralized 系とは対照的である。
- Inferred [inference]: 5 秒 MVCC window はメモリ抑制には効くが、長時間 transaction や大規模 scan を多用する層が上に乗ると、history 保持との緊張が強まりうる。

## Relations
- [[2025-tpctc-gao-distash.md]] — DiStash は FoundationDB を拡張して複数 stash を単一 transaction 空間に収めるシステムであり、本論文はその基盤そのものに当たる。
- [[2026-pvldb-kuschewski-btrlog.md]] — BtrLog は WAL を外部ログサービス化して single-writer 前提を強く押し出すが、FDB は Sequencer + LogServers を含む transaction/logging architecture 全体を unbundled に分解する古典的基準点として読める。
- [[2024-sosp-luo-lazylog.md]] — LazyLog は shared log の順序付けを遅延させる方向だが、FDB は Sequencer による決定的順序付けを commit path の中心に据えている。

## Idea seeds
- [inference] FDB の deterministic simulation は「実装を直接検証する」点で極めて強い。近年の CXL / disaggregated storage 系でも、性能だけでなく recovery / reconfiguration まで含んだ deterministic fault simulation を持ち込めるかは大きな差別化点になりうる。最初の検証は、公開 artifact を持つ近年論文に対して FDB 型 fault matrix を適用できるか棚卸しすること。
- [question] Sequencer による単一順序付けと、後年の decentralized logging / autonomous commit / shared-log 遅延順序付けとの比較を、「回復時間」「tail latency」「実装検証容易性」の3軸で整理すると何が見えるか。BtrLog や LazyLog を読む際の比較軸として使える。
- [inference] FDB は recovery で redo/undo を critical path から外すことを強く重視している。オブジェクトストレージ前提の最近のログ研究でも、この「commit latency」だけでなく「recovery simplicity」を同時に評価軸に置くと、議論がかなり変わる可能性がある。

## Changelog
- 2026-07-06: created (status: read)
- 2026-07-06: verification pass checked metadata, architecture summary, and headline performance numbers against the SIGMOD PDF; no immediate factual correction identified
