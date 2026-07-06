---
title: "Xerxes: Extensive Exploration of Scalable Hardware Systems with CXL-Based Simulation Framework"
authors: [Yuda An, Shushu Yi, Bo Mao, Qiao Li, Mingzhe Zhang, Diyu Zhou, Ke Zhou, Nong Xiao, Guangyu Sun, Yingwei Luo, Jie Zhang]
venue: "FAST '26 (24th USENIX Conference on File and Storage Technologies)"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/fast/AnY00ZZ000L026"}
urls: {paper: "https://www.usenix.org/conference/fast26/presentation/an", pdf: "literature/pdfs/2026-fast-an-xerxes.pdf", code: "https://github.com/ChaseLab-PKU/Xerxes"}
status: read
read_date: 2026-07-06
tags: [cxl, simulation, interconnect, cache-coherence, port-based-routing, device-managed-coherence, snoop-filter, pcie, memory-expansion, disaggregated-memory]
---

## TL;DR
CXL 3.0/3.1 の新機能 — Port-Based Routing(PBR、非ツリー任意トポロジ)と
Device-Managed Coherence(DMC、デバイス側コヒーレンス管理)— は対応ハードウェアが
存在せず、既存の NUMA エミュレーション・挙動再現型シミュレータ(Lat-BW 曲線注入)・
計算中心/ネットワーク中心の伝統的シミュレータのいずれでも探索できない。Xerxes は
interconnect layer(グラフベース接続 + PBR)と device layer(全デバイスを能動的 peer
agent として扱い、DCOH snoop filter を実装)の2層から成る C++ 製シミュレーション
フレームワークで、gem5 / DRAMsim3 / SimpleSSD と統合可能。実 CXL ハードウェアでの
検証で帯域誤差 0.1–10%、負荷時レイテンシ平均誤差 4.3% を主張。DSE により (1) tree
トポロジは root ボトルネックで chain 並みに劣化、(2) DMC snoop filter には LRU でなく
LIFO 系の victim 選択が適する、(3) full-duplex の read-write 混合利得はヘッダ
オーバーヘッドに強く依存する、という3つの観察を導く。

## Problem & motivation
- [paper] PCIe はコヒーレンス機構を欠くため、外部 PCIe メモリデバイスでホストの
  ローカルメモリを拡張できない。PCIe デバイスメモリへのアクセスは non-cachable で
  なければならず、CPU コアはコピーを内部キャッシュに保持できず、ソフトウェアによる
  コヒーレンス維持が必要 → 大規模データ集約アプリの要求を満たせない (§1)。
- [paper] CXL は PCIe の物理層の上に構築された cache-coherent interconnect。3つの
  sub-protocol(CXL.io = I/O・設定、CXL.cache = デバイスがホストメモリを coherent に
  アクセス、CXL.mem = デバイスメモリを byte-addressable にホストへ公開)と 3 種の
  デバイスタイプを定義 (§2.1, Fig. 1)。CXL 2.0 以前のスイッチは Single/Multiple VCS
  モードで PCIe 互換のツリー階層として動作 (§2.1, Fig. 2a, 2b)。
- [paper] 初期 CXL 仕様の 2 つの障壁: ①ツリー型トポロジ(HBR)は root に通信ボトル
  ネックを作り、異なるブランチ間の直接通信を妨げる。②ホスト管理コヒーレンスは
  多数の intelligent peer デバイスにスケールしない (§2.2)。
- [paper] CXL 3.0+ の対策: **PBR** = ソース/宛先ポート ID(12-bit、最大 4096
  エンドポイント)とスイッチ内ルーティングテーブルによる転送で、mesh や spine-leaf 等の
  任意非ツリートポロジを可能にする (§2.2, Fig. 2c)。**DMC** = デバイス上の DCOH
  (Device Coherency Agent)がローカルメモリのコヒーレンスを管理する HDM-DB モード。
  peer が他 peer にキャッシュ済みの cacheline への排他アクセスを要求すると、DCOH が
  CXL.mem の専用チャネルで BISnp(Back-Invalidate Snoop)を全 sharer/owner に送り、
  BIRsp 収集後に所有権を付与(dirty なら BIRsp が更新データを運ぶ)。HDM-DB 利用
  デバイスは PCIe 6.0 物理層(64 GT/s/lane)上での動作が要求される (§2.2)。
