---
title: "A Logically Disaggregated Cache for Replicated Storage Systems"
authors: [Kiran Hombal, Henry Zhu, Shreesha G. Bhat, Neil Kaushikkar, Ramnatthan Alagappan, Aishwarya Ganesan]
venue: "EuroSys"
year: 2026
ids: {doi: "10.1145/3767295.3803608", arxiv: "", dblp: "conf/eurosys/HombalZBKAG26"}
urls: {paper: "https://doi.org/10.1145/3767295.3803608", pdf: "literature/pdfs/2026-eurosys-hombal-disagg-cache.pdf", code: "https://github.com/dassl-uiuc/Logically-Disaggregated-Caches"}
status: read
read_date: 2026-07-06
tags: [caching, replication, disaggregation, key-value-store, storage, rdma, cache-redundancy, cost-benefit-analysis]
---

## TL;DR
レプリケートストレージの各レプリカに埋め込まれたキャッシュはサイロ管理され、読み・書き
両方の経路で同一オブジェクトが複数レプリカに重複キャッシュされる(5つの実システムで
CSF 計測により定量化)。Ldc は埋め込みキャッシュ群を「単一の論理キャッシュ」として
論理的に分離し、①任意レプリカから one-sided RDMA で他レプリカのキャッシュを直接読む
(リモートヒット、デフォルトではローカル非アドミット)、②書きは main cache とは別の
tiny queue(キャッシュの 0.01%)に選択的に入れて素早く demote、③オンラインの
cost-benefit analyzer (CBA) が「重複キャッシュすべきホットオブジェクト数 R_opt」を
解析モデルで周期決定、の3点で重複とカバレッジを両立する。Twig-kv(eventual)、
Craq-kv(CRAQ で線形化可能)、RethinkDB(プロダクション、読みパスのみ)に実装し、
YCSB で 2.6×–5.4×(Twig-kv)/ 2.5×–5.9×(Craq-kv)、実トレース 50 本で平均 1.57×
のレイテンシ改善を報告。

## Problem & motivation
- [paper] レプリケートストレージの各レプリカ(分散プロトコル層+ストレージエンジン+
  埋め込み in-memory キャッシュ)はキャッシュをサイロで管理し、レプリカ間で同一
  オブジェクトを重複キャッシュして貴重なメモリを浪費する。メモリはデータセンタ
  サーバコストの最大 50% を占める (§1, p.1)。
- [paper] 重複の原因は2つ: 書きは全レプリカに適用されキャッシュ経由で行われるため
  同一オブジェクトを全キャッシュに持ち込む。読みは異なるクライアントが同一
  オブジェクトを別レプリカから読むことで重複を生む (§1, p.1)。
- [paper] 重複の定量化に cache similarity factor (CSF) を定義:
  CSF = (1 − |∪C_i| / ΣS_i) · (N/(N−1))。全キャッシュ同一で 1、完全排他で 0 (§2.2)。
- [paper] 5システム(RethinkDB / RQLite / Replicated SplinterDB / Cassandra / HBase、
  レプリケーション方式・エンジン・キャッシュ粒度は Table 1)を 3 レプリカ、YCSB、
  24B key / 1KB value、各レプリカキャッシュ = データセットの 33.3% で計測 (§2.2, Fig. 2)。
  RethinkDB は read-only でも CSF ≈ 50%(ページ粒度キャッシュも寄与)、write-heavy で
  75% に上昇し、理想では 100% 入るはずのデータセットの約 50% しかカバーされない (§2.2)。
- [paper] Cassandra は row cache 粒度で CSF が相対的に低く、書きが OS ページキャッシュ
  経由で row cache を invalidate するため write-heavy ではむしろ CSF が下がる。HBase は
  ブロック粒度+書きで invalidate しないため write-heavy で Cassandra より高い (§2.2, Table 1)。
