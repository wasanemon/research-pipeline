---
title: "BtrLog: Low-Latency Logging for Cloud Database Systems"
authors: [Maximilian Kuschewski, Lam-Duy Nguyen, Matthias Jasny, Tobias Ziegler, Viktor Leis, Muhammad El-Hindi]
venue: "PVLDB 19(10):2894-2907"
year: 2026
ids: {doi: "10.14778/3828612.3828640", arxiv: "2606.27051", dblp: ""}
urls: {paper: "http://arxiv.org/abs/2606.27051v2", pdf: "https://arxiv.org/pdf/2606.27051v2", code: "https://github.com/maxi-k/btrlog"}
status: read
read_date: 2026-07-06
tags: [wal, logging, cloud, durability, quorum-replication, object-storage, single-writer]
---

読んだ版: arXiv v2 (2606.27051v2)。PDF 冒頭の PVLDB Reference Format で
PVLDB 19(10):2894-2907, 2026 / doi:10.14778/3828612.3828640 と確認 (p.1)。
DBLP には 2026-07-06 時点で未収載(収載後に BibTeX を差し替える)。

## TL;DR
クラウド DB の WAL をリモート化せざるを得ない問題に対し、「single-writer な WAL には
専用シーケンサが不要」という観察に基づき、クライアント主導のクォーラム複製で
**1ネットワーク往復の durable append** を実現する再利用可能なログサービス。ログノードは
NVMe SSD にステージングし、満杯セグメントを非同期に S3 へ退避してコストを下げる。
EBS io2 比で append レイテンシ最大4×改善、LeanStore 統合で YCSB-A スループット 1.25×。

## Problem & motivation
- [paper] クラウドではインスタンスローカルストレージが ephemeral なので WAL はリモート必須 (§1)。
- [paper] EBS(io2 でも)はローカル SSD 比で高レイテンシ・高コスト、S3 は append 単価と
  レイテンシで OLTP に不適 (§1, Table 1)。
- [paper] 業界の専用ログ基盤(Socrates XLOG、TaurusDB PLog、Neon Safekeeper、AWS 内部
  "Journal")はプロプライエタリでエンジンに密結合、再利用不能。設計空間の体系的理解も
  文献に無い (§1)。BookKeeper はクラウド以前の設計で低遅延NW/オブジェクトストレージを
  活かせない (§1-2)。

## System model & assumptions
- [paper] **single-writer 前提**: Aurora/HyperScale/PolarDB/AlloyDB の primary、Spanner の
  Paxos グループリーダー等、ログストリームには常に単一ライターが居る、が根拠 (§2.1)。
  並列ロギング(per-thread ログ)は複数の BtrLog ログを使えばよい (§3.2)。
- [paper] 故障モデル: non-Byzantine crash-stop + 非同期ネットワーク(メッセージ喪失・
  順序逆転・重複・分断を許容)。オブジェクトストレージとメタデータストアは信頼できる
  ものとして扱う(S3 の 99.99% avail / 11-nines durability を根拠に)(§4)。
- [paper] ハードウェア前提: AZ 内 RTT 約 100µs、NVMe SSD 書き込み約 30-35µs、
  クロス AZ 約 500µs (§3.3, §5, §6.1, §6.3。30µs は §5、35µs は §6.1)。
- [inference] メタデータストアを S3 の conditional write で済ませる設計 (§3.1) は、
  failover 頻度が低いことを暗黙に仮定している(CAS のレイテンシは failover 時のみ許容)。

## Approach
- [paper] 構成4要素: クライアントライブラリ / ログノード群(ステージング層)/
  オブジェクトストレージ(アーカイブ)/ メタデータストア (§3.1, Fig. 2)。
- [paper] append パス: クライアントが LSN を自分で採番し(シーケンサ排除)、全ログノードへ
  並列送信。各ノードはメモリ内セグメントに追記+ローカル NVMe SSD に out-of-place 書き込み
  +fsync 後に ack。クォーラム Qw(例 2/3)で commit。in-flight が複数あっても ack は
  LSN 順に返して ARIES 互換を保つ (§3.1)。
- [paper] セグメント(例 16MB)は満杯時に非同期で S3 へ。prefix sum で全ノードの
  セグメントをバイト単位で同一にし、決定的オブジェクト名+条件付き PUT (If-None-Match)
  でフラッシュを冪等化、PUT 重複コストを回避 (§1, §4.1)。
- [paper] failover: 単調増加の write token (wtoken) をメタデータ CAS で取得し、クォーラムに
  install して旧ライターをフェンシング。テイル修復は「read クォーラム中の≥1ノードに存在する
  連続 LSN をすべて採用」(クォーラムが不在を確認した LSN のみ未コミットと断定できる)。
  wtoken をエポックとしてオブジェクトキーに埋め込み、旧エポックの S3 データを読み時に排除
  (§4.2, §4.4, Fig. 4。エポック機構は §4.4 "Handling duplicate data")。
- [paper] ノード故障: ピア間ハートビートで検出し、再複製の代わりに S3 へのスナップショット
  フラッシュで対応(N−Qw 故障まではフラッシュ不要、フラッシュリーダーを決定的に割当)(§4.3)。
- [paper] 安全性(順序 commit・commit 済みデータ不喪失)は TLA+ でモデル化し model check
  (§4, artifact)。
- [paper] 実装: Rust + 自作 io_uring ランタイム + UDP(クォーラムプロトコルが TCP の保証を
  不要にする)、thread-per-core 対称ネットワーキング(reply_to ポートでログの thread 間移動)、
  LSN ウィンドウ W でパイプライン化と tail 読者向け retention を兼ねる (§5)。
