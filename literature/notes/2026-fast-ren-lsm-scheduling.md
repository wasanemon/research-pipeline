---
title: "Holistic and Automated Task Scheduling for Distributed LSM-tree-based Storage"
authors: [Yuanming Ren, Siyuan Sheng, Zhang Cao, Yongkun Li, Patrick P. C. Lee]
venue: "USENIX FAST '26 (24th USENIX Conference on File and Storage Technologies)"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/fast/RenS00L26"}
urls: {paper: "https://www.usenix.org/conference/fast26/presentation/ren", pdf: "literature/pdfs/2026-fast-ren-lsm-scheduling.pdf", code: "https://github.com/adslabcuhk/hats"}
status: read
read_date: 2026-07-06
tags: [lsm-tree, compaction, task-scheduling, load-balancing, replica-selection, tail-latency, cassandra, distributed-kv, gossip, raft]
---

## TL;DR
分散 LSM-tree KV ストア(Cassandra)で、フォアグラウンド read とバックグラウンド
compaction を「分散層+ストレージ層」横断で co-scheduling するフレームワーク HATS。
①epoch 単位の coarse-grained read 割当(Gossip で集めた全ノード負荷から期待状態を計算)、
②unified score による fine-grained レプリカ選択、③read 負荷比例の compaction レート配分
(replica decoupling で key range 別 LSM-tree 化)、を閉ループで回す。YCSB read-dominant で
C3/DEPART 比 P99 −58.6%/−59.9%、スループット 2.41×/2.90×(abstract, p.2)。

## Problem & motivation
- [paper] 分散 KV ストアのレイテンシ変動の主因の一つはストレージ層のバックグラウンド
  タスク(compaction)の干渉。だが compaction は LSM-tree のレベル横断 lookup を減らす
  ために不可欠で、単純なレート制限や先送りは実用的でない (§1)。
- [paper] 既存の replication ベース負荷分散は分散層のフォアグラウンドタスクの均衡に
  集中し、ストレージ層のバックグラウンドタスクとの相互作用をほぼ扱わない (§1)。
  また、現在の資源使用量は将来のリクエストレイテンシの予測に乏しい(YouTube DC の
  研究 [52] を引用: CPU 負荷が完全均衡でもレイテンシスパイクは起きる)(§1)。
- [paper] **Observation 1**: アクセス頻度の均衡 ≠ read レイテンシの均衡。10 ノード均質
  クラスタ+YCSB-B (Zipf 0.99) で、レプリカ分散によりノード間アクセス頻度差は最大
  18.9% まで縮むが、最悪ノードの平均 read レイテンシは最良ノードの 4.24× (§3.1, Fig. 2)。
- [paper] **Observation 2**: 1 分窓では正規化レイテンシは 0.5×〜2.0× に収まるが、
  1 秒窓では 90.8% の窓が 0.5×〜2.0× の範囲外。小さいタイムスケールでの負荷分散が
  必要 (§3.1, Fig. 3)。
- [paper] **Observation 3**: compaction 有効化から 2 分以内に read スループットが
  26.3 KOPS → 7.3 KOPS に落ちる(Cassandra 内蔵レート制限が効くと 7.1 → 11 KOPS に
  部分回復)(§3.2, Fig. 4)。
- [paper] **Observation 4**: 一方 compaction は長期 read 性能に不可欠: compaction を
  挟んだ後の compaction 無効期間では平均 read スループットが 29.8 → 40.7 KOPS に向上。
  SSTable 数減少による読み効率化のため。ただし両期間ともキャッシュ暖機後に page-cache
  swap でスループットが落ちる(前半 35.9% / 後半 21% 低下)(§3.2, Fig. 4)。

## System model & assumptions
- [paper] 対象は replication を用いる分散 LSM-tree KV ストア。ベースは Cassandra:
  consistent hashing のハッシュリング、ノードごとに key range(議論は 1 ノード 1 連続
  range に単純化、複数 range でも設計は成立と主張)、中央コントローラなしの分散
  マッピング (§2.1)。
- [paper] R-way replication(時計回りに R ノードへ複製)。read/write のコンシステンシ
  レベル(ack に必要なレプリカ数)はユーザ設定。コーディネータ(レプリケーション
  グループ内のランダムなノード)がルーティングし、dynamic snitching で最小負荷レプリカ
  を選ぶ (§2.1)。メンバーシップは Gossip(デフォルト 1 秒間隔)+seed ノード (§2.1, §4.2.1)。