- [paper] 外部キャッシュ(Memcached 等)流の key-based routing は埋め込みキャッシュには
  不十分: (i) 外部キャッシュでは書きはバックエンドに行きキャッシュは invalidate される
  だけだが、埋め込みキャッシュでは書きが全レプリカのキャッシュを通るため routing では
  write 起因の重複を防げない。書き 5%(YCSB-B)で既に劣化し始め、50%(YCSB-A)では
  CSF が random routing 並みに悪化 (§2.3, Fig. 3)。(ii) nested query や join のような
  opaque クエリはアクセスキーが事前に分からず正確に route できない (§2.3)。
- [inference] 「重複 vs カバレッジのトレードオフ」という abstract 段階で読み取った
  フレーミングは本文で §3.4 の CBA として明示的に定式化されており、単なる標語ではなく
  解析モデル(下記 Approach)として実装されている。

## System model & assumptions
- [paper] 対象は shared-nothing のレプリケートストア。クラウドネイティブ DB のように
  fault-tolerance をクラウドストレージにオフロードする構成は対象外(それらも最終的には
  サーバ間レプリケーションに帰着すると注記)(§2.1 脚注, p.3)。
- [paper] 各レプリカ = 分散プロトコル層 + ストレージエンジン(B-tree 等のディスク索引)
  + 埋め込みキャッシュ(オブジェクト粒度またはページ粒度)。読みは任意レプリカで受理
  (eventual が多数派、追加機構で strong も可)。書きはリーダー(またはコーディネータ)
  経由で全レプリカに(少なくとも eventually)適用され、各レプリカでキャッシュ経由で
  dirty 化→周期的 write-back される (§2.1)。
- [paper] ネットワーク仮定: one-sided RDMA が利用可能(データセンタで普及と主張)。
  RDMA レイテンシは数 µs で、SATA SSD の数百 µs、NVMe の数十 µs より速い。fault domain
  を跨ぎ複数スイッチを経由しても disk より速い(先行研究を引用)(§3.2)。RDMA は
  本質ではなく RPC でも実現可能(受信側 CPU 処理とやや高いレイテンシを許容すれば)
  (§3.2, p.2 脚注)。
- [paper] 信頼モデル: 各レプリカのキャッシュ領域は RDMA-able region として全レプリカに
  read 許可、ローカルレプリカのみ read-write 許可で公開される (§4)。
- [paper] 故障モデル: ベースラインと同じ耐故障性(レプリカクラッシュ・ネットワーク
  分断)。追加の単一障害点は導入しない。クラッシュしたレプリカへの RDMA アクセスは
  失敗し、ディスクアクセスパスにフォールバック(この時の性能はベースライン同等)。
  CBA はレプリカ故障時に総キャッシュ容量 C を調整して R_opt を再計算 (§3.5)。
- [paper] 整合性: リモートキャッシュのインデックスは lazy に伝播され stale になり得る。
  Ldc は重複の「排除」ではなく best-effort の最小化を狙う(zipfian でリモートアクセスの
  0.5% が stale index による誤 lookup → ディスクにフォールバック)(§3.2)。リモート読みの
  正しさはオブジェクト ID の照合(意図と違うオブジェクトが page-in されていた場合の検出)
  とチェックサム(ローカル書き込みと並行したリモート読みの partial read 検出→リトライ)
  で担保 (§3.2)。
- [paper] CBA の前提: 直近ウィンドウ t 秒のアクセス頻度分布 A を各レプリカが把握し、
  キャッシュポリシーは top-C オブジェクトを最適にキャッシュすると仮定。l_local /
  l_rdma / l_disk は定数ではなく前ウィンドウの実測値を使用(ネットワーク・ディスクの
  競合を反映)。各レプリカが独立に CBA を実行 (§3.4)。
- [paper] 評価時の運用仮定: クライアントは読みで1レプリカと sticky session を張り、
  書きはリーダーに送る(実運用を模すと主張)(§5 Setup, p.10)。
