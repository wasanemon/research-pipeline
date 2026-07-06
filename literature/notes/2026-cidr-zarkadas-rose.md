---
title: "Rosé: Flexible Replication With Strong Semantics For Partitioned Databases"
authors: [Ioannis Zarkadas, Kelly Kostopoulou, Thomas Graham, Junfeng Yang, Philip A. Bernstein, Asaf Cidon, Tamer Eldeeb]
venue: "CIDR 2026"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/cidr/ZarkadasKGYBCE26"}
urls: {paper: "https://vldb.org/cidrdb/2026/rose-flexible-replication-with-strong-semantics-for-partitioned-databases.html", pdf: "literature/pdfs/2026-cidr-zarkadas-rose.pdf", code: ""}
status: read
read_date: 2026-07-06
tags: [replication, primary-backup, asynchronous-replication, monotonic-prefix-consistency, partitioned-database, epochs, failover, backpressure, wal, geo-distributed]
---

## TL;DR
パーティション化 DB の非同期 primary-backup レプリケーションが抱える3つの問題
(failover 時にバックアップ全体が undefined な状態になる/レプリケーションラグが
無制限に伸びる/failover 後の性能劣化)を、①既存のグローバルスナップショット機構
(epoch 等)との統合で backup に monotonic prefix consistency を与え、②パーティション
ごとの有界キュー+backpressure でラグを cap し、③WAL の複製と KV ストアへの適用を
分離した coordinated apply で failover 後即フル性能、の3点で解決する提案
(CIDR 系のビジョン/プロトタイプ論文)。Chablis に統合して評価し、failover 後の
Yugabyte のスループット低下 22% / P99 上昇 15% に対し Rosé は劣化 0% を示す。

## Problem & motivation
- [paper] 非同期 primary-backup は書き込みレイテンシと耐久性のバランスが良く広く
  使われるが、パーティション化 DB では各パーティションが独立に複製されるため、
  failover 時のデータ喪失が DB を「undefined で開発者が推論しにくい状態」に残す
  (abstract, p.1)。
- [paper] 具体例: トランザクション T が P1 の K1 と P2 の K2 に書いた場合、複製ペース
  の差で K1 の書きだけが backup に届いた状態で backup を読むと T の一部だけが見え、
  atomicity が壊れる (§1, p.1)。
- [paper] monotonic prefix consistency (Helt et al. [8] の定義) があれば、failover で
  durability は失われても他の ACID 特性は保たれ、アプリ不変条件が守られる。単一ログの
  非パーティション DB では比較的容易だが、パーティションごとにログが分かれると全体
  状態は inconsistent になり得る (§1, p.1)。
- [paper] 実務では disaster recovery 時に複雑な整合性チェックと修復が要り、定期的な
  drill が必要。consistent point-in-time snapshot への復元機能 [2,15] はあるが時間が
  かかり、そのスナップショットがどれだけ遅れているかの保証もない (§1, p.1-2)。
- [paper] さらに failover 後は、最新の複製済みスナップショットより新しいデータの
  クリーンアップのため、昇格した新 primary の性能が劣化しがち (§1, p.2)。

## System model & assumptions
- [paper] 対象は geo-distributed なパーティション化 DB の非同期 primary-backup 複製。
  primary リージョンが全トランザクションを実行・コミットし、書き込みを非同期に
  backup リージョンへ送る形態 (§1, §4, p.1, p.3)。
- [paper] 非同期プロトコルである以上、通常運転時の性能と引き換えに durability を
  妥協する(primary リージョン喪失時の直近データ喪失は許容する)前提。Rosé が守るのは
  monotonic prefix consistency であって同期複製の durability ではない (§4, p.3)。
- [paper] 前提となる基盤: 対象 DB は既に globally consistent / serializable な
  スナップショットリード(real-time [5]、HLC [2,15]、epoch [6,7] のいずれか)を
  持っている。この既存インフラを monotonic prefix consistency の拡張の土台に使う。
  Chablis 統合のため本論文では epoch を時間の単位として使うが、他の方式でも動くと
  主張 (§4.1, p.3)。
- [paper] ホスト DB 側の永続化モデル: まず高速な WAL に durable 化し、周期的に
  構造化 KV ストアへ適用する、という一般的な2層構造を仮定(coordinated apply は
  この分離に依存)(§4.3.2, p.5)。
