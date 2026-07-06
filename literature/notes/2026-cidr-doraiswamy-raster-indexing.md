---
title: "Raster is Faster: Rethinking Ray Tracing in Database Indexing"
authors: [Harish Doraiswamy, Jayant R. Haritsa]
venue: "CIDR '26 (16th Annual Conference on Innovative Data Systems Research)"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/cidr/DoraiswamyH26"}
urls: {paper: "https://vldb.org/cidrdb/2026/raster-is-faster-rethinking-ray-tracing-in-database-indexing.html", pdf: "literature/pdfs/2026-cidr-doraiswamy-raster-indexing.pdf", code: "https://github.com/Microsoft/raster-scan"}
status: read
read_date: 2026-07-06
tags: [gpu, rasterization, ray-tracing, column-index, range-query, olap, texture, bvh, vulkan]
---

## TL;DR
近年の GPU の RT コア(ray tracing 専用ハードウェア)を DB の列インデックスに使う流れ
(RTIndex / RTScan)に対し、「DB のデータもクエリもグリッドに整列した 'well-behaved' な
幾何なので、BVH 木と ray-triangle 交差計算は overkill」と主張し、同じデータモデルのまま
古典的なラスタライゼーションパイプラインだけでインデックス構築・検索を行う RasterScan を
提案。列値をテクスチャのピクセル(ビン)に離散化し、探索は矩形描画+算術比較に置き換える。
RTScan 比で index build 約 50×、search はしばしば一桁以上の高速化、メモリも 1.12GB vs
3GB(BVH)と小さいと報告。

## Problem & motivation
- [paper] 現代 GPU は ray tracing (RT) 専用プロセッサ(RT コア)を持ち、BVH
  (Bounding Volume Hierarchy)木の走査をネイティブ支援する。BVH は空間 DB の
  R-tree の一般化にあたる木構造で、レイと交差する三角形群を特定する (§1, Fig. 1)。
- [paper] この数年、RT コアを DB 処理(クエリ実行、列インデックス等)に転用する研究が
  出ており、本論文はその適否を測る例題としてインデックス用途に注目する (§1)。
- [paper] RTIndex(整数列インデックスへの RT の最初の適用)は列値を x 軸上の三角形として
  配置し、探索述語をレイに変換して交差三角形=検索結果とする。重複値は同一位置の三角形を
  複数生むため、単一レイの交差処理負荷が増え並列性を損なう (§1, Fig. 2a)。
- [paper] 後続の RTScan は、①長い 1 本のレイを多数の短い垂直レイに分割、②N 点を
  [0, N−1] に一意に写像するエンコードで重複を除去、③三角形をより小さいキューブに置換、
  ④Bindex 風のデータフィルタ、⑤単一 BVH で最大 3 列のインデックス化、で改良した
  (p.2, Fig. 2b)。
- [paper] しかし DB 文脈では、データ点を収める三角形/キューブはグリッド上に整然と並び、
  探索述語を表すレイも(列述語の線形性ゆえ)グリッド軸に整列している。BVH 木と
  ray-triangle 交差はこの「行儀の良さ」を活かせず、(a) BVH 木は負荷不均衡・不規則
  メモリアクセス・メモリダイバージェンスで GPU 上で重い、(b) 幾何交差計算は計算量が
  大きい、という無用のオーバーヘッドを払う (p.2 "Is RT an Overkill?")。
- [paper] そこで「RT と同様のデータモデルを使いつつ、成熟したラスタライゼーション
  パイプラインで軽量にインデックスを実現できるか」を仮説として、RasterScan を設計・
  評価する。データは既にグリッド上の点なので画像としてモデル化し、探索レイは
  ラスタライズで描く線分に置換、幾何交差テストを高速な算術比較に置き換える
  (p.2 Contributions)。

