---
title: "Efficient Temporal Subgraph Management: A New Interval Index"
authors: [Dian Ouyang, Yikun Wang, Dong Wen, Wenjie Zhang, Yaping Liu, Xuemin Lin]
venue: "Proceedings of the VLDB Endowment (PVLDB), Vol. 19, No. 6, pp. 1170–1183"
year: 2026
ids: {doi: "10.14778/3797919.3797926", arxiv: "", dblp: "journals/pvldb/OuyangWWZLL26"}
urls: {paper: "https://www.vldb.org/pvldb/vol19/p1170-wen.pdf", pdf: "literature/pdfs/2026-pvldb-ouyang-interval-index.pdf", code: "https://github.com/iykw/TEM-Graph"}
status: read
read_date: 2026-07-06
tags: [interval-index, temporal-graph, range-query, allen-algebra, index-maintenance, streaming-updates, in-memory-index]
---

## TL;DR
temporal graph のマイニングで得られる大量の temporal subgraph(= 活動区間付きレコード)に対し、
クエリ窓に含まれる(sub-valid)/窓を覆う(super-valid)ものを列挙する interval index
「TEMS-Graph」を提案。end-time 順に並べたノード間に「無効ノードをスキップする」ための有向
エッジ(planar な DAG)を張り、さらに各エッジに successor ポインタを持たせて二分探索を排除する。
空間 O(n)・構築 O(n)・クエリ O(k+log n)(k は結果数)・追記型挿入は変更量 Δ に比例(文脈内で
最適と主張)・削除 O(1)。interval tree / HINT 比で sub-valid クエリ最大 2 桁の高速化を主張。

## Problem & motivation
- [paper] temporal subgraph(モチーフ、コミュニティ等)の集合から、指定時間窓に関係するものを
  取り出すのは temporal graph 分析の共通かつ基本的なタスク (§1)。sub-valid = subgraph の窓が
  クエリ窓に含まれる(s.start ≥ t_s ∧ s.end ≤ t_e)、super-valid = subgraph の窓がクエリ窓を
  覆う(s.start ≤ t_s ∧ s.end ≥ t_e)(§2, Def. 2.1, Def. 2.3)。
- [paper] 応用例: SNS のコミュニティ検出(試験前週の活動コミュニティ)、金融不正検出
  (規制期間内の三角アービトラージ等のモチーフ)、サイバー攻撃検出(深夜 0–4 時の DoS)(§1)。
- [paper] sub-valid は Allen's algebra の Contains 述語に等しく、fundamental interval range query
  の一種 (§1, §3)。
- [paper] 実世界の temporal subgraph は高ボリューム(1 本のエッジが多数の subgraph に現れる)・
  大きな重なり・頻繁な更新という特性を持ち、既存 interval index はこれに合わない (abstract, §1)。
- [paper] interval tree [16] の欠点: sub-valid でも Overlaps 候補全体の検証が必要で、クエリ時間は
  O(k_o + log n)(k_o = クエリ窓と重なる区間数 ≥ k)。区間が互いに包含し合う temporal subgraph
  ではバランスも崩れやすく、更新はノード内の start/end ソート済みリストの並べ替えが必要で
  高コスト (§3.1, Table 1)。
- [paper] HINT [8,9](SOTA の in-memory interval index)の欠点: 階層的な一様パーティションに
  区間を非冗長に割り当てる設計だが、sub-valid ではクエリに関係する最初〜最後のパーティションの
  全区間走査が要り、コストを k で bound できない。またドメインを事前に知る必要があり、
  edge stream でドメインが拡大するとパーティションと割当の再調整が必要 (§3.2)。空間は
  O(nφ)(φ はデータセットのドメインと平均区間長で決まる係数)(Table 1)。
- [paper] Table 1 の比較: 提案手法のみが sub/super-valid とも O(k+log n)・空間 O(n)・更新対応を
  同時に達成(著者らの知る限り既存研究に無い)(§1 Contributions, Table 1)。
