---
title: "ArceKV: Towards Workload-driven LSM-compactions for Key-Value Store Under Dynamic Workloads"
authors: [Junfeng Liu, Haoxuan Xie, Siqiang Luo]
venue: "PVLDB 19(5):958-972"
year: 2026
ids: {doi: "10.14778/3796195.3796208", arxiv: "", dblp: "journals/pvldb/LiuXL26"}
urls: {paper: "https://www.vldb.org/pvldb/vol19/p958-liu.pdf", pdf: "literature/pdfs/2026-pvldb-liu-arcekv.pdf", code: "https://github.com/NTU-Siqiang-Group/ArceKV"}
status: read
read_date: 2026-07-06
tags: [lsm-tree, compaction, write-stall, dynamic-workload, rocksdb, key-value-store, cost-model]
---

## TL;DR
動的ワークロード下の LSM では「目標構造への遷移」ではなく「遷移中も含めた継続的最適化」を
すべき、という発想転換。レベル容量・ラン数・ランサイズの構造制約を全廃した ElasticLSM
(不変条件はレベル間タイムスタンプ順序のみ)と、NP-hard な大域最適化をスコアベースで
近似する軽量決定エンジン Arce を RocksDB 上に実装。動的シナリオで約3×高速、
ワークロード変化後 2,000万操作以内に適応。

## Problem & motivation
- [paper] 実ワークロードは1日の中でも大きく変動(Meta の5アプリ分析を引用)(§1)。
- [paper] 既存の workload-aware 手法は静的構成の計算はできても遷移が下手:
  Moose/Wacky は遷移機構なし、Dostoevsky の lazy 適応は収束が遅く更新量依存、
  Ruskey (FLSM) も更新が少ない read-intensive 局面で適応が遅い (§1, Table 1)。
- [paper] Greedy 遷移は書き込みストールで遅延スパイク、Lazy は収束前の性能劣化が長い
  (Fig. 2)。遷移中の性能を最適化対象にしない設計が根本原因 (§2.3)。

## System model & assumptions
- [paper] LSM の必須不変条件を「浅いレベルのタイムスタンプ > 深いレベル」のみに縮約。
  同一レベル内のラン間はタイムスタンプ重複可。コンパクションは下方向のみ (§3.1, Fig. 4)。
- [paper] write stall はコンパクションから分離され、全ラン数 s が閾値 c を超えたときに
  レート k で遅延させる独立ノブ (§3.1)。
- [paper] コストモデルは当初シングル前景スレッド+1バックグラウンドワーカーを仮定し、
  マルチスレッドは Amdahl 則(並列化率 φ=0.5)で補正 (§3.4)。
- [paper] Bloom filter FPR α、ブロック I/O 時間 I_r=12us / I_w=15us は実測プロファイルで
  設定 (§5)。

## Approach
- [paper] **ElasticLSM**: 有効なコンパクション候補は3パターン — ①レベル内の複数ラン統合、
  ②隣接レベルへの統合、③複数レベル(i〜j)一括統合。候補爆発はサイズ昇順の増分列挙で
  枝刈りし、レベル数≤8 の制約下で候補集合を 30us で構築 (§3.1)。
- [paper] **窓ベースコストモデル**: MemTable 1回分の更新数(u=F/E)を1「カウント窓」とし、
  窓内は木状態が安定と見なす。点検索 P(s)=(α(s−1)+1)·I_r、範囲検索 R(s)=s·I_r、
  更新 U(s)=flush I/O+k·1[s>c]。コンパクション(X バイト、y ラン削減)の完了窓 t は
  「前景操作の累積 I/O 時間がコンパクション I/O 時間に達する窓」として推定 (Eq. 1-6, §3.2)。
- [paper] m 手先のコンパクション列で平均コスト (Eq. 7) を最小化する問題は **NP-hard**
  (Lemma 3.2、証明はテクニカルレポート)。
- [paper] **Arce の有効性スコア**: E(s,t,y) = M·(長期利益: y ラン削減が将来の読みに効く,
  Eq. 10) − (短期ペナルティ: 実行中の読み遅延+ストール, Eq. 9)。スコア最大の候補は必ず
  非支配(dominating)候補 —(t, y) 平面の左上フロンティア — になり (Lemma 3.3)、
  「支配的コンパクションの少なくとも一部は最適列に含まれる」ことを拡張版で示す (§3.3)。
