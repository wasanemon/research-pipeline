---
title: "DiStash: A Disaggregated Multi-Stash Transactional Key-Value Store"
authors: [Yiming Gao, Hieu Nguyen, Jun Li, Shahram Ghandeharizadeh]
venue: "TPCTC (LNCS 16261, Springer)"
year: 2025
ids: {doi: "10.1007/978-3-032-18070-4_8", arxiv: "2606.27979", dblp: "conf/tpctc/GaoNLG25"}
urls: {paper: "https://doi.org/10.1007/978-3-032-18070-4_8", pdf: "https://arxiv.org/pdf/2606.27979v1", code: "https://github.com/ebay-USC/DiStash"}
status: read
read_date: 2026-07-06
tags: [disaggregated, kv-store, transactions, storage-hierarchy, caching, foundationdb, mvcc]
---

読んだ版: arXiv v1 (2606.27979v1)。出版版は TPCTC 2025 (LNCS 16261, pp.115–133) で、
改訂版 (Revised Selected Papers) のため本文が異なる可能性あり。

## TL;DR
DRAM/SSD/HDD/NVM といった異種ストレージ(stash)のプール群を、**単一のトランザクション**で
読み書きできる disaggregated KV ストア。FoundationDB を拡張して実装し、プールごとに
複製度と ephemeral/durable を設定できる。stash プールごとに別々のトランザクショナル
ストレージマネージャを使う現行方式が生む「プール間コピーの不整合」を、ストレージマネージャの
一元化で排除する。eBay の本番ナレッジグラフのワークロードで評価した workshop 論文。

## Problem & motivation
- [paper] 異なる stash プールを別々のトランザクショナルストレージマネージャで管理すると、
  race condition によりデータのコピーがプール間で不整合になり得る (§1, abstract)。
- [paper] キャッシュ増強型データストア、フロントエンドキャッシュによる負荷分散、階層型
  ストレージの3用途すべてでこの整合性問題が発生する (§2)。
- [paper] Flashstore [6] は複数 stash での整合性を非自明な問題として future work に先送り
  していた (§2.3, citing §4.6-4.7 of [6])。

## System model & assumptions
- [paper] stash = DRAM / SSD / HDD / NVM 等の記憶媒体。プール単位で管理され、複数データ
  センターに分散し得る (§1, §3)。
- [paper] 各プールは volatile/non-volatile(媒体特性)× ephemeral/durable(運用モード)で
  分類される (Fig. 2)。ephemeral は容量超過時に eviction、durable は ENOSPC 等のエラーを返す (§1)。
- [paper] データはプールごとの key prefix でパーティションされる。プールごとに独立した複製度 (§4)。
- [paper] ログサーバは全プールで1つ (§4)。
- [paper] 故障モデル: 複製度 R のプールで R−1 台の stash 故障まで耐える (§5.2.1)。volatile stash
  の復旧はレプリカから、60秒(調整可)のネットワーク復帰待ちの後に新インスタンスとして再編入 (§4, §5.2.2)。
- [inference] 評価は read-dominated(キャッシュヒット率 ~100%)なワークロードのみ。
  書き込み競合が激しい OLTP 的ワークロードは想定の外にある(§5.1.3 の設定から)。

## Approach
- [paper] 核となる主張は「1つのトランザクション」: 全プールを1つのストレージマネージャ
  (拡張 FoundationDB)が管理し、読み書きが複数プールにまたがっても ACID を保証 (§3, §3.2)。
- [paper] 2つのストレージマネージャ構成では、write-through が2つの独立トランザクションに
  分割され、MVCC の下で並行 read が古い値を読んで DRAM に stale データを書き戻す race が
  発生し isolation/durability に違反する (Fig. 6, Fig. 7, §3.2)。DiStash は重なった場合に
  片方を abort してリトライさせることで直列化する (§3.2)。
- [paper] FoundationDB 拡張の主な変更点 (§4):
  - プールごとに Data Distributor の TeamCollection (DDTC) と Queue (DDQ)。DD は計 2h+1
    プロセス(+実装簡略化のための Shard forwarder, footnote 5)。
  - DRAM ephemeral 用に LRU 置換を実装した新 StorageServer
    (fdbserver/KeyValueStoreCache.actor.cpp)。
  - 設定ファイルでプール定義・prefix・複製度・ephemeral/durable を指定。
