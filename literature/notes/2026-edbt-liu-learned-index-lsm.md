---
title: "Evaluating Learned Indexes in LSM-tree Systems: Benchmarks, Insights and Design Choices"
authors: [Junfeng Liu, Jiarui Ye, Mengshi Chen, Meng Li, Siqiang Luo]
venue: "EDBT '26 (Tampere), pp.183-195"
year: 2026
ids: {doi: "10.48786/edbt.2026.16", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.48786/edbt.2026.16", pdf: "literature/pdfs/2026-edbt-liu-learned-index-lsm.pdf", code: "https://github.com/buchuitoudegou/LearnedIndexInLSM"}
status: read
read_date: 2026-07-06
tags: [lsm-tree, learned-index, benchmark, fence-pointer, memory-efficiency, compaction, range-lookup, leveldb, key-value-store]
---

## TL;DR
LSM-tree の fence pointer を learned index で置換する設計空間を、**index type /
position boundary / index granularity** の3軸に統一し、LevelDB ベースの共通テストベッドで
10 個の learned index(data-clustered 6 + data-unclustered 4)を fence pointer と比較した
ベンチマーク論文。主要な結論: data-clustered 系(特に PGM/RMI/RS/PLEX)がメモリ効率で
一貫して優位、position boundary は 16 を下回ると利得が逓減、モデル学習はエントリが
大きければコンパクション時間の 5% 未満(小エントリでは unclustered で最大 80%)、
granularity を粗くするとメモリ 10× 超削減で性能はほぼ不変。

## Problem & motivation
- [paper] fence pointer のメモリはデータ量に線形で増える: 10TiB のデータ+128B キーで
  最大 320GiB。クラウド・マルチテナント環境ではメモリが制約資源で、Bloom filter /
  write buffer / block cache と競合する (§1)。
- [paper] learned index は代替候補(例: PGM の空間計算量は O(log log N) [36] 引用)だが、
  LSM への統合は Bourbon(PLR)[8] や TridentKV(RMI)[38] など狭い範囲しか探索されて
  おらず、index type 横断の強弱・チューニング指針が不明 (§1, §7)。
- [paper] 2つの中心的な問い: (1) すべての learned index は LSM-tree に適するか?
  (2) どう統合し、どうチューニングするか? (§1)。
- [paper] 多くの learned index は in-memory 向け設計(可変長文字列対応、更新性、
  セグメンテーション改良など)で、LSM 固有の課題 — メモリ効率、コンパクション起因の
  rebuild コスト、range query の seek セマンティクス(start key 以上の最初のキーの発見)—
  への影響は未探索 (§1)。

## System model & assumptions
- [paper] ベース系: LevelDB。leveling compaction、size ratio T=10、Bloom filter は
  10 bits/key (§5)。SSTable(部分コンパクション用の分割ファイル)を持つ標準構成 (§2.1)。
- [paper] learned index 置換が成立する前提2点: (1) ディスク上のソート済み配列は
  **immutable**(コンパクション時のみ生成・削除)なので更新不能な learned index でも
  よい、(2) データは既にソート順で格納されているため学習が容易 (§2.2)。
- [paper] モデル学習はフラッシュ/コンパクション時の TableBuilder 内で実施し、
  SSTable フォーマットを LearnedIndexTable 形式(inner index と data segment を分離
  シリアライズ、オフセットをファイルヘッダに記録)に置換 (§4.1, Fig. 4)。
- [paper] キー空間は整数ドメインに正規化してからモデルを学習 (§4.1)。可変長キーは
  最大長にパディングして整数化(LITS のみ Trie で直接扱う)(§5.3)。
- [paper] data-clustered index はモデルが誤差保証付きで位置予測 → [pos−err, pos+err]
  を読み二分探索。キーがデータブロック内に連続格納されているため mapped key segment を
  メモリに持たなくてよい (§4.1, Fig. 5)。
- [paper] data-unclustered index は全 mapped key をメモリ保持する必要がある。データ
  ブロックのオフセットだけ持つと大量のランダム I/O が発生し、単純な二分探索より悪化
  する (§3.3)。
- [paper] HW/OS: Intel Core i9-13900K(L3 36MB)、DRAM 128GB、2TB NVMe SSD、
  Ubuntu 22.04。cgroup で OS ページバッファを総メモリの 70%(75GB)に制限、
  LevelDB cache はデフォルト 8MB (§5)。
- [paper] データセット (Table 1): YCSB-Gen 合成 3 種(Uniform / Zipfian θ=0.9 /
  θ=0.99、各 100GiB、104,857,600 entries、24B key + 1000B value)と実データ 3 種
  (Facebook ID: 200M keys 8B/8B、OSM Cell ID: 800M keys、Wikipedia Timestamp:
  200M keys)。
- [paper] position boundary の制御法は index 依存: PLR/FITing-Tree/PLEX は error bound、
  RMI は第2レベルのモデル数、RS/PGM は error bound + 内部パラメータ、FP は LevelDB の
  データブロックサイズで代替制御。PGM は EpsilonRecursive=4(影響小と確認)、RS は
  RadixBits=1 が最良と判断 (§5)。
- [inference] 評価はレイテンシ(µs/op)中心の単一ノード実験。スレッド数・並行実行に
  ついての記述は評価節に見当たらず、並行性下の挙動は本論文からは分からない。

## Approach
- [paper] **分類**: データレイアウトに基づき、KV ペアを物理的に連続なブロックに格納する
  **data-clustered**(PLR, FITing-Tree, PGM, RadixSpline, PLEX, RMI)と、ポインタ追跡が
  必要な **data-unclustered**(ALEX, LIPP, DILI, NFL, LITS)に二分 (§3, Fig. 2, Fig. 3)。
- [paper] **互換性 4 軸**で分析: memory efficiency / point lookup / range lookup
  (seek 相 + scan 相)/ compaction & index rebuild (§3.3, Table 2)。unclustered は
  将来の挿入用に空きスロットや gapped array を持つため、immutable な SSTable 上では
  純粋なメモリ overhead になる (§3.3, §5.1)。
- [paper] **テストベッド**: LevelDB の Table クラスを継承する LearnedIndexTable を新設し、
  InternalGet(点検索)/ NewIterator(range・compaction 用)/ TableBuilder(構築)の
  3 関数をオーバーライドして 10 index を統一インタフェースで統合 (§4.1, Fig. 4)。
- [paper] **統一 config 空間**: ①index type(モデル構造でメモリ-性能と rebuild コストが
  変わる)、②position boundary(ディスクから取得する最終探索範囲 = I/O コスト直結)、
  ③index granularity(SSTable 単位か level 単位か、SSTable サイズ)(§4.2)。
- [paper] range lookup の seek 相では「探索キー以上の最初のキー」をモデルで予測。
  data-clustered はキー不在でも誤差範囲内に正しい開始キーが入ることが保証される。
  unclustered の多く(ALEX 以外)はこの seek インタフェースを欠き、リーフが非連結
  なので最悪ツリー全走査になる (§4.1, §5.2)。

## Evaluation
- Setup [paper]: 上記テストベッドで 1M point lookups(Fig. 7)、1M 連続 range lookups
  (Uniform、Fig. 9)、可変長キー(8〜24B、boundary=8、Fig. 10(C))、コンパクション実験
  (50M キー追加挿入で既存 50M キーとマージ = YCSB で 50GiB、FB で 5GiB、Fig. 10(D),
  Fig. 11)、granularity(SSTable 8MB〜128MB + level model、Fig. 12)、YCSB A〜F
  (boundary=16、Fig. 13)(§5.1〜§5.6)。
- [paper] **Obs 1**: YCSB 3 データセットでは data-clustered は FP よりメモリ効率が良いが、
  8B キーの実データでは PGM/RMI/RS/PLEX のみ一貫して FP 以下。FP のコストはキーサイズに
  線形なので 8B では縮み、PLR/FITing-Tree は依然モデルあたり同数の整数が必要で逆転される
  (§5.1, Fig. 7, Fig. 8)。スキューが強いほど learned index の圧縮が効く(FB uniform より
  WIKI skewed の方が省メモリ)(§5.1)。
- [paper] **Obs 2**: メモリを足して boundary を下げると I/O 支配のレイテンシが改善するが、
  **16 で頭打ち**: 16 エントリの取得は 1 エントリより約 2µs 遅いだけ。mapped key 全保持
  (数百 MB)の改善は約 2µs に対し、boundary 128→16(数十 MB)で約 10µs 改善 (§5.1,
  Fig. 7, Fig. 8)。intro の言い換えでは「セグメントサイズが I/O ブロックサイズを下回ると
  追加メモリはほぼ無意味」(§1)。
- [paper] **Obs 3**: unclustered は mapped key 保持だけで 2GiB 以上、clustered は
  boundary=8 で数 MB。レイテンシ差は 1〜2µs (§5.1)。clustered に mapped key segment を
  保持させると unclustered とほぼ同性能でなおメモリは少ない (Fig. 7(C)(F)(I))。
- [paper] 実データの具体値 (Fig. 8, boundary=16): FB で FP 372MB/2.13µs に対し
  RMI 17.7MB/2.0µs、PGM 66MB/2.50µs; ALEX 3.2GB/1.01µs、LIPP は 23GB。WIKI では
  RMI 1.7MB、PGM 10.9MB。OSM では LIPP(メモリ超過)と DILI(キー分布非対応)が
  実行不能 (Fig. 8 caption)。点検索の内訳ではディスク I/O が単一エントリ取得でも
  クエリ時間の約半分 (Fig. 8 右, §5.3)。
- [paper] **Obs 4 (range)**: seek 相のコストは boundary とともに増加。scan 長が短い間は
  大きい boundary が(セグメント共有によるキャッシュヒットで)わずかに有利だが、
  scan 長の増加とともに効果は消え、scan 相の時間は scan 長にほぼ比例 (§5.2, Fig. 9)。
  unclustered の seek はツリー走査が遅いにもかかわらず clustered と同等 — 支配的コストが
  全レベル横断のディスクアクセスだから (§5.2, Fig. 10(A)(B))。
- [paper] **可変長キー**: レイテンシは固定長の場合とほぼ同一。文字列特化の LITS も
  有意に勝たない — in-memory では index アクセスが支配的だが LSM では I/O が支配する
  ため (§5.3, Fig. 10(C))。
- [paper] **Obs 5 (compaction)**: 学習 overhead は 1000B 値の大エントリでは全コンパクション
  時間の 5% 未満。エントリが小さくなると I/O 時間だけが縮んで学習時間は不変のため、
  data-clustered で最大 20%、data-unclustered で最大 80% に達する (§5.4, Fig. 10(D),
  Fig. 11)。DILI 等はキーを1件ずつツリーに挿入し split/balance が走るため学習が遅い (§5.4)。
- [paper] **Obs 6 (granularity)**: SSTable 8MB→128MB→level model でルックアップ
  レイテンシは数 µs しか変わらないが、メモリは 8MB SSTable → level model で 10× 超削減
  (§5.5, Fig. 12)。LITS は Trie 保持のためデータ量とともにメモリが急増 (§5.5)。
- [paper] **Mixed workload**: YCSB A〜F の結果は基本の点/範囲検索実験をほぼなぞり、
  read-write 混合でも大きな劣化なし (§5.6, Fig. 13)。
- [paper] **Tuning guide / takeaways**: ①エントリが大きいかキー分布がスキューなら
  learned index を使え、②data-clustered(PGM/RS/RMI/PLEX)を選べ、③boundary は
  16 より大きい時だけ下げよ(それ以下は Bloom/write buffer/cache に回せ)、
  ④granularity を上げよ(メモリ-性能トレードオフ最大 10% 改善)。ただし level 単位
  モデルは full merge が前提 (§6.2, §6.3)。
- [inference] 評価がカバーしないもの: (a) compaction policy は leveling のみで、
  tiering や partial compaction との相互作用は granularity 実験以外にない。(b) 並行
  スループット(ops/s、マルチスレッド)や write stall への影響は測っていない。
  (c) メモリ配分の帰結を「他コンポーネントへ回せ」と述べるが、Bloom bits と boundary
  の joint tuning 実験は無い。(d) エントリサイズは実質 1024B と 16B の2点+可変長
  8〜24B で、中間域は粗い。(e) Bourbon/TridentKV そのもの(システム全体)との
  end-to-end 比較ではなく、index 部品の比較である。

## Limitations
- Stated [paper]: level-granularity モデルは full merge(レベル全体のマージ)でのみ
  成立する。full merge は全体の write amplification を増やさない([12] 引用)が、
  短期的なリソース使用のスパイクとフォアグラウンド性能の一時劣化を招き得る (§6.2)。
- Stated [paper]: LIPP は OSM でメモリ要求超過、DILI は OSM のキー分布に非対応で失敗
  (Fig. 8 caption)。unclustered の多くは seek インタフェースがなく統合にコード修正が
  必要 (§5.2, §6.1)。
- Inferred [inference]:
  - 結論の多くは「I/O が支配的」という前提から導かれている(boundary 16 の閾値、
    LITS が勝たない理由など)。より高速なデバイス(または block cache ヒット率が
    高い運用)では閾値も順位も変わる可能性があるが、デバイスは 2TB NVMe 1 種のみ。
  - 論文内で index 数の記述が揺れる: abstract は「eight learned indexes」、§1 の
    貢献では「six representative」「ten representative indexes」が併存し、§3 では
    11 個(clustered 6 + unclustered 5)を記述、評価は 10 個(NFL 不在)。
  - [question] NFL は §3.2 で紹介されながら評価に登場しない。除外理由は本文に
    見当たらない。

## Relations
- [[2026-pvldb-liu-arcekv.md]]: 同一グループ(Junfeng Liu / Siqiang Luo、NTU)。
  ArceKV は LSM の構造側(レベル容量・ラン構成)の動的最適化、本論文は index 側の
  設計空間という相補関係。[inference] 本論文の level-granularity モデルは full merge
  前提 (§6.2) なので、ArceKV のような構造制約を外した LSM とは組み合わせ方が非自明。
- [[2026-pvldb-zhao-sidle.md]]: index のメモリ階層配置という観点で接続。本論文の
  「mapped key 保持=数百 MB で約 2µs 改善」(§5.1) というトレードオフは、階層メモリ
  では配置問題として読み替えられる(Idea seeds 参照)。

## Idea seeds
- [inference] **Joint memory allocation**: 論文自身が「learned index とシステム
  コンポーネント間のメモリ配分は open question」と明言 (§1) し、指針も「boundary<16 なら
  他へ回せ」止まり (§6.2)。総メモリ予算を固定して Bloom bits × boundary × block cache を
  同時 sweep する実験は公開テストベッド (§9) 上で直ちに可能で、LSM 全体のコストモデル
  (Monkey 系)に learned index 項を足す論文の素材になる。
- [inference] **Index-rebuild-aware compaction scheduling**: 小エントリでは学習が
  コンパクション時間の最大 80% (§5.4)。コンパクションのコストモデルに learn 時間を
  入れて、ジョブサイズ・granularity・index type を動的に選ぶ scheduler は未探索に
  見える。検証: テストベッドで entry size を振り、learn 時間予測(エントリ数に線形、
  §5.4)に基づくジョブ分割が tail latency を下げるか測る。
- [question] **Retained segment の階層メモリ配置**: 「数百 MB 追加で 2µs」(§5.1) の
  mapped key 保持セグメントは、CXL/遅いメモリ層に置いてもまだ得か? SIDLE 的な
  ノード粒度配置と組み合わせ、fast memory は model 本体だけに絞る設計が成り立つかを
  マイクロベンチで確認する価値あり。

## Changelog
- 2026-07-06: created (status: read, OpenProceedings 公式 PDF の抽出テキスト全文を読解)