## System model & assumptions
- [paper] 対象は数値列(比較のため RT 系手法と同じ土俵に限定)。現行実装は 4 byte 整数列を
  仮定。8 byte 整数や単精度/倍精度浮動小数への拡張はバッファのプリミティブ型と
  binning の実装変更のみで可能と主張 (§3, §7)。非数値列は辞書(順序型なら
  ソート順の添字)で整数化してから索引・問い合わせ (§7)。
- [paper] OLAP シナリオを仮定: インデックスは分析クエリ実行前に一度構築される。
  理由は (1) GPU を分析クエリ高速化のコプロセッサと位置付けるため、(2) 同じ仮定を置く
  RT 系手法との公平な比較のため。更新が必要でも build が速いので再構築コストは低いと
  主張 (§7)。
- [paper] クエリモデル: 範囲クエリ q = [l, r]。等値は l = r、< / > はドメインの
  最小/最大を l または r に設定して表現 (§4)。多列は最大 3 列を単一インデックスで、
  連言的(conjunctive)範囲クエリを扱う (§5)。n ≥ 4 列は RTScan 推奨の戦略に従い
  「3 列以下のインデックスを複数作り、個別に問い合わせて結果の積を取る」 (§5.1)。
- [paper] 実装は C++ と Vulkan(グラフィクスパイプラインを提供)。入力データは RTScan
  論文のエンコード(N 点を [0, N−1] に一意写像)を両手法で共通に使用し、出力構造も
  RTScan と同一に揃える (§6.1)。
- [paper] 並列実行モデル: ラスタライゼーションパイプライン(vertex shader → geometry
  shader → クリッピング+ラスタライズ → fragment shader → blending)の各段が SPMD で
  並列実行され、virtual screen(テクスチャへのレンダリング)を使う (§2, Fig. 3)。
- [paper] 同一ピクセルへ複数 fragment shader が書く際の正しさは atomicAdd()(原子的
  インクリメントして旧値を返す)で担保 (§3.2)。warp(Nvidia では典型 32 スレッド)の
  ストラグラー化を避ける設計判断が随所にある (§4.1)。
- [inference] インデックス(テクスチャ T + バッファ B)は GPU の VRAM に常駐する前提。
  評価でのフットプリントは 1.12GB(100M 行 × 3 列)で 4GB VRAM のラップトップ GPU でも
  動いているが (§6.4, §6.6)、VRAM を超えるデータの扱い(out-of-core)は本文に記述なし。
- [inference] 更新・並行実行・障害回復はスコープ外(§7 の update 拡張は設計スケッチのみ)。

## Approach
- [paper] **インデックス構造**: 物理的にはペア (T, B)。T は R×R 解像度のインデックス
  テクスチャで、各ピクセルが対応ビンへのポインタ(B 内の開始位置)を保持。B はインデックス
  バッファで、各エントリが「索引対象のデータ値 + 入力テーブル内の rid」を格納。データ点は
  テクスチャのピクセルに論理的に「ビニング」される (§3, Fig. 4)。
- [paper] **Build(2 フェーズ、点プリミティブのみ描画するため geometry shader 不使用)**
  (§3, Fig. 4):
  - Setup phase (§3.1): ビンのヒストグラムを作る。vertex shader が値 u を
    du = ⌈(u_max − u_min)/R²⌉ で bin i = ⌊u/du⌋ に写像し、row-major で 2D 位置
    (i mod R, ⌊i/R⌋) に変換 (Eq. 1–2)。fragment shader がピクセルごとにカウントを
    インクリメント(blend 操作で効率化)。トイ例: 14 値・R=4・値域 30 → du = ⌈30/16⌉、
    各ピクセルは [0,1], [2,3], …, [30,31] を担当 (Fig. 4a)。
    ※[inference] 本文の Eq. 2 は「i mod r」と表記されるが、文脈上 r はテクスチャ解像度 R の
    誤植と読むのが自然。
  - Bin assignment phase (§3.2, Fig. 4b): setup のカウントの exclusive prefix-sum を
    計算してそれを T とする(各ピクセル値 = B 内のビン開始位置)。T のコピー T′ で
    「次に挿入する位置」を動的に追跡し(assignment 終了後に破棄)、fragment shader が
    atomicAdd() で位置を取得して点(値, rid)をビンへ格納。
