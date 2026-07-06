---
title: "DCSR: A Fast Data Structure with Leaf-Oriented Locks for Streaming Graph Processing"
authors: [Yue Shen, Jie Zhang, Huawei Cao, Yuan Zhang, Xuejun An]
venue: "EDBT '26 (24-27 March 2026, Tampere, Finland)"
year: 2026
ids: {doi: "10.48786/EDBT.2026.29", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.48786/edbt.2026.29", pdf: "literature/pdfs/2026-edbt-shen-dcsr.pdf", code: "https://github.com/IamwhatIamSY/DCSR"}
status: read
read_date: 2026-07-06
tags: [streaming-graph, packed-memory-array, csr, graph-update, leaf-locks, parallel-update, batch-update, locking, data-structure]
---

注: 本ノートの (p.N) は抽出テキストの PDF ページ番号(論文の刷りページは 359–371)。
著者は全員 State Key Lab of Processors, Institute of Computing Technology, CAS 所属
(第一著者は University of Chinese Academy of Sciences 併記)、corresponding author は
Huawei Cao (p.1, p.12 Acknowledgments)。

## TL;DR
Streaming graph 処理の動的グラフ格納構造として広く使われる PMA(Packed Memory
Array)は、並列エッジ更新の方式が「vertex lock ベースの単一エッジ更新(競合が激しい)」
か「lock-free バッチ更新(ソートフェーズが大バッチで支配的)」の両極端に割れていた。
DCSR は PMA の性質(leaf 内 left-packed、更新は target leaf のみ、rebalancing は規則的)
を突き、①lock 無しで leaf を絞ってから leaf 単位ロックで entry を探す regulated
location search、②locating+updating を行う lock-based update フェーズと、③flag 配列
+ temp leaf vector で必要な leaf だけ処理する decoupled rebalancing フェーズの2段構成
を提案。挿入で PPCSR/CPMA/PaC-tree/Terrace/LSGraph 比 平均 5.84×/12.98×/25.63×/
27.45×/11.14×、約 1000 万 updates/s を主張(abstract)。

## Problem & motivation
- [paper] streaming graph 処理は graph update フェーズと graph computation フェーズの
  両方が速い必要があり、静的処理用の CSR は更新時のデータ移動過多で不適 (§1)。
  応用例: 金融不正検知、SNS 分析、コンテンツ推薦 (§1)。
- [paper] PMA は sorted な辺を単一配列に gap 付きで保持する implicit complete binary
  tree で、計算(良い locality)と更新(gap による挿入余地)の両立に向くため、既存
  streaming graph 系で人気 (§1, §3.2)。
- [paper] 既存の PMA 並列更新は2方式 (§3.3):
  - **LSU(lock-based single-edge update, 例: PPCSR)**: 1 スレッド 1 エッジ更新で
    排他 vertex lock を使う。locating/updating の各ステップで複数スレッドが同じ
    vertex lock 群を取り合い、ほぼ逐次化する。atomic 操作のオーバーヘッドを考えると
    serial 実行より遅くなり得る (§3.3.1, Fig. 3)。
  - **BU(lock-free batch update, 例: CPMA)**: sort → merge → count-and-redistribute の
    多フェーズ処理でロック不要 (§3.3.2, Fig. 4a)。だが (i) フェーズ分割によるスレッド
    スケジューリング・同期のオーバーヘッドが小バッチで無視できず、(ii) バッチ k 件の
    ソートに O(k log k) の追加作業が要り、batch size 10^4 で総時間の 60% 超、より大きい
    バッチでは最大 80% をソートが占める (§3.3.2, Fig. 4b; §1 も「80% 超」と記述)。
- [paper] 洞察: PMA の3性質が「ソートフェーズ無しで競合を減らす」機会を与える
  (§1, §3.3.3): (i) leaf 内の要素は left-packed → 探索アルゴリズムを規制(regulate)して
  locating と updating の競合を減らせる、(ii) updating で触るのは target leaf のみ →
  粗粒度 vertex lock でなく細粒度 leaf lock で並列度を上げられる、(iii) rebalancing は
  locating/updating より規則的 → 別フェーズに分離してさらに競合を減らせる。
- [paper] 貢献の位置付け: leaf-oriented parallel update strategy を「初めて」提案、
  BYO フレームワーク [48] 上に実装して graph container 間の apples-to-apples 比較を
  提供 (§1)。

## System model & assumptions
- [paper] 単一マシン・共有メモリのマルチコア環境(評価は 4× Intel Xeon Gold 6148、
  計 80 コア(2-way HT)、2.7GHz、256GB、CentOS 7.9)(§5.1)。分散設定は future work
  (§6 ❹)。
- [paper] グラフは CSR ベースの PMA に格納: offset array が各頂点の近傍開始 index を
  持ち、PMA 内の sentinel 要素が各頂点の近傍先頭を示す。empty entry は MAX_NUM、
  sentinel は MAX_NUM−1 で表現 (§3.2, Fig. 2)。
- [paper] PMA の密度制御: N は2の冪、N/log N 個の segment(= leaf、サイズ log N)、
  レベル l のノードの密度は ρ_l < Density < τ_l に制約され、root が上限/下限を割ると
  PMA の倍化/半減(expansion/contraction)が要る。2ρ_h < τ_h が要件 (§3.1)。
- [paper] エッジ更新は (f, v_a, v_b)(f=1 挿入 / f=0 削除)で、挿入バッチ ΔG+ と
  削除バッチ ΔG− は先行研究同様に**別々の手続き**で処理する (§3.2, §4)。
- [paper] 2フェーズ(lock-based update → decoupled rebalancing)は順次実行され、
  各フェーズ内部が leaf lock で並列化される (§4)。バッチ ≤10^2 では並列2フェーズを
  やめ、ロック無しの逐次1フェーズで処理する(実装上の閾値)(§4.3.4)。
- [paper] 重複挿入は CheckElement で検出して no-op(PMA と temp edge vector の両方を
  確認)、頂点次数は AtomicAddDegree で原子的に増減 (§4.2.2, Alg. 2; §4.2.3, Alg. 3)。
- [paper] 評価対象のグラフは undirected・unweighted(全比較対象構造の要件を満たす
  ため)(§5.1)。
- [paper] graph computation は静的アルゴリズム(BFS 等)を毎回スクラッチ実行し、
  増分計算は他研究の課題として対象外 (§5.1)。ACID なトランザクション処理や
  MVCC による更新・クエリ並行実行を提供する graph database 系も対象外と明言 (§2)。
- [inference] 従って本設計の一貫性単位は「フェーズ境界」であり、更新バッチ適用中に
  並行して読み取り(クエリ)が走る状況の正しさは論じられていない。leaf lock は
  update 同士の整合性のためのもので、computation はロックを一切使わない
  (§5.3 に「graph computation does not require any locks」)。
- [inference] 頂点の追加・削除の手順は本文に記述が無い(§2 で tree 系構造の利点として
  頂点挿入・削除効率に触れるのみ)。対象はエッジ更新に限られると読める。

## Approach
- [paper] **DCSR フォーマット (§4.1, Fig. 5)**: primary 構造 = offset array P_o、PMA
  P_e、**leaf lock array P_l(leaf ごとに 4B のロック)**、**flag array P_f(leaf ごとの
  rebalancing フラグ)**。auxiliary 構造 = **temp edge vectors P_t(leaf ごと、挿入のみ
  使用)** と **temp leaf vectors Q(スレッドごと)**。auxiliary は graph update フェーズ
  開始時に確保し終了時に解放。full な leaf への挿入は (located entry の index, v_b) の
  ペアを P_t[leaf] に積み、その leaf の index をスレッドの Q に記録。削除で leaf が
  空になる場合はその leaf index を Q に記録。
- [paper] **Regulated location search (§4.2.1, Alg. 1)**: 素朴な binary search には
  3つの欠点がある — (i) 探索領域 (P_o[a], P_o[a+1]] に empty entry が混じるため
  アルゴリズムが複雑化、(ii) 領域へのアクセスが不規則、(iii) locating と updating の
  ステップ間の競合(§3.3.1 で述べた vertex lock 由来の競合に関する欠点。抽出テキスト
  が一部乱れているため細部の文言は要 PDF 再確認)。DCSR の手順:
  1. FindLeaf で領域の leaf_begin / leaf_end を計算(ロック無し)。
  2. BinaryLeaf: (leaf_begin, leaf_end] の**各 leaf の先頭要素だけ**を binary search し、
     先頭要素が v_b より大きい最初の leaf(leaf_larger)を探す。見つかれば
     leaf_tgt = leaf_larger − 1、無ければ leaf_tgt = leaf_end。**leaf の先頭 entry しか
     読まないためロック不要** (§4.2.4)。
  3. target leaf のみ P_l でロックし、探索範囲 [left, right) ⊂ (P_o[a], P_o[a+1]] ∩
     [leaf_tgt×logN, (leaf_tgt+1)×logN) を境界計算して BinaryEntry で leaf 内 binary
     search → located entry の index を返す。
- [paper] BinaryLeaf のロック無し実行の正当性 (§4.2.4): 挿入では located entry が
  leaf 先頭になるケースでも先頭 entry は変更されない(非 target leaf なら挿入されず、
  target leaf なら既存要素と等しい=重複)。削除では、leaf 唯一の要素は dummy edge 化
  されて読める状態が保たれ、そうでなければ先頭より大きい要素の左詰めで先頭は
  2番目以降の(より大きい)要素に置き換わるため BinaryLeaf の出力は正しい。
- [paper] **Lock-based update(挿入, §4.2.2, Alg. 2)**: 1 スレッド 1 挿入。
  RegulatedLocSearch(復帰時点で target leaf ロック保持)→ CheckElement で重複なら
  return → target leaf が full なら (loc, v_b) を P_t[leaf_tgt] に push し、flag 未設定
  なら Q に leaf index を push して P_f[leaf_tgt]=1 / full でなければ AddElement で
  P_e[loc] に挿入し、動いた sentinel に合わせて offset array を更新 → 次数を原子加算
  → unlock。
- [paper] **Lock-based update(削除, §4.2.3, Alg. 3)**: located entry に v_b が無ければ
  return。leaf が空になる場合(先頭 entry のみ非空)は本当に消さず **dummy edge**
  (存在しない印だが読める)に変換し、leaf index を Q に push、flag=1。空にならない
  場合は RemoveElement で削除 + offset array 更新。次数を原子減算 → unlock。
  dummy edge は decoupled rebalancing フェーズの冒頭で一括除去 (§4.2.3, §4.3)。
- [paper] **Decoupled rebalancing (§4.3)**: temp leaf vector をスレッドごとに1本ずつ
  処理(vector 数 = スレッド数なので全スレッド活用)。vector 内の leaf は逐次処理。
  rebalancing 前に leaf の flag を確認し、0 なら他スレッドが処理済みなので即 return
  (冗長 rebalancing の除去)。temp leaf vector 内に leaf index の重複は生じない
  (挿入は flag を見てから push、削除は dummy edge 化済み leaf で即 return するため)
  (§4.2.4)。
  - 挿入の rebalance (§4.3.1, Fig. 6a): 祖先の密度を下から上に計算(PMA 中の要素数
    + 対応 temp edge vector 中のペア数を合算)し、密度制約を満たす最初の祖先領域の
    leaf 群のロックを取得。領域内要素を (loc(e), e) ペアに変換して temp array に集め、
    temp edge vector のペアと併せて loc → 要素の順にソートし、領域に均等再配置。
    offset array 更新、flag=0、ロック解放。フェーズ末尾で auxiliary 構造を解放。
  - 削除の rebalance (§4.3.2, Fig. 6b): まず dummy edge を除去し、各スレッドが担当
    leaf の祖先密度を計算して下限を満たす領域で均等再配置。
- [paper] flag array を直接走査せず temp leaf vector を使う理由 (§4.3.3, Fig. 7a, Fig. 8):
  rebalance が要る leaf は極めて疎 — Web-uk-2005(leaf 数 67,108,864)では batch
  ≤10^4 で 0 枚、batch 10^7 でも全 leaf の 0.023%。flag array 走査方式にすると batch
  10^3 で DCSR の性能は 52.6% 低下する。
- [paper] **小バッチ最適化 (§4.3.4)**: batch ≤10^2 では rebalancing フェーズ時間比が
  20% を超え (Fig. 7a)、leaf lock・atomic のコストが並列化の利得を上回るため、
  ロック無し逐次1フェーズに切り替える。逐次1フェーズは並列2フェーズ比で
  2.89×–8.00× 速い (Fig. 7b)。
- [paper] **計算量 (§4.4)**: work-span モデル + external memory モデルで、バッチ k 件
  あたり total work O(k log n + (k log² n)/B)(locating O(k log n)、updating
  O((k log n)/B)、rebalancing は標準 PMA 同様に per-update O(log² n) amortized moves
  = O((k log² n)/B))、worst-case span は O(log² n)(decoupled rebalancing が critical
  path。O(log n) レベルを辿り、各レベルの再配置は polylogarithmic depth の並列
  プリミティブ)。B はキャッシュライン長 (§3.2, §4.4)。

## Evaluation
- Setup [paper] (§5.1): 4× Xeon Gold 6148(計 80 コア、2-way HT)、256GB、CentOS 7.9。
  DCSR は C++ で BYO フレームワーク [48] 上に実装。DCSR/PPCSR/CPMA/PaC-tree/
  Terrace は GCC 11.2.1 + OpenMP、LSGraph のみ原論文の構成に従い clang++ 10.0.1 +
  OpenCilk 1.0。データセットは実グラフ5本(Table 1): LiveJournal(3.99M/34.7M)、
  Orkut(3.07M/117.2M)、Web-uk-2005(39.5M/936.4M)、Twitter(41.7M/1.47B)、
  Friendster(65.6M/1.81B)。更新は RMAT 生成(a=0.5, b=0.1, c=0.1)。計算ワーク
  ロードは BFS / PageRank / betweenness centrality / triangle counting(スクラッチ実行)。
- 方法 [paper] (§5.2): throughput = batch size / 実行時間、5 試行平均(毎回別のエッジ
  集合)。LSGraph は batch < スレッド数の更新を実装がサポートしないため、その領域は
  除外して speedup を計算。
- **更新スループット** [paper] (§5.2, Fig. 9, Fig. 1):
  - 挿入(batch 10/10^3/10^5/10^7、5グラフ): PPCSR 比 1.10×–36.45×、CPMA 比
    1.44×–66.87×、PaC-tree 比 1.48×–210.01×、Terrace 比 3.43×–153.32×、LSGraph 比
    0.52×–50.76×。batch ≤10^5 では全ケースで5構造すべてに勝つ。abstract の平均値は
    5.84×/12.98×/25.63×/27.45×/11.14×(対 PPCSR/CPMA/PaC-tree/Terrace/LSGraph)。
  - 削除: 平均 4.97×(最大 22.06×)/ 4.72×(17.96×)/ 26.51×(208.33×)/ 18.79×
    (51.02×)/ 2.19×(5.93×)(同順)。
  - Web-uk-2005 のみ(Fig. 1): 挿入平均 4.64×/14.41×/18.05×/19.14×/12.84×、削除平均
    4.73×/4.27×/18.01×/15.39×/1.90×。batch 10–10^7 で 1000 万 updates/s 超を維持
    (§1, Fig. 1)。
  - batch=10 で PPCSR/CPMA/PaC-tree/Terrace に対する speedup が最大になる理由
    [paper]: 単一 PMA による location search の locality(対 PaC-tree/Terrace)、
    merge/count/redistribute より単純な関数群(対 CPMA)、小バッチの逐次実行最適化
    (対 PPCSR)(§5.2)。
  - **負けるケース** [paper]: batch 10^7 では OR/TW/FR で LSGraph に対し 0.52×/0.93×/
    0.56× と下回る (Fig. 9d)。理由: AL 系は頂点ごとの辺構造を競合無く個別調整できる、
    階層 index と HITree、OpenCilk の最適化、そして**厳格な PMA 更新原理のため大バッチ
    (≥10^6)では lock-based 手法に大量の競合とデータ移動が生じる** (§5.2)。ただし
    batch 10^3/10^5 では LSGraph 比 28.09×/4.43× (§5.2, Fig. 9b, 9c)。
- **graph computation** [paper] (§5.3, Fig. 10): CSR 正規化の slowdown は DCSR
  1.00×–4.03×、PPCSR 1.00×–4.08×、CPMA 1.00×–5.30×、PaC-tree 0.29×–1.42×、Terrace
  0.57×–9.28×、LSGraph 1.19×–6.84×。DCSR の平均 speedup は PPCSR 比 1.06×(最大
  1.71×)、CPMA 比 1.32×(4.87×)、PaC-tree 比 0.83×(1.42×)、Terrace 比 1.37×
  (4.93×)、LSGraph 比 4.97×(6.78×)。PaC-tree は圧縮ブロック + 並列デコードで
  BFS 平均 1.58× と CSR より速い場合すらある。DCSR が PPCSR より速いのは lock を
  offset array に同居させず別配列に置くため計算時の locality が良い、CPMA より
  速いのは圧縮の展開オーバーヘッドが無いため。LSGraph は triangle counting が
  UK/TW/FR で 5 時間以内に終わらず結果なし。
- **スケーラビリティ** [paper] (§5.4, Fig. 11): Web-uk-2005、スレッド 2^0–2^7。DCSR は
  全ケースで最良。両バッチサイズで良くスケールするのは DCSR/CPMA/PaC-tree のみ。
  LSGraph は batch 10^3 で 64 スレッドから低下(vertex-level 並列のため)、PPCSR は
  大バッチで 128 スレッド時に低下(vertex lock と atomic のコストが並列利得を超過)、
  Terrace は PMA 部の探索・移動ボトルネックで両サイズともスケールせず。
  [inference] 本文は「batch sizes of 10^3 and 10^7」と書くが Fig. 11 のキャプションは
  10^3 と 10^6 で、本文と図の表記が食い違っている(どちらかが誤記)。
- **メモリ** [paper] (§5.5, Table 2): DCSR は LJ/OR/UK/TW/FR で 1.13/2.15/17.19/33.36/
  35.42 GB。auxiliary 構造(挿入 batch 10^7 時)は DCSR 本体の 8.90%–17.67%。
  Terrace は DCSR の 1.17×–1.46×(高次数頂点用 B-tree のポインタ)。PPCSR よりわずかに
  小さい(leaf lock 4B vs vertex lock 16B)。CPMA(UK: 2.19GB)/ PaC-tree(6.59GB)は
  圧縮するため DCSR より小さく、LSGraph も gap が少ないぶん小さい。temp edge vector
  の空間計算量は O(log N) と記述 (§5.5)。
- [inference] 評価がカバーしていないもの:
  - 更新とクエリ(graph computation)の**並行実行**。更新スループットと計算時間は
    別々に測られており、streaming 設定で両者が混ざる場合の干渉(leaf lock は計算に
    使われないので read の安全性自体が問題)は測定・議論されていない。
  - **スキュー更新**。RMAT(a=0.5, b=0.1, c=0.1)のみで、少数ホット頂点への集中更新は
    未評価。著者自身が future work ❸ で「少数ホット頂点への集中更新では激しい競合が
    起こり得る」と認めており、leaf lock の競合上限は未知。
  - 挿入と削除の**混合バッチ**(別手続きで処理する設計 §4 のため、混在ストリームの
    挙動・削除→挿入の順序依存は実験に無い)。
  - レイテンシ分布(すべてスループット/実行時間ベース。テールの測定なし)。
  - PMA 全体の expansion/contraction(root が密度制約を割るケース §3.2)が並列
    2フェーズとどう共存するかの記述・測定。
  - 頂点数が増減するワークロード(頂点挿入・削除)。

## Limitations
- Stated [paper]:
  - 大バッチ(≥10^6)では厳格な PMA 更新原理により競合とデータ移動が増え、
    AL 系(LSGraph)に一部グラフで負ける(batch 10^7 の OR/TW/FR で 0.52×–0.93×)
    (§5.2, Fig. 9d)。
  - 非圧縮格納のため CPMA / PaC-tree よりメモリ消費が大きい(将来課題 ❶ で delta
    encoding による圧縮 PMA を挙げる)(§5.5, Table 2, §6)。
  - auxiliary 構造(主に temp edge vectors)が挿入時に本体の 8.90%–17.67% の追加
    メモリを消費(更新手続き中のみ)(§5.5, Table 2)。
  - スキュー更新(ホット頂点集中)では激しい競合が起こり得るため、lock-free バッチ
    更新との hybrid が将来課題 (§6 ❸)。大バッチのデータ移動削減には階層エッジ構造
    (LSGraph/LPMA 流)が将来課題 (§6 ❷)。分散設定は未対応 (§6 ❹)。
- Inferred [inference]:
  - decoupled rebalancing フェーズでスレッドは祖先領域内の**複数 leaf のロック**を
    取得する(例: §4.3.1 で thread 3 が leaves 2, 3 のロックを取得)。複数スレッドが
    重なる領域のロックを異なる順序で要求した場合のデッドロック回避規則は本文に
    記述が無い(公開コードで確認すべき点)。
  - phase 2 は temp leaf vector 単位の割り当てで、vector 内の leaf は逐次処理される
    (§4.3)。特定スレッドに rebalance 対象 leaf が偏った場合(スキュー挿入で同一
    領域の leaf が集中した場合)の負荷不均衡は分析されていない。
  - 「rebalance が要る leaf は極めて疎」(0.023% @ batch 10^7, §4.3.3)という temp leaf
    vector 設計の前提は uniform 寄りの RMAT 更新での観測であり、ホット leaf に挿入が
    集中するワークロードでは前提ごと崩れる可能性がある(§6 ❸ の将来課題と同根)。
  - 挿入バッチと削除バッチを別手続きにする設計 (§4) は、同一 key への insert/delete が
    混在するストリームでは適用順序の意味論(バッチ内の重複更新の扱い)がユーザ側の
    分割方法に依存する。本文はバッチ分割の意味論を規定していない。
  - 更新中の PMA は temp edge vector に「あふれた挿入」を保持したまま phase 1 を終える
    ため、phase 2 完了までは PMA 本体だけを見ても最新状態ではない。フェーズ間で
    クエリを許す拡張をする場合、CheckElement 同様に temp 構造も見る必要があり、
    read パスのコストが上がるはず。

## Relations
- 競合 baseline(本文 §5.1): PPCSR(PMA + vertex lock の LSU)、CPMA(圧縮 PMA +
  lock-free BU)、PaC-tree(tree 系)、Terrace(hybrid 3 層)、LSGraph(AL 系)。
  いずれも corpus 内にノート無し。実装基盤は BYO framework [48] (§5.1)。
- [[2026-fast-wei-dmtree.md]](DMTree: disaggregated memory 上の B+-tree)
  [inference] ドメインは異なる(DCSR は単一マシン共有メモリのグラフ格納、DMTree は
  DM 上の range index)が、「順序付き構造の更新競合を leaf 粒度のロックで細分化し、
  さらに競合源の操作(DCSR は rebalancing の分離、DMTree は lock/fingerprint の
  compute 側移設)をホットパスから外す」という設計思想が共通する。leaf-granularity
  locking の適用範囲を考える際の対照事例。直接の引用関係は無い(本文の参照文献にも
  DMTree は無い)。

## Idea seeds
- [inference] DCSR の「locating はロック無し(leaf 先頭要素のみ読む)+ updating だけ
  leaf lock」という分割は、B+-tree 系 index の optimistic lock coupling と同じ精神を
  PMA で実現したものと読める。DB のクラスタ化ストレージとして PMA を使う系
  (VCSR 等、本文 refs [26,27])に対し、この regulated search + decoupled rebalancing を
  組み合わせると index maintenance(SMO)を遅延バッチ化する WAL 付きストレージ
  エンジンが構想できる。最初の検証: 公開コード(github.com/IamwhatIamSY/DCSR)の
  更新パスに WAL を挿入し、rebalancing 遅延がリカバリ境界とどう干渉するかを観察。
- [question] phase 2 の複数 leaf ロック取得にデッドロック回避(取得順序の規約や
  try-lock + retry)があるか。論文からは読み取れないため、公開コードの rebalancing
  実装を確認するのが先決。もし低アドレス順ロックなら、領域が重なる rebalance 同士の
  待ち行列がスキュー時のスループット崩壊(§5.2 の大バッチでの LSGraph 逆転)を
  説明する変数になり得る。検証: batch 10^6–10^7 でロック待ち時間のプロファイル。
- [inference] 「更新は leaf lock、読みはロック無し」の非対称性は、更新と計算を並行
  させる streaming 設定(本論文は対象外と明言 §5.1)に進むと壊れる。dummy edge と
  left-packed 性質を使って read-only 走査を epoch ベースで安全化できれば、graph
  database 系(§2 が対象外とした MVCC 系)との中間点になる。最初の検証: BFS を
  update フェーズと同時実行して観測される不整合(欠落辺・重複辺)を分類する。
- [question] 本文は §5.4 で「batch sizes of 10^3 and 10^7」と述べるが Fig. 11 の
  キャプションは 10^3 / 10^6。どちらの構成で測ったのかは artifact で確認したい
  (スケーラビリティ主張の再現条件に関わる)。

## Changelog
- 2026-07-06: created (status: read)