- [inference] CBA の推定式はユニークキャッシュされたオブジェクトへの読みの 1/N が
  ローカル、(N−1)/N が RDMA になると仮定している (§3.4)。これは読み負荷がレプリカ間で
  ほぼ均等という暗黙の仮定であり、クライアント集合が特定レプリカに偏る配置では推定が
  ずれるはず(本文に感度分析はない)。
- [question] tiny queue に滞留中の書き(メモリのみ、周期 flush)の永続性は誰が保証する
  のか。Twig-kv は非同期レプリケーションで書きを「メモリで吸収」しており (§5.2)、
  WAL や fsync タイミングの記述が本文にない。クラッシュ時のデータ喪失はレプリケーション
  頼みに見えるが明示されていない。

## Approach
- [paper] **アーキテクチャ (§3.1, Fig. 4)**: 各レプリカの物理キャッシュを構成要素とする
  単一の論理キャッシュを形成。個々のキャッシュは自分が論理キャッシュの一部であることを
  「自覚」して動く。分散プロトコルにもストレージエンジンにも変更不要で、変更は
  キャッシュ層に閉じる (§1, §4)。
- [paper] **リモートキャッシュアクセス (§3.2)**: ローカルミス時、リモートキャッシュ
  インデックスのローカルコピーを引き、ヒットすれば one-sided RDMA で当該レプリカの
  キャッシュから直接読む(受信側 CPU 不介入なので相手の負荷を増やさない)。リモートで
  取得したオブジェクトはデフォルトではローカルにアドミットしない(重複を作らない)。
  どこにも無ければディスクから自レプリカのキャッシュに page-in し、インデックス更新を
  lazy に他レプリカへ伝播。stale index による誤 fetch はオブジェクト ID 照合で検出して
  ディスクへフォールバック、並行書き込みはチェックサム検証+リトライで対処 (§3.2, Fig. 4)。
  この設計は正確な routing を不要にし、opaque クエリ(nested/join)も受理レプリカが
  ローカル/リモートキャッシュから必要行を引いて処理できる (§3.1)。
- [paper] **Selective and quick write demotions (§3.3, Fig. 4)**: main cache から切り出した
  レプリカ私有の tiny queue(典型的にはキャッシュの 0.01%)を用意。書き対象が main cache に
  無いレプリカでは queue に入れて周期的にディスクへ evict(= 素早い demote)。既に
  main cache にあるレプリカでは main cache 内で直接更新(重複を増やさないので demote
  不要)。これにより write 起因の重複は queue サイズに制限され、かつ直接ディスク書きの
  遅さも回避。queue 内オブジェクトが読まれたら、他レプリカの main cache に無い場合に
  限り main cache へ promote(重複を作らない昇格)(§3.3)。
- [paper] **Cost-benefit analyzer (CBA) (§3.4, Fig. 5–6)**: 人気オブジェクトへの RDMA
  反復アクセスはローカルメモリより遅いので、重複キャッシュした方が得な場合がある。
  重複レベル R(top-R オブジェクトを全 N レプリカにキャッシュ)を上げるとカバレッジは
  (N−1)·R 減る。推定レイテンシ L_est(R) = Σ_{i≤R} A[i]·l_local
  + Σ_{R<j≤C−(N−1)R} A[j]·(l_local/N + ((N−1)/N)·l_rdma)
  + Σ_{k>C−(N−1)R} A[k]·l_disk を計算し、P_est(R)=1/L_est(R) を最大化する R_opt を
  t 秒ごとに決定 (§3.4, p.7–8)。リモート読みのたびに、対象が頻度上位 R_opt 内なら
  ローカルへアドミット、でなければ非アドミットで応答。R_opt を下げた場合は eviction で
  重複レベルが下がるまで新規アドミットを停止 (§3.4)。Fig. 6 の実例: uniform では
  R_opt=0(カバレッジ全振り)、zipfian ではピーク選択、「アクセスの大半が 30% の
  オブジェクト」のワークロードではキャッシュ 33.3%/レプリカなら 30% を全レプリカに
  重複キャッシュ、10%/レプリカならカバレッジ優先を正しく選ぶ (§3.4, Fig. 6)。
