---
title: "Terark-DS: A High-Performance and Storage-Efficient Key-Value Separation Storage Engine on Disaggregated Storage"
authors: [Jianshun Zhang, Xun Deng, Fang Wang, Jiaxin Ou, Yi Wang, Hao Wang, Jianjun Chen, Peng Fang, Dan Feng]
venue: "PVLDB 19(5):822-835"
year: 2026
ids: {doi: "10.14778/3796195.3796198", arxiv: "", dblp: "journals/pvldb/ZhangDWOWWCFF26"}
urls: {paper: "https://www.vldb.org/pvldb/vol19/p822-zhang.pdf", pdf: "literature/pdfs/2026-pvldb-zhang-terark-ds.pdf", code: "https://github.com/SZ-NPE/terark-ds"}
status: read
read_date: 2026-07-06
tags: [kv-separation, lsm-tree, disaggregated-storage, wal, garbage-collection, erasure-coding, replication, bytedance]
---

## TL;DR
compute-storage 分離環境では、①コンパクション+3重複製のネットワーク増幅が NIC を食い潰し、
②リモート WAL が書き込み遅延を増やし、③GC が遅くなって KV 分離の空間増幅が悪化する。
Terark-DS(ByteDance TerarkDB 拡張)は、ファイル種別ごとの**差別化冗長化**
(WAL=クォーラム複製、KeySST=3複製、ValueSST=EC 4:2)、**適応的 WAL 書き込み**
(バッチサイズで直列/並列を切替)、**ネットワーク効率 GC** の3点で、書きスループット
+20.4〜63.9%、総コスト −22.7〜58.6% を達成した産業論文。

## Problem & motivation
- [paper] 分離アーキテクチャで RocksDB の書きスループットは 34.9〜45.5% 低下、WAL 有効時は
  リモート永続化で書き込み遅延 +44.6%。3複製下でコンパクションが NIC 帯域の最大 87.8% を
  消費 (§1, §3.1, Fig. 3)。
- [paper] KV 分離(TerarkDB)は書きを 3.8× 改善するがローカル比 44.9% の差が残り、
  リモートアクセスで GC レイテンシが 2.03× に伸びて空間増幅が 1.51×(ローカル)→
  1.96×(分離)に悪化(RocksDB は両環境で 1.12×)(§1, §3.2, Fig. 4)。
- [paper] 既存の分離向け LSM(Disag-RocksDB、CaaS、MirrorKV)はパラメタ調整・
  コンパクションオフロード・KV 分離統合のいずれかに留まり、ネットワーク起因の
  根本課題が残る (§1)。

## System model & assumptions
- [paper] ByteDance の分離ストレージ(MetaServer 3 + ChunkServer 6、25Gbps NIC、
  star-topology 書き込み)上で動作。ページキャッシュによる WAL 緩衝は分離環境では
  使えず、全 WAL レコードが RPC 永続化される前提 (§3.1.1-§3.1.2, §5.1)。
- [paper] 冗長化の選択肢: N 複製(容量・帯域 N×、低遅延)vs EC M:(N−1)(容量 (M+N−1)/M、
  小 I/O の読み・修復が遅い)(Table 1)。
- [paper] KV 分離の3ファイル種のアクセス特性: WAL=追記のみ・短命・読みは復旧時のみ、
  KeySST=小さく高頻度・レイテンシ敏感(YCSB-A で ValueSST より 46.8% 高頻度アクセス)、
  ValueSST=大きく低頻度・帯域指向 (§4.2.1)。

## Approach
- [paper] **差別化冗長化** (§4.2): WAL=クォーラム複製(3複製中2で commit、3つ目は非同期、
  リーダーレスで低遅延)、KeySST=3複製(点検索のレイテンシ優先)、ValueSST=EC 4:2
  (容量 1.5×)。QPS/ストレージコスト比のモデルで Mixed R3-EC が All-R3 に対し
  ∀α>0 で優位(α→0 で効率 2×)、All-EC に対しても KV 分離の典型域(α<0.1)で優位
  (実測 K_s=1.3, K_l=1.5)(Eq. 1-5, Table 3, Fig. 7)。
- [paper] **適応的 WAL 書き込み** (§4.3): group commit のバッチを大型化(〜512KB)し、
  大きい write group はセグメント分割して sub-WAL(親 WAL 番号+セグメント ID の別ファイル)
  へ並列書き込み(分離ストレージの single-writer 制約を回避)。セグメント閾値 16KB、
  <64KB は直列。親 WAL がセグメントマッピング表(GroupID/SegID/Offset/Length)を保持し、
  復旧も並列リプレイ。非同期 WAL 運用向けには 1MB ログバッファ。