- [paper] ストレージ層: 各ノード WAL → MemTable → SSTable flush → レベル容量超過で
  compaction、という標準 LSM-tree。read は MemTable → キャッシュ → FS キャッシュ →
  下位から上位レベルの SSTable の順 (§2.2)。
- [paper] 対象は **read のレイテンシ変動**。write は in-memory バッファ+シーケンシャル
  書きで比較的安定とし、write パスは Cassandra のまま変更しない(ただし read 変動には
  フォア/バックグラウンド write の影響が入っており、write-intensive でも効果を主張)
  (§3 冒頭, §4.1)。
- [paper] 記法: M ノード、レプリケーション係数 R、K_{i,j} = N_i にハッシュされた key
  range の j 番目レプリカ(N_{i+j} が保持)、L = coarse-grained 均衡化の epoch 長 (§4.1 Setup)。
- [paper] デプロイの前提 2 点: (i) **replica decoupling** [55](レプリカを別 LSM-tree に
  分離。Cassandra なら約 150 行の変更で実装可、write 時間の 0.4% のオーバーヘッド
  [55] 引用)、(ii) **replica selection** [49]。後者は eventual consistency 系
  (Cassandra/Dynamo/ScyllaDB)にも follower read の強整合系(TiKV)にも載ると主張
  (§4.1 Applicability)。
- [paper] スケジューラノード = seed ノード群(実運用 2〜3 台 [2])から Raft で選出した
  リーダ。故障時は再選出。ストレージノード故障時は Cassandra 既存の hinted handoff /
  read repair がそのまま機能し、HATS は内部スケジューリングポリシーのみ変更 (§4.2.1)。
- [paper] タスク(read/write/flush/compaction)の主資源は CPU とディスク I/O と仮定
  (§4.4)。compaction レート制限は「第 2 最下位レベル以上」のみに適用し、最下位レベルの
  compaction は read amplification 抑制に重要なので無制限 (§4.4)。
- [paper] パラメータ既定値: L = 60 秒(Cassandra のデフォルト compaction 間隔に整合)、
  ノードあたり許容 compaction レート 64 MiB/s(Cassandra デフォルト準拠)(§5)。
- [paper] Gossip 追加オーバーヘッドは 8×(M×R+M+1)/(211×M)。R=3, M=100 で 15.2% (§4.2.1)。
- [inference] 「クライアントが期待状態を受け取って確率的ルーティングする」(§4.2.3)
  設計なので、クライアント(ドライバ)側がスケジューリング状態を保持する thick-client
  前提。プロキシ越しの薄いクライアント構成での適用性は本文に議論が見当たらない。

## Approach
閉ループで 3 つの操作を反復する (§4.1, Fig. 5):
- [paper] **Coarse-grained read task assignment (§4.2)**: 各ノードが epoch ごとに
  平均 read レイテンシ T_i(4B)と R 個の key range 別 read 件数(4R B)+単調増加
  バージョン番号を Gossip に埋めて配布。スケジューラノードが epoch 末に現在状態
  C(M×R 行列)をスナップショットし、Algorithm 1 で期待状態 E を計算: ノードごとに
  余裕 ∆_i = L/T_i − ΣC(L/T_i = 処理可能件数の見積り)を求め、高負荷ノード→低負荷
  ノードへ δ = min(|∆_h|, |∆_ℓ|, E) ずつ貪欲に読み負荷を移す。計算量 O(MR²/4)/epoch
  (§4.2.2, Algo. 1)。E は Raft term 番号+epoch 番号付きで Gossip 配布され、クライアント
  は key range のレプリカ N_{i+j} を確率 E_{i,j}/ΣE_{i,j} でコーディネータに選ぶ (§4.2.1, §4.2.3)。
- [paper] **Fine-grained read task coordination (§4.3)**: 最速レプリカ選択は負荷振動と
  テール悪化を招く [49] ため、**unified score** = L/t_{i,j} − Q_{i+j} を使う。t_{i,j} は
  瞬時 read レイテンシ(ネットワーク往復+ストレージ層処理。dynamic snitching の
  EWMA、重み 0.5 で更新。epoch 先頭 R リクエストはラウンドロビンで初期化)、
  Q_{i+j} = 期待状態ベースの当該ノードの総処理予定件数。スコア = 「追加で捌ける read
  件数」であり、コーディネータは最大スコアのレプリカへ再ルーティング。大きい
  タイムスケールではローカルアクセス優位で期待状態に収束し、小さいタイムスケールでは
  well-compacted な LSM-tree を持つレプリカが選ばれやすくなる (§4.3)。