- [paper] **既存システムへの統合 (§4)**: ローカルキャッシュ側の変更は (i) RDMA region 化
  と保護設定、(ii) インデックスの公開と更新共有、(iii) キャッシュオブジェクトへの
  ID・チェックサム付与、(iv) Ldc 層からのアドミット制御(書きの page-in は tiny queue へ、
  読みの page-in は main cache へ)。Ldc 層は RDMA 接続・リモート読み検証・インデックス
  交換・CBA・tiny queue 管理を担い、大部分はシステム間で再利用可能 (§4)。
  - Twig-kv: 自作の eventually-consistent KV(primary-backup、非同期レプリケーション、
    LRU + キャッシュ内索引)。キャッシュ 210 LOC 変更 + Ldc 層 2.5 KLOC (§4.1)。
  - Craq-kv: CRAQ チェーンレプリケーションで線形化可能読みを提供する変種。各
    オブジェクトの clean/dirty バージョン番号を保持し、ローカル読みは両者一致時のみ。
    リモートキャッシュ読みでは clean/dirty バージョンも一緒に fetch して分散層に返し、
    分散層が通常どおりバージョン照合(不一致なら tail から取得)。つまりリモート読みは
    CRAQ の一貫性ロジックを一切変えない(「リモートレプリカが受理してローカルキャッシュ
    から応えたのと同じ」)(§4.2)。
  - RethinkDB: プロダクション DB(Raft、カスタム B-tree、ページキャッシュ)。時間制約で
    読みパスのみ実装(書きパスは未実装)。キャッシュ割当を連続領域化して RDMA region に。
    2.4 KLOC 追加/変更(ローカルキャッシュ 850 行 + 共通 Ldc 1.5 KLOC)で 282 KLOC の
    1% 未満 (§4.3)。

## Evaluation
- Setup [paper]: サーバレプリカ 3 台(一部 5 台)+ 多数クライアント。各マシン
  Intel 10-core E5-2640 v4 / 64GB DRAM / 25Gb Mellanox ConnectX-4 / 480GB SATA SSD
  (CloudLab XL170, Appendix A.2.2)。データセット 10M KV、24B key / 100B value。
  読みは sticky session、書きはリーダーへ。比較は各システムの OrigCache 版 vs Ldc 版。
  実トレース実行にはシミュレータも併用 (§5 Setup, §5.11)。
- Read-only マイクロベンチ (§5.1, Fig. 7): uniform では Ldc は CSF=0 を達成し、キャッシュ
  33.3%/レプリカで全データセットをカバーして 5.3×。zipfian は long tail のためカバレッジが
  効き低 CSF(CBA が人気オブジェクトだけ重複させるためゼロではない)。hotspot
  (読みの 80% が 20% のオブジェクト)ではキャッシュ 10% なら CSF=0 でカバレッジ優先、
  33.3% ならホットオブジェクトを重複キャッシュしつつ高カバレッジ、をそれぞれ正しく選択。
- Read-write マイクロベンチ (§5.2, Fig. 8): zipfian、キャッシュ 33.3%、書き 1/5/50%、
  tiny queue = キャッシュの 0.01%。書き 50% で OrigCache 比 4.2×、tiny queue なし変種
  (LDC-no-tq) 比 1.5×。書きレイテンシの増分は OrigCache 比わずか 10µs(人気オブジェクト
  への書きは重複キャッシュされた main cache で吸収されるため)。読みレイテンシは
  OrigCache / LDC-no-tq 比 5.8× / 1.8× 低い。tiny queue を持たない write-around 変種
  (未キャッシュキーの書きを同期的にディスクへ)は Ldc 比 3.2× 低スループットで
  OrigCache より 1.3× 遅い(グラフ非掲載と明記)。