- [paper] **ネットワーク効率 GC** (§4.4): ①On-Demand Value Fetching — vSST 内で鍵と値を
  さらに分離し、GC-Read は鍵のみバッチ取得、有効エントリの値だけ取得。
  ②Batched & Localized GC-Lookup — 計算ノード側の Flat Index Cache(鍵領域とインデックス
  領域を連続メモリに分離配置)でローカル検証、専用ワーカー向けには compaction が更新する
  補助 LSM「Invalid Tree」を1 RPC で照会。③Adaptive Readahead — 有効領域ビットマップから
  16KB 未満の間隙を(結合後有効率 ≥80% なら)結合し、最大 2MB の読み窓に集約。

## Evaluation
- Setup [paper]: 上記 ByteDance 環境。ワークロード: Mixed-8K(小 100-512B と 16KB の 1:1)、
  Fixed-16K、Pareto-1K。100GB ロード + 300GB 更新 + 100GB 読み + 4,000万 SCAN。
  ベースライン: 分離版 RocksDB / BlobDB / TerarkDB(全て同一分離ストレージ上、R3)(§5.1)。
- [paper] Insert: RocksDB 比 2.72〜6.70×、KV 分離系比 +20.4〜63.9%。Update: RocksDB 比
  2.10〜6.02×、KV 分離系比 +21.3〜62.6% (§5.2)。
- [paper] Read: インデックスキャッシュと差別化冗長化により、EC 使用にも関わらず
  +32.1%(Mixed-8K)/ +25.7%(Pareto-1K)(§5.2)。Scan は小値ワークロードで KV 分離系
  一般の劣化傾向あり(追加の退行はなし)(§5.2)。
- [paper] アブレーション: 差別化冗長化で書き +22.7〜32.0%(EC 寄与 12.0〜21.7%)。All-EC は
  小 KV の読みで −12.9〜15.2%。適応 WAL は大値で +6.1〜19.6%(バッチ平均 263KB の
  Fixed-16K で最大)、ログバッファは +29.8%(大値)〜+134%(小値)(Fig. 14-15)。
- [paper] ストレージ実使用量: R3 で RocksDB 比 −30.4〜40.1%、BlobDB/TerarkDB 比
  −51.9〜77.3%(Fig. 16)。総コスト削減は −22.7〜58.6%(abstract)。
- [inference] カバーされないもの: 障害時の挙動(EC 復元中の性能、クォーラム WAL の
  リーダーレス一貫性の詳細検証)、マルチテナント環境での NIC 競合、レイテンシ分布
  (テール)の系統的報告。

## Limitations
- Inferred [inference]:
  - 冗長化モデル (Eq. 1-5) は読みスループット中心で、書き込み経路の差(EC のエンコード
    CPU、star-topology の複製)は「大きく順次だから同等」という仮定に依存 (§4.2.3)。
    小さな flush が頻発する構成では成立しない可能性。
  - Flat Index Cache は「インデックスは小さく全メモリに乗る」前提 (§4.4.2)。
    超大規模テーブルや多インスタンス同居ではこの前提が崩れる。
  - ByteDance 固有のストレージ(クォーラム書き込み API 等)に依存する部分があり、
    S3 的なオブジェクトストア上での再現性は別問題。

## Relations
- [[2025-tpctc-gao-distash]] — 同じ「分離ストレージ×KV」でもレイヤが違う(DiStash は
  トランザクション統合、Terark-DS はエンジン内部の I/O 経路)。
- [[2026-pvldb-kuschewski-btrlog]] — WAL のリモート化問題意識が共通。BtrLog は WAL を
  専用サービスに切り出し、Terark-DS は既存分離ストアの上で適応バッチ+並列化で解く。
  「sub-WAL 並列化+単一 writer 制約回避」と BtrLog の「クライアント採番+クォーラム」は
  対照的な設計で、比較検討の価値が高い。
- [[2026-pvldb-lee-how-to-write-to-ssds]] — WA の主戦場がローカル SSD か
  ネットワークかの違いで、「増幅を最上位層(エンジン)が一元管理する」思想は共通。

## Idea seeds
- [inference] 差別化冗長化の判断(R3 vs EC)は静的なファイル種別ベース。アクセス頻度の
  時間変動(ホット vSST)に応じた動的な冗長化切替は未探索に見える — ArceKV 的な
  コストモデル駆動の動的決定と組み合わせられそう。検証: vSST 単位のアクセス統計で
  R3⇄EC を移行するシミュレーション。
- [question] クォーラム WAL(2/3 commit + 非同期第3複製)の一貫性・回復の正確な保証は
  何か。本文は「強一貫性を保つ」と主張するが (§4.2.2)、フェイルオーバ時のテイル確定
  手順が書かれていない — BtrLog §4.2 のような明示的プロトコルがあるか、コードで確認。

## Changelog
- 2026-07-06: created (status: read, PVLDB 公式 PDF を読解)
- 2026-07-06: 検証パスによる修正(セクションアンカー2件を訂正: GC レイテンシ 2.03× の出典は §1、star-topology 書き込みの記述は §3.1.1。数値・主張自体は全件ソースと一致)
