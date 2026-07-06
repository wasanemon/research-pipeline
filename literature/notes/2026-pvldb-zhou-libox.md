---
title: "LiBox: A Learned Index as an Array to Minimize Last-Mile Search"
authors: [Jian Zhou, Luna Wang, Shuaihua Zhao, Chen Zhong, Song Jiang]
venue: "Proceedings of the VLDB Endowment, Vol. 19, No. 5 (PVLDB 19(5): 836-848)"
year: 2026
ids: {doi: "10.14778/3796195.3796199", arxiv: "", dblp: "journals/pvldb/ZhouWZZJ26"}
urls: {paper: "https://www.vldb.org/pvldb/vol19/p836-jiang.pdf", pdf: "literature/pdfs/2026-pvldb-zhou-libox.pdf", code: "https://github.com/strivesnail/Libox.git"}
status: read
read_date: 2026-07-06
tags: [learned-index, in-memory-index, simd, avx-512, last-mile-search, segmentation, overflow-buffer, concurrency, memory-footprint]
---

## TL;DR
learned index の二大コスト(モデル評価と、予測誤差を吸収する last-mile search)を、
キー空間を固定幅 window に切って各 window を固定容量 64 slot の「box」へ線形写像する
ことで排除する in-memory learned index。box は誤差ゼロの単純線形回帰で特定でき、
box 内は unsorted のまま 1B comparison byte の配列に対する AVX-512 1 命令で検索する。
top/bottom の 2 レベル + overflow box + re-segmentation で更新に対応し、
ALEX+/LIPP+/XIndex/SALI/ART+/B+-tree に対して point 操作で高スループット
(特に高スレッド・write-heavy)を主張。range search は明確な優位なし。

## Problem & motivation
- [paper] learned index はソート済み配列中のキー位置をモデルで計算することで原理上
  O(1) の indexing が可能で、hash table と違い sorted layout を保つため range query を
  サポートできる (§1)。
- [paper] しかしモデルは予測誤差 e(k) を持ち、個々のキーの誤差は記録できないため
  探索範囲は全キーの最大誤差 E = max e(k)(error bound)で定義される。結果、
  (1) 単一の大きな誤差が全 misprediction の探索範囲を膨らませ、(2) 予測が exact で
  ない限りペナルティは予測精度と相関せず error bound いっぱいの探索コストまで
  最大化される (§1, p.2)。
- [paper] 既存 learned index の限界は 3 点: (1) ReLU ベース NN のような比較的単純な
  モデルでも超低レイテンシ index 操作にはコスト過大、(2) 2〜3 レベルを超える階層
  モデルはランダムメモリアクセスで検索性能を大きく落とす、(3) 数百のソート済み
  キーに対する last-mile search が高コスト。これらは相互依存で、レベル削減や軽量
  モデル採用は error bound を増やし last-mile 範囲を広げる (§1)。
- [paper] キー分布は大局的には滑らかな CDF でも個々のキーレベルでは高度に不規則で、
  キーを正確に位置へ写す効率的な関数を見つけるのは難しい(例: VMware W018 トレース、
  3,068,126 unique keys)(§2.1, Fig. 1)。
- [paper] 目標は「超単純な線形回帰のみ・ごく少ない階層・last-mile search 最小化」を
  同時に満たすこと。線形回帰を 2〜3 回実行するだけで予測誤差なしに位置を計算する (§1)。

## System model & assumptions
- [paper] 単一ノードの in-memory index。評価環境は single-socket AMD EPYC 9634
  (84 コア、最大 3.70GHz)、168GB DRAM、SMT 無効、単一 NUMA ノード限定、
  Ubuntu Linux 24.10 (§3)。
- [paper] AVX-512 の存在が前提。box サイズ c=64 で、AVX-512 1 命令で box 内全キーの
  comparison byte を一斉比較する。AVX-512 が無い低価格帯 CPU では box 内キーの
  ソート保持 + binary search が必要になり insert コストが増える —「AVX-512 は LiBox の
  性能優位の維持に必須」と明言 (§2.4)。