- [paper] **Search(2 パスのラスタライゼーションパイプライン)** (§4):
  - Index texture search (§4.1, Fig. 5a): vertex shader が l, r を build と同じ変換
    (Eq. 1–2)でピクセル位置 (x₁,y₁), (x₂,y₂) に写像。geometry shader は要求領域を覆う
    「T の完全な行の最小集合」に対応する単一矩形(対角 (0,y₁);(R,y₂+1)、三角形 2 枚で
    表現)を描く。矩形内には冗長ピクセルが含まれ得るが、fragment shader が
    (1) クエリ範囲外のピクセル、(2) 空ビンのピクセル、を破棄する。範囲内ピクセルは
    T のルックアップでビンの範囲 [st, en) を取得。
  - ビンを fragment shader 内でそのまま線形処理すると並列性を失い、分布が歪んでいると
    そのスレッドが warp 内の他スレッドのボトルネックになる。そこで [st, en) を 2D 点として
    Range Search バッファ S に書き出し、第 2 パスに委ねる (§4.1)。Fig. 5(b) の例では
    クエリ範囲内の populated ピクセルに対応する 7 レンジが S に入る。
  - Index buffer search (§4.2, Fig. 5b): d = S 中の最大ビンサイズ、R′ = ⌈√d⌉ として
    R′×R′ のビューポートを設定。vertex shader は S の 2D 点を素通しし、geometry shader が
    対角 (0,0);(R′, y_max) の軸平行矩形を生成。fragment shader はピクセル (x,y) を
    B 内位置 i = st + x + y·R′ に対応付け、i ≥ en なら破棄、さもなくば B[i] をクエリ範囲と
    算術比較で評価。これにより対象ビン内の全点が独立に処理され並列性が最大化される。
- [paper] **多次元拡張** (§5):
  - 2D: 列 C₁ の値域を x 軸、C₂ の値域を y 軸に一様分割し、(x,y) = (⌊u/du⌋, ⌊v/dv⌋)
    (Eq. 3) でビニング (§5.1)。※[inference] §5.1 の 2D ビンの範囲式は v 側の下限にも
    x が現れる表記になっており、これも誤植と思われる(意図は y·dv 起点のはず)。
  - 3D: T は C₁, C₂ で 2D のまま作り、B のエントリに 3 次元すべての値を格納 (§5.1)。
  - クエリ: vertex shader が [l₁,r₁], [l₂,r₂] を Eq. 3 でピクセル位置 2 点に変換、
    geometry shader はその 2 点を対角とする軸平行矩形(三角形 2 枚)を生成。buffer search の
    fragment shader は次元数に応じて点をクエリ範囲と評価する (§5.2)。
- [paper] **RT との本質的差分**: 探索が「BVH 走査 + ray-triangle 幾何交差」ではなく
  「テクスチャルックアップ + 単純な算術比較」になる (§6.3)。build も「BVH 構築の不規則
  メモリアクセス・同期」が「単純な算術と atomic increment」に置き換わる (§6.2)。

## Evaluation
- Setup [paper]: RasterScan は C++/Vulkan 実装(公開 [8] = github.com/Microsoft/raster-scan)、
  RTScan は公開コード [9] を使用。比較を「rasterization vs ray tracing」に純化するため
  Bindex ベースのフィルタは両者とも評価に含めない(データモデルが同様なので RasterScan
  にも適用可能と注記)。入力データのエンコードと出力構造は両手法で同一 (§6.1)。
- Metrics [paper]: index build 時間と、インデックス構築後にクエリを GPU 上で実行する
  時間(query response time)を分けて報告 (§6.1)。
- Testbed [paper]: RTX 4090(24GB VRAM)を主とし、旧世代 RTX 2080 Ti(12GB VRAM)と
  低電力 RTX A2000 Laptop GPU(4GB VRAM)でも評価 (§6.1)。
