---
title: "RIOT: Replicated Independently-Ordered Transactions"
authors: [Jim Webber, Georgios Theodorakis, Hugo Firth, Natacha Crooks]
venue: "SIGMOD Companion"
year: 2026
ids: {doi: "10.1145/3788853.3803094", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3788853.3803094", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [consensus, replication, distributed-transactions, graph-database]
---

> **ソース注記**: 本ノートは abstract のみに基づく。abstract は OpenAlex API
> (https://api.openalex.org/works/doi:10.1145/3788853.3803094) の
> abstract_inverted_index から復元したもの。dl.acm.org の PDF は自動取得に対して
> HTTP 403 を返した。本文未読のため、以下の各節は abstract が支持する範囲に限定する。

## TL;DR
[paper] Raft / Paxos 型コンセンサスは単一リーダーが全順序ログを強制することで SMR
(state machine replication)を実装するが、その逐次性がスケーラビリティのボトルネックに
なる、というのが出発点 (abstract)。RIOT は中央集権的リーダーとログ複製を廃し、エントリの
DAG(有向非巡回グラフ)上の分散協調に置き換えた「一般化コンセンサスプロトコル」で、
全サーバが論理的に同一の DAG を維持し、競合下では順序を強制しつつ可換な操作は並行実行を
許す (abstract)。concurrency control やトランザクションモデルに仮定を置かず、DAG エントリを
トランザクションのプレースホルダとして扱う replicated state machine 抽象を提供し、
single-phase / two-phase の両変種を持つ (abstract)。Neo4j に統合して同社の本番 Raft 実装と
比較し、common workloads で最大 2.5× のスループットと 2.3× 低いテールレイテンシを、
一貫性保証を維持したまま達成したと主張 (abstract)。

## Problem & motivation
- [paper] Raft / Paxos のような単一リーダー + 全順序ログの SMR は正しさの議論を単純化する
  一方、逐次的ボトルネックを導入しスケーラビリティを制限する (abstract)。
- [paper] 動機は著者らの分散グラフデータベースに関する研究であり、シャードを跨ぐエッジに
  対して reciprocal consistency を保証する必要がある (abstract)。
- [paper] 特化型トランザクションプロトコルと異なり、RIOT は concurrency control や
  トランザクションモデルについて仮定を置かない。トランザクショナルデータベースと
  きれいに統合できる RSM 抽象を提供し、エントリとその順序制約への atomic agreement を
  保証する (abstract)。
- [question] 「可換な操作は並行実行できる」(abstract) とあるが、可換性を誰が・どう判定
  するのか(アプリケーション宣言か、システムによる推論か)は abstract からは読み取れない。
  本文入手後に要確認。

## System model & assumptions
(abstract-only のため未記載)

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

## Limitations
(abstract-only のため未記載)

## Relations
- 既存ノートの大半はストレージエンジン・HTAP・キャッシュ・テスティング系だが、
  `2026-sigmod-kettaneh-leader-leases.md`(CockroachDB の multi consensus group 向け
  leader lease、tags: consensus / replication)はコンセンサス・レプリケーション層を扱う点で
  本論文と直接関係する。
- [inference] RIOT が単一リーダーそのものを廃するのに対し、leader-leases はリーダー維持
  コストを下げる方向であり、「リーダーのボトルネック」への対照的な 2 アプローチとして
  読み比べられる。
- [inference] distributed transactions / deterministic 系の既存ノート
  (`2026-sigmod-arkhangelskiy-aurora-limitless.md`、`2026-eurosys-lopes-pim-txn.md`)とは、
  「順序付けを合意層でどこまで一般化するか」という軸で対置できる可能性がある。

## Idea seeds
- [question] abstract は「競合下では順序を強制し、可換操作は並行実行」(abstract) と言うが、
  非可換操作が支配的な高競合ワークロードで DAG 維持コストが Raft の逐次ログより高く付く
  逆転点がどこかは不明。本文入手後、評価の workload 構成(「common workloads」(abstract) の
  定義)を確認し、競合率を振ったときの交差点を再実験で探るのが第一歩。
- [inference] 「CC / トランザクションモデルに仮定を置かず、DAG エントリをトランザクション
  プレースホルダとして扱う」(abstract) という層分離が本当に成立するなら、グラフ DB 以外の
  トランザクショナルシステム(例えば決定的実行系)への合意層の差し替え実験が考えられる。
  検証: 本文の RSM 抽象の API と「entries and their ordering constraints への atomic
  agreement」(abstract) の意味論を読み、既存 CC プロトコルが要求する順序保証と突き合わせる。
- [question] single-phase と two-phase の両変種がある (abstract) が、どちらをいつ使うのか
  (レイテンシ vs 何のトレードオフか)は abstract からは不明。本文の変種間比較の有無を確認。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: 検証パスによる修正(Relations の「直接関係する既存ノート無し」は誤り —
  leader-leases ノート(consensus / replication)等が既存のため訂正)