- レプリカスケーリング (§5.3.1, Fig. 9): uniform read-only、各 20% キャッシュで 3→5 台。
  OrigCache は重複でデータセットの 67% しかカバーできず 1.3× どまり、Ldc は 3.3×。
- 等価キャッシュサイズ (§5.3.2, Fig. 10): 5 レプリカ・20% キャッシュの Ldc に OrigCache が
  追いつくには zipfian で 4.35×、hotspot で 3.5× のレプリカあたりキャッシュが必要。
- NVMe (§5.4, Fig. 11): NVMe SSD でも YCSB-C 2.2×、YCSB-A 2.5×。
- データセットスケール (§5.5, Fig. 12): 25M・50M KV(キャッシュ比率維持)でも利得は一貫。
- Routing 比較 (§5.6, Fig. 13): 読み書き混合で routing 比 1.6×–3.7×。nested query
  read(read(key)) では routing は正確に route できずディスク多発、Ldc は約 10× 低レイテンシ。
  join(1M キーの2表)ではクライアント側処理の routing 比約 4.1×。
- Cooperative caching / ローカルポリシー比較 (§5.7, Fig. 14): n-chance CC は
  「リモートアクセス時は常にローカルアドミット」「singleton を他キャッシュへ evict」の
  両ポリシーがサーバ設定に不適合で、read-only でも Ldc に劣る。書きはディスク直書き+
  invalidate の CC-WI が特に悪く、write-back 併用の CC-WB でも書き汚染で Ldc に届かない。
  S3-FIFO はサイロ内では重複を減らすがレプリカ横断の重複は防げない (§5.7.2)。
- YCSB マクロ (§5.8, Fig. 15): Twig-kv で C: 2.6×、write-intensive (A, F): 5.4×。D(insert
  5%)はデータセット増でディスクアクセスが増えるが、それでも優位。
- 強一貫ストア (§5.9, Fig. 16): Craq-kv で最大 5.9×、YCSB-A で 6.5× 低レイテンシ
  (Ldc 版もバージョン照合による強一貫チェックを実施した上で)。
- プロダクションストア (§5.10, Fig. 17): RethinkDB 読みワークロードで最大 1.9×(§1 では
  1.3×–1.9× と要約)。実装は未最適化の同期 RDMA 呼び出しで、さらに改善余地ありと主張。
  メモリオーバーヘッドはリモートキャッシュインデックス(リモートレプリカごとに
  4K ページあたり 8B)+ CBA 統計で 1% 未満。
- 実トレース (§5.11, Fig. 18): 50 本(Twitter 47 / Meta 2 / Alibaba 1、書き 0–80%、分布も
  多様)。平均レイテンシ改善は Twitter 1.57×(最大 5.76×、ディスクアクセス 50.07% 減)、
  Meta 1.46×(40.04% 減)、Alibaba 1.39×(32.6% 減)。
- CBA の効果 (§5.12, Fig. 19): CBA 無し変種(リモートアクセスを一切ローカルアドミット
  しない)との比較。高 skew read-heavy な trace-17/28 では CBA 無しは OrigCache より
  悪化するが、CBA 有りは人気オブジェクトを重複させ OrigCache に並ぶ。書き多め・
  非 skew の trace-26/48 では CBA は正しく非アドミットを選び CBA 無しと同等。