- Datasets [paper]: RTScan 論文 [7] と同一のデータセット・クエリワークロード。一様分布
  1 種(選択率の影響測定用)+ 歪みデータ 4 種(zipf 1.1 / 1.3 / 1.5、正規分布)。
  いずれも 1 億点 × 3 列の連合インデックス。1 列・2 列でも同様の傾向と注記 (§6.1)。
- Build [paper]: RasterScan は RTScan の約 50× 速く構築 (Fig. 6, §6.2)。
- Search(一様)[paper]: 選択率が上がるほど差が拡大し、選択率 0.7 では一桁以上
  (order-of-magnitude 超)高速。RasterScan の応答時間の傾きは緩やかで、選択率 0.1 の
  1.2ms → 0.7 の 2.3ms (Fig. 7a, §6.3)。
- Search(歪み)[paper]: 選択率 0.7–0.8 のクエリで、zipf/正規いずれも一様の場合と同傾向。
  「well over order-of-magnitude」の高速化 (Fig. 7b, §6.3)。
- GPU 世代 [paper]: 2080 Ti / A2000 では選択率の影響が 4090 より顕著。原因はメモリ帯域が
  遅いことと計算コア数が少ないこと (Fig. 8, §6.4)。
- パラメータ R [paper]: R = 512〜4096 を掃引(一様データ、選択率 0.3)すると
  「カップ型」で 1024×1024 が最良。R が小さいと探索レンジ数は減るが各レンジが大きくなり、
  buffer search の矩形が大きくなるトレードオフ。実装は R = 1024 を採用 (Fig. 9, §6.5)。
- メモリ [paper]: 1 億行 × 3 列でインデックス 1.12GB、build 中の中間構造 +1MB、
  クエリ中の中間構造 +2MB(結果格納分は別)。RTScan の BVH は 3GB [7] (§6.6)。
- [inference] 評価がカバーしていないもの:
  - ベースラインは RT 系(RTScan)のみ。同じ (T, B) 構造を通常の GPGPU(compute
    shader / CUDA)で実装した場合との比較が無いため、「raster が RT に勝つ」ことは
    示されても「グラフィクスパイプライン経由が素朴な GPU 実装より速い」ことは
    この論文からは判定できない。
  - 本文で報告される選択率は 0.1–0.7(一様)と 0.7–0.8(歪み)で、点クエリ相当の
    極低選択率レジームの数値は本文に無い(等値クエリの扱い自体は §4 に定義あり)。
  - Bindex フィルタ込みのフル構成 RTScan との絶対比較は意図的に除外されている (§6.1)。
  - CPU–GPU 間のデータ転送や結果の返送コストは metric の定義(GPU 上の実行時間)から
    外れている (§6.1)。
  - R = 1024 のスイートスポットは一様データ・選択率 0.3 の 1 設定で選ばれており (§6.5)、
    データ分布・列数・データサイズへの感度は示されていない。
  - §7 の更新対応(ページリスト化)は設計スケッチのみで未実装・未評価。

## Limitations
- Stated [paper]:
  - 現行実装は 4 byte 整数列のみ(他の数値型は小変更で対応可能と主張)(§7)。
  - 更新なしの OLAP 前提。更新が必要な場合の設計拡張(B をページのリスト化し、T の
    セルからリストを指す。insert はページ追記、delete は同様、update は delete+insert。
    texture search 段で S に「クエリ範囲を満たすセルに紐づく全非空ページ」のレンジを
    入れる)は提案のみ (§7)。
  - n ≥ 4 列は単一インデックスでは扱えず、複数インデックスの結果の積に落ちる
    (RTScan と同じ戦略)(§5.1)。
  - 解像度 R はレンジ数とレンジサイズのトレードオフを持つチューニングパラメータ (§6.5)。