- [paper] CXL 3.0+ 対応ハードウェアは現在入手不可能で、初期研究にはシミュレーション/
  エミュレーションが必須 (§2.3)。しかし:
  - NUMA エミュレーション: UPI 等の NUMA インターコネクトと実 CXL デバイスには
    プロトコルレベルの乖離があり(先行研究 [56] の報告)、新機能でさらに悪化。
    ソケット数の物理制約で 4096 エンドポイント規模の fabric をエミュレートできない (§2.3)。
  - 挙動再現型 CXL シミュレータ(MESS, CXLMemSim): 事前測定した Lat-BW 曲線を
    入力に遅延注入する方式で、reproductive であって predictive でない。既知デバイスの
    アプリへの影響評価には向くが、PBR のマルチパスルーティングや DMC の snoop
    メッセージのネットワークレイテンシはモデル化できない (§2.3)。
  - 計算中心シミュレータ(gem5, GPGPUsim): メモリシステムが CPU 密結合の厳格な
    階層で fabric をモデル化できず、コヒーレンスが中央集権エンジン(directory
    controller)管理で peer-to-peer の DMC と非互換。gem5 のネイティブ対応は legacy
    PCI 止まり (§2.3)。
  - ネットワーク中心シミュレータ(BookSim, Garnet): トポロジ・ルーティングは扱えるが
    メモリ・コヒーレンス意味論を持たず、汎用パケットの流れしかモデル化しない (§2.3)。

## System model & assumptions
- [paper] 設計原理: ①modularized design(interconnect fabric とデバイス機能ロジックの
  分離)、②graph-based connectivity(システム接続をグラフとして構築し任意非ツリー
  トポロジをネイティブ対応)、③peer-centric device model(ホストもアクセラレータも
  全て能動的 peer としてモデル化。DMC のシミュレーションに必須)(§3.1)。
- [paper] 計算主体は全て Requester という統一コンポーネントに抽象化: request queue
  (キュー深さ + 発行間隔で on-the-fly 要求数をモデル化)、address translation unit
  (複数メモリエンドポイント間の interleaving ポリシー)、cache coherence management
  unit(内部キャッシュ状態を保持し BISnp に応答)から成る。合成トラフィック生成
  モードとアプリケーショントレース再生モードの両方で動作 (§3.3)。
- [paper] シミュレーション対象の検証ハードウェア: dual-socket、各ソケット Intel Xeon
  Gold 6416H + DDR5-4800 DIMM×8(ピーク 76.8GB/s、主記憶 512GB)。片ソケットに
  Montage MXC コントローラ搭載 CXL memory expander(**CXL 2.0 / PCIe 5.0×16 まで
  対応**、DDR5-4800×4、HDM-H 128GB)。expander はローカルソケットに PCIe レーン、
  リモートソケットに MCIO ケーブルで接続され、ケーブルが物理レーンの半分を専有する
  ため各ソケットは PCIe 5.0×8 相当(理論 32GB/s、実効 24GB/s)しか使えない (§4, Fig. 5)。
- [paper] シミュレーションのレイテンシ設定(Table 2): requester 処理 10ns、cache
  access/invalidate 12ns、device controller 処理 40ns、PCIe port 遅延 25ns、bus 1ns、
  switch port-to-port 25ns。値は複数の公開先行研究の典型値から導出 (§4, Table 2)。
- [paper] CXL 3.1 機能(PBR / DMC)はハードウェアが存在しないため、実測でなく
  理論性能モデル(校正済み遅延の合算)との比較で正しさを検証する方針 (§4)。