- [inference] 評価がカバーしていないもの:
  - value は 100B(§2.2 の CSF 計測のみ 1KB)。大 value での RDMA 帯域(25Gb NIC)律速や
    チェックサム検証コストのスケーリングは未評価。
  - レプリカ数は最大 5。リモートインデックスのメモリ(リモートレプリカ数に線形)と
    lazy 伝播のトラフィック・staleness がレプリカ数でどう伸びるかの実験はない。
    stale index 起因の誤 lookup 0.5% という数字も zipfian の一点のみ (§3.2)。
  - Craq-kv のリモート読みでバージョン照合に失敗し tail へ行く割合(強一貫性の実コスト)
    は報告されていない。
  - RethinkDB は読みパスのみなので、「プロダクション DB でも write 側機構(tiny queue)が
    機能する」ことは実証されていない。
  - CBA のウィンドウ長 t の感度、ワークロード急変時の R_opt 追従遅れの実験はない
    (トレースは多様だが t の掃引はない)。
  - 外部キャッシュクラスタ(Memcached を前段に置く従来構成)との直接比較はない。
    比較対象はあくまで埋め込みキャッシュ内の代替(routing / CC / S3-FIFO)。
  - 書きは常にリーダー経由の構成のみ。Cassandra のようなクォーラム書き込み系への
    実装は §2.2 の分析対象ではあるが Ldc 実装は無い。

## Limitations
- Stated [paper]:
  - tiny queue 経由の書きは eviction 待ちで書き性能を下げ得る(選択的 demote で緩和、
    実測では 50% 書きでも +10µs)(§3.3, §5.2, Fig. 8d)。
  - インデックス lazy 伝播により stale lookup が起き得る(zipfian で 0.5%、ディスクへ
    フォールバック)。Ldc は重複排除を保証せず best-effort (§3.2)。
  - RethinkDB 実装は読みパスのみ・同期 RDMA で未最適化 (§4.3, §5.10)。
  - RPC 実装も可能だが受信側 CPU 処理とレイテンシ増を伴う (§3.2, p.2 脚注)。
- Inferred [inference]:
  - CBA は「各レプリカが独立に実行」(§3.4) であり、レプリカ間で観測頻度分布 A がずれると
    R_opt が食い違い、重複レベルの意図しない不均衡(あるレプリカだけアドミット継続)が
    起こり得る。合意や交換の機構は記述がない。
  - 利得の源泉は「disk ≫ RDMA」のギャップ。NVMe では利得が 5.3×→2.2× (YCSB-C) に
    縮んでおり (§5.4)、さらに速いストレージ(PM や CXL-SSD 級)や、より遅いネットワーク
    (RDMA 無し RPC)では損益分岐が動く。CBA は実測レイテンシで適応するとはいえ、
    利得の絶対幅は環境依存性が大きい。
  - リモートヒットは相手レプリカの CPU は使わないが NIC 帯域と PCIe は消費する。
    ホットオブジェクトが単一レプリカのキャッシュに集中した場合の当該ノード NIC への
    負荷集中は論じられていない(CBA が人気上位を重複させるので極端例は緩和されるはず
    だが、R_opt 境界近傍の中温オブジェクトでは起こり得る)。
  - tiny queue はメモリ上の私有バッファであり、flush 前のレプリカクラッシュ時の書きの
    耐久性はレプリケーション(他レプリカへの適用)に依存する構図に見えるが、本文に
    耐久性セマンティクスの明示的議論がない(上記 [question] 参照)。
  - §2.2 の CSF 計測は「キャッシュ 33.3% × 3 レプリカ = データセット 100%」という、
    カバレッジ改善の余地が最大になる設定を採用しており、redundancy の害を強調する
    方向のセットアップになっている(より小さい/大きいキャッシュでは害の構図が変わる。
    ただし §5.1 はサイズ掃引で利得を示している)。

## Relations
- [inference] [[2026-fast-wei-dmtree.md]](DMTree: DM 上の range index): 同じ
  「one-sided RDMA で相手 CPU を使わずリモートメモリを読む」基盤の上で、DMTree は
  compute server 間で索引メタデータ(fingerprint table)を共有し、Ldc はレプリカ間で
  キャッシュ本体を共有する。「未飽和なノード間 RDMA 資源に仕事を逃がす」という設計
  発想が共通し、staleness の扱い(DMTree: version/entry 検証、Ldc: ID+checksum 検証と
  fallback)も比較軸になる。
