---
title: "AdCache: Adaptive Cache Management with Admission Control for LSM-tree Key-Value Stores"
authors: [Jiarui Ye, Junfeng Liu, Siqiang Luo]
venue: "EDBT '26 (OpenProceedings, pp.131-143, Tampere)"
year: 2026
ids: {doi: "10.48786/edbt.2026.12", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.48786/edbt.2026.12", pdf: "literature/pdfs/2026-edbt-ye-adcache.pdf", code: "https://github.com/qingshanlanshan/AdCache-LSM"}
status: read
read_date: 2026-07-06
tags: [lsm-tree, caching, block-cache, range-cache, admission-control, reinforcement-learning, rocksdb, range-query, key-value-store]
---

## TL;DR
LSM-KVS のキャッシュを block cache(物理ブロック)と range cache(クエリ結果)の
ハイブリッドにし、actor-critic RL エージェントが①両者のメモリ分割比、②point lookup 用の
頻度ベース admission 閾値、③scan 用の部分キャッシュパラメータ (𝑎, 𝑏) をオンラインで調整する。
報酬は「キャッシュ無し時の推定ブロック I/O 数」に対する削減率(推定ヒット率)。RocksDB 実装で
default block cache 比ヒット率最大 +14%・SST 読み最大 −25%、動的ワークロードで平均
スループット +12%。

## Problem & motivation
- [paper] LSM-KVS は point lookup に加え range scan を頻繁に処理し、compaction が
  データレイアウトを周期的に書き換えるため、「大フットプリントのクエリ」と「構造変化」という
  従来の point アクセス中心キャッシュに無い2つの課題を持つ (§1, p.1)。
- [paper] block-based caching(RocksDB Block Cache 等)は point lookup に有効だが、
  compaction で file+offset で識別されるキャッシュブロックが無効化されヒット率が急落する。
  Leaper [47] は compaction 後 prefetch で緩和するが物理ブロック粒度の限界は残る (§1 p.1, §2.2)。
- [paper] result-based caching(Range Cache [43]: skip list にクエリ結果を論理キー順で保持)は
  compaction 耐性があり scan-heavy に向くが、更新が少ない read 中心ワークロードでは
  ディスク上の block 構造とのミスマッチにより block cache よりヒット率が低い (§1 p.1, §2.2, Fig. 3)。
- [paper] どちらの戦略も全ワークロードで一貫して勝てず(Fig. 1)、両者を静的にメモリ分割する
  naive な組合せは動的ワークロードに適応できない。さらに静的設計は低頻度・大サイズの
  「ノイズ」アクセス(特に長い range scan)を選別できず、admission が価値あるエントリを
  追い出す (§1, p.1-2)。
- [paper] リサーチクエスチョン: LSM-tree のキャッシュに compaction-resistance /
  noise-resistance / workload-adaptivity を同時に持たせるには? (§1, p.2)。

## System model & assumptions
- [paper] 対象は RocksDB 型の leveled LSM: Level-1 以降は各レベル1 sorted run、Level-0 は
  複数の重複 run を許容 (§2.1, Fig. 2)。実装は RocksDB 上 (§5.1)。
- [paper] I/O コストモデルは「1-leveling 構造」を仮定: run 数の推定 𝑟 = 𝐿−1 + 𝑟₀ᵐᵃˣ/2
  (𝐿 = レベル数、𝑟₀ᵐᵃˣ = Level-0 の最大 run 数 = write stall トリガで決まる)(§3.5, p.6, Table 1)。
- [paper] Bloom filter 前提: point lookup の I/O は IO_point = 1 + FPR とし、10 bits/key なら
  FPR ≈ 0 とみなす。key 24B / value 1000B なら Bloom のメモリは DB の約 1.2% であり、
  Bloom と cache のメモリトレードオフ(1–5 bits/key の極端に制約された設定で生じる)は
  「実運用では稀」として最適化対象から除外 (§3.5, p.6)。
- [paper] scan の I/O モデル: seek フェーズで (𝐿−1)+𝑟₀ 個のイテレータを初期化し、各ブロックが
  𝐵 エントリを含むとして IO_scan = 𝑙/𝐵 + (𝐿 + 𝑟₀ᵐᵃˣ/2 − 1)(𝑙 = scan 長)(§3.5, p.6)。
  [inference] ブロックあたりエントリ数 𝐵 が一様、つまり固定長 KV を暗黙に仮定している。
- [paper] クエリ処理順: range cache → MemTable → block cache → disk の top-down
  (§3.2, Fig. 5)。[question] range cache を MemTable より先に見る以上、新しい書き込みとの
  一貫性は range cache への同期的な update/invalidate に依存するはずだが(Fig. 5 に
  "Update" 矢印はある)、その機構の説明は本文に見当たらない。
- [paper] 制御は window 単位(既定 1000 操作)。window 末尾で統計収集・非同期にモデル更新し、
  適用されるパラメータは常に1 window 遅れ (§4.2, p.7)。推論・学習はバックグラウンドで
  クエリパスから分離 (§3.1, §4.2)。
- [paper] モデルは CPU 常駐(RocksDB を動かす本番環境に GPU は普通無い、モデルが小さく
  GPU 転送レイテンシが不利、という理由)(§4.1)。actor/critic とも隠れ次元 256・
  2 隠れ層の全結合 NN、両モデル合計 ~14万パラメータ・重み ~550KB、オンライン学習中は
  Adam の状態込みで計 ~2.2MB (§4.3, Table 2)。
- [paper] 並行性: single-client ならキャッシュ操作は逐次で競合なし。multi-client 用に
  range cache を shard 化(キー空間分割+shard ごとのロック)。multi-client では系が
  I/O バウンドなのでロック競合レイテンシは無視できると主張 (§4.4)。
- [paper] 評価の既定値: Zipfian skew 0.9、single client、cache = DB の 25%、pretraining 無し、
  DB 100GB、key 24B / value 1000B、SST 4MB、block 4KB、size ratio 10、Bloom 10 bits/key、
  write slowdown/stop = L0 4/8 ファイル、actor/critic 学習率 1e-3、α = 0.9 (§5.1, p.8)。
- [inference] 障害・永続化モデルの議論は無い。キャッシュも RL モデルも揮発性メモリ上の
  話で、再起動後のウォームアップや学習済み状態の復元は pretraining の節 (§3.6) 以外に
  扱いが無い。

## Approach
- [paper] **全体構成 (§3.1, Fig. 4)**: LSM-tree システム内に Dynamic Cache Component
  (block cache + range cache、境界は実行時に可変)を置き、Background Tuning Module
  (Stats Collector + actor-critic の Policy Decision Controller)が (1) block/range の
  メモリ分割、(2) admission 制御パラメータの2つを出力する。workload log を集めて
  pretraining にも使える。
- [paper] **適応的パーティショニング (§3.3)**: RL が point/scan 比・ヒット率・scan 長・
  compaction の影響などの実時間統計から動的境界を調整。更新が少なく安定したアクセスでは
  block cache 寄り、compaction が頻発するワークロードでは range cache 寄りに配分しつつ、
  scan 時に下位レベルのホットブロックを捕まえる小さな block cache は常に残す
  (この現象は [43] でも観察と明記)。
- [paper] **point lookup の頻度ベース admission (§3.4)**: miss 時に Count-Min Sketch で
  キーの頻度をカウントし、「そのキーの頻度 / miss したキー全体の頻度和」の正規化スコアが
  閾値を超えたときだけ admit。閾値は固定でなく RL が動的調整(Zipf の歪度が違えば top-N
  ホットキーに対応する頻度比が大きく異なり、固定閾値は over/under-admit するため)。
  頻度カウントは飽和点(例: 8)に達したら全カウントと総和を半減する decay 付き。
- [paper] **range scan の部分 admission (§3.4, Fig. 6)**: 全量キャッシュは有害
  (Fig. 6 の例: 長さ16の scan が block cache から約8ブロックを追い出す
  〈4 entries/block なら理想は4ブロック〉— scan 範囲が各 sorted run と重なり run ごとに
  最低1ブロック触るため。range cache では長さ64の scan が64エントリを追い出し、それらが
  point lookup を捌いていた場合最大64回の追加 I/O になる)。そこで scan 長 𝑙 < 𝑎 なら全量
  admit、𝑙 > 𝑎 なら 𝑏·(𝑙−𝑎) 個だけキャッシュする。𝑏 は「全範囲がキャッシュされるまでに
  必要な繰り返しアクセス回数」を決める攻撃性パラメータで、重複 scan は自然に蓄積を加速。
  𝑎 の初期値はワークロードで観測される短 scan の平均長。ブロック数を制御対象にすれば
  block cache にも適用可能。[question] 𝑏·(𝑙−𝑎) 個として「どの」アイテムを選ぶか
  (先頭 prefix か等)は本文に明記が無い。
- [paper] **RL 制御 (§3.5)**: actor の入力状態 = キャッシュ統計(占有率、hit/miss 比)+
  ワークロードパターン(アクセス頻度、scan/point 比、scan 長分布)。出力 = メモリ分割と
  部分 admission パラメータ。連続制御に向き低オーバヘッドで安定学習できるとして
  actor-critic を選択。
- [paper] **報酬 (§3.5, p.6-7)**: range cache は結果を持つため通常のヒット率が測れない。
  そこでキャッシュ無し時の総ブロック I/O を
  IO_estimate = 𝑝×(1+FPR) + 𝑠×𝑙/𝐵 + 𝑠×(𝐿 + 𝑟₀ᵐᵃˣ/2 − 1) で推定し、実測 miss I/O との比から
  h_estimate = 1 − IO_miss/IO_estimate を推定ヒット率とする。block cache の文脈では
  h = h_estimate となることを「精度検証済み」と主張 (§3.5, p.7)。生の h_estimate は
  使わず、指数平滑 h_smoothed ← α·h_smoothed + (1−α)·h_estimate、
  reward ← Δh_smoothed/h_smoothed とし、短期変動への過剰反応(頻繁な境界調整→eviction 増)を
  抑える (§3.5, p.7)。
- [paper] **適応学習率 (§3.5, p.7)**: 各 window 先頭で 𝑙𝑟 = 𝑙𝑟×(1−reward)。ワークロード
  シフトでヒット率が落ちると reward が負→学習率が上がり探索的になり、安定時は正の
  reward で学習率が減衰して収束を速める。
- [paper] **pretraining (§3.6)**: 教師あり(代表ワークロードベクトル+制御実験で得た目標
  構成のペア)または教師なし(オンラインと同じ RL)。利点は可搬性(マシン間で再学習不要)、
  デプロイ時計算コスト削減、良い初期化による warm-up 回避。

## Evaluation
- Setup [paper]: Ubuntu 22.04、Intel i9-13900K(L3 36MB)、RAM 128GB、NVMe SSD 2TB。
  レイテンシ測定時は SST 読みに direct I/O を使い OS ページキャッシュを排除 (§5.1, p.8)。
  ベースライン: RocksDB Block Cache / KVCache(point 結果のみ)/ Range Cache
  (**非公開のため論文記述から再実装**)/ Range Cache + LeCaR / Range Cache + Cacheus
  (LSM 特化でない学習ベース eviction を naive に組み合わせた代表として)(§5.1, p.8)。
- [paper] 静的ワークロード4種(Point Lookup / Short Scan 長16 / Balanced 33-33-33 /
  Long Scan 長64)、cache サイズ DB 比 10–40% (§5.2, Fig. 7)。
  - Point Lookup: AdCache は全サイズで最良または同率最良。Range Cache 比最大 +9%、
    Block Cache 比最大 +14% のヒット率、SST 読み最大 −25% (§5.2, p.9)。
  - Short Scan: Range Cache 系は意外にも Block Cache に負ける(部分ヒットでも LSM seek の
    フルコストがかかるため)。AdCache は range cache を丸ごと block cache に転換して適応
    (§5.2, p.9)。
  - Balanced: Block Cache 比ヒット率 +6%、SST 読み −16.2% (§5.2, p.9)。
  - Long Scan: 全量キャッシュは eviction 過多。AdCache は部分 admission で SST 読みを
    RocksDB 比約 −17.2% (§5.2, p.9)。
- [paper] 動的ワークロード: 6フェーズ A→F(Table 3、各 5,000万操作。A = 97% long scan
  から F = 75% put まで)。AdCache は throughput/hit rate の平均順位 1.3/1.3 で全手法中
  最良 (Table 4)。read-heavy 相 (A–C) では block cache、write-heavy 相 (D–F) では
  range cache に切替え、write-heavy・long-scan 相では RocksDB 比 throughput +25–37%
  (§5.3, p.9-10, Fig. 8)。コントリビューション記述では動的ワークロード平均 throughput
  +12% (§1, p.2)。
- [paper] 歪度感度(50% update + point/short scan 半々): AdCache は全歪度域で最良。
  skew 1.0 でヒット率 77%、1.2 で最大 93%。Block Cache 比ヒット率最大 +12%、
  SST 読み −34.3% (§5.4, Fig. 9, p.10)。低歪度では block cache が優位(ブロック内に低頻度
  キーを同居させることがランダムアクセスで利く)という分析も (§5.4, p.10)。
- [paper] 学習パラメータ: window 100/1000 は同等で 10000 は収束が遅い。pretrained のみ
  (オンライン学習無し)はシフト時のヒット率低下が最も急。α=0 は短期変動に過剰反応して
  準最適に停留、α=0.5/0.9 は同様に安定収束 (§5.4, Fig. 10, p.11)。パラメータ軌跡:
  range cache 比率は point-lookup 相でほぼ 100% → short-scan-heavy 相でほぼ 0% に遷移、
  頻度閾値はほぼ 0(one-off でないキーは大半 admit)、scan 閾値は scan 長16に対し 16–18 に
  安定 (§5.4, Fig. 10, p.11)。
- [paper] 学習オーバヘッド: クライアント 1→32 で per-client QPS はほぼ不変(ボトルネックは
  I/O)(§5.4, Fig. 11(a))。
- [paper] ablation(Range Cache 基準): admission control のみ +11%、適応パーティショニング
  のみ +55%(long-scan では block cache 優位なので range→block へ実質転換)、両方で +61% の
  ヒット率改善 (§5.4, Fig. 11(b), p.11)。
- [inference] 評価がカバーしないもの:
  - 実トレースが無い。全て合成(Zipfian、固定長 scan、固定比率フェーズ)。
  - §2.2/§6 で挙げた LSM 特化キャッシュ(AC-Key、Leaper、SpotKV、LSbM-tree)との直接比較が
    無い。特に AC-Key は「複数キャッシュ間の動的メモリ配分」という最も近い競合に見えるが
    ベースラインに入っていない。
  - 動的ワークロードのヒット率比較 (Fig. 8(b)) は軸ラベルが "Estimated Hit Rate"、つまり
    報酬に使う自前の推定量そのもの。推定器が systematically 有利に働かないかは検証されて
    いない(QPS と SST 読み削減は独立測定なので主結果は支えられる)。
  - コストモデルが leveled (1-leveling) 前提。tiered compaction 等での推定精度・学習挙動は
    未評価。
  - cache サイズは DB 比 10–40% のみ。メモリが極端に細い設定(数%以下)は無い。
  - direct I/O でレイテンシ測定可能な構成にした (§5.1) 割に、tail latency の数値・図は
    本文に見当たらない(throughput と hit rate のみ)。
  - pretraining + オンライン学習の併用構成の効果は Fig. 10 からは分離されていない
    (pretrained 曲線はオンライン学習無しの条件)。

## Limitations
- Stated [paper]:
  - workload D(書き込み 49% への遷移直後)で性能低下: (1) シフト後のキャッシュ適応が
    未完了、(2) range cache の skip list への頻繁な挿入オーバヘッド+ range/block 両キャッシュ
    への逐次アクセス (§5.3, p.10)。C→D 遷移で一時的なヒット率低下 (§5.3, Fig. 8)。
  - α=0(平滑化無し)は準最適構成に停留、window 10⁴ は収束が遅い (§5.4, Fig. 10)。
- Inferred [inference]:
  - 報酬 = 推定ヒット率は IO_estimate の正確さに依存する。IO_scan は平均 scan 長 𝑙 を使う
    ため、scan 長分布が heavy-tailed な場合に推定がずれ、RL がずれた目的関数を最適化する
    恐れがある。推定精度の検証は「block cache の文脈で検証済み」という一文 (§3.5, p.7) に
    留まり、range cache 混在時の検証は示されていない。
  - パラメータ適用が常に 1 window 遅れ (§4.2) なので、window より速い周期のワークロード
    振動には原理的に追従できない(評価のシフトは 5,000万操作単位の緩いもの)。
  - Range Cache ベースラインが再実装 (§5.1) であり、対 Range Cache の相対値
    (+9%、ablation の +61% 等)は再実装の忠実度に依存する。
  - 書き込みと range cache の一貫性維持コスト(write-heavy 相での skip list 挿入オーバヘッド
    として D 相で顕在化)は、admission/partitioning と違って RL の制御対象になっていない。

## Relations
- [inference] 著者重複: Junfeng Liu と Siqiang Luo(NTU)は 2026-pvldb-liu-arcekv.md
  (ArceKV)と共通(本論文ヘッダ p.1 と ArceKV ノートの著者欄の照合)。同じ RocksDB 上で
  「動的ワークロードへのオンライン適応」を、ArceKV は compaction 構造側から、AdCache は
  キャッシュ側から攻めており、compaction 頻度がキャッシュ無効化率(= 最適な block/range
  比)を決めるという結合点がある。両コントローラを同居させたときの相互作用は両論文とも
  扱っていない。
- 論文内の先行/競合 [paper]: Range Cache [43](ベース+比較対象)、AC-Key [45]
  (KV/KP/block の3キャッシュを ARC で配分)、Leaper [47](compaction 後 prefetch)、
  TinyLFU [15](頻度ベース admission の源流)、LeCaR [41] / Cacheus [37](学習ベース
  eviction、naive 統合ベースラインとして評価)(§2.2, §3.4, §5.1, §6)。

## Idea seeds
- [inference] **報酬推定器の独立検証**: h_estimate は評価指標と報酬を兼ねており、しかも
  leveled+平均 scan 長前提。トレースを冷キャッシュでリプレイして実測 no-cache I/O と
  IO_estimate を突き合わせれば、推定バイアス(特に scan 長分布の裾と tiered compaction)を
  定量化できる。バイアスが大きければ「推定器のずれが RL を誤誘導する」という一般的な
  learned-DB 問題の良い実例になる。公開コードがあるので最初の実験は安価。
- [inference] **compaction 制御との共同最適化**: AdCache は compaction を所与としてキャッシュを
  適応させ、ArceKV(同グループ)は compaction を適応させる。compaction 攻撃性→ブロック
  無効化率→最適キャッシュ分割という因果があるため、独立に動かすと振動(cache ratio の
  thrashing)が起きうる。検証: compaction 頻度を外生的に振りながら AdCache の range/block
  比の軌跡を観測し、発振や遅延収束が出るかを見る。出れば joint controller の動機になる。
- [question] **range cache と書き込みの一貫性**: クエリパスが range cache を MemTable より
  先に引く (§3.2, Fig. 5) 以上、更新時の range cache 無効化/更新の設計が正しさの要なのに
  本文に説明が無い。公開コードで write パスを確認し、read-your-writes を破るケースが
  ないか(あるいは同期 invalidate のコストが write-heavy 相の劣化の真因ではないか)を
  マイクロベンチで検証する価値がある。

## Changelog
- 2026-07-06: created (status: read, OpenProceedings 公式 PDF を読解)
- 2026-07-06: 検証パスによる修正(scan 部分 admission の全量キャッシュ条件を 𝑙 ≤ 𝑎 → 𝑙 < 𝑎 に訂正〈§3.4 原文は "less than a threshold 𝑎"〉、Relations の TinyLFU admission 記述のアンカーに §3.4 を追加)