- [paper] ケーススタディ(College データセット = UC Irvine 学生のメッセージ網、2004 年 4–10 月):
  月初起点・窓長 7–30 日の sub-valid クエリ群で、5 月のコミュニティ数が他月より 1 桁多い、
  5 月はコミュニティの約 4‰–15‰ が 2–3 日で形成される(他期間には見られない)、9 月の新学期に
  star 型パターンが再活性化する、といった傾向を抽出 (§1, Fig. 2)。
- [paper] 位置付け: subgraph mining / continuous subgraph matching(発見側)を補完し、列挙
  アルゴリズムが生成した subgraph インスタンス+活動区間の管理・検索を担う。既存マイニング
  パイプラインとシームレスに統合できると主張 (§1)。

## System model & assumptions
- [paper] 入力は temporal subgraph の集合 S。temporal graph の各エッジは (u, v, t) の 3 つ組で、
  subgraph の窓 [s.start, s.end] は含まれるエッジの最小/最大タイムスタンプ (§2)。
- [paper] subgraph の生成(列挙)自体は本手法の外側(既存のマイニング/列挙アルゴリズム)が
  担う (§1, §7)。
- [paper] start / end はユニークと仮定(実際には subgraph ID でタイブレーク)。窓は閉区間で、
  開区間にも自明に適応可能 (§2)。
- [paper] 更新モデルは append-only の edge stream: 新着エッジの時刻は既存の全タイムスタンプより
  大きく、したがって新しい subgraph の end time は既存の全 subgraph より大きい (§5.2)。同一
  end time の複数挿入は start 昇順を仮定(radix sort で線形時間に強制可能)(§5.2)。削除は
  最古エッジの失効によるもので、常に start-time 順の先頭ノードを消す戦略を取る (§5.3)。
- [paper] in-memory index として設計・評価(空間コストはメモリ使用量として計測、Fig. 11;
  比較対象の HINT を in-memory interval index の SOTA と位置付ける §1)。
- [paper] 紙幅の都合により証明は artifact 収録の complete version に置かれている (§2)。
- [inference] 並行アクセス(クエリと更新の同時実行)、永続化、障害回復は扱われていない。
  §7 の実験はクエリを逐次実行しており、並列化の記述も無いため単一スレッド前提とみられる。

## Approach
- [paper] 基本アイデア: 全 subgraph を end-time 順に並べれば、クエリ [t_s, t_e] は「end が窓内」の
  範囲を二分探索+順次走査で見つけられる。問題は start < t_s の無効 subgraph の走査であり、
  これをスキップするためのグラフ構造を設計する (§4.1)。
- [paper] **TEM-Graph** (§4.1, Def. 4.1): ノード = subgraph。v が u の out-neighbor ⇔
  (i) v.end > u.end、かつ (ii) v.end > w.end > u.end なる w で w.start > min(u.start, v.start) と
  なるものが存在しない。out-neighbor は end 昇順に並ぶ(条件から start も昇順になる)。
  仮想 head ノード h(h.start = ∞, h.end = −∞)を置き、最初の valid ノードも同じ機構で探す
  (§4.1)。Fig. 1 の例からの構築例が Fig. 3。
- [paper] TEM-Graph は planar graph であり (Lemma 4.3)、空間計算量は O(n) (Theorem 4.4)。
- [paper] クエリ原理: valid ノード u の次の valid ノードは「u の out-neighbor のうち
  start ≥ t_s なる最初の v」であり、v.end ≤ t_e なら v が答え、さもなくば以降に valid は無い
  (Theorem 4.5)。エッジ定義の条件 (ii) により、end 順で u と v の間にあるノードは全て start が
  小さい(=無効)ことが保証される (Lemma 4.7, Lemma 4.8)。out-neighbor 上の二分探索
  (Algorithm 1, O(log n))を結果ごとに繰り返して O(k·log n) (§4.1)。