- [inference] [[2025-tpctc-gao-distash]](DiStash: FoundationDB 多階層 KV): 本文読解で
  比較軸が確定した — DiStash は単一ノード内の縦の階層(キャッシュ/ストレージ層)、
  Ldc はレプリカ横断の横の共有。Ldc §6 の exclusive caching(多層キャッシュの排他性)
  との関係整理「層内は既存技術、レプリカ横断は Ldc、両者は補完的」(§6) がそのまま
  DiStash との棲み分けに写像できる。
- [inference] [[2026-pvldb-zhang-terark-ds]](Terark-DS: 分離ストレージ上の KV 分離):
  abstract 段階の推測どおり、Ldc の「分離」は物理的な資源分離ではなく論理分離
  (embedded cache を単一論理キャッシュに見せる。ハードウェアは shared-nothing のまま)
  であることを本文で確認 (§1, §3.1)。物理 disaggregation 系(Terark-DS ほか)との対比は
  「メモリプールを作らずに pooling の効果だけ得る」設計点として面白い。

## Idea seeds
- [inference] Craq-kv の手法(リモートキャッシュ読みで clean/dirty バージョンを同時
  fetch し、分散層の既存バージョン照合に流す, §4.2)は「リモートキャッシュ読みは
  一貫性ロジックに対して透過」という一般原理に見える。MVCC の DB でスナップショット
  読みに同じ透過性が成り立つか(リモートキャッシュのページにコミット済み最新版が
  無い場合の fallback 頻度)は Phase 2 の課題候補。最初の検証: Craq-kv 相当の
  バージョン照合失敗率(リモートヒットのうち tail 再取得になる割合)を write 比率を
  振って測る — 本文はこの数字を出していない。
- [inference] CBA (§3.4) は「単一の R をグローバルに決める」1変数モデル。buffer
  management の観点では、これはオブジェクトごとの admission policy を頻度順位という
  1軸に射影したものと読める。オブジェクト単位の cost-benefit(サイズ・更新頻度・
  レプリカ別局所性を含む)に拡張したとき利得がどれだけ残るかは、シミュレータ
  (§5.11 で構築済み、artifact 公開)を使えば安価に検証できる。
- [question] tiny queue の耐久性セマンティクス: 書きパスを RethinkDB のような
  「Raft でコミット済み = 永続」を要求するシステムに実装する場合(§4.3 では未実装)、
  tiny queue への書き込みと WAL/グループコミットの順序をどう組むか。queue が
  0.01% と極小なだけに flush 頻度と fsync の相互作用が書きレイテンシに直撃するはず。
  検証: artifact の Twig-kv に fsync-before-ack モードを足して Fig. 8(d) を再測定。
- [inference] 「レプリカ数を増やすとキャッシュ総量が増える」(§5.3.1) は、レプリカ追加の
  コスト計算を変える: 従来はレプリカ追加 = 耐故障性と読みスループットの対価だったが、
  Ldc 下では実効キャッシュ容量の線形増でもある。geo 分散や read replica の台数設計
  (メモリ何 GB 分の価値か)を Fig. 10 の「等価キャッシュサイズ」(4.35×/3.5×) の方法論で
  定式化するのは、コスト最適化の小粒だが実用的なテーマ。
- [question] 誤 lookup 率 0.5%(zipfian, §3.2)はインデックス lazy 伝播の頻度に依存する
  はずだが、伝播周期・バッチサイズはパラメータとして明示されていない。write-heavy
  uniform(page-in が高頻度)での staleness の悪化と、その時の RDMA 無駄撃ちコストは
  開いた問題。artifact で伝播周期を振って測るのが第一歩。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: 検証パスによる修正(Problem & motivation の [paper] 行から abstract に無い「静的な重複排除ではなく」「動的な」の対比表現を削除)
- 2026-07-06: full-text 格上げ(status: abstract-only → read。手動取得した PDF 全文を読解し全節を執筆)
