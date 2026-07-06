---
title: "An Evaluation of B-tree Compression Techniques"
authors: [Sikang Sun, Chuqing Gao, Shreya Ballijepalli, Jianguo Wang]
venue: "The VLDB Journal 35:4"
year: 2026
ids: {doi: "10.1007/s00778-025-00950-8", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1007/s00778-025-00950-8", pdf: "literature/pdfs/2026-vldbj-sun-btree-compression.pdf", code: "https://github.com/chuqingG/BtreeComp"}
status: read
read_date: 2026-07-06
tags: [btree, index-compression, prefix-compression, tail-compression, experimental-evaluation, storage-engines, page-layout, in-memory, disk-based]
---

## TL;DR
7つの B-tree 圧縮技術(Head / Tail / Head+Tail [1977年提案]、DB2、MongoDB WiredTiger、
MySQL MyISAM、PkB)を、著者らいわく史上初めて相互比較した実験評価論文
(SIGMOD'24 論文の拡張版)。合成・実データの双方で、最古の Head+Tail Compression が
検索 +25%〜120%、挿入 +10〜30%(対非圧縮)で一貫して最良と結論。さらに Lomet の
3最適化(prefix vector / unrolled binary search / key normalization)を現代環境で検証し、
prefix vector のみ有効(最大 +27%)と示す。

## Problem & motivation
- [paper] B-tree 圧縮は 1977 年の Prefix B-tree 論文 [18] 以来複数の手法(DB2、
  WiredTiger、MyISAM 等)が実システムに実装されてきたが、**これらが相互比較された
  ことは一度もない**。Head/Tail の有効性を示す実験結果も 1970 年代ハードウェアでの
  もの [18] しか存在しない (§1, abstract)。
- [paper] 圧縮の期待効果は3つ: ①空間削減(索引は DB 全体の約 50-55% を占めるとの
  Oracle ブログ [26]・研究 [58] の引用)、②金銭コスト削減(ディスクが全体コストの
  24%〜78% [19])、③クエリ性能向上(Head/Tail は無伸長のまま検索可能、キー比較長も
  短縮)(§1)。
- [paper] 本稿は SIGMOD'24 の実験論文 [30](結論: Head+Tail が最良)の拡張版で、
  新規貢献は §6 の Head+Tail 改良技術(prefix vector 表現・unrolled binary search・
  key normalization)の評価。新規分は少なくとも 30% と自己申告 (§1)。
- [paper] コードは公開: https://github.com/chuqingG/BtreeComp (§1 Open-source)。

## System model & assumptions
- [paper] 「B-tree」は B+-tree の意(全キーを leaf に格納)(p.1 脚注1)。
- [paper] **value は格納しない**(キーのみの索引)。値の導入は圧縮率をわずかに下げるが
  結論は変わらないと主張 (§3.1.2)。
- [paper] キーは可変長文字列としてモデル化し、比較はすべてバイト単位
  (先行研究 [9,12,18,19,21,43,52] に従う)(§3.1.2 Parameters)。
- [paper] ハード: Intel Xeon Gold 6330 @2.00GHz (x86)、128GB DRAM、
  L1/L2/L3 = 2.6MB/70MB/84MB、1.6TB NVMe SSD(帯域 R/W 1/3 GB/s、レイテンシ
  9/12µs)(§3.1.1)。C++ / GCC 11.4.0 -O3 / Ubuntu 22.04 (§3.1.2)。
- [paper] 各手法はソース非公開のものも含め著者らによる**再実装**。非 leaf 圧縮が
  オプションの手法では公平のため有効化。DB2 論文 [19] は検索方法を書いていないため
  prefix 層→suffix 層の 2 段 binary search を著者らが設計。MyISAM は MySQL ソース [8]
  の設計原理から、WiredTiger はソースコード [5] から実装 (§3.3)。
- [paper] split 方針: Tail は split radius r=1/6 の範囲 [(1−r)/2, (1+r)/2] から最短
  separator を選択(予備実験 Fig. 8 に基づく)。split 点の記載がない他手法は中央で分割
  (§3.3, Fig. 8)。
- [paper] WiredTiger の best prefix group は予備実験で挿入 ~50% 劣化・クエリ改善なし
  だったため無効化。roll-forward distance control はディスク実験のみ推奨値
  (skipping distance=10)で有効化 (§3.3)。
- [paper] ディスク実験の木の置き方: 大半の手法は**非 leaf ノードをメモリに置き、leaf
  ページのみディスク**。PkB は逆に完全キーをディスクへ、B-tree 全レベルをメモリに保持
  (§3.3)。
- [paper] デフォルト設定 (Table 2): ページ 512B (mem) / 4096B (disk)、キー数 100M、
  キー長 32B、ドメインサイズ(アルファベット)10、一様分布。§4.6 のみ正規分布の
  long number キー。20/80 の warm-up/run 方式、3 回実行の平均で分散は通常 1% 以内
  (§3.1.2, Table 2)。
- [paper] PkB の partial key 長: メモリでは原論文 [21] の最適値 2、ディスクでは
  予備実験 (Fig. 10) に基づき 5 バイト (§3.1.2, §4.1.2)。
- [paper] DB2 の prefix メタデータ総量はページの 25% を上限に設定 (§4.4.1)。
- [paper] 評価指標は圧縮率・検索時間(デフォルトは point query、range は §4.7)・
  挿入時間の3つ (§3.2)。
- [inference] 並行性(マルチスレッド、latch)への言及が本文に見当たらず、スループットは
  単一実行文脈と読める。ロギング・リカバリ・バッファプール置換も対象外。つまり
  「スタンドアロン C++ 実装のキーのみ B-tree」という強い抽象化の上での比較である。

## Approach
評価対象 7 手法の分類 (§2):
- [paper] **Tail Compression** [18]: leaf split 時に full key でなく最短 separator
  (= 左 leaf 末尾キーと右 leaf 先頭キーの LCP + 次の1文字)を親へ昇格。split 点を
  範囲内で選び separator をさらに短縮可能。非 leaf の separator 縮小 → fan-out 増・
  木の高さ減・比較短縮 (§2.1, Fig. 1, Fig. 2)。
- [paper] **Head Compression** [18]: ノード内キーの共通 prefix を1回だけ格納。prefix は
  現在のキー集合からでなく**親から来る最大下界と最小上界の共通 prefix** で決める
  (挿入時の再計算を不要にするため)。木の左端・右端ノードは界がなく非圧縮。検索は
  探索キー側を圧縮して suffix バイトのみ比較、伸長不要 (§2.2, Fig. 1)。
- [paper] **Head+Tail**: 両者の単純結合 (§2.3, Fig. 1d)。
- [paper] **DB2** [19]: ページ内に複数の (prefix, suffix) グループ。ページがほぼ満杯の
  時に prefix 最適化を起動し、Prefix Merge(Closed Range 概念でグループ統合)と
  Prefix Expand(prefix を伸ばし suffix を削る)のうち節約が大きい方を適用 (§2.4,
  Fig. 3-5)。
- [paper] **WiredTiger prefix compression** [12]: 隣接キーとの delta encoding
  (前キーとの共通 prefix 長 + suffix を格納、ノード先頭キーは full)。伸長は完全
  instantiate 済みキーまで後退→前進走査が必要。緩和策として best prefix group と
  roll-forward distance control(skipping distance ごとに1キーを instantiate)を持つ。
  suffix truncation は Tail 相当 (§2.5, Fig. 6)。
- [paper] **MySQL MyISAM** [9]: 表現は WiredTiger 同様の隣接 delta だが、ページ先頭から
  の**逐次検索**なので前キーから直接キーを構成でき instantiation 不要 (§2.6)。
- [paper] **PkB** [21](SAP HANA の CPB-tree はその変種 [22]): indirect key(ポインタ)
  方式で、base key(ノード先頭キーは探索時に比較される祖先キー、以降は直前キー)との
  相違開始 offset + l ビット(実装では l=2 バイト相当)+レコードへのポインタを格納。
  目的は空間でなく**CPU キャッシュミス削減**で、ノードあたり高々 1 回のポインタ参照で
  済むよう検索を設計 (§2.7, Fig. 7)。

Head+Tail への追加最適化(本誌版の新規部分、Lomet [46] の3技術を初めて実験検証)(§6):
- [paper] **Prefix Vector (PV)**: 各キーを固定長部(2/4/8B)+可変長部に分割し、固定長
  部を配列(vector)化して binary search をまず固定長部で行う。間接参照の削減と
  キャッシュ効率が狙い (§6.1, Fig. 26)。
- [paper] **Unrolled Binary Search (UBS)**: Shar のアルゴリズム [39] に基づき、最初の
  probe 以降の分岐と index 計算を除去し変位を定数として switch 文に埋め込む。"flip"
  時の境界過大評価により重複比較が生じ得る(比較回数は高々 ⌊lg n⌋+1)(§6.2, Algo. 1-2,
  Fig. 28)。
- [paper] **Key Normalization (KN)**: バイト単位でなく word 単位比較(little-endian では
  BSWAP 命令で変換)。prefix のみ正規化する KP と、全キー長を word 境界へ null padding
  する FN の2変種。Head Compression のポインタシフトと両立させるため、キーはノード
  挿入時に正規化 (§6.3)。

## Evaluation
- Setup [paper]: 合成データ(§4: キー数 1M〜100M、キー長、ページサイズ 256B〜16KB、
  ドメインサイズ 10/26/36/62、正規分布 scale、range query 10〜100)+実データ 4 種
  (Table 1: TPC-H LINEITEM SF10 60M 行・平均 129.58B、WEBSPAM-UK2007 25M URL・平均
  112.33B、WikiTitles 25M・平均 19.34B、MemeTracker 5.5M・平均 75.90B / 最大 21.2KB)。
- [paper] **メモリ・デフォルト設定 (Fig. 9, Table 3)**: 検索は Head+Tail が非圧縮比
  +48.2% で最高(Head 単体 +2%、Tail 単体 +23.5%)。挿入で非圧縮を上回るのは
  Tail と Head+Tail のみ。delta 系 3 手法は挿入が非圧縮比 WiredTiger −46.8% /
  PkB −7.3% / MyISAM −6.7%(WiredTiger は挿入時間の 44.6% が伸長)。DB2 は in-page
  検索時間の約 30% が prefix 検索。高さは Origin 9 → Tail/H+T/WiredTiger 6、fan-out は
  H+T 42.87 / WiredTiger 41.45 vs Origin 9.27。圧縮率は H+T と WiredTiger が最高で
  約 1.27x。PkB はメモリでは完全キー+圧縮キーの両持ちで**負の圧縮効果** (§4.1.1)。
- [paper] **ディスク (Fig. 11)**: 4KB ページでは PkB 以外どの手法も leaf アクセスは
  ディスク I/O 1 回で、固定コストが圧縮の相対利得を圧縮する。傾向はメモリと一致。
  Tail は高さ 5→4 の削減でなお有効 (§4.1.2)。
- [paper] **パラメータ感度**: キー数増で prefix 系の圧縮率はほぼ線形改善、Tail は
  separator 伸長で非 leaf 比率が 3.055%→3.507%(1M→100M)と劣化 (§4.2, Fig. 12)。
  ページサイズ増で MyISAM/DB2 の圧縮率は上がり Head/Tail は下がる。Tail の高さ削減
  効果は 256B ページで 13→8、2048B では 5→4 に縮む (Table 4, §4.4.1)。DB2 と Head の
  圧縮率は 2KB で逆転(複数 prefix が効き始める)(§4.4.1, Fig. 14)。ディスクでは
  2KB→16KB で prefix 系のどの手法も圧縮率 ~1.2 で頭打ち・スループットは漸減 (§4.4.2, Fig. 15)。
  ドメインサイズ増(10→62)で prefix 系の圧縮率は 1 へ漸近、Tail はほぼ不変(平均キー
  長変化 <0.2B)(§4.5, Fig. 16)。正規分布の集中度(scale)が小さいほど delta 系
  (MyISAM/WiredTiger)の圧縮率が急伸し、DB2 は Head と MyISAM/WT のほぼ中間
  (§4.6, Fig. 18)。scale < 1M では DB2/MyISAM の挿入も非圧縮を上回る (§4.6)。
- [paper] **Range query (Table 5)**: 伸長不要の Tail が常に最良。メモリでは伸長を要する
  (prefix 系含む)全手法が非圧縮を下回る。PkB のディスク range は partial key と
  full key の分離で局所性が消え壊滅的(range 10 で 30.66 vs 非圧縮 275.23 Kop/s)
  (§4.7)。
- [paper] **実データ (§5)**: TPC-H は複合キーを単一列に連結して索引化、列 separator の
  ため prefix 圧縮は第1列にしか効かず、suffix 切詰め系が優位。H+T が throughput・
  圧縮率とも最良 (Fig. 19, §5.1)。URL 系(WEBSPAM/MemeTracker)は delta 系が
  空間で優位、DB2 は長い共通 prefix +メタデータ過多で Head より劣る (Fig. 20-21,
  §5.2)。WikiTitles(平均項目長 23.73B)では MyISAM の圧縮率は高いが相対 throughput
  は低い (Fig. 22, §5.3)。深掘り (§5.4): 検索性能は木の高さに強く支配され
  (Table 6)、TPC-H→MemeTracker で平均比較長 8.92→25.67B、比較時間比率
  62.5%→71.2%。MyISAM は圧縮率 2 以上で競争力を持つ (Fig. 23-25)。
- [paper] **Head+Tail 最適化 (§6)**: PV は全変種で改善、H+T では挿入 +27.6% / 検索
  +26.1%、Head 単体では +37.2%/+36.8%(prefix 同士の相性)。追加ノードは +0.004% と
  無視できる (Table 7)。prefix 長は 4B が最良 (Table 8)。ただし 100K キー以下では
  内部フラグメンテーションで PV が逆効果、16KB ページでは効かない (Fig. 27)。
  UBS は比較関数呼び出しが +6.01%/+5.83% 増え (Table 10)、throughput は挿入
  1.021 (−10.3%) / 検索 1.0811 (−5.92%) と**悪化** (Table 9)。KN は KP が
  +4.6%/+2.9%、FN が +4.9%/+2.6% だが FN は総ノード数 +7.3% の空間代償
  (Table 11)。
- [paper] **総括 (§8.1)**: H+T は検索で非圧縮比 +25%〜120%、DB2 比 21.7%〜90.2%、
  WiredTiger 比 129%〜684%、MyISAM 比 7.3%〜139% 高速。挿入は非圧縮比 +10〜30%。
  空間は H+T と WiredTiger がトップ2で圧縮率 1.2x〜3.5x。ランダムキーでは H+T、
  意味を持つ実データ(名前・文・URL)では WiredTiger/MyISAM が最も空間効率的。
  推奨は Head+Tail + PV (§8.2)。
- [inference] 評価がカバーしないもの: ①並行実行(スレッドスケーラビリティ、latch/
  ロックカップリングとの相互作用)、②実 DBMS 内での挙動(バッファプール・WAL・
  vacuum 等との干渉。PostgreSQL/MySQL への実装は future work と明言 (§8.3))、
  ③update/delete を含む混合ワークロード(指標は挿入と検索のみ (§3.2))、④value 込み
  のページレイアウト、⑤ディスク実験は非 leaf を常にメモリ常駐させており、内部ノード
  もエビクションされ得る本物のバッファプール構成での圧縮効果は未測定 (§3.3 の設定
  からの帰結)。
- [question] Table 9 の数値(挿入 −10.3% / 検索 −5.92%)と本文 §6.2.2 の記述
  (「search throughput (−10.3%)、insertion throughput (−5.92%)」)は割当てが逆で
  矛盾している。1.137→1.021 の算術からは −10.2% が挿入側なので表が正しいと読めるが、
  引用時は要注意。

## Limitations
- Stated [paper]:
  - DB2 の prefix 検索オーバーヘッドの fine-tuning は本稿のスコープ外 (§4.1.1)。
  - PkB をそのままディスクへ移すのは不適(range query で大量 I/O)(§4.7)。
  - UBS は DB のような比較コストが高い環境では有効でない (§6.2.3)。FN は suffix 比較が
    多い稀なケース以外不要 (§6.3.2)。
  - 実 DBMS への統合・複合キー最適化・ハードウェア別最適化・ML 活用は future work
    (§8.3)。
- Inferred [inference]:
  - 全手法が著者らの再実装であり、比較の妥当性は再実装の忠実さと最適化の均質さに
    依存する。特に DB2 の検索は原論文に記載がなく著者ら設計の 2 段 binary search
    (§3.3)なので、「DB2 が遅い」という結論の一部は実装選択の産物であり得る
    (著者ら自身も prefix 検索の作り込みがスコープ外と認めている)。
  - WiredTiger は本来 disk/メモリ混成の設計を丸ごとメモリに移した上、best prefix group
    を無効化して評価しており (§3.3)、製品文脈(ディスク上の圧縮ページ+ブロック圧縮
    併用)での性能を代表しない可能性がある。
  - 合成データのデフォルト(一様ランダム・ドメイン 10・32B)は prefix 共有が確率的に
    決まる人工的な設定で、§8.1 自身が認める通り実データでは空間の勝者が逆転する。
    「H+T 推奨」は検索/挿入性能を空間より重く見る価値判断を含む (§8.2)。

## Relations
- 既存ノート群(CC・WAL・LSM・分離ストレージ系)と直接の build-on/compete 関係は
  なし。
- [inference] テーマ的隣接: [[2026-pvldb-zhao-sidle]] とは「索引のメモリコストを
  どう抑えるか」で補完的 — 本稿は圧縮で索引自体を 1.2〜3.5x 縮める路線 (§8.1)、
  SIDLE は安い階層へ置く路線。圧縮率が上がるほど階層配置の損益分岐が動くはずで、
  組み合わせの検討余地がある(本稿は CXL/階層メモリに言及しない)。

## Idea seeds
- [inference] §6.1.2 の異常観察(2B prefix の方が 4B より総ノード数が少ない;prefix
  サイズの微差が separator 選択を通じて木全体の密度に波及)は、著者ら自身が「split
  interval prediction や事後的な separator 再計算」の最適化余地を示唆している (§6.1.2)。
  公開コード(BtreeComp)上で separator 長を考慮した split 点予測器を実装し、ノード数
  と挿入 throughput への効果を測るのが最初の実験として安価。
- [question] Head Compression の prefix は親由来の界から決まる (§2.2) ため、split の
  たびに界の更新がノード内容の再圧縮に波及し得る。並行 B-tree(OLC / latch coupling /
  Bw-tree 系)でこの更新がどれだけ contention を生むかは本稿の単一実行評価では見え
  ない。BtreeComp に OLC を足してスレッドスケールを測る検証が考えられる。
- [inference] ディスク実験は非 leaf を全部メモリ常駐 (§3.3) にしているが、Table 3 の
  fan-out(9.27→42.87)を信じるなら Head+Tail は内部ノードのワーキングセットを
  ~6x 縮める。バッファプール容量を絞った(内部ノードもミスする)構成では、本稿の
  測定より圧縮の利得が大きく出る可能性がある。バッファプール付き実装での再測定は
  future work の PostgreSQL 統合 (§8.3) より軽い中間検証になる。

## Changelog
- 2026-07-06: created (status: read, Springer 公開 PDF 全文を読解)
- 2026-07-06: 検証パスによる修正(§4.4.2 の圧縮率 ~1.2 頭打ちを prefix 系手法に限定;UBS の比較回数上界を ⌈lg n⌉+1 → ⌊lg n⌋+1 に訂正;PV が効かないページサイズを「16KB 超」→「16KB」に訂正)