- [paper] **O(k+log n) 化 = TEMS-Graph** (§4.2): 各エッジ (u,v) に successor を格納する。
  successor は「v の out-edge (v,w) で、(1) w.start ≥ min(u.start, v.start)、(2) それより
  start の小さい候補 (v,w') が無い」もの (Def. 4.10)。満たすエッジが無ければ v の最後の
  out-edge、v に out-neighbor が無ければ Null。各 out-neighbor を ⟨id, successor(オフセット)⟩
  ペアで持つ (§4.2)。クエリ時は前ラウンドの valid ペア (u,v) の successor で候補 w に跳び、
  v の out-neighbor リストを後ろ向きに線形走査して最初の valid を見つける(二分探索排除)
  (§4.2, Algorithm 2)。全体の時間計算量は O(k + log n) (Theorem 4.12)。
- [paper] **構築** (§5.1, Algorithm 3): end-time 順の doubly linked list (DLL) を作り、初期
  out/in-neighbor は DLL の隣接ノード。次に start-time 順に「start 最小のノード v」を DLL から
  繰り返し削除し、その前後 u, w を直結してエッジ (u,w) を追加する(削除済みノードは start が
  小さいので Def. 4.1 の条件 (ii) を構成的に満たす)。successor は「in-neighbor と out-neighbor
  がともに start 昇順に並び、in-neighbor の successor が非減少に伸びる」性質を使い、各ノードで
  2 ポインタの一回走査で一括計算。全体で O(n) (Theorem 5.3)。
- [paper] **挿入** (§5.2, Algorithm 4): 新ノード w は end 順の末尾なので out-edge は生じず、
  in-edge の追加と既存エッジの successor 更新のみ。in-neighbor は「latest incoming edge
  (start 最大の in-neighbor)」を辿って順次決定する(Lemma 5.4 / Lemma 5.5 が正しさと完全性を
  保証)。successor 更新は、v の既存 in-edge を 3 分類 — case 1: successor (v,w') が
  min(u.start,v.start) < w'.start を満たす(変更不要)/ case 2: 最後の out-edge が successor に
  なっていた / case 3: successor = Null — したとき case 2/3 のみ新エッジ (v,w) に変更すれば
  よい。in-edge は source の start 昇順に並ぶため case 3 → case 2 → case 1 の順に後ろから
  現れ、逆順走査して case 1 に当たったら打ち切れる (§5.2, Lemma 5.6)。時間計算量は
  O(Δ)、Δ = w の in-neighbor 数 + successor が変わるエッジ数(= index 内の変更値のサイズ)で、
  この文脈で最適と主張 (Theorem 5.8)。
- [paper] **削除** (§5.3): start-time 順の先頭ノード v を削除する。このとき v の in-neighbor /
  out-neighbor はちょうど 1 個ずつ(end 順の前後 u, w)であり、v は u の out-neighbor リストと
  w の in-neighbor リストの先頭要素なので、リスト先頭位置のインジケータをインクリメントする
  だけで削除でき O(1) (Theorem 5.9, Fig. 5)。削除される 2 エッジ (u,v), (v,w) が残存エッジの
  successor になり得ないことも論証 (§5.3)。start 順先頭の特定は「start ごとの 2 次元配列
  (同一 start 内は end 昇順)」で、挿入時も末尾追加のみで維持できる (§5.3)。
- [paper] **super-valid への拡張** (§6): 対称な Sup-TEMS-Graph(v が u の out-neighbor ⇔
  v.end < u.end かつ介在ノード条件が max(u.start, v.start) 基準、out-neighbor は end 降順、
  head は h.start = −∞, h.end = ∞)を定義 (Def. 6.1, Fig. 6)。クエリ (Algorithm 5) の空間・
  時間計算量は Theorem 4.12 と同じ。構築・挿入・削除も同様で同じ計算量が成り立つ(詳細は
  紙幅で省略)(§6)。
- [paper] その他の Allen 述語: Overlaps は Algorithm 5 の自明な変更で O(k+log n)、Starts /
  Finishes は super-valid の特殊ケースとしてサポート可能 (§6)。

## Evaluation
- Setup [paper]: 全アルゴリズム C++ 実装、g++ -O3、Intel Xeon 2.80GHz / 500GB RAM の Linux 機
  (§7)。データは SNAP の実 temporal graph 6 種に対し、一般的パターン(triangle, square,
  k-clique, k-star)を一様サンプリングして subgraph 集合を生成 (§7)。規模はドメイン 193–2,774 日、
  College(頂点 1,899 / エッジ 59,835 / subgraph 2.39 億)〜 Stack(頂点 260 万 / エッジ
  6,350 万 / subgraph 42.95 億)。平均区間長はドメインの 21.30–47.97% で重なりが大きい
  (Table 2)。全体で 40 億超の subgraph を含む (§1 Contributions)。
- クエリ生成 [paper]: t_s をドメインからランダムサンプルし、窓長 1 時間〜90 日(約四半期)を
  変化。各グループ 1,000 クエリを逐次実行し、平均クエリ時間と hit rate(アクセスした subgraph
  数に対する valid 結果の比率)を報告 (§7)。
- Baselines [paper]: interval tree(公開実装 github.com/ekg/intervaltree)、HINT(公開実装
  github.com/pbour/hint)、Brute-force(start 昇順ソート+二分探索+順次走査)(§7)。
- Exp-1 sub-valid (Fig. 7): 小さい窓で baseline 比 1–2 桁高速。hit rate は 3 baseline とも 10%
  未満に対し TEMS-Graph は 40% 超(out-neighbor 経由で valid 結果に直接ジャンプできるため)。
  窓 90 日では差が縮まり、brute-force が index 空間オーバーヘッド無し+逐次アクセスのキャッシュ
  局所性で有効になる (§7)。
- Exp-2 super-valid (Fig. 8): 窓が広いほど覆う subgraph が減り実行時間は減少。HINT は hit rate が
  急落(Wiki で約 100% → 約 10%)し baseline 中最低のクエリ効率。TEMS-Graph は全 baseline に
  一貫して勝ち、hit rate は全テストケース平均で約 80% と安定 (§7)。
- Exp-3 synthetic (Fig. 9): 頂点集合と時間ドメインを固定しエッジを 20–100% サンプル([1] と
  同様の方法)。密度が上がるほど valid 結果が増えて全手法の時間が伸びるが、TEMS-Graph と
  baseline の差は密なグラフほど開く (§7)。
- Exp-4 pattern query (Fig. 10): 窓+パターン種別を指定するクエリでは、パターン別に index を
  分ける Separate が単一 index の Mix を 2–5 倍上回る(Mix は窓内全件を取ってからパターンで
  フィルタするため hit rate が下がる)(§7)。
- Exp-5 構築 (Fig. 11): TEMS-Graph の構築時間は interval tree と同程度でクエリ性能は大幅に上。
  HINT は全データセットで構築時間最大。空間は interval tree と TEMS-Graph が線形で同程度、
  HINT は φ 係数のため最大 (§7)。
- Exp-6 更新 (Fig. 12, Table 3): end 順 5 分割のバッチ挿入では、累積 index 構築時間がデータ量に
  線形に伸び、全量一括構築の時間に収束(Theorem 5.8 の解析と整合)。[8,9] に倣い 80% 構築 →
  残り 20% を挿入、また 20% が消えるよう失効タイムスタンプを選んで削除を評価した平均コストは、
  全データセットで 1 subgraph あたり 1μs 未満(構築 0.026–0.238μs、挿入 0.043–0.310μs、削除
  0.011–0.078μs)。一方、エッジ 1 本あたりの subgraph 生成(列挙)コストは 0.015–25.328 秒で、
  密/大規模グラフでは列挙が主ボトルネック、index 更新は無視できるオーバーヘッドと結論
  (§7, Table 3)。HINT のドメイン拡大版 [10] は Overlaps のみ実装で削除未対応のため、更新比較
  からは除外 (§7)。
- [inference] 評価がカバーしていないもの:
  - 評価対象の subgraph 集合はパターンの一様サンプリングによる生成で、実際のマイニング出力
    (時間的に偏在するモチーフ分布)での hit rate・性能は未検証。
  - out-of-order の挿入・任意タイミングの削除の実験は無い(そもそも設計上サポート外、§8)。
  - 並列クエリ・並行更新下のスループットは未測定(クエリは逐次実行)。
  - sub-valid の hit rate 40% 超は「アクセス数 ≈ 結果数の 2–2.5 倍」を示唆する。O(k+log n) の
    定数項(successor 経由の後ろ向き走査で触れる無効ノード)の内訳分析は無い。

## Limitations
- Stated [paper]:
  - 挿入は「最新 end time を持つノードの追記」、削除は「最古 start のノードの失効」に限定
    (§5.2, §5.3)。out-of-order の挿入・削除(ad hoc interval updates)を効率的に扱う
    メンテナンスは進行中の将来課題で、それができれば汎用の dynamic interval index になると
    展望 (§8)。
  - 大きなクエリ窓(90 日)では優位が縮小し、brute-force が単純さとキャッシュ局所性で競争力を
    持つ (§7 Exp-1)。
  - エンドツーエンドのストリーミング処理では subgraph 列挙が主ボトルネック(index 更新は
    誤差程度)。スケーラビリティ向上には既存の continuous subgraph matching 技術の統合が必要
    (§7, Table 3)。
- Inferred [inference]:
  - 挿入コスト O(Δ) の Δ(新ノードの in-neighbor 数+successor 変更エッジ数)は「変更量に
    比例するから最適」という相対的な主張であり、Δ 自体の n に対する最悪値は論文中で bound
    されていない。実測平均は <1μs (Table 3) だが、敵対的な区間列(例: start が単調減少する
    ネスト区間列)での挙動は不明。
  - 削除の O(1) は「消すのは常に start 最古で、それが隣接リストの先頭に居る」ことに依存する。
    subgraph ごとに失効時刻が異なる(TTL 非一様な)ワークロードではこの前提が崩れ、§8 の
    ad hoc 更新問題に帰着する。
  - 隣接リストの先頭削除をインジケータの前進で実装しているため (§5.3)、配列領域の物理的な
    回収(コンパクション)がいつどう行われるかは記述が無く、長期稼働時のメモリ膨張の有無は
    読み取れない。

## Relations
- 本文内の比較対象: interval tree [16] と HINT [8,9](+ 索引無しの Brute-force)(§3, §7)。
  timeline index / period index は sub/super-valid 対応済みだが HINT に 1–2 桁劣るとの引用 (§3.3)。
  HINT のドメイン拡大版は LIT [10] (§3.3, §7)。
- [inference] 既存ノートコーパス(storage engine / トランザクション / disaggregated memory 系が
  中心)には、temporal graph の interval index を直接扱うノートは無い。本ノートはコーパス内で
  独立したトピック(interval range query / 時間付きデータの索引)の最初のエントリとして扱う。

## Idea seeds
- [inference] TEMS-Graph の中身(end 順+スキップエッジ+successor)は subgraph 固有ではなく
  任意の区間集合に適用できる(§8 自身が general-purpose dynamic interval index 化を展望)。
  DB システム文脈では、MVCC のバージョン可視性判定([begin_ts, end_ts] とスナップショットの
  包含関係)や temporal DBMS の time-travel クエリが同型の interval containment 問題であり、
  「新規バージョンはコミット順に生まれる」という性質は TEMS-Graph の append-only 挿入モデル
  (§5.2)とよく合う。最初の検証: 公開コード(https://github.com/iykw/TEM-Graph, p.1)に
  TPC-C 履歴から生成したバージョン区間トレースを流し、素朴なバージョンチェーン走査と
  スキャン量を比較する。
- [question] out-of-order 挿入(§8 の open problem)は、LSM 的な「新着はサイド構造にバッファ
  して定期マージ」で回避できるか。小さな TEMS-Graph を複数持ち、クエリ時に各構造の結果を
  マージすれば O(Σ(k_i + log n_i)) で済むはずだが、構造数 L とマージコストのトレードオフ、
  および削除(失効)との整合は自明でない。検証: 2 構造構成のプロトタイプで挿入順序を
  シャッフルした際の劣化を測る。
- [inference] Table 3 の「index 更新 ≪ subgraph 列挙(最大 25.3 秒/エッジ)」という結果は、
  ストリーミング環境の真のボトルネックが索引でなく列挙側にあることを示す。研究機会は index
  単体の改良よりも「列挙と索引更新の協調」(列挙器が持つ end 順の中間状態を Insert の
  in-neighbor 計算に流用する等)にありそう。まず公開コードで列挙器と Algorithm 4 の間で共有
  可能な中間情報を洗い出すコード読みから始める。

## Changelog
- 2026-07-06: created (status: read)