- [paper] 統合先 Chablis のモデル: RangeServer(2PL + 2PC、mostly stateless、WAL
  Service に prepare/commit/abort を永続化し、Key-Value Service へ非同期適用、WAL を
  随時 trim)、Warden(range 割当と heartbeat 監視)、epoch(regional epoch publisher
  から 2PC 中に現 epoch を読み、global epoch service が全リージョンの epoch を周期的に
  前進;グローバル順序は epoch 境界でのみ well-defined)(§2.2, Fig. 1, p.2)。
- [paper] 障害モデルの重要な仮定: 各パーティションはリージョン内で既に複製されて
  高可用(標準的な複製係数 R=3、ノード可用性 99.9% を仮定すると、パーティションが
  完全に落ちる確率は 0.001^3、つまり可用性 99.9999999%)。よって「パーティションが
  長時間完全停止してラグが無限に伸びる」ケースは極めて起きにくいとする (§4.2.2, p.4)。
- [paper] backup リージョンの長期停止・喪失時は、管理者または外部の稼働監視システムが
  backpressure を手動で解除して可用性を回復することを仮定する (§4.2.3, p.4)。
- [paper] backpressure のキュー上限 L はユーザーごとに調整すべきハイパーパラメータ
  (ネットワーク帯域をフル活用でき、通常負荷と一時スパイクを吸収できる程度に大きく、
  かつユーザーの望む durability 保証に合う値)(§4.2.3, p.4)。
- [inference] 「多くの分散 DB は既にグローバルスナップショット機構を持つ」という
  前提の裏返しとして、そうした機構を持たない(パーティション横断の一貫スナップショット
  を提供しない)DB には Rosé の §4.1 はそのまま載らない。適用可能な DB の範囲は
  この前提で切られている。

## Approach
- [paper] **①monotonic prefix consistency の維持 (§4.1)**: 各 primary パーティションが
  トランザクション write-set を epoch 昇順(WAL 順)で対応する backup パーティションに
  送る。backup 側のクラスタ管理コンポーネントが各パーティション P_i の「完全適用済み
  最新 epoch e_i」を(既存のヘルスチェックに piggyback して)追跡し、読みに使える
  最新スナップショットを e_snapshot = min(e_i) とする。e_snapshot は単調に進むので
  backup の読みは monotonic prefix consistency を満たす (§4.1, p.3)。
- [paper] **②backpressure によるラグの cap (§4.2)**: replication lag は
  replication_lag_i = e_primary,i − e_backup,i と定義。パーティションごとに outstanding
  トランザクションを追跡する有界キュー(サイズ L)を持ち、push 型(primary が能動的に
  伝播しつつ全パーティションの複製進捗を監視)で複製する。あるパーティションの
  キューが満杯になると**そのパーティションだけ**書き込みを throttle する。straggler は
  自分にしか影響せず、かつ backlog の際限ない蓄積を防ぐ。副次効果として straggler
  検出にも使え、より速い/空いているサーバへの migration などの対処が打てる
  (§4.2.1, p.3-4)。
- [paper] 可用性の議論: 単一パーティションでは Rosé が受理するトランザクションは
  同期複製が受理するものの strict superset。B=L で新トランザクションが来たとき、
  同期複製が受理するなら backup へのリンクは生きておりキューのスロットが空くはず
  なので、キュー満杯時はタイムアウト θ だけ待って判断する。複数パーティションでも
  同様、とする (§4.2.2, p.4)。
- [paper] 実装上の要点: 「backup が追いつけないせいで throttle される」事態を避けるため
  C5 アルゴリズム [8] で primary と backup の並列度を揃える (§4.2.3, p.4)。
- [paper] **③coordinated apply による復旧時間の最小化 (§4.3)**: backup のデータは
  スナップショット epoch までしか使えないため、failover 時は全パーティションを
  min epoch まで巻き戻す必要がある。既存 DB は複製レコードを到着次第すぐ KV ストアに
  適用するため、failover 時に高価な bulk-delete を払うか読み性能を劣化させる。Rosé は
  WAL 複製(自由に進めてよい)と KV ストアへの適用(協調して進める)を分離する:
  backup が全パーティションの最小複製済み epoch を常時追跡し、各パーティションに
  「その epoch まで WAL を適用せよ、それ以上は適用するな」と通知する。failover 時に
  必要なのは WAL の trim(挿入順に並ぶログを過去オフセットまで切るだけの高速操作)
  のみで、KV ストアは常にクリーンなので failover 後もフル性能を保つ (§4.3.2, p.5)。