- Inferred [inference]:
  - ビン内探索の並列度は「最大ビンサイズ d」でビューポートを決める設計 (§4.2) のため、
    ビンサイズの偏りが極端な場合(少数の巨大ビン + 多数の小ビン)は、小ビンの
    fragment の大半が i ≥ en の即時破棄になり、生成 fragment 数が無駄に膨らむ可能性が
    ある。歪みデータの評価 (Fig. 7b) はスループットのみで、この内部効率は示されていない。
  - du = ⌈(u_max − u_min)/R²⌉ の一様分割ビニング (§3.1) は値域ベースであり、
    値域が極端に広い/外れ値がある列では大半のピクセルが空になり、テクスチャ探索段の
    矩形が大きくなる。空ビンは fragment shader で破棄される (§4.1) が、そのコストの
    定量評価は無い。
  - 検索結果の出力(結果バッファへの書き出し・コンパクション)の仕組みは本文に説明が
    なく、「出力構造は RTScan と同一」(§6.1) と述べられるのみ。結果サイズが大きい
    高選択率クエリでの出力コストの内訳は不明。
  - 重複値の扱いは RTScan 由来のエンコード(N 点 → [0, N−1] の一意写像)に依存して
    おり (§1, §6.1)、このエンコード自体の構築コストが build 時間に含まれるかは
    本文からは読み取れない。

## Relations
- [paper] 競合・比較対象は本文中の RT 系インデックス: RTIndex(単一列、三角形 + レイ)
  と RTScan(≤3 列、キューブ + 短レイ分割 + エンコード。評価のベースライン)(§1, §6)。
  構造面では BVH は R-tree の一般化という位置付け (§1)。関連する RT 応用として
  空間インデックスライブラリ(LibRTS)や RT ベースのクエリ実行(RTCUDB)が言及される
  (§8, refs [1, 10])。
- 現在のノートコーパス(disaggregated memory / LSM / WAL / CXL / HTAP / トランザクション
  系が中心)には、GPU グラフィクスハードウェアによる索引・スキャンを扱うノートが無く、
  直接リンクすべき既存ノートは無し。[inference] 本ノートはコーパス内で
  「特殊ハードウェアの DB への転用(とその適否の見極め)」という新しい軸の起点になる。

## Idea seeds
- [inference] 本論文の核は「データとクエリがグリッド整列なら、汎用の幾何加速(BVH+RT)
  より固定機能のラスタライズ+算術比較が勝つ」という一般原理の実証で、RT 系 DB 研究全体
  への反例として機能する。ただし §6 の比較は raster vs RT に限られるため、第 3 の腕として
  「同じ (T, B) 構造の素朴な CUDA/compute shader 実装」を足した 3 者比較が最初の検証実験に
  なる。公開コード(github.com/Microsoft/raster-scan, §6.1)があるので追試コストは低い。
  これが出ると「グラフィクスパイプラインの固定機能(ラスタライザ・blend)自体の寄与」と
  「BVH を捨てた寄与」を分離でき、この種のハードウェア転用研究の評価方法論への示唆になる。
- [question] 更新対応(§7 のページリスト設計)を実装した場合、build が ~50× 速い (§6.2)
  ことを考えると、増分更新と周期的フル再構築のどちらが得か。更新レートを掃引して
  クロスオーバー点を測る実験が素直な第一歩。
- [question] n ≥ 4 列で「複数インデックス + 結果の積」(§5.1) に落ちるときの積集合コストは
  本文で評価されていない。列数を 3→6→9 と増やしたときの応答時間の劣化曲線を測れば、
  この手法群(RTScan も同じ制約)の適用限界が定量化できる。
- [inference] 著者ら自身が §8 で「クエリ実行や空間クエリ処理でも同様の考察(RT vs raster)が
  成り立つはず」と将来課題を明言している。空間結合や近傍探索は述語がグリッド軸に整列
  しないため、本論文の「well-behaved だから raster で十分」という前提がどこで崩れるかの
  境界を探る調査は、Phase 2 の課題候補として筋が良い。

## Changelog
- 2026-07-06: created (status: read)