- [paper] キーは 8B 符号なし整数(W048/Msr_web は元 4B だが一律 8B で格納)、
  value は全実験で 8B 固定 (§3.1)。文字列等ほかのキー型への拡張は future work (§4)。
- [paper] 更新モデル: insert は box 内の任意の空き slot(bitmap で管理)へ、
  溢れたキーは overflow box へ。write の蓄積は re-segmentation(out-of-place の
  構造再編)で吸収する (§2.3, §2.6)。
- [paper] 並行性制御: segment 単位の shared-exclusive lock(reader は segment レベルで
  常に lock-free、writer 同士は共有、re-segmentation のみ排他)+ box 単位の
  shared-exclusive lock(box あたり writer は 1、reader は複数可)。メモリ回収は
  Epoch-Based Reclamation (EBR) (§2.7)。
- [paper] re-segmentation は out-of-place 書き込みなので、進行中も reader は旧 segment を
  読み続けられる (§2.7)。
- [inference] 永続化・クラッシュリカバリへの言及は本文に無い(純粋な揮発性
  in-memory index)。また削除は underflow→re-segmentation の記述 (§2.6) があるのみで、
  削除 API のアルゴリズム記述や削除実験は無い。

## Approach
- [paper] **中核となる変換**: 不規則なキー分布を「完全に線形な window 分布」に変換する。
  window はキー空間の固定幅区間(中のキー数は可変)、box は配列上の固定数の連続
  slot(容量固定、中のキー数は可変)。i 番目の window を i 番目の box に写像するので、
  key→box の写像は単純な線形関数になり、box の特定に予測誤差が無い (§2, §2.1)。
  不規則性の「規則性への変換」は box 粒度で行われ、局所の不規則さは box 内に
  閉じ込められる (§3.3, Table 2 の議論)。
- [paper] **segment と window size 選択 (§2.2, Alg. 1)**: segment = 共通の window size を
  持つ box の配列で、キー空間の連続領域をカバーする。パラメータは累積 overflow 比
  閾値 α と累積 underflow 比閾値 β(いずれも segment 容量 = 全 box の slot 総数に
  対する、overflow キー総数 / 空き slot 総数の比)。固定 window size でキー配列を
  先頭からスキャンして box を切っていき、累積比が α または β を超えた時点で
  segment を打ち切る。window size の候補は、開始キー〜期待終了キー(直近最大
  segment 長の 2 倍)から k 点(デフォルト k=5)をサンプルし、各点で「ちょうど
  c=64 キーを覆う」最大 window size を計算してソートしたリスト。中央値から始め、
  overflow 違反なら次に小さい候補、underflow 違反なら次に大きい候補へ移り、
  segment 長が伸びなくなる等の条件で打ち切って最長 segment を採用する。box 境界の
  特定は全キースキャンでなく前 box のキー数分のジャンプ + 近傍探索 (§2.2)。
- [paper] **2 レベル階層 (§2.3, Fig. 3)**: キー本体は bottom level。各 bottom segment の
  先頭キーをソート順に並べた配列を top level とし、これも同じ segment/box 構造で
  索引する。top の segment 数が非常に大きければさらに上位レベルも作れるが、実世界
  データセットでは稀と主張。root segment は β=100% に設定して常に 1 個。検索は
  root segment の線形関数 pos = a·key + b で box を特定し、その box を AVX 命令
  (_mm512_cmpge_epi8_mask / _mm512_cmple_epi8_mask)で検索して top-level segment を
  特定 → top segment の線形関数で top box を特定し、その box の SIMD 検索で
  bottom segment を特定 → bottom segment の線形関数で bottom の box を特定 →
  SIMD で box 内検索 (§2.3, Alg. 2)。