- [paper] Xerxes 単体モードはトレース駆動: Intel PIN でメモリアクセストレースを収集し、
  シミュレートしたキャッシュ階層でフィルタして Xerxes に投入。実行駆動は gem5 統合
  (SE モード)で行う (§4)。
- [inference] つまり Xerxes 自体は CPU マイクロアーキテクチャを持たない
  メモリシステム/インターコネクトシミュレータであり、エンドツーエンド評価の忠実度は
  トレースの代表性か gem5 側のモデルに依存する(§3.6, §4 の構成から)。
- [paper] DSE の負荷モデル: §5.1 は N requester + N memory device(system scale = 2N)、
  requester は全メモリデバイスへランダムに要求を発行、スイッチポート帯域は一定値に
  固定 (§5.1)。§5.2 は skewed パターン(要求の 90% が hot データ、hot データは全
  フットプリントの 10%)、ローカルキャッシュ = フットプリントの 20%(hot データを
  全て収容)、SF サイズ = ローカルキャッシュサイズ、bus は帯域無限に設定 (§5.2)。

## Approach
- [paper] **2 層アーキテクチャ** (§3.2, Fig. 3):
  - Interconnect layer: 初期化時にシステムトポロジのグラフ表現を構築し、デフォルトの
    shortest-path ルーティングを全コンポーネントに提供。スイッチ等の複雑な
    コンポーネントはトポロジグラフを直接照会してカスタムルーティングを実装可能 (§3.2)。
  - Device layer: ホスト・アクセラレータ・メモリモジュールを全て agent として統一
    モデル化し、中央デバイス(ホスト CPU)を介さず能動的に動作。デバイスロジックが
    interconnect から分離されているため、既存シミュレータの統合やカスタム CXL
    デバイスのプロトタイピングがネットワーク側の変更なしに可能 (§3.2)。
  - C++ 実装。ユーザは設定ファイルを用意するだけでシステムを構成・シミュレートできる (§3.2)。
- [paper] **Interconnect コンポーネント** (§3.4): bus はデバイス間物理リンクを模擬し、
  CXL 3.1 が利用する PCIe 6.0 物理層の **full-duplex 伝送モデル**(双方向同時転送を
  追跡し方向別に全帯域を割当)を実装。帯域・レイテンシ・half-duplex 動作
  (turnaround オーバーヘッド設定可)などが設定可能。switch は PBR 対応スイッチの
  全機能を実装し、interconnect layer のルーティング情報から内部転送テーブルを構築 (§3.4)。
- [paper] **Device-side snoop filter(SF)= DMC の具体実装** (§3.5): 独立した
  fully-associative バッファモジュール。各エントリは peer agent にキャッシュされた
  ラインのコヒーレンスメタデータ(state、owner list)を追跡。所有権競合時は元 owner に
  BISnp を発行してから新要求を処理。バッファ満杯時は victim を選択し BISnp で
  エントリをクリア(dirty ラインは該当エンドポイントに書き戻し)。victim 選択手続きは
  モジュール化されポリシー差し替え可能 (§3.5)。
- [paper] **既存シミュレータとの統合** (§3.6, Table 1, Fig. 4):
  - gem5: XerxesWrapper が gem5 MemCtrl を拡張し、UpInterface / DownInterface が
    gem5 のメモリパケットと Xerxes 要求を相互変換、完了イベントは gem5 のイベント
    キューを再利用。DMC 機能は gem5 ネイティブの SLICC で coherence interface を実装し、
    Xerxes 側 DCOH の back-invalidation を gem5 キャッシュ階層の無効化イベントに変換 (§3.6, Fig. 4a)。
  - DRAMsim3(cycle-based): wrapper が定期的に clocking イベントを登録して進行 (§3.6, Fig. 4b)。
  - SimpleSSD(event-driven): wrapper がイベント形式を変換して Xerxes イベント
    エンジンに登録 (§3.6, Fig. 4c)。