- [paper] 対比事例(Yugabyte): xCluster 複製は pull 型(Rosé と異なる)。RocksDB の
  SST メタデータに max_ts を持たせ、巻き戻し時は max_ts が目標スナップショット ts を
  超えるファイルにだけ keep_ts を記録して即座にサービス再開する。ただし読みは
  invalid entry のパースという追加コストを払い、compaction が少しずつ掃除する。
  この手の込んだ方式でも failover 後の性能劣化は残る (§4.3.1, Fig. 3, p.5)。
- [paper] coordinated apply の懸念への反論: (a) 単一 straggler がログ適用全体を
  停滞させる問題は backpressure が緩和する(throttle されて追いつける)。
  (b) epoch 境界で適用がバースト化する問題は dead_time_i = (w_max − w_i)·
  epoch_duration / network_bw で定式化され、epoch を数ミリ秒に設定すれば hot
  パーティションがあってもスパイクは最小化でき、hot パーティションがなければ
  dead time はほぼゼロ。スナップショット epoch の前進速度は blind apply と変わらない
  (§4.3.2, Fig. 4, p.5)。
- [question] effective replication lag が「min(replication_lag_i)」と書かれている
  (§4.2.1, p.3)。しかし同じ節の論理(backup はスナップショット epoch =
  min(e_backup,i) までしか使えず、それを超えて進んだパーティションのデータは
  failover 時に捨てられる)からは max が自然に見える。誤植か、e_primary,i の解釈が
  異なるのか、原文 PDF の式を再確認したい。

## Evaluation
- Setup [paper]: Rosé を Chablis [6] に統合。マルチノード構成とネットワーク障害を
  単一の Cloudlab c6525-25g マシン上でシミュレート。Yugabyte はバージョン
  2.25.2.0-b359、failover は公式の手動手順 [19] を使用 (§5.1, p.6)。
- [paper] Q1(ラグの cap): 1パーティションのラグを backpressure 有/無で追跡。
  backpressure はラグを効果的に cap しパーティションを追随させる。代償は性能低下
  だが、影響は過負荷のパーティションのみ (§5.2, Fig. 5, p.6)。
- [paper] Q2(failover 後の性能): Chablis と Yugabyte を各リージョン2ノードの
  primary-backup 構成で走らせ、uniform な read-write トランザクション実行中に
  backup 側1ノードへのリンクを切断。Yugabyte は到達可能なノードで書き込み適用を
  続けるが、Chablis の coordinated apply は timestep 50 のリンク断以降、到達不能
  ノードの最終複製 epoch を超える適用を止める (§5.3, Fig. 6(a), p.6)。
- [paper] 両システムとも failover 自体は2秒未満で即時。しかし failover 後、Yugabyte は
  読みのスループットが 22% 低下・P99 レイテンシが 15% 上昇するのに対し、Rosé は
  KV ストアがクリーンなため劣化 0% (§5.3, Fig. 6(b), p.6)。
- [paper] 絶対性能は比較しない: Yugabyte はフル SQL 対応の production システム、
  Rosé は KV ストアのプロトタイプであり apples-to-apples でないため。相対的な挙動
  のみが instructive とする (§5.3, p.6-7)。
- [inference] 評価がカバーしていないもの: (a) 実 WAN/マルチマシン環境での測定は
  なく、全て単一マシン上のシミュレーション。geo 環境のレイテンシ・帯域変動下での
  backpressure の挙動(throttle の頻度、primary 側の書き込みレイテンシへの影響の
  定量)は未検証。(b) パーティション数のスケール(2パーティション/2ノード規模のみ)。
  (c) backpressure による primary スループット低下の定量値は本文になく、Fig. 5 の
  「reduced performance」という定性記述のみ。(d) L と θ の感度分析なし。(e) TPC-C 等の
  標準ベンチマークは使われておらず uniform read-write のみ。(f) 実際の failover →
  昇格 → WAL trim の end-to-end 復旧時間の内訳も示されていない(「2秒未満」のみ)。

## Limitations
- Stated [paper]:
  - 非同期である以上 durability は failover 時に妥協される(直近データ喪失はあり得る。
    喪失量の上限を L で制御するのが Rosé の立場)(§1, §3, §4, p.1, p.3)。
  - パーティション完全停止時にはラグが伸び得るが、リージョン内複製の高可用性で
    確率的に無視できるとする(確率計算は独立故障を仮定)(§4.2.2, p.4)。
  - backup リージョン長期喪失時の backpressure 解除は自動でなく、管理者/外部監視
    システム頼み (§4.2.3, p.4)。
  - Rosé は KV ストアプロトタイプであり、production システムとの絶対性能比較は
    していない (§5.3, p.6-7)。