- [paper] **box 内検索 (§2.4)**: box 内のキーは unsorted(挿入・削除でキー移動不要)。
  各 8B キーに単純ハッシュを適用して 1B の comparison byte を生成し、box 内全キーの
  comparison byte を byte 配列に集めて AVX-512 1 命令で検索キーの comparison byte と
  一斉比較。マッチした byte ごとに full key 比較を行う。window が小さいので衝突
  (複数マッチ)は「very rare」とし、空き slot 上のマッチは bitmap で無視。存在する
  キーの検索は「ほぼ常に 2 比較命令(SIMD 1 + full-key 1)」(§2.4)。
- [paper] **insert と overflow box (§2.3, Alg. 3)**: box に空きがあれば bitmap で即座に
  空き slot を見つけて挿入。満杯なら overflow box(regular box と同構造・同サイズ)へ。
  overflow box は共有から始まる: segment の overflow キーが box 容量未満のうちは
  segment 全体で 1 個を共有し、満杯になると split して前半 ⌈box_num/2⌉ 個の regular
  box 用と後半用に分かれ、以後 ⌈box_num/4⌉… と共有範囲が狭まり、最終的には
  regular box ごとの専用 overflow box の linked list になる (§2.3, Fig. 3)。
- [paper] **range search (§2.5)**: 検索範囲と重なる box を全て特定し、範囲に部分的に
  重なる境界 box では AVX-512 の範囲比較(cmpge/cmple)でフィルタする。この場合は
  1B の comparison byte が使えない(完全一致でなく範囲比較のため)ので命令を複数回
  適用する必要があり、回数削減のため境界 box 内のキーを事前にソートして early
  termination できるようにする。完全に範囲内の box は全キーを返す。
- [paper] **re-segmentation (§2.6)**: 発動条件は 3 つ — segment の overflow 比
  (overflow box 数 / regular box 数)が閾値 γ 超過、いずれかの regular box の overflow
  list 長が閾値 L 超過、segment の underflow 比(underflow box 数 / 総 box 数、削除起因)
  が γ 超過。regular + overflow box のキーを merge-sort して新配列を作り、§2.2 の
  手順で新 segment/box を生成。低レベル re-segmentation で segment 数が増えると
  top level にキーを挿入し、空きが無ければ top-level re-segmentation を即時実行
  (このとき β を 20% ステップで最大 90% まで増加。top segment の α は常に 0%、
  root の β は常に 100%)。top level は検索が全て通るため overflow box を禁止
  (pointer chasing による cache miss 回避)。占有率 80% 超の top box は
  compaction-ready フラグを立て、ユーザ要求が無い時に背景で関連 bottom segment を
  まとめて opportunistic に再編する。異なる segment の低レベル re-segmentation は
  並列実行可 (§2.6)。
- [paper] **並行性 (§2.7)**: writer が新 overflow box を作る間は元 box のロックを保持し、
  regular box から overflow box への他スレッド進入を防ぐ。EBR の適用場面は 3 つ —
  (1) re-segmentation スレッドが排他ロックを取る前に segment 内に writer がいない
  ことの保証、(2) 既存 overflow box が満杯で新 overflow box を作る際に既存 box への
  アクセスが無いことの保証、(3) re-segmentation 完了時の旧 segment メモリ回収。

## Evaluation
- Setup [paper]: 上記 AMD EPYC 9634 サーバ (§3)。baseline は learned 系 = ALEX+
  (gapped array + exponential search の ALEX の並行版)、LIPP+(精密位置予測、
  FMCD アルゴリズム、最大 100 万キーのノード)、XIndex(delta buffer + 二相
  compaction)、SALI(LIPP ベースにアクセス統計と node evolution を加えた
  スケーラビリティ枠組み)、非 learned 系 = B+-tree(マルチスレッド実装 [29])、
  ART+ [17]。実装は index 比較研究 GRE [31, 4] から取得し、各 index のデフォルト
  設定を使用。LiBox のデフォルトは α=10%, β=50%, γ=20%, L=2。AVX-512 の寄与を
  分離するため、box 内ソート + binary search の LiBox_noAVX 変種も比較 (§3)。