## Evaluation
### 検証(実ハードウェア・理論モデル比較, §4)
- Setup [paper]: 上記 dual-socket + CXL 2.0 expander プラットフォーム。比較対象:
  NUMA エミュレーション(公平のため DIMM 数を expander と同じ 4 に調整)、
  MESS / CXLMemSim(**実ハードウェア実測の Lat-BW を入力に与えた best-case 設定**)、
  gem5-garnet。トラフィック生成は Intel MLC(ハードウェア側)/ Xerxes requester
  (シミュレーション側)。Xerxes のエンドポイントには統合 DRAMsim3 を使用 (§4, Table 2)。
- Idle latency / bandwidth (Fig. 6): 校正後の Xerxes は NUMA エミュレーションより
  高いレイテンシ精度。帯域は CXL ハードウェア比誤差 0.1–10%(NUMA remote DRAM は
  絶対値を再現できない)。read-write 混合比が上がると CXL ハードウェアと Xerxes は
  帯域が大きく増加するが、NUMA エミュレーションの増加はごく小さい (§4, Fig. 6)。
- Loaded latency(Lat-BW 曲線, Fig. 7): Xerxes は read/write とも CXL ハードウェアの
  曲線に整合し平均誤差 4.3%。NUMA エミュレータの曲線は完全に乖離。MESS 9.3%、
  CXLMemSim 16.6%(実測データ入力にもかかわらず)(§4, Fig. 7)。
- 先進機能の理論モデル検証 (Fig. 8): PBR はスイッチホップ数 0–7 のパスで平均
  レイテンシ予測誤差 10.4%。DMC は BISnp/BIRsp 往復を要する dirty write の
  レイテンシが理論値と誤差 1.4% (§4, Fig. 8)。
- SPEC CPU2017 エンドツーエンド (Table 3): CPU マイクロアーキテクチャの影響を
  除くため「CXL メモリ起因の実行時間オーバーヘッド」を指標に採用。実機 gcc 18.0% /
  mcf 24.2% に対し、Xerxes 単体 +0.7% / +5.6%、gem5-Xerxes −2.4% / −4.4%。
  比較: NUMA 最大 −9.2%、gem5-garnet 最大 −9.0%、gem5-MESS 最大 −28.3%、
  CXLMemSim 最大 −16.5%(挙動再現型は遅延を平均集約として適用するため個々の
  アクセスの正確なタイミングを捉えられない、と分析)(§4, Table 3)。
- シミュレーション速度 (Table 4): vanilla gem5 比で gem5-MESS は平均 6.0% 高速化
  (gem5 の詳細 DRAM シミュレーションをバイパスするため)、gem5-Xerxes は平均 +2%
  のオーバーヘッド、gem5-garnet は +22.5% (§4, Table 4)。

### DSE①: システムトポロジ (§5.1)
- [paper] 5 トポロジ(chain / tree / ring / spine-leaf / fully-connected, Fig. 9)、
  scale 4–16 で集約帯域を比較 (Fig. 10): chain と tree は全 requester が共有する
  「bridge」経路(chain のスイッチ間経路、tree の root スイッチ直結経路)により
  帯域がスイッチポート 1 本分に頭打ちで、スケールしても改善しない。ring は迂回路
  1 本追加で 2×。spine-leaf は spine でボトルネック経路を置換するが leaf ポートの
  競合が残り N/2×。fully-connected はペア間直結で N× (§5.1, Fig. 10)。
- [paper] ISO-bisection bandwidth 条件・scale 16 のレイテンシ (Fig. 11): ホップ数
  増加でレイテンシ増。bridge 経路の輻輳により最大ホップのレイテンシは最小ホップ比で
  chain 2× / tree・ring 1× 長く、予測不能性ももたらす。spine-leaf / fully-connected は
  ホップが少なく安定 (§5.1, Fig. 11)。
- [paper] シミュレーションコスト: scale 1→64 で実行時間 90 秒未満、メモリは大半の
  トポロジで 200MB 未満。fully-connected はリンク数が二次関数的に増えるため急峻 (§5.1, Fig. 12)。