- [paper] **Compaction task scheduling (§4.4)**: ノードごとの許容 compaction レートを
  上限とし、期待状態から key range ごとの read 比率 E_{i,j}/Q_i を計算して、read 負荷の
  高い key range ほど高い compaction レートを比例配分。key range 別 compaction のために
  DEPART [55] の replica decoupling を採用し、各ノードが R 本の LSM-tree(自ノード起源
  K_{i,0} + 前 R−1 ノード起源のレプリカ)を管理、LSM-tree 単位でレート制限。read の
  多い LSM-tree の compaction を優先し、低アクセスのものは先送り (§4.4)。
  LSM-tree の内部構造(索引管理)は保持 (§5)。
- [paper] **Starvation 回避**: read が恒常的に少ない write-heavy key range の compaction
  飢餓を防ぐため、compaction レートに下限(compaction throughput / R)を設け、下限を
  上回るときのみ key-range 別 compaction、下回るときは Cassandra デフォルトの FCFS に
  戻して全 compaction の進行を保証 (§5)。
- [paper] 実装: Java、Cassandra v5.0 + クライアントドライバ v3.0.0 に対して 6K 行の
  変更(コードベース計 1.3M 行)。Raft はプロダクショングレードのライブラリ [48] を統合。
  レート調整は Cassandra のレート制限 API 経由 (§5)。

## Evaluation
- Setup [paper]: 22 台(サーバ 20 + クライアント 2)、10 Gbps、Ubuntu 22.04。既定は
  10 ノード均質クラスタ(quad-core i5-3570 3.4 GHz、16 GiB DRAM、128 GiB SATA SSD)。
  Exp#8 のみ 20 ノード異種構成。ワークロードは YCSB A–F(既定 Zipf θ=0.99、D は
  latest)+ Facebook 生産ワークロードモデル [14](key range 局所性、ホット度分布
  f(x)=ae^bx+ce^dx、Pareto 値サイズ、sine 波 QPS)。100M レコード(24B key / 1,000B
  value)、クライアントスレッド 100、R=3、read CL=1 / write CL=3、50M ops(E のみ 5M)、
  5 回試行の平均+95% CI (§6.1)。
- Baselines [paper]: mLSM(replica decoupling のみ)、C3 [49](+decoupling を追加適用)、
  DEPART [55](セカンダリレプリカを two-layer log 管理)。全て Cassandra v5.0 上に
  再実装してバージョン差を排除 (§6.1)。
- [paper] Exp#1(アブレーション): coarse だけではスループット +3.3〜67.2% だが P99 は
  ほぼ不変(−4.1%)。fine 追加で P99 −8.3%/−24.4%/−40.4%(A/B/C)。compaction
  スケジューリング追加でさらにスループット +32.4%/+5.7%、P99 −49.0%/−9.8%(A/B)。
  手法を足すほど誤差棒も縮む (Fig. 6, §6.2)。
- [paper] Exp#2(YCSB): スループット最大 1.53×/2.47×/2.67×/2.90×/2.04×(A/B/C/D/F)。
  P50/P99/P999 の削減は最大 53.6%/62.2%/88.7%(B,C,D,F)。例外: A の P50 は mLSM 比
  +14.6%(スケジューリングオーバーヘッド)だがスループットは +48.6%。scan 主体の E
  では DEPART が 5.4〜6.0% 上回る(two-layer log が append-only で compaction の
  split/sort を回避するため)(Fig. 7, §6.3)。
- [paper] Exp#3(Facebook 生産: 85% Get/14% Put/1% Seek): HATS 48.8 KOPS vs mLSM 17.1 /
  C3 20.2 / DEPART 21.5(2.85×/2.42×/2.27×)。Get P99 は最大 −83.2%(vs mLSM)/
  −78.9%(vs C3)/−68.3%(vs DEPART)。Put/Seek の P99 は C3 より +22.9%/+11.0% 高いが
  P999 は −31.1%/−71.8% (Fig. 8, §6.3)。