- Datasets [paper] (Table 1, §3.1): W048(CloudPhysics の VMware 仮想ディスク LBA、
  5,458,867 keys、95% 超のキーが 1,000 連続 LBA 超のシーケンスに属す)、Msr_web
  (MSR Cambridge のエンタープライズサーバ LBA、8,974,377)、Longitudes(OSM の
  経度、200,000,000)、Genome(ヒト染色体の loci pair、200,000,000)、OSM(一様
  サンプルした OpenStreetMap 位置の 1 次元射影、200,000,000)。OSM は多次元→1 次元
  射影で規則性が壊れた learned index にとって悪名高い最難データセットで、先行研究
  では従来 index がしばしば learned index に勝つ (§3.1)。
- Workloads [paper] (§3.2): 全キーを random shuffle して参照トレースを構成。
  RO = 全キー bulk load 後、各キーをランダム順に 1 回 read。BAL = 50% を bulk load、
  残り 50% をランダム順に insert し、各 write 直後に index 内の既存キーから
  ランダムに選んだ read を 1 回。WO = 50% bulk load 後、残り 50% を insert のみ。
  write 1 回あたりの read 回数を変えて 80/20 等の比率も生成。
- Headline numbers:
  - [paper] 単一スレッド (Fig. 4) およびスレッドスケーリング (Fig. 5) の双方で LiBox が
    ほとんどの実験で最高スループット。特に高スレッド数で差が開く (§3.3)。
  - [paper] データセットが難しいほど learned index は不利になる。RO では OSM を除き
    LiBox 以外にも ART+ に勝つ learned index が常に存在するが、OSM では ART+ に
    勝つ learned index は LiBox のみ。OSM では最下位常連の B+-tree すら XIndex に勝つ
    (§3.3)。
  - [paper] write 比率が上がるほど learned index の優位は縮む。WO では ART+ が
    LiBox 以外のほぼ全 learned index を抜き、B+-tree も XIndex と LIPP+ に一貫して
    勝つ (§3.3, Fig. 5, Fig. 6)。
  - [paper] WO で 40→80 スレッドに倍増した際、LiBox のスループットは W048/Msr_web/
    Longitudes/Genome/OSM でそれぞれ +69%/57%/37%/47%/62% (§3.3)。
  - [paper] LIPP+ は BAL/WO でスレッド数を増やしてもほぼ改善しない(ノードが最大
    100 万キーまで成長するため粗粒度ロックになり、writer がロックを取ると当該
    ノードへの全アクセスがブロックされる)。SALI はアクセス強度に応じた再構造化で
    LIPP+ を改善するが、大半のケースで LiBox より大幅に低い。LiBox は 64 キーの
    box 粒度で write ロックを掛ける (§3.3, p.8–9)。
  - [paper] LiBox_noAVX は LiBox より大幅に低スループット(それでも一部 index には
    競争力あり)。SIMD 命令が性能優位の本質 (§3.3)。
  - [paper] bulk load 後の segment 数 (Table 2): W048 = top 1 / bottom 57、Msr_web =
    2/81、Longitudes = 2/2,369、Genome = 1,700/1,022,494、OSM = 4,331/839,869。
    bottom が 100 万 segment 級でも top は数千で、top-level の補助構造は CPU cache に
    全部載る。overflow box が絡まなければ 1 lookup のメモリアクセスは top/bottom の
    box 各 1 個 = 2 box のみ (§3.3, Table 2)。
  - [paper] range search (Fig. 7、クエリ長 100 キー、比較対象は range 対応の ALEX+ と
    B+-tree のみ): LiBox に明確な優位は無い。境界 box での local sort と複数回の
    AVX-512 演算が point 検索の強みを相殺するため。read-only segment の事前ソートで
    binary search を可能にするのが future work (§3.3 Range Search)。
  - [paper] メモリフットプリント (Fig. 8、メモリ消費を報告する ALEX+/ART+/LIPP+ のみ
    比較): LIPP+ は ART+ の 2 倍超。LiBox と ALEX+ は ART+ より一貫して小さく
    互いに同程度だが、スループットは LiBox が上 — box の計画的な空き slot は
    正当化されると主張 (§3.3 Memory Space)。
  - [paper] α 感度 (Table 3, Fig. 9a; Genome, β=50%): α を 5%→50% にすると bottom
    segment は 1,282,918→332,393 に減り、overflow box は 450,080→1,389,417 に増える。
    RO/WO ともスループットは α 増で低下するが、overflow box が regular box に
    比較的均等に分散するため劣化は緩やか。index サイズは中程度減少。デフォルト
    α=10% (§3.3)。
  - [paper] β 感度 (Table 4, Fig. 9b; α=10%): β を 10%→80% にすると top segment は
    246→1,837、bottom segment は 1,528,519→967,224、regular box は
    3,697,200→4,131,951。興味深いことに overflow box も 494,643→721,685 に増える —
    α/β は個々の box でなく segment 単位の累積比を制約するため、大きい β は疎な
    window の混入を許し、後から密な window も admit されて個々の box が overflow
    しやすくなる。スループット低下とサイズ増はいずれも小さい。デフォルト β=50%
    (§3.3)。