- [paper] 実ワークロードトレース(BTree, liblinear, redis, silo, XSBench)の再生:
  chain / tree が最低スループット・最高レイテンシ。ring は最大 1.72×、spine-leaf /
  fully-connected は最大 3.63× のスループット向上 (§5.1, Fig. 13)。
- [paper] データ集約ワークロード(Bert = AI 推論、Pagerank = グラフ解析、YCSB-F =
  インメモリ DB。トレースは公開データセット [51,63] 由来): 標準的なツリー型メモリ
  拡張構成(requester 1 + エンドポイント 1→16)で、スイッチ内ルーティングロジックと
  ポート競合により平均レイテンシ約 9× 増 (§5.1, Fig. 14)。

### DSE②: Back-invalidation / DMC (§5.2)
- [paper] SF victim 選択ポリシー 5 種(FIFO / LRU / LFI / LIFO / MRU)を skewed
  ワークロードで比較 (Fig. 15): SF ではヒットイベントがほぼ無いため FIFO≈LRU、
  LIFO≈MRU。**LIFO は FIFO 比で帯域 +5%、平均レイテンシ −15%、invalidation 数
  −16%**。理由: 定常状態では hot データはローカルキャッシュに常駐し SF はその
  コヒーレンス状態を記録、SF に届く要求の大半は cold データへのキャッシュミス。
  よって「last-in / most recent」なエントリこそ cold データの情報を持つ適切な victim で、
  FIFO / LRU は hot データを invalidate しがち (§5.2, Fig. 15)。
- [paper] 著者ら提案の LFI(Least Frequently Inserted、挿入回数のグローバルカウンタ
  表を保持)は invalidation 数を FIFO 比 −15% にするが、挿入回数が均一化すると全
  hot cacheline を周期的に invalidate してしまい LIFO / MRU よりわずかに劣る (§5.2, Fig. 15)。
- [paper] プロトコルレベル最適化 InvBlk(1 つの BISnp で連続アドレスの 2–4 cacheline を
  一括 invalidate)の評価 (Fig. 16): 長さ 2 で invalidation 待ち時間が減り帯域増・
  レイテンシ減。しかし 2 超では requester ローカルキャッシュへのアクセスオーバー
  ヘッドが増え、BISnp 内のデータフローが伝送帯域を奪い合うため長さ 2 から改善なし
  (§5.2, Fig. 16)。

### DSE③: Full-duplex 伝送 (§5.3)
- [paper] 指標: bus utility(bus がビジーな時間割合)、transmission efficiency(bus
  伝送時間中 payload 伝送の割合)(§5.3)。requester 1 + bus + メモリデバイス 4 の
  専用システムで R:W 比とヘッダオーバーヘッドを掃引 (§5.3)。
- [paper] half-duplex bus の帯域は R:W 比にほぼ不変だが、full-duplex は read-write
  混合で帯域が向上。ヘッダオーバーヘッド 0 なら 1:1 混合で帯域ほぼ 2×。ヘッダ長 =
  payload 長では利得ゼロ (§5.3, Fig. 17)。単一方向トラフィックは full-duplex の片方向
  しか使えず、混合が両方向を同時利用して bus utility を倍にする一方、ヘッダ増は
  transmission efficiency を下げて利得を食い潰す (§5.3, Fig. 18)。
- [paper] 実ワークロードトレースでは mix degree(= min{read_ratio, write_ratio})の
  増加が half-duplex 比のスピードアップを拡大 (Fig. 19a)。silo では mix degree と帯域に
  強い正相関があり、mix degree +0.1 ごとに帯域 +9%。「CXL メモリ上ではワークロードが
  read と write をより積極的に混ぜると性能が上がる」ことを示唆 (§5.3, Fig. 19b)。