- [paper] パラメタ (M, c, k) は格子探索+シミュレーション(Algorithm 1)で選び、状態/
  ワークロードのドリフトが閾値 d=0.1 を超えたときだけ再計算。16 スレッド並列+Eigen の
  SIMD ベクトル化で、バランス負荷なら窓 >200ms に対しシミュレーション <150ms (§3.4, §4)。
- [paper] 実装は RocksDB 上(統計モジュールは 100万操作ごとに (r,u,p) を報告、
  c*/k* は RocksDB write controller へ)(§4, Fig. 7)。

## Evaluation
- Setup [paper]: i9-13900K、128GB(cgroup で 75GiB に制限)、1TB NVMe。ベースライン:
  Leveling / Tiering / 1-Leveling(RocksDB デフォルト)/ LazyLeveling / Moose / Ruskey /
  CAMAL + 産業系(Pebble / WiredTiger / Cassandra)。複合ワークロード I(急変)と
  II(漸変)は各 2.4576億操作 (§5)。
- [paper] 平均スループット: Workload I で 2.92×、II で 2.17×(対 Tiering 正規化)。
  対 1-Leveling(最強ベースライン)では 2.00× / 1.41× (§1, Fig. 9)。
- [paper] 適応速度: ワークロード変化後 2,000万操作以内、大きな遅延スパイクなし (§1)。
  B→D(激烈な書き→読み転換)のみ read 最適化系にわずかに劣る (§5.1)。
- [paper] ElasticLSM の効果: read-intensive 局面では multi-level compaction で Leveling より
  速くラン数を削減、write-intensive 局面では Tiering よりも積極的にコンパクションを遅延
  (Fig. 9)。
- [paper] マルチスレッド(1/4/8/16)で最高スケーラビリティ。産業系比較: Cassandra /
  WiredTiger の 10× 超、Pebble の 3×。YCSB A〜F すべてでトップ(最小値正規化で
  1.89〜5.47×)(Fig. 10, Table 3)。
- [inference] カバーされないもの: 空間増幅の明示的評価(スコアは読み書きコスト中心)、
  複数 column family / 複数 bg ワーカーが標準の実運用構成(Moose フレームワーク制約で
  bg 1 スレッド固定の比較が多い)、削除・TTL を含むワークロード。

## Limitations
- Stated [paper]: Ruskey/CAMAL はマルチスレッド評価から除外(メトリクス収集と同期機構の
  制約)(§5.1)。Moose/CAMAL は静的設計のため平均構成を与えるという評価上の妥協 (§5)。
- Inferred [inference]:
  - スコアの長期項の重み M はシミュレーションで選ぶとはいえ、コストモデル自体が
    I/O 時間の線形モデル+Amdahl 補正であり、SSD の内部状態(WA、GC)には盲目。
    [[2026-pvldb-lee-how-to-write-to-ssds]] の Total WAF 視点と組み合わせる余地が大きい。
  - タイムスタンプ順序保存のため「下方向のみ」の制約があり、ホットデータを浅いレベルに
    引き上げる類の最適化(promotion)は行えない。

## Relations
- ベースライン系譜: Dostoevsky / LazyLeveling (Dayan)、Moose、Ruskey(RL)、CAMAL
  (active learning)。RL/学習ベース (Ruskey/CAMAL) に対しモデルベース+探索で対抗する
  位置づけ。
- キュー内関連: AdCache(EDBT、LSM キャッシュ管理)、FAST の分散 LSM スケジューリング
  (Ren+)、Terark-DS(KV 分離)。LSM クラスタとしてまとめ読み推奨。

## Idea seeds
- [inference] 「構造制約を消して行動空間を広げ、コストモデル+スコアで統治する」構図は
  バッファ管理やチェックポイント間隔にも移植できそう。特に write stall を独立ノブ化した
  点は、トランザクション系の admission control(abort/backoff 制御)との統合先として自然。
  検証: ArceKV の c/k を TP スループット SLA と連動させる小実験。
- [question] NP-hardness の証明(テクニカルレポート)が仮定する行動空間はどの範囲か。
  ①〜③のパターン制限下でも hard なのか、無制限マージで hard なのかで、近似保証の
  設計余地が変わる。
- [inference] 窓ベースの状態安定近似は、コンパクション完了時刻の推定誤差 (Eq. 5) に
  敏感なはず。誤差が大きい環境(共有ストレージ、スロットリングされたクラウドディスク)
  での頑健性は開いた問題。

## Changelog
- 2026-07-06: created (status: read, PVLDB 公式 PDF を読解)