- [inference] 評価がカバーしていないもの:
  - レイテンシ(平均・tail)の測定が一切ない。スループットのみ。re-segmentation
    (特に top-level の即時再編、§2.6)が writer を排他ブロックする間の停止時間や
    発動頻度も数値化されていない。
  - アクセス分布は「全キーの random shuffle」による一様のみ (§3.2)。Zipfian など
    skew した read/write の実験が無く、特定キー領域への集中挿入で overflow chain
    (L=2 で再編発動)や box ロック競合がどう振る舞うかは不明。
  - range search はクエリ長 100 の単一設定 (Fig. 7) で、range と point の混合
    workload や長短の掃引が無い。learned 系の range 比較相手も ALEX+ のみ。
  - 削除を含む workload が無い(underflow 起因の re-segmentation は設計記述のみ)。
  - メモリ比較 (Fig. 8) に XIndex と SALI が含まれない(「明示的にメモリ消費を報告
    する index のみ」という基準)。B+-tree も含まれない。
  - 単一 NUMA ノード限定 (§3) で、NUMA 跨ぎ・マルチソケットのスケーリングは
    未評価。
  - comparison byte の衝突率(box あたりの余分な full-key 比較回数)の実測分布は
    示されていない(「very rare」の定性主張のみ、§2.4)。

## Limitations
- Stated [paper]:
  - AVX-512 非搭載 CPU では box 内キーのソート保持と binary search が必要になり
    insert コストが増える。AVX-512 は LiBox の性能優位の維持に必須 (§2.4)。
  - range search では明確な性能優位が無い(境界 box の local sort + 複数 AVX-512
    演算のため)。read-only segment の事前ソートは future work (§3.3 Range Search)。
  - 対応キー型は現状の整数キーで、他のキー型・データモダリティへの拡張は
    future work (§4)。
- Inferred [inference]:
  - 設計が AVX-512 の 512bit 幅(= 64 個の 1B comparison byte)に強く結合している。
    box 容量 64・comparison byte 1B という選択は §2.4 の記述上この命令幅に由来して
    おり、キー数/box を増やす・衝突率を下げる(byte を増やす)には命令回数との
    トレードオフに直面するはずだが、その設計空間は探索されていない。
  - overflow box の共有→二分割という split 規則 (§2.3) は segment 内の挿入が一様で
    あることを暗黙に想定して見える。挿入がごく少数の box に集中すると、共有
    overflow box の分割が「関係ない半分」にも波及する一方、ホットな box の
    overflow list だけが L=2 に達して re-segmentation が頻発する可能性がある
    (skew 実験が無いため検証不能)。
  - top-level re-segmentation は全検索の通り道の排他再編であり (§2.6, §2.7)、
    Genome/OSM のように top segment が数千ある場合の再編中 write 停止の影響は
    スループット平均では見えない(tail レイテンシ未測定と併せて盲点)。
  - BAL workload は「write 直後に既存キーを read」という定義 (§3.2) で、read が
    直近の write と同じキーに当たるとは限らない。write→read の因果的な
    read-your-writes 型アクセスや hot-set アクセスでの挙動は別問題として残る。