### 評価がカバーしていないもの
- [inference] 実ハードウェア検証は CXL 2.0 / PCIe 5.0 の memory expander **1 台**
  (HDM-H)構成のみ (§4, Fig. 5)。マルチデバイス・マルチホストで coherent 共有する
  構成のハードウェア照合は存在しない。PBR / DMC の「検証」は著者ら自身が校正済み
  遅延から組み立てた理論モデルとの一致 (§4, Fig. 8) であり、独立した ground truth では
  ない(遅延パラメータも Table 2 の文献値由来)。
- [inference] エンドツーエンド精度検証は SPEC CPU2017 の 2 ワークロード(gcc, mcf)
  のみ (Table 3)。Xerxes 単体の mcf 誤差 +5.6% は gcc(+0.7%)より大きく、
  トレース駆動 + キャッシュフィルタの限界がワークロード依存で現れる可能性がある。
- [inference] トポロジ DSE (§5.1) のトラフィックは全メモリデバイスへの一様ランダム
  発行。skew やホットスポット(DB ワークロードで典型)がある場合に spine-leaf の
  leaf 競合や bridge 輻輳の結論がどう変わるかは未評価(§5.2 の skew 実験は SF 対象で
  トポロジは扱わない)。
- [inference] SF 実験は requester 1(victim policy)または 2(InvBlk)の小構成 (§5.2)。
  DMC の本来の動機である多数 peer 間共有(BISnp の多 sharer ファンアウト)での
  挙動・スケーラビリティは探索されていない。

## Limitations
- Stated [paper]:
  - CXL 3.1 機能(PBR / DMC)対応ハードウェアが存在せず、実測検証は不可能。
    理論性能モデルとの比較で代替 (§4)。
  - 実アプリ性能は CPU マイクロアーキテクチャに強く依存するが、それは未知で正確に
    シミュレートできないため、指標を「CXL メモリ起因のオーバーヘッド」に限定 (§4)。
  - full-duplex の read-write 混合効果は「エンドツーエンド性能に影響する複数要因の
    ひとつ」であることを明記 (§5.3 Takeaway)。
  - fully-connected トポロジのシミュレーションメモリはリンク数の二次増加により急増
    (それでも scale 64 まで実用範囲と主張)(§5.1, Fig. 12)。
- Inferred [inference]:
  - 「予測的(predictive)」の主張の実証は、ハードウェアが存在する CXL 2.0 領域では
    強い(Fig. 6, 7, Table 3)が、CXL 3.1 領域では自己構築した解析モデルとの一致に
    依存しており、実機登場後に PBR 輻輳・DMC プロトコル実装の細部(リトライ、
    順序保証等)で乖離が出る余地がある。
  - Requester のトラフィックモデルは request queue + 発行間隔の抽象 (§3.3) で、
    実 CPU の MLP・プリフェッチ・メモリ順序の効果はトレース or gem5 統合頼み。
    Xerxes 単体モードのトレースはキャッシュ階層フィルタ済みで、タイミング
    フィードバック(遅延がアクセス列自体を変える効果)は再現されないはず。
  - SF victim 選択の知見(LIFO 優位)は「ローカルキャッシュが hot データを全て収容
    できる」設定 (§5.2) に依存する。キャッシュ容量が hot set より小さい(SF にも hit
    が発生する)場合に結論が保たれるかは示されていない。

## Relations
- 本文中の比較対象: NUMA エミュレーション、MESS / CXLMemSim(挙動再現型 CXL
  シミュレータ)、gem5 / GPGPUsim(計算中心)、BookSim / Garnet(ネットワーク中心)
  (§2.3, §4)。統合先: gem5, DRAMsim3, SimpleSSD (§3.6)。
- [[2026-pvldb-zhao-sidle.md]](SIDLE: CXL 索引配置): CXL 上のデータ構造配置を扱う
  DB 側研究に対し、Xerxes は PBR トポロジや DMC まで含む CXL 3.1 環境を評価する
  シミュレーション基盤を提供する。[inference] SIDLE 型の配置判断を CXL 3.1 fabric
  (マルチスイッチ・マルチホスト)へ拡張する際の評価手段として直接接続する。