- [paper] Exp#4(クラスタ内均衡): ノード間 read レイテンシの CoV が全ワークロードで
  最小、削減は最大 29.4%/52.0%/72.5%(A/B/C)(Table 1)。
- [paper] Exp#5(最悪ノードの 1 秒窓分布): YCSB-B で 0.5×〜2× 範囲外の点が
  mLSM 91.6% / C3 82.7% / DEPART 93.4% に対し HATS 8.7% (Fig. 9, §6.4)。
- [paper] Exp#6(パス分解, 1 MiB 処理あたり): write パスで WAL −最大 61.9%、compaction
  −最大 81.8%(HATS 39.2 ms vs mLSM 215.0 ms)。read パスでレプリカ選択 −66.5%/−93.5%/
  −80.7%(HATS 50.8 ms vs C3 776.6 ms)、リモート転送率は HATS 0.04% vs mLSM 6.2% /
  C3 84.9% / DEPART 19.3%。ディスク読みも −75.1%/−39.5%/−83.0% (Table 2, §6.4)。
- [paper] Exp#7(資源): CPU 時間 −最大 47.5%、ディスク I/O −81.7%、ネットワーク I/O
  −64.6%。メモリは JVM 管理のため各方式同等 (Fig. 10, §6.4)。
- [paper] Exp#8(20 ノード異種): スループット最大 2.08×/1.87×/2.11×(A/B/C)、P99 は
  A/B で −64.3%/−48.3%。C の P99 は mLSM 同等だが mLSM の P999 は HATS の 4.65× (Fig. 11)。
- [paper] Exp#9–12(感度): read CL 1/2/3 で DEPART 比スループット +42.9%/+29.3%/+24.5%
  (CL が上がるほどレプリカ選択の余地が減り利得は縮小)(Fig. 12)。key 分布 uniform/
  Zipf0.9/0.99 で DEPART 比 +59.7%/+51.2%/+42.9% (Fig. 13)。値サイズ 512〜2048B で
  +20.5〜50.6%(大きい値ほど増幅が効き利得拡大)(Fig. 14)。飽和度(100〜200 スレッド)
  でも P99 最大 −52.8% を維持 (Fig. 15)。
- [paper] epoch 長 L は 5s〜120s で頑健(YCSB-A で最大/最小スループット比 1.025×、
  最大は L=60s = デフォルト compaction 間隔)— ただし詳細結果は紙面の都合で省略 (§6.6)。
- [inference] 評価がカバーしないもの:
  - 最大 20 ノード。M=100 のスケジューラ/Gossip オーバーヘッド(15.2%)は解析値のみで
    実測なし。スケジューラノードの Raft 再選出中・ネットワーク分断時のスケジューリング
    品質も未評価。
  - ハードウェアは quad-core デスクトップ CPU + SATA SSD。NVMe など高速ストレージでは
    CPU/I/O の競合バランスが変わり、compaction 干渉の大きさ自体が違い得る。
  - ノード故障・リカバリ(hinted handoff / read repair)との相互作用は「そのまま機能
    する」と主張されるのみで、故障注入実験はない。
  - ローカル LSM スケジューラ(SILK [10] / ADOC [54] 等)は関連研究で「本研究は
    分散設定のタスク干渉に焦点」とスコープ上区別されるのみ(「互換」と明言されるのは
    内部 LSM 管理技術の側)で、組み合わせ・比較の実験はない (§7)。
  - ホットスポットが key range 間を高速に移動するワークロード(epoch 長 60s より
    速いスキュー変化)の明示的な実験は見当たらない(Facebook モデルの QPS 変動は
    sine 波)。