- [paper] durable stash には既存の SQLite / RocksDB 実装を利用可能 (§4)。

## Evaluation
- Setup [paper]: マイクロベンチマーク(YCSB、16GB ingest)+ eBay 本番ナレッジグラフの
  トレース駆動評価。グラフ DB 約 2.1TB を 40 SSD に3重複製、クエリ結果 12.6GB。
  1Stash(全部 SSD)vs 2Stash(グラフ=SSD、クエリ結果=DRAM×5)。3データセンター構成、
  第3DC がログサーバ保持 (§5, §5.1.3)。
- [paper] マイクロベンチ: DRAM stash は 850 tx/s(CPU 15%)で安定、SQLite の SSD stash は
  Durability Lag と RateKeeper の制御で 480–900 tx/s に変動 (Fig. 9, §5.1.2)。YCSB 10 スレッド
  で DRAM は 10,000 inserts/s、CPU 100% (§5.1.2, footnote 8)。
- [paper] eBay moderate 負荷: 2Stash が全体レイテンシの 95th を 10.4%、99th を 10% 改善
  (50th はほぼ同等: 2.23ms vs 2.18ms) (Table 1)。
- [paper] 故障時: 欠損レプリカの積極的再構築が残存 stash の CPU を順に飽和させ、処理レートが
  大きく低下する (Fig. 12, §5.2.2)。2Stash はクエリ結果のみ再複製するため復旧スパイクが
  1Stash より短い (Fig. 15 vs Fig. 13, §5.2.3)。
- [inference] 評価に無いもの: 書き込み競合下の abort 率・スループット(§3.2 の abort 機構が
  本題なのに、その代償が定量化されていない)。他システムとの比較ベースラインなし
  (1Stash vs 2Stash という自己比較のみ)。HDD 実験は CloudLab で 0–120 tx/s と不安定
  (footnote 7)ながら詳細分析なし。

## Limitations
- Stated [paper]: 少数 stash × 軽負荷での負荷分散が不均一(Fig. 16 の議論、§7)。FDB の
  負荷分散は moderate/heavy 負荷でのみ有効に働く (§7)。write トランザクションを含む
  包括的ワークロード分析と NVM 向け ephemeral ストレージは future work (§7)。
- Inferred [inference]:
  - 全プール共通の単一ログサーバ (§4) は書き込み集約時のボトルネック候補。実験では
    ログサーバ SSD 使用率 15% (footnote 8) までしか観測されていない。
  - workshop 論文(§7 冒頭で自認)であり、プロトコル自体の新規性は薄い — 貢献は
    「FDB の単一トランザクション空間に異種プールを収容した」工学的統合にある。
- [question] FoundationDB 自体のトランザクション制約(サイズ・時間上限など)が大規模な
  プール間移行にどう影響するか、本文に記載なし。FDB 論文 [37, 38] で要確認。

## Relations
- FoundationDB (Zhou et al., SIGMOD 2021 [37]) の直接拡張 — キューに Mode B で追加検討。
- Flashstore [6]、Orthus (FAST'21 [36]) は階層ストレージの先行例として位置づけ (§2.3, §6)。
- 著者の一人 (S. Ghandeharizadeh) の階層構成プランナ [13, 14] を将来統合予定 (§7)。

## Idea seeds
- [inference] 「ヒエラルキー間の一貫性を単一 CC ドメインで解く」アプローチは、CC の観点では
  最も保守的な設計。プール間の一貫性要求は用途ごとに非対称(キャッシュは stale 許容度がある)
  なので、プールごとに isolation level を変えられる multi-pool CC は自然な拡張候補。
  最初の検証: DiStash(公開コード)上で write-heavy YCSB を流し、cross-pool トランザクションの
  abort 率を測る。
- [question] MVCC の版管理が「同一論理データの物理コピーがプールごとに存在する」状況と
  どう相互作用するか(版はコピーごとか論理キーごとか)、本文からは読み取れなかった。
  コードで確認する価値あり。

## Changelog
- 2026-07-06: created (status: read, arXiv v1 を読解)