## Relations
- 競合 baseline(本文 §3): ALEX+ / LIPP+ / XIndex / SALI(learned)、B+-tree / ART+
  (非 learned)。実装はいずれも GRE ベンチマーク・スイート [31, 4] 由来。
- [[2026-edbt-liu-learned-index-lsm.md]](learned index の LSM 統合ベンチマーク):
  同じ learned index 領域の直接の隣接研究。Liu らは immutable なディスク上 sorted run
  (fence pointer 置換)での learned index を評価し、LiBox は in-memory で updatable な
  learned index を設計する。LiBox が §4 で単一パス構築の系譜として挙げる
  PGM / RadixSpline は Liu ノート側で data-clustered 系の主要候補として評価されており、
  「last-mile search のコスト構造」を静的(LSM)/動的(in-memory)両文脈で突き合わせる
  比較軸になる。
- [[2026-fast-wei-dmtree.md]](DMTree: disaggregated memory 上の range index):
  DMTree は learned index(ROLEX)を含む DM 上 range index の read amplification を
  問題視し、leaf 内 1B fingerprint table で精密位置特定を行う。[inference] LiBox の
  「box 内 1B comparison byte 配列 + 一斉比較」は単一ノード SIMD 版の同型の発想で
  (どちらも 1B ダイジェストの並びで last-mile を 1 回の走査に潰す)、この構造を
  RDMA/DM に持ち出す発想の接点になる(下の Idea seeds 参照)。

## Idea seeds
- [inference] 「不規則性を box に閉じ込めて box 粒度の線形性を作る」変換は、LSM の
  immutable な sorted run 上でこそ単純化する: 更新が無いので overflow box も
  re-segmentation も不要になり、α/β を構築時に一度だけ最適化すればよい。
  fence pointer 置換(2026-edbt-liu-learned-index-lsm.md の枠組み)として LiBox 静的版を
  PGM/RadixSpline と比較する価値がある(メモリ/lookup と、ブロック粒度が box 粒度と
  揃うか)。最初の検証: 公開コード(https://github.com/strivesnail/Libox.git)から
  構築パスだけ抜き出し、SOSD 系データセットで PGM とサイズ・lookup を比較。
- [question] unsorted box + 1B ダイジェスト配列という構造は disaggregated memory に
  持ち出せるか。box(64 keys × 16B = 1KB)は 1 RDMA read の単位として自然で、
  comparison byte 配列(64B)だけを compute 側にキャッシュすれば remote read を
  1 slot に絞れる — これは DMTree の collaborative fingerprint caching とほぼ同じ役割に
  なる。開いた問い: 誤差ゼロの box 特定(線形関数)が internal node キャッシュを
  どこまで置換できるか。検証: DMTree(公開 artifact あり)の leaf を LiBox box に
  置換し RDMA 回数を比較。
- [inference] range 性能の弱さは「box 内 unsorted」の直接コストであり、著者の
  future work(read-only segment の事前ソート、§3.3)は §2.6 の compaction-ready
  フラグ機構(top box 占有率 80% で背景再編)をほぼ流用して実装できるように見える。
  最初の検証: 公開コードで境界 box のソート有無を切り替えて Fig. 7 の range 実験を
  再現し、point 性能への副作用(insert 時のキー移動)を測る。
- [question] tail レイテンシは本当に問題にならないのか。box 粒度ロック + out-of-place
  再編という設計は tail に有利なはずだが、top-level の即時排他再編 (§2.6) が
  スパイクを作る可能性は未測定。検証: 公開コードで WO workload 中のレイテンシ
  分布(p99/p999)を取り、re-segmentation イベントと突き合わせる。

## Changelog
- 2026-07-06: created (status: read)
- 2026-07-06: 検証パスによる修正(Alg.2 検索経路の段抜け補正: top box の SIMD 検索で bottom segment を特定する段を復元。LIPP+/SALI 議論のページアンカー p.9–10 → p.8–9)