## Limitations
- Stated [paper]:
  - アーティファクトの Scope として、replica decoupling と replica selection への依存を
    研究プロトタイプの制約として明記 (Appendix A)。
  - レプリカ選択の効果は read コンシステンシレベルとレプリカ数に依存(CL=3 では全
    レプリカを読むため利得が縮小)(§6.6, Exp#9)。
  - write-heavy(YCSB-A)では P50 が mLSM 比 +14.6%(スケジューリングオーバーヘッド)
    (Fig. 7(b), §6.6)。scan 主体(YCSB-E)では DEPART に劣る (Fig. 7(a), §6.3)。
  - 5 回試行は実世界の動的環境に対しては少ないと自認 (§6.1)。
- Inferred [inference]:
  - 期待状態 E は epoch(既定 60 秒)ごとの更新で、期間中のスキュー激変には
    fine-grained 層の t_{i,j}(EWMA)だけで追随することになる。しかし unified score の
    Q 項は古い E に基づくため、epoch 内のホットスポット移動時にはスコアの片側だけが
    現実を反映し、系統的な誤ルーティングが起き得る(この状況の実験は §6 に見当たらない)。
  - compaction レート配分は「read 負荷に比例」という発見的規則で、compaction 1 MiB
    あたりの read amplification 削減効果(レベル構成・SSTable 重なりに依存)はモデル化
    されていない。read が多くても既に well-compacted な range に帯域を割く無駄が原理上
    あり得る。
  - replica decoupling によりノードあたり R 本の LSM-tree を持つ設計は、本論文自身の
    ベースライン解説で「mLSM の複数 LSM-tree は資源競合を生み、DEPART はそれを
    two-layer log で緩和する」(§6.1)とされるトレードオフの上に立つ。write/scan 側の
    コスト(E での劣位)はその帰結に見える。
  - starvation 回避の下限(compaction throughput / R)は静的で、write 偏重度に応じた
    調整の議論はない。

## Relations
- 論文内の直接の系譜 [paper]: DEPART [55](replica decoupling の拡張元・比較対象)、
  C3 [49](replica selection の採用元・比較対象)、Prequal [52](瞬時負荷シグナルの
  動機付け)、Hailstorm/Nova-LSM/Tebis/RubbleDB(専用ハードによる compaction
  オフロード系。HATS は専用ハード不要という差別化)(§7)。
- [[2026-pvldb-liu-arcekv.md]] [inference]: 同じく LSM compaction を扱うが軸が直交:
  ArceKV はノード内の compaction 設計、HATS は「いつ・どの key range に・どれだけの
  レートで」を分散層の read 負荷から決める外側のスケジューラ。ノード内手法とは
  組み合わせ可能なはず(HATS も内部 LSM 管理技術と互換と主張 (§7))。
- [[2026-pvldb-wu-aqd.md]] [inference]: AQD(HTAP のクエリディスパッチ)と HATS の
  fine-grained 層は「瞬時負荷を見てリクエストの行き先を選ぶ」同型問題。HATS の
  unified score(処理容量 − 予定負荷)という定式化は HTAP レプリカ選択にも移植候補。

## Idea seeds
- [inference] **Benefit-aware compaction 配分**: HATS のレート配分は read 負荷比例
  (E_{i,j}/Q_i)のみで、「その compaction がどれだけ read amplification を減らすか」を
  見ていない。key range ごとの SSTable 重なり・レベル状態から限界効用を推定して配分に
  掛け合わせれば、同じ帯域でテールをさらに削れる可能性。検証: 公開プロトタイプ
  (github.com/adslabcuhk/hats)のレート配分部を差し替え、Zipf+ホット度が
  compaction 状態と非相関なワークロードで P99 を比較。
- [question] **期待状態の陳腐化限界**: L=60s の epoch でスキュー変化がどこまで速いと
  破綻するか。論文は L の頑健性(5〜120s、比 1.025×)を静的スキューで示すのみ (§6.6)。
  ホットスポット移動周期を L の 1/10〜10× で振る再現実験で、fine-grained 層(EWMA)
  だけで吸収できる領域と、E の再計算を trigger-based(変化検知駆動)にすべき領域の
  境界を測る価値がある。
- [inference] **read/compaction co-scheduling の他構造への一般化**: 論文自身が B+-tree
  系でも同種の干渉があると述べる (§4.1)。checkpoint/GC/index maintenance を持つ
  分散 DB(HTAP 含む)へ「unified score + バックグラウンド帯域の負荷比例配分」を
  移植できるかは開いた問題。検証の第一歩: 単一ノードでフォアグラウンド read と
  checkpoint の干渉を計測し、read 負荷連動のレート制御で P99 が動くか確認。

## Changelog
- 2026-07-06: created (status: read)
- 2026-07-06: 検証パスによる修正(§7 の SILK/ADOC の位置づけ表現を修正: 論文が「補完的」と述べるのは内部 LSM 管理技術であり、SILK/ADOC 等のローカルスケジューラは分散設定との区別のみのため)