- [[2026-edbt-lee-cxl-pools.md]](CXL メモリプール): [inference] Xerxes のトポロジ
  DSE(tree の root ボトルネック、spine-leaf / FC のスケーラビリティ、Fig. 10–14)は
  CXL プール構成の設計選択に定量的根拠を与える関係。
- [[2026-cidr-huang-cxl-hash-joins.md]](CXL 上の hash join): [inference] CXL メモリの
  帯域・レイテンシ特性に依存する DB オペレータ研究であり、Xerxes の full-duplex
  分析(R:W 混合で帯域向上、§5.3)や拡張スケール時のレイテンシ増(Fig. 14)は
  この種のワークロード評価の前提条件に関わる。
- [[2026-fast-wei-dmtree.md]](DMTree: disaggregated memory 索引): DMTree §4.3 は
  CXL 環境への適用可能性を議論するが実験は RDMA のみだった。[inference] Xerxes の
  ような CXL fabric シミュレータは、ああした「CXL でも有効」という主張を(実機不在
  でも)定量検証する手段になる。
- [[2026-edbt-krause-disaggregated-survey.md]](分離型アーキテクチャのサーベイ):
  [inference] 分離メモリ研究の評価方法論(NUMA エミュレーション常用)に対し、本論文
  §2.3 はその精度限界(プロトコル乖離・スケール制約)を定量的に指摘する位置にある。

## Idea seeds
- [inference] DMC の SF victim 選択の知見(SF に届くのはほぼ cold miss、LIFO/MRU が
  適切、§5.2)は、DB のバッファプールと CXL デバイス側コヒーレンスディレクトリの
  「二重キャッシュ」問題として読める。マルチホストが CXL 共有メモリ上の DB ページ
  (索引 root、lock word)を共有すると、hot ページの BISnp 無効化がトランザクション
  レイテンシに直撃するはず。最初の検証: 公開されている Xerxes(configs + traces、
  Appendix A)で YCSB/silo 系トレースを複数 requester に分割再生し、SF サイズ・
  ポリシー掃引で invalidation 数とレイテンシ分布を測る。
- [inference] full-duplex の mix degree 相関(+0.1 → 帯域 +9%、silo、Fig. 19b)は、
  DB エンジン側で read と write の発行を意図的にインターリーブする(例えば WAL
  書き込みや dirty page write-back を read バーストに混ぜる)スケジューリングが CXL
  メモリ上で帯域利得を生む可能性を示す。検証: Xerxes の bus モデルで、同一トレースの
  read/write 並べ替え(意味論を保つ範囲で)による帯域変化を測る。
- [inference] ツリー型メモリ拡張で 16 エンドポイント時に平均レイテンシ約 9×
  (YCSB-F 含む、Fig. 14)という結果は、larger-than-memory DB の buffer manager が
  CXL 拡張メモリを「一様な second tier」と扱う近似を壊す。トポロジ/ホップ数を意識
  したページ配置(hot ページを低ホップのエンドポイントへ)の効果を Xerxes 上で
  検証できる。
- [question] HDM-DB(DMC)は PCIe 6.0 物理層を要求する (§2.2)。現行の CXL 2.0
  世代ハードウェアを前提にした DB 側のマルチホスト共有設計(ソフトウェア
  コヒーレンス)と、DMC ネイティブな設計のどちらが DB ワークロードに有利かは
  開いた問題 — Xerxes は両方をモデル化できるはずで、比較実験の土台になるか要調査。
- [question] Xerxes 単体モードのトレース駆動は、コヒーレンス起因のストール(BISnp
  待ち)がアクセス列に及ぼすフィードバックをどこまで再現できるのか。DB のロック
  競合のような timing-dependent な挙動の評価には gem5 統合が必須かもしれない
  (§3.6 / §4 の構成からの疑問)。

## Changelog
- 2026-07-06: created (status: read)