- Inferred [inference]:
  - 可用性証明 (§4.2.2) は「同期複製の受理集合の strict superset」という形の議論で、
    タイムアウト θ の待ち時間そのものが書き込みレイテンシに与える影響(throttle 中の
    テールレイテンシ)は評価されていない。相関故障(リージョン内 3 レプリカが同一
    ラック/AZ 障害で同時に落ちる等)下では 0.001^3 の独立性仮定が崩れる。
  - coordinated apply は backup の KV ストアを常に min epoch で止めるため、backup で
    のスナップショットリードの鮮度は最遅パーティションに律速される。read-only
    ワークロードを backup にオフロードする使い方では、blind apply + Yugabyte 型
    keep_ts 方式のほうが新しいデータを読める局面があり得る(このトレードオフは
    本文で論じられていない)。
  - 「WAL trim は高速」という主張は WAL がオフセットで切れる単純な構造であることが
    前提。Chablis のように WAL Service が分離された構成では自然だが、WAL とストレージ
    エンジンが密結合な既存 DB(例: LSM の group commit ログ)への移植コストは
    論じられていない。

## Relations
- [paper] Chablis [6](CIDR 2024、同著者グループの Eldeeb らによる geo-distributed
  transactional KV store)の上に統合されている。backpressure 実装の並列度合わせに
  C5 [8](Helt et al.、monotonic prefix consistency の定義もここから)を使用
  (§2.2, §4.2.3, p.2, p.4)。
- [inference] epoch 機構は同著者らの Chardonnay [7](OSDI '23)の系列とみられる。
  本文は epoch ベース手法として [6,7] を併記するのみで(§4.1, p.3)、系譜の明示は
  ない。
- [paper] 競合/対比: Yugabyte xCluster(pull 型・keep_ts による即時 failover)、
  consensus 複製(Spanner / CockroachDB / Yugabyte)、Aurora・Socrates 等の
  primary-backup 系 [3,16,17] (§2.1, §4.3.1, p.2, p.5)。
- [inference] 2026-pvldb-kuschewski-btrlog.md と補完的: Rosé の coordinated apply は
  「WAL への複製は自由に、KV への適用は協調して」という WAL 中心の設計であり、
  WAL をクラウドサービスとして分離する BtrLog 系の設計と組み合わせると、backup
  リージョンの WAL Service に複製だけ先行させる構成が自然に描ける。

## Idea seeds
- [inference] coordinated apply は backup の読み鮮度を min epoch に固定する。
  「パーティション部分集合ごとの consistent prefix」(読みたいキー集合に触る
  パーティションだけの min を取る)を返せれば、straggler 1個で全体の鮮度が落ちる
  問題を緩和できるかもしれない。検証: Chablis 型 epoch モデルで、read set が触る
  パーティション集合ごとの snapshot epoch を返すシミュレーションを書き、uniform /
  skewed ワークロードで鮮度向上を測る。
- [question] backpressure の cap は「epoch 数」単位のラグに効くが、ユーザーが本当に
  制御したいのは failover 時の喪失バイト数/トランザクション数のはず。L(キュー長)
  と実際の喪失量の関係はワークロードの write-set サイズに依存する。喪失量ベースの
  適応的 L 制御は成立するか。第一実験: write-set サイズ分布を変えながら固定 L での
  喪失量のばらつきを測る。
- [inference] §4.2.2 の可用性議論と §4.3.2 の dead time 解析はいずれも簡略なモデル
  ベースで、形式化の余地が大きい(θ の選び方、相関故障、epoch duration と spike の
  関係)。TLA+ 等で monotonic prefix consistency +有界ラグの保証を機械検証する
  小テーマになり得る。検証: まず §4.1 の最小プロトコルだけをモデル化して invariant
  (e_snapshot の単調性・prefix 性)をチェックする。

## Changelog
- 2026-07-06: created (status: read, CIDR 2026 公式 PDF テキスト全文を読解)
- 2026-07-06: 検証パスによる修正(Relations の「epoch 機構は Chardonnay [7] 系列」を [paper] から [inference] に降格。本文に系譜の明示的記述はなく §4.1 の [6,7] 併記のみのため)
