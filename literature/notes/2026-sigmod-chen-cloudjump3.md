---
title: "CloudJump III: Optimizing Cloud Databases for Tiered Storage"
authors: [Zongzhi Chen, Mo Sha, Feifei Li, Sheng Wang, Baolin Huang, Guoqing Ma, Huaxiong Song, Ke Yu, Xizhe Zhang, Yuan Wang]
venue: "SIGMOD Companion"
year: 2026
ids: {doi: "10.1145/3788853.3803084", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3788853.3803084", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [tiered-storage, cloud-database, buffer-management, disaggregation]
---

<!-- ソース: OpenAlex API レスポンス
     https://api.openalex.org/works/doi:10.1145/3788853.3803084?mailto=miyayu@keio.jp
     (abstract は OpenAlex の abstract_inverted_index から復元。
      dl.acm.org の PDF は自動取得に HTTP 403 のため未読)。 -->

## TL;DR
Alibaba Cloud の CloudJump フレームワーク第3世代。ローカル NVMe SSD /
リモート高性能ブロックストレージ / 低コストオブジェクトストレージという
異種ストレージ階層に対し、ブロック層・ファイルシステム層ではなく DB カーネル内
(buffer manager の eviction / flush という制御点)でページ単位の tiering 配置を
決める engine-integrated 設計を導入する (abstract)。プロダクションの
MySQL 互換サービスに展開済みで、near-local スループット・fast-tier フットプリント
削減・安定した tail latency を達成したと主張する (abstract)。

## Problem & motivation
- [paper] 現代のクラウド DB は local NVMe SSD、remote 高性能 block storage、
  低コスト object storage という異種ストレージ層にまたがり、これが hot/cold
  データ分離の自然な階層を成す (abstract)。
- [paper] 既存の block-level / filesystem-level tiering は DB のセマンティクスへの
  可視性を欠き、動的な OLTP ワークロード下でしばしば最適でない配置
  (suboptimal placement)を招く (abstract)。
- [paper] 先行世代の CloudJump(I/II)は I/O とバージョン管理を最適化しており、
  III はその上に構築される (abstract)。
- [paper] III の位置づけ: compute-storage disaggregation を「page-level,
  engine-integrated な tiering を DB カーネルに統合する」ことで前進させる (abstract)。
- [paper] 設計の骨子(abstract で言及される範囲): eviction-centric かつ
  engine-aware な設計で、buffer manager の制御点(eviction と flush)で配置を決定。
  engine-visible なメタデータで性能とコストをバランスし、階層間のデータフローを
  統一、recovery / snapshot プロトコルと協調して crash-consistent かつ
  zero-downtime な運用を保証する (abstract)。
- [paper] 主張される結果: Alibaba Cloud のプロダクション MySQL 互換サービスに
  展開され、near-local throughput、fast-tier フットプリント削減、安定した
  tail latency を達成。engine-integrated tiering がプロダクション規模で予測可能な
  性能とコスト効率を可能にすると結論 (abstract)。

## System model & assumptions
(abstract-only のため未記載)

- [question] 「eviction と flush を配置決定の制御点にする」とあるが、どの
  engine-visible メタデータ(アクセス頻度? トランザクション文脈? ページ種別?)を
  使うのかは abstract からは不明。full read で最優先に確認する点。
- [question] 3 層(NVMe / block storage / object storage)のどこまでが
  同期パス上にあるのか、object storage 上のページへの読みのパスがどうなるかも
  abstract からは読めない。

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

- [inference] abstract の効果主張(near-local throughput / fast-tier 縮小 /
  安定 tail latency)はいずれも定量値なしの定性表現であり、比較対象
  (block-level tiering? 全量 fast-tier?)も abstract には明示されていない。
  数値・ベースラインは本文確認まで一切引用しない。

## Limitations
(abstract-only のため未記載)

- [inference] 「Deployed in production」型の industrial paper であるため、
  公開ベンチマークでの再現可能性や他エンジンへの一般化可能性は本文でも
  限定的な可能性がある — full read 時に評価の切り分け(production 計測か
  controlled experiment か)を確認する。

## Relations
- [inference] tiered storage を DB/KV 側の知識で制御するという問題設定は
  [[2025-tpctc-gao-distash.md]](FoundationDB の多階層 KV)と同じ土俵に見える。
  本論文はページベースの buffer manager を持つ MySQL 互換エンジン側
  (abstract)、DiStash は KV ストア側というレイヤ差の比較候補。
- [inference] compute-storage disaggregation 文脈という点で
  [[2026-pvldb-zhang-terark-ds.md]](分離ストレージ上の KV 分離)、
  [[2026-pvldb-kuschewski-btrlog.md]](クラウド WAL サービス)と隣接。
  特に abstract が「recovery / snapshot プロトコルとの協調」を掲げている点は
  BtrLog 系のログ/リカバリ設計との相互作用を比較する切り口になり得る。

## Idea seeds
- [question] eviction / flush という buffer manager の既存制御点だけで配置を
  決める設計は、「ページがいったん cold 層に落ちた後の promotion」を誰が
  いつ判断するのかが abstract から見えない。cold 層からの初回アクセスの
  tail latency がどう「安定」しているのかは、full read で確認する価値が高い
  (もし promotion がアクセスパス同期なら、tail の安定性主張と緊張関係にあるはず)。
- [inference] 「engine-integrated tiering vs. block/FS-level tiering」という
  対立軸は、階層をまたぐ配置決定に DB セマンティクスがどれだけ効くかの
  定量化問題として一般化できそう。第一歩の検証: オープンソースの
  MySQL/InnoDB + 疑似 2 層ストレージ(fast/slow デバイス)で、
  FS レベル tiering と buffer-pool 統計を使う簡易 engine-aware 配置を
  同一ワークロードで比較する再現実験。
- [question] recovery / snapshot と tiering の協調で「crash-consistent,
  zero-downtime」を保証すると主張する (abstract) が、階層間移動中クラッシュの
  一貫性はチェックポイント/WAL とどう絡むのか。ここが本文の技術的コアなら、
  当リポジトリの recovery / checkpoint 系キーワードと直結するので deep-read 候補。

## Changelog
- 2026-07-06: created (status: abstract-only)