- [paper] マルチ AZ 版は 6 ノード(AZ ごと2)で 4/6 write / 3/6 read クォーラム、AZ+1 故障
  耐性。階層的複製(AZ 内転送は無料・約100µs)でクロス AZ 転送コストを2×削減 (§3.3)。

## Evaluation
- Setup [paper]: AWS eu-central-1、ログノード 3× c6id.metal(ローカル SSD)+クライアント
  c6in.metal、partitioned placement group、Linux 6.14。append サイズ 128B(YCSB/TPC-C/
  pgbench の LSN 書き込みサイズ観測に基づく)。オープンループ(Poisson 到着)(§6, §6.1)。
- [paper] ベストケース median 70µs / p99 79µs(35,500 appends/s 時)。500k appends/s で
  median 111µs。SSD IOPS 限界の約 1M appends/s で median 188µs (§6.1)。
- [paper] EBS io2: ベスト median 318µs、1M appends/s で median 503µs / p99 651µs。
  BookKeeper: 240k appends/s 以上にスケールせず、ベスト median 262µs@6.8k/s (§6.1, Fig. 6)。
- [paper] ブロックストレージの対 network+SSD レイテンシ倍率: AWS 4.1× / GCP 6.4× /
  Azure 2.6×(全ハイパースケーラで WAL append に不向き)(§6.1)。
- [paper] ノード kill(400k/s 負荷): median 95→115µs (+21%)、p99 192→221µs (+15%)。
  クォーラム待ち(2/3)は全ノード待ち(3/3)比で median 約30µs・p99 約50µs 改善@500k/s
  (Fig. 7, Fig. 8)。
- [paper] LeanStore(autonomous commit, per-worker ログ)統合の YCSB-A: BookKeeper
  バックエンド比 2×、EBS gp3 比 3×、EBS io2 比 1.25× (Fig. 9, §6.4)。
- [paper] コスト: single-AZ BtrLog $0.00125/1M appends vs EBS io2 $0.0036/1M(256k IOPS
  プロビジョニング $9,651.20/月、フル稼働仮定)。S3 PUT は 16MB バッチで ~$3×10⁻¹⁰/append (§6.5)。
- [inference] 評価でカバーされないもの: TPC-C 等の書き込み混在トランザクションの
  end-to-end(YCSB-A のみ)、failover の実測レイテンシ(プロトタイプは failure-free パスのみ
  実装のため)、マルチテナント干渉(2,186 並行ログの実験はあるが tenant 間分離の評価なし)。

## Limitations
- Stated [paper]:
  - プロトタイプは「レイテンシクリティカルな failure-free append パス」のみ実装。故障系は
    TLA+ モデルのみ (§5 Implementation overview)。**実測の故障実験はノード kill のみ (Fig. 7)**。
  - ノードの自動再配備・クラスタリサイズは未対応(上位の監視コンポーネント前提、future work)(§4.3)。
  - ログ数はメインメモリで制約(平均 32MiB/ログ、2,186 ログで 71GiB)。低頻度ログの
    SSD/S3 退避は production 実装の課題 (§6.1)。
- Inferred [inference]:
  - コスト比較 (§6.5, Fig. 10) は全システム「フル資源稼働」仮定であり、低負荷時は
    プロビジョニング型(自前ノード)の per-append コストが跳ね上がる。マルチテナントで
    埋める前提が成立するかは運用次第。
  - single-writer 前提が崩れるワークロード(マルチマスタ書き込み)は明示的にスコープ外。
    順序付け層を足せば Corfu/Scalog 的にできると主張するが未実装・未評価 (§8)。

## Relations
- [[2026-pvldb-lee-how-to-write-to-ssds]] — 同グループ(Leis 研)。BtrLog のログノードの
  out-of-place SSD 書き込み [51] として引用 (§3.1)。
- FoundationDB [83] は専用ログコンポーネントを持つ例として引用 → [[2025-tpctc-gao-distash]]
  (FDB 拡張)と同じ基盤系譜。
- 競合/隣接: LazyLog (SOSP'24)・SpecLog は LSN 遅延束縛で ARIES 非互換 (§2.2, §7)。
  Milliscale (arXiv 2603.02108) は S3 Express で multi-ms、BtrLog は multi-µs 狙い (§7)。
- LeanStore + autonomous commit (Nguyen et al. 2025 [64]) が end-to-end 評価の土台 (§6.4)。

## Idea seeds
- [inference] 「クォーラムが不在を確認した LSN のみ未コミット」というテイル修復規則 (§4.2) は
  commit 済みかの判定を保守側に倒すため、failover 後に「アプリには失敗と報告されたが
  ログには残る」append が生じ得る(dedup は読み時)。この曖昧領域のセマンティクスを
  DBMS のリカバリ(特に論理 undo)と突き合わせる分析は論文に無い → 検証: 故障注入で
  failover 前後の commit 判定の食い違いを数える実験。
- [question] LSN ウィンドウ W (§5) は commit レイテンシと follower 読者の取りこぼしの
  トレードオフを生むはず。W の感度分析が本文に見当たらない — artifact で確認する価値。
- [inference] WAL を外部サービス化すると group commit / commit 順序の工学が
  クライアント側ライブラリに移る。ローカル NVMe 前提の commit プロトコル研究
  (autonomous commit 等)がリモートログでどう変質するかは開いた問題に見える。

## Changelog
- 2026-07-06: created (status: read, arXiv v2 を読解)
- 2026-07-06: 検証パスによる修正(アンカー精密化2件: wtoken エポック機構の出典に §4.4 を追記、SSD 書き込み 35µs の出典に §6.1 を追記。数値・主張の誤りは検出されず)
