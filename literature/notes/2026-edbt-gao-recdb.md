---
title: "RecDB: An LSM-Tree based Storage System for Training Large Recommendation Model in Low-Resource Scenarios"
authors: [Ming Gao, Qingyin Lin, Zhitao Chen, Yunling Chen, Zhiguang Chen]
venue: "EDBT '26 (24-27 March 2026, Tampere, Finland)"
year: 2026
ids: {doi: "10.48786/edbt.2026.37", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.48786/edbt.2026.37", pdf: "literature/pdfs/2026-edbt-gao-recdb.pdf", code: "https://github.com/magicalcloud/RecDB_Paper"}
status: read
read_date: 2026-07-06
tags: [lsm-tree, ssd, compaction, embedding-tables, recommendation-model, prefetching, block-cache, read-amplification, garbage-collection, rocksdb, hot-cold-separation, larger-than-memory]
---

## TL;DR
低リソース環境(小さい DRAM + 1台の NVMe SSD)で推薦モデルの巨大 embedding table を
SSD にオフロードして学習する際、LSM-Tree は書き込みには向くが、①ランダム読みでの
block cache 非効率(read amplification)、②旧値(outdated data)の蓄積、③compaction と
読みの資源競合が残る。RecDB は RocksDB 拡張として、(1) look-ahead した読み要求列を
ソートし hot key に特殊 prefix を付けて hot データを同一ブロックに集める Request
Preprocessor、(2) 「読まれた値は backward pass 後に必ず更新される」という学習特有の
対称アクセスから旧値の所在をファイル単位でカウントし、旧値密度の高いファイルを
compaction 対象に選ぶ Compaction Picker、(3) prefetch バッファの残量が compaction 時間を
上回るときだけ compaction を許す Compaction Scheduler を導入。RocksDB 比で end-to-end
学習 1.03×–2.94× の高速化を主張。

## Problem & motivation
- [paper] 深層推薦モデルの embedding table は成長を続けており、Facebook の DLRM では
  数 GB から数 TB へスケールした。小規模ベンダー・研究者には学習が高コスト化 (§1, p.1)。
- [paper] CPU メモリへのオフロードより SSD への オフロードが費用効率的:
  Google Cloud で 1.4TB CPU メモリのサーバは $10.6/h、1.4TB SSD + 32GB メモリの
  サーバは $0.6/h (§1, p.1)。
- [paper] embedding table へのアクセスは強いランダム性を持ち、ブロックデバイスに
  不向き。自環境 SSD の帯域は 128KB sequential read 2.30GB/s / write 1.55GB/s に対し、
  4KB random read 1.91GB/s / write 1.34GB/s (Table 1, p.2)。
  - [inference] Table 1 のデバイス生帯域の差は read で 17% 程度と小さい。本文の主要な
    敵は生帯域ではなく「ブロック単位アクセス × 小さい(144B)ベクトル」による
    増幅(有効バイト率)で、実際 §3.1.1 の増幅測定がそれを裏付ける構図。
- [paper] SSD の書き込み粒度は典型的に 4KB で、144B の embedding vector の in-place
  更新でもブロック全体の書き換えが要る(write amplification)。out-of-place 更新で
  緩和できるが、AIbox 流のハッシュ索引は 10^10 ベクトルの索引に 149GB の CPU
  メモリを要する (§1, p.2)。読みもブロック単位で read amplification が発生。
  OC-DLRM は hot ベクトルを同一 flash block に集めるが Open-Channel SSD 前提 (§1, p.2)。
- [paper] LSM-Tree は乱雑更新をメモリでバッファし sequential write で flush するため
  小メモリで書き込み効率が良く、既存研究も embedding 格納に採用してきたが、
  LSM-Tree 自体が持ち込む課題は無視されてきた (§1, p.2)。課題は3つ:
  1. **Read amplification** (§3.1.1): 読み要求列が無秩序なため同一ブロックが 1 iteration
     内でも繰り返しロードされる(実験では最大 47% のデータブロックが単一 iteration 内で
     重複ロード、Fig. 5)。さらにアクセスは強く偏り(アクセスの 99% 超が 1% の
     ベクトルに集中)、LSM-Tree は hot/cold を同一ブロックに混在させるため、hot を
     含むブロックのロードが cold を道連れにし帯域とキャッシュを浪費。測定した
     read amplification(実ロード量/有効データ量)は SSD 起因 28 に対し LSM-Tree で
     124(4 倍超)(§3.1.1, p.3–4)。
  2. **旧値の蓄積** (§3.1.2): update-intensive な学習ワークロードで outdated data が
     SSD 空間を浪費する。compaction 対象の選び方で削除効率が変わる(Fig. 4 の例:
     最大ファイル優先の従来戦略は旧値 1 個削除、別選択なら 2 個)が、従来の
     LSM-Tree は旧値の所在情報を持たず最適選択ができない (§3.1.2, Fig. 4)。
  3. **Compaction 干渉** (§3.1.3): LSM-Tree はレベルサイズ閾値超過で盲目的に
     compaction を起動し、embedding lookup の read スレッドと資源競合する。
     compaction サイズ次第で read レイテンシは最大 258% 増 (Fig. 6, §3.1.3)。
- [paper] 一方で機会も3つ (§3.2): ①学習は将来の embedding index が予測可能
  (offline は自明、online も1日分のログをデータセット化して逐次学習するため)。
  既存 prefetch は次バッチ分しか先読みせず(AIbox の 3-stage pipeline でも prefetch
  レイテンシの 22% が露出)、読み順を SSD フレンドリーに並べ替える機会を逃す
  (§3.2.1)。②アクセス偏在: 既存の hot/cold 分離(HotKey-LSM, SplitDB)は「読みが
  多い key」を追加 compaction で後から集めるが、embedding は「頻繁に読まれ且つ
  頻繁に更新される」ので挿入時点で集められる (§3.2.2)。③読みと書きの対称性:
  forward pass でアクセスされたベクトルだけが backward pass で更新されるので、
  lookup がヒットしたファイルには「その iteration の終わりに旧値となる値」が
  含まれると分かる = 旧値の所在が読みからタダで得られる (§3.2.3)。

## System model & assumptions
- [paper] 対象は低リソース単一ノード学習: 評価では 40 コア Xeon Gold 6230N /
  187GB DRAM のサーバに cgroups で 16GB の DRAM 上限を強制し、OS ページキャッシュを
  0.02 秒ごとに flush してメモリ制約環境を模擬。ストレージは Intel DC P3600 1.6TB
  NVMe SSD 1 台 (§5.1.2)。
  - [inference] テストベッドに GPU の記載がなく(PyTorch 2.6.0 + Xeon のみ)、計算は
    CPU 実行と読める。GPU で計算時間が縮む環境では lookup レイテンシを計算に
    隠し切れなくなり、block time 0% (Table 3) の結論は変わり得る。
- [paper] 格納モデル: embedding table 内のベクトルの index を key、ベクトル本体を
  value として LSM-Tree(RocksDB 拡張)に格納。embedding 以外の学習パラメータは
  割合が小さいのでメモリに置く (§2.2, §4.1)。
- [paper] 学習の 1 iteration は embedding lookup → computation → embedding update の
  3 フェーズ。lookup/update が SSD へのランダム read/write を生む (§2.1)。
- [paper] ワークロード仮定(設計の根拠):
  - 将来バッチの embedding index が look-ahead で入手可能(offline/online とも)(§3.2.1)。
    全実験で look-ahead window = 512 (§5.1.3)。
  - アクセスの 99% 超が 1% のベクトルに集中。hot は隣接 iteration で繰り返し
    アクセスされ、cold は例えば 200 iteration といった長い間隔では再アクセスが稀 (§3.1.1)。
  - 読み書きの対称性: forward で読まれたベクトルは backward 後にほぼ即座に更新
    される。ゆえに「読まれたデータは読了後に安全に削除対象とみなせる」(§3.2.3, §4.3)。
- [paper] hot key の判定閾値はデータセットのアクセスパターンをオフライン分析して
  決める: アクセス頻度 1% 超を hot とする(典型バッチサイズ B>128 なら
  B×frequency>1.28 で、ほぼ全ミニバッチに再出現するため)。top-k =
  lookahead_num × p(p は hot-key 率)(§4.2)。
  - [question] §3.2.1 は online 学習も対象と言うが、hot 閾値・top-k の決定は
    「データセットのオフライン分析」に依存する (§4.2)。hot 集合がドリフトする
    online 設定で誰がいつ再分析するのかは本文から読めない(§5.1.1 の Radix Tree に
    よる「アクセス頻度が落ちた key の追い出し」が部分的な答えの可能性はある)。
- [paper] 公平性のための評価上の設定: 全ベースラインにも RecDB と同じ prefetch
  機構・同サイズの prefetch buffer を与える (§5.1.4)。

## Approach
- [paper] **全体構成 (§4.1, Fig. 7)**: RocksDB ベースの LSM-Tree の前段に
  ① Request Preprocessor(読み書き要求を横取りする middleware)、
  ② Compaction Picker、③ Compaction Scheduler を置き、メモリ側に
  EV Buffer(Embedding Vector Buffer: look-ahead 分の先読みベクトル置き場)と
  OD Monitor(Outdated Data Monitor: ファイル別旧値カウンタ)を持つ。
  write batch は各 iteration 末の更新ベクトル、read batch は将来 iteration の
  look-ahead lookup 要求 (§4.1)。
- [paper] **Request Preprocessor (§4.2)** — 3 部品:
  - *Hot Key Identifier*: 複数バッチ分の読み要求をバッファしてアクセス回数を数え、
    look-ahead バッチ内の top-k を hot と判定。新たに hot になった embedding は
    update 時に特殊 key で SSD に書き直される。
  - *Key Allocator*: hot embedding の key に「特殊 prefix + 元 key」を付与
    (prefix は辞書順最大 or 最小の文字)。LSM-Tree の性質上、同一 prefix の
    hot データは自然に同じ場所に集まり、cold と分離される。
    [inference] 追加 compaction で後から集める HotKey-LSM/SplitDB 系 (§3.2.2) と
    違い、「hot は頻繁に更新される」性質を使って通常の書き込みパスだけで
    クラスタリングを達成するのが新規性の芯。
  - *Key Sorter*: 読み要求を key 順に並べ替え、同一ブロックの重複ロードを回避 (§4.2)。
  - 先読みしたベクトルは EV Buffer に index で整理して格納し、将来の参照回数
    (ref)を記録。学習の lookup 要求は EV Buffer が返して ref を減算 (§4.2)。
- [paper] **Compaction Picker (§4.3, Fig. 8)**: lookup が level L_i のファイル(例: file 3)で
  ヒットするたびに OD Monitor のそのファイルの旧値カウンタを +1(例: 30→31。
  「file 3 を compaction 入力にすれば旧値を少なくとも 31 個消せる」の意)。学習後、
  新値 e' は L0 に flush される。ファイル選択は compaction score
  C_score(fid) = outdated_num(fid) / T_merge(fid)、
  T_merge(fid) = V_merge × Σ_{k∈comp_files(fid)} size(k) (Eq. 1) が最大のものを選ぶ。
  - [paper] 旧値削除は L0 compaction に統合される (Algorithm 1, 2): DeleteFilePicker は
    L_in ≠ 0 なら何もせず、level ≥ 2 のファイルから C_score 最大のものを選ぶ。
    L0 compaction 時に、選ばれたファイル内の key のうち compaction 出力
    (F_comp)に存在する key を削除し、残りを元の level に書き戻す (Algorithm 2, §4.3)。
  - [inference] 削除の安全性は「F_comp(浅い level 由来 = 新しい版)に同じ key が
    在るときだけ深いファイルから消す」という版ベースの条件で担保されており、
    §3.2.3 の「読まれたら更新される」仮定はカウンタ(選択の優先度)にしか効かない。
    したがって lookup 後に update が来ないケースがあってもカウンタが過大になる
    (compaction 選択が歪む)だけで、生きた値を消す誤りにはならないはず。
- [paper] **Compaction Scheduler (§4.4, Fig. 9)**: compaction スレッドと prefetch
  スレッドの並行実行を禁止し、EV Buffer が支えられる学習時間
  T_train(t) = V_buff × Size(Buff, t) (Eq. 2a) が compaction 所要時間
  T_merge(t) = V_merge × Σ size(k) (Eq. 2b) を上回るときだけ compaction を起動。
  満たさない場合は延期して定期的に再判定。Fig. 9 の例では T0(バッファ 3 バッチ、
  compaction = 3 iteration 相当)で延期し、T1(6 バッチ蓄積)で実行 —
  実行中は prefetch を一時的にブロックする (§4.4, Fig. 9, p.7)。

## Evaluation
- Setup [paper]: RecDB は C++ で RocksDB の拡張として実装、pybind11 で Python
  バインディング。変更された embedding key の監視に Radix Tree を使用(hot 判定と、
  アクセス頻度低下時の追い出し)(§5.1.1)。モデルは DeepFM(embedding 次元 9)/
  PNN(18)/ DLRM(36)、データセットは Criteo Kaggle(モデルサイズ 14G/22G/40G)と
  Criteo Terabyte(136G/241G/446G)(Table 2, §5.1.3)。look-ahead window 512。
  breakdown と ablation は Kaggle のみ (§5.1.3)。
- Baselines [paper] (§5.1.4): HashDB(AIbox の2層ハッシュ索引 + LRU/LFU キャッシュ、
  cache full 時に in-place 書き込み)、RocksDB、SplinterDB(STB𝜖-tree、GC 付き)、
  SILK(クライアント負荷に応じ compaction へ日和見的に I/O 帯域配分)。
  全手法に等しく 1GB の CPU メモリ(LSM 系: write buffer 856MB + LRU block cache
  168MB、HashDB: 15MB + 1008MB)。全ベースラインに同一の prefetch 機構と
  prefetch buffer を装備 (§5.1.4)。指標は RocksDB 正規化の Training / Read / Block /
  Update Latency (§5.1.5)。
- Headline numbers [paper]:
  - End-to-end: RocksDB 比 1.03×–2.94× の学習高速化 (abstract, §1)。Kaggle では平均
    1.70×(RocksDB 比)/ 5.54×(HashDB 比)。モデル別では DeepFM 1.33× / PNN 1.43× /
    DLRM 1.44× (Fig. 10a, §5.2)。Terabyte では平均 DLRM 2.09× / PNN 1.84× /
    DeepFM 2.08× と Kaggle より大きい(大モデルほど hot データが SSD 上で
    疎らに散るため grouping の効果が増す)(Fig. 10b, §5.2)。
  - HashDB は平均で RocksDB の 25.10% の性能、Terabyte 最悪ケースで学習レイテンシ
    13.21× 悪化。メモリ制約下のハッシュ衝突で、Kaggle では 45KB 超、Terabyte では
    443KB 超のベクトルが同一物理アドレス/ファイルに写像されるため (§5.2)。
  - SplinterDB は時折 RecDB を上回る(B𝜖-tree の write 最適化。ただし空間増幅が
    RecDB より大きい代償)。SILK は持続的ピーク負荷で RocksDB を下回ることもある
    (§5.2)。
- Breakdown [paper] (Table 3, batch 64): iteration 時間を block(読み待ち)/
  computation / update に分解。RecDB は block 0.00%(3 モデルとも)で computation
  57.83–65.85%。RocksDB は block 41.89–58.68%(read がボトルネック)。HashDB は
  update 74.30–79.69%(cache full 時のファイル全書き換えがボトルネック)(§5.3.1)。
- Read / Update レイテンシ [paper] (Fig. 11, batch 32–1024): RecDB の read time は
  RocksDB 比 2.53%–72.96% 減。HashDB は LSM 系比で平均 6.20× の read レイテンシ、
  update は少なくとも 2.17×。RecDB の update レイテンシは RocksDB より平均 17.48%
  高い(preprocessor のオーバーヘッド。全体 1.71× の高速化に見合うと主張)。
  SILK は軽負荷(DeepFM/Kaggle/batch 32)で read 32.65% 減だが負荷増で利得消失。
  SplinterDB は write レイテンシを Kaggle で 21.11%、Terabyte で 73.48% 削減 (§5.3.2)。
- Ablation [paper] (§5.4, Table 4 の略号 RP/KS/KA/CP/CS):
  - RP: read レイテンシ 41.06% 減(RocksDB 比)(Fig. 12a)。RocksDB では 23.85% 超の
    ブロックが再ロードされ最大 16 回のものもあるが、KS 適用後は 99.93% 超が
    1 回のみロード (Fig. 13)。ロードブロック数は 49.96×10^5 → 31.78×10^5
    (36.39% 減)、KA 追加でさらに 15.48% 減 (Fig. 14)。
  - CP: GC 効率(compaction 参加ベクトル数に対する削除済み旧値数の比)が
    RocksDB の 9.11% から 23.30% 改善(Fig. 15 の表示は RecDB w/ CP 11.23)(§5.4.2)。
  - CS: read レイテンシを RP+CP 比でさらに 11.53% 減 (§5.4.3, Fig. 12a)。compaction
    レイテンシ自体も 24.10s → 18.05s(25.10% 減)(Fig. 16)。compaction 早期完了で
    flush への write 帯域が増え、update レイテンシも 4.80% 減 (Fig. 12b, §5.4.3)。
    compaction 実行回数は 47.83% 減(lazy 化)だが GC 効率は向上と主張 (Fig. 19, §5.4.4)。
  - オーバーヘッド: update 中の key allocation は実行時間の 16.50% 未満。read 側は
    hot key の allocate / identify / sort がそれぞれ全 read 時間の約 3.83% / 9.43% /
    1.19% (Fig. 17)。CP は OD Monitor とロックの管理で read time +2.50%、平均
    65.71ns (Fig. 18)。
- [inference] 評価がカバーしていないもの:
  - EVStore / RecRT / MTrainS などメモリキャッシュ系の関連研究 (§1) は比較対象に
    含まれず、baseline は全て「SSD 上のストレージエンジン」のみ。key 粒度キャッシュは
    §6 で将来課題扱い。
  - SSD は Intel DC P3600 1 台のみで、デバイス世代・並列度(複数 SSD、より高速な
    NVMe)を変えたときに compaction 干渉(§3.1.3 の 258%)がどれだけ残るかは不明。
  - 学習精度への影響の議論・測定がない。look-ahead 512 バッチの先読みと EV Buffer
    経由の読みが、更新と交錯したときに古い値を返さないのか(下記 [question])を
    含め、精度指標は一切報告されない。
  - GC 効率 23.30% 改善の絶対値は 9.11% → 11.23% (Fig. 15) であり、依然 9 割弱の
    compaction 参加ベクトルは旧値でない = 空間増幅の解消幅としては控えめに見える。
    空間消費の直接測定(GB 単位の space amplification カーブ)は示されない
    (SplinterDB より良いという定性主張のみ、§1, §5.2)。
  - SILK / SplinterDB は Fig. 10–11 に登場するが、Table 3 の breakdown は
    HashDB / RocksDB / RecDB のみ。
- [question] EV Buffer の一貫性: iteration t で先読みしたベクトルが t より後・消費前に
  更新された場合、EV Buffer 内のコピーはどう無効化されるのか。§5.1.1 の Radix Tree
  (modified key の監視)が示唆的だが、本文に明示的な staleness 処理の記述は
  見当たらない。学習の意味論(look-ahead 分は同一パラメータスナップショットで
  よいのか)にも関わる。

## Limitations
- Stated [paper]:
  - RecDB の update レイテンシは RocksDB 比で平均 17.48% 高い(preprocessor の
    前処理コスト。全体の 1.71× 高速化に照らして許容と主張)(§5.3.2, Fig. 11)。
  - CP は read time を 2.50% 増やす(OD Monitor とロック管理。平均 65.71ns で
    無視できると主張)(§5.4.4, Fig. 18)。
  - CS は lazy compaction 方針で compaction 回数を 47.83% 減らすため、compaction に
    よる読み高速化(データ再編)の機会は減る(GC 効率向上で相殺されると主張)
    (§5.4.4, Fig. 19)。
  - SplinterDB が時折 RecDB を上回る(書き込み最適化 vs 空間増幅のトレードオフ)
    (§5.2)。
  - 現状は block 粒度キャッシュ・SSD 単層。key 粒度キャッシュ、温度別階層配置
    (L0–L2 を DRAM/NVMe に、L_max を HDD に)、hot key を compaction 時に浅い
    level に「昇格」させる data-promotion compaction は §6 の Discussion(将来拡張)
    に留まる。
- Inferred [inference]:
  - 設計全体が「将来アクセス列が look-ahead で得られる」ことに強く依存する。
    look-ahead が使えない・短い設定(真のオンライン学習、ストリーミング特徴)では
    KS/CS(EV Buffer 残量ベースのスケジューリング)の前提が崩れる。RP 無しの
    CP+CS 単体の効果は ablation の積み上げ順(RP → RP+CP → RP+CP+CS, Fig. 12)から
    分離できない。
  - hot 判定閾値(頻度 1%、top-k = lookahead_num × p)はオフラインのデータセット
    分析で固定され (§4.2)、hot 集合のドリフトへの追従性は Radix Tree の追い出しに
    暗黙に委ねられている。閾値誤設定時の挙動(hot 過剰認定による特殊 prefix 領域の
    肥大、update 時の書き直しコスト増)は分析されていない。
  - OD Monitor のカウンタや Radix Tree 自体のメモリ消費は定量化されていない
    (1GB 制約の内訳 §5.1.4 には write buffer と block cache しか現れない)。
  - compaction 実行中は prefetch がブロックされる設計 (Fig. 9, §4.4) なので、
    T_merge の見積り(V_merge × サイズ)が外れる長時間 compaction では EV Buffer が
    枯渇して block time が復活し得る。V_merge の較正方法・誤差の影響は示されない。

## Relations
- 競合 baseline(本文 §5.1.4): HashDB(AIbox 由来)、RocksDB、SplinterDB、SILK。
  下敷きは RocksDB の compaction 機構 (Algorithm 2 の green 部分は標準 RocksDB
  ロジックと明記, §4.3)。
- [[2026-pvldb-liu-arcekv.md]](ArceKV: LSM compaction): RecDB の Compaction Picker は
  「どのファイルを compaction 入力に選ぶか」を旧値密度/マージコスト比 (Eq. 1) で
  決める話であり、LSM compaction 戦略というテーマで直接接続する(ArceKV 側の
  文脈は当該ノート参照)。
- [[2026-fast-ren-lsm-scheduling.md]](Ren: LSM スケジューリング): RecDB の
  Compaction Scheduler は「フォアグラウンド(prefetch)への干渉を避けて compaction を
  いつ走らせるか」というスケジューリング問題 (§3.1.3, §4.4) で、SILK(本文 baseline)
  ともども LSM の compaction スケジューリング系列に属する。
- [[2026-pvldb-lee-how-to-write-to-ssds.md]](SSD への書き方: WA / out-of-place):
  RecDB の動機部(4KB 書き込み粒度と 144B 値の write amplification、out-of-place
  更新によるその緩和、§1)は SSD 書き込み経路の一般論と正面から重なる。ホット/
  コールド分離を key prefix というソフトウェア層で実現する点は、デバイス側の
  placement 手法との対比軸になる。

## Idea seeds
- [inference] 「読みが将来の死(旧値化)を予告する」という OD Monitor の発想は、
  read-modify-write が支配的な一般のワークロード(パラメータサーバ、セッション
  ストア、カウンタ系 KV)にも移植できるはず。compaction 選択を「サイズ最大」でなく
  「期待死亡密度/マージコスト」で行う RocksDB パッチを書き、YCSB の
  read-modify-write 比率を振って GC 効率と空間増幅を測るのが最初の実験。
  RecDB の実装が公開されている(https://github.com/magicalcloud/RecDB_Paper, §8)
  ので流用可能。
- [inference] Compaction Scheduler は「アプリが自分の余裕(EV Buffer 残量)を
  ストレージエンジンに教える」インタフェースと読める (Eq. 2)。これを一般化した
  「クライアント供給スラック付き compaction スケジューリング API」は、SILK 的な
  負荷推定(エンジン側の推測)との対比で面白い。検証: RocksDB の
  CompactionFilter/rate limiter に外部スラック信号を注入し、レイテンシ SLO 違反率で
  SILK 方式と比較。
- [question] hot key への特殊 prefix 付与は論理 keyspace を汚す(元 key との対応維持、
  hot→cold 遷移時の書き戻し)。hot 判定が誤った/ドリフトした場合の整合性・
  性能崩れ方は本文から読めない (§4.2 は Radix Tree による追い出しに言及するのみ)。
  公開コードで hot 集合を人工的にドリフトさせるワークロード(周期的に 1% の
  hot 集合を入れ替える)を流し、性能劣化カーブを取るところから。
- [question] look-ahead 512 の先読みと更新の交錯で EV Buffer が古い値を返す可能性と
  その学習精度への影響(bounded staleness とみなせるのか)。精度指標が論文に
  無いため、公開コードで AUC/loss 曲線を RocksDB 直読み構成と比較するのが
  第一歩。

## Changelog
- 2026-07-06: created (status: read, openproceedings.org 公式 PDF を読解。ソース URL: https://openproceedings.org/2026/conf/edbt/paper-229.pdf)
