---
title: "Scalable Leader Leases For Multi Consensus Groups in CockroachDB"
authors: [Ibrahim Kettaneh, Tsvetomira Radeva, Arul Ajmani, Sumeer Bhola, Nathan VanBenschoten, Alexander Shraer, Rebecca Taft]
venue: "SIGMOD Companion"
year: 2026
ids: {doi: "10.1145/3788853.3803081", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3788853.3803081", pdf: "literature/pdfs/2026-sigmod-kettaneh-leader-leases.pdf", code: "https://github.com/cockroachdb/cockroach/tree/master/docs/tla-plus/StoreLiveness"}
status: read
read_date: 2026-07-06
tags: [consensus, replication, leases, fault-tolerance, distributed-database, raft, failure-detection, cockroachdb]
---

<!-- PDF は p.1 脚注に "Corrected VoR published on June 29, 2026" とある(修正版 Version of Record)。
     urls.code は本文 §4.1 が参照する TLA+ 検証コード(ref [9])であり、システム本体の artifact ではない。 -->

## TL;DR
Range(= consensus group)が数十万〜数百万ある CockroachDB では、read を quorum 通信なしで
返すための per-Range lease の維持が支配的なバックグラウンド負荷になる(expiration lease は
per-Range 更新で CPU が爆発し、centralized lease は liveness Range への集中で partial partition や
disk stall に脆い)。本論文は、store 間の有向ペアごとに epoch ベースの support を交換する
cluster-wide failure detector「Liveness Fabric」を基盤に、Raft を Leader Fortification で拡張して
「LSU(LeadSupportUntil)まではリーダー交代が起きない」という強い leadership 保証を作り、
その LSU をそのまま lease 期限として leader と leaseholder を統合する(Leader Leases)。
per-Range の lease 更新も Raft heartbeat も消え、liveness コストは group 数でなく store 数に
スケールする。idle な 3 ノードクラスタで expiration lease が 80K Ranges で CPU 90% 超に達する
のに対し Leader Leases は 100K Ranges まで 15% 未満 (Fig. 6)。partial partition・disk stall でも
数秒で復旧する(centralized は partition 継続中ずっと復旧不能)(Fig. 5)。

## Problem & motivation
- [paper] consensus 複製 DB では、leaseholder replica が strongly consistent read をローカルに
  返し write は leader に委譲する、という最適化が一般的。stale read を防ぐため leaseholder の
  権限は lease duration で時間制限され、定期更新が要る (§1)。
- [paper] leader 自身を leaseholder にする統合は、多くの consensus protocol が stable leadership を
  保証しない(leader は自分が交代させられたことを事後にしか知れない)ため難しく、実運用
  システムは consensus の上に別レイヤの lease protocol を重ねてきた (§1)。
- [paper] 現代の分散 DB は独立な consensus group を数百万規模で持ち、group ごとの lease
  付与・更新がバックグラウンドオーバーヘッドの支配項になる。最大級の本番 CockroachDB
  クラスタでは Raft group の 60% 超が長期間 read-only であり、lease 維持のためだけの
  Raft-group 活動は無駄になっている (§1)。
- [paper] 既存の緩和策はすべて妥協: lease を長くする(Spanner の 10s lease)と failover が遅く
  なり、write への更新 piggyback は idle group に効かず、lease 管理の集中化は単一障害点を
  生む (§1)。理想の protocol は Correctness(lease の時間非重複)・Fault tolerance(node/disk/
  network 故障の迅速な検知)・Scalability(集中協調も per-group heartbeat も無しで数百万
  group)の 3 性質を満たすべき (§1)。
- [paper] 従来の CockroachDB には 2 つの lease 方式があった (§2.3):
  - expiration lease: Raft コマンドの複製で期限を定期延長。lease 延長が Raft パイプライン全体を
    通るので故障検知は Raft 可用性と整合するが、per-Range のタイマーと更新が必要。
  - centralized lease: 明示期限を持たず、node ごとの epoch に間接化。epoch→期限の対応は特別な
    システム Range(liveness Range)に集中し、全ノードが per-node heartbeat で epoch を延長。
    per-Range 延長を per-node 延長に合体できるが、Range の leaseholder と follower quorum の間の
    partial network partition では、leaseholder が liveness Range に heartbeat できる限り lease を
    延長し続け、write を一切通せないまま Range が不可用になる (§2.3, §7.1)。

## System model & assumptions
- [paper] 対象は CockroachDB: key の range-partitioning で Range に分割し、Range が複製単位。
  各 Range はデフォルト 3 replica の Raft group で複製される (§2.3)。クラスタは数百ノードまで
  スケールし、1 ノードが数万の Raft group を含み得る (§3.1)。
- [paper] ノードは複数ディスク(store)を持ち得て、Liveness Fabric は node 単位でなく store
  単位に 1 インスタンス走る(heartbeat も store 間。ディスク故障の影響半径をその store 上の
  Range に限定するため)(§3.1, §7.3)。
- [paper] lease の意味論: leaseholder は lease 区間内の timestamp でのみ write を提案でき、lease
  期限未満の timestamp で read を返せる。任意の 2 つの lease は時間的に非重複でなければ
  ならない(lease disjointness 不変条件)(§2.3, Definition 4.6)。
- [paper] クロック仮定: Liveness Fabric は各ノードの monotonic clock のみに依存し、クロック
  同期を要求しない。メッセージが HLC タイムスタンプを運んで受信側クロックを進め、因果性
  保証と粗い同期を与える(粗い同期は leaseholder 不在期間の最小化のため、因果性は Support
  Disjointness 確立のため)(§3.4)。single-key linearizability は HLC と uncertainty interval で
  上位のトランザクション層が担い、クロック同期の話題は本論文の範囲外 (§2.3.1)。
- [paper] トランザクション: 複数 group に跨る txn は per-group linearizability に頼れず、MVCC と
  2PC を lease 層の上で使う (§2.2)。lease 層自体の保証は Range 単位。
- [paper] 故障モデル: node 故障、ネットワーク故障(対称・非対称。liveness は有向ペア
  n1⇒n2 ごとに管理)(abstract, §3.4)、partial network partition (§2.3, §5.1)、および disk stall
  (write が成功も失敗もせず無期限に停滞する故障クラス)(§7.2) を扱う。
- [paper] 永続化の仮定: 他ノードへ約束した support(support_for)、要求した最大期限
  (max_requested)、support 撤回の最大時刻(max_withdrawn)は永続化。受けている support
  (support_from)は揮発で、再起動時は max_epoch を増やして新 epoch で要求し直す。再起動時は
  自クロックが max_requested と max_withdrawn を超えるまで待つ (§3.4.2)。Raft 側にも
  Lead / LeadEpoch の 2 つの永続フィールドを追加(再起動した follower が fortification の約束を
  破って早期に立候補し、serializable isolation を破るのを防ぐ)(§3.3.6)。
- [paper] Liveness Fabric の heartbeat は要求・応答とも送信前に同期ディスク書き込みの成功を
  要求する(disk stall した node が「生きているように見える」ことを防ぐ)(§5.1, §7.2)。
- [paper] heartbeat は consensus group を共有するノード(store)間でのみ交換される (§3.1)。
- [paper] 出発点は leader ベースの consensus protocol(EPaxos 等 leaderless は対象外)(§6)。
  本番の大規模 resilient クラスタは multi-region の k=5 replica が通例 (§6)。

## Approach
3 層構成: Liveness Fabric(failure detection)→ 拡張 Raft(Leader Fortification)→ lease 層
(Leader Leases)(§3.1, Fig. 1)。

- [paper] **Liveness Fabric (§3.4)**: 有向ペア n1⇒n2 ごとに「n1 の epoch e を n2 が時刻 t まで
  support する」という promise を管理する分散 failure detector。
  - support は epoch(中断のない support の区間)として公開される。n2 が epoch の support を
    撤回したら、その epoch への support は永久に再確立されない(one-way door)。n1⇒n2 の
    liveness 喪失は n1 の epoch カウンタを進めるだけで n1 自体を落とさず、n1⇒n3 の有効
    epoch にも影響しない(epoch は n1 の単一 monotonic counter から引かれるが、支持者ごとに
    異なる epoch がありうる)(§3.4, §4.1)。
  - 各ノードは毎秒、全対象ノードに heartbeat を送り、数秒先(Algorithm 1 では now+3s)の
    期限で support を要求する。応答受信時は epoch と期限を後退させないよう support_from を
    更新し、遅延した古い応答は無視する (§3.4.2, Alg. 1)。受信側は同 epoch なら期限延長、
    高い epoch なら新規 support を記録して応答する (Alg. 2)。
  - support の撤回は受動的: 自クロックが期限を超えたら support_for の epoch を +1 して期限 0 に
    するだけで、相手には通知しない(相手は次の要求時に知る)(§3.4.2, Alg. 3)。クロック
    skew で「n′ は撤回済みだが n はまだ有効に見える」期間が生じ得るが、epoch ごとの support
    期間が非重複である限り安全 (§3.4.2)。
  - 上位層への API は SupportFrom(ID) / SupportFor(ID)(⟨timestamp, epoch⟩ を返す)(§3.1)。
- [paper] **Leader Fortification(Raft 拡張, §3.3)**:
  - 新 RPC 2 種: MsgFortifyLeader(leader→follower。「クロックが特定時刻を超えるまで立候補も
    投票もしない」一時的 promise の要求。term 入り)と MsgFortifyLeaderResp(term、ack flag、
    LeadEpoch = follower の node が support している leader node の Liveness Fabric epoch)。
    follower は term が一致し、かつ Liveness Fabric で leader の node を support している場合のみ
    受諾。自身を含む majority quorum の ack で leader は fortified になる (§3.3.1, Fig. 2)。
  - **LSU (LeadSupportUntil)**: fortified leader が「この時刻までは交代させられない」と確信できる
    timestamp。LSU = max_{Q∈quorums}( min_{r∈Q} τ_r )(τ_r は replica r の support 期限)。
    Raft tick(デフォルト 500ms)ごとに再計算され、majority が support を維持する限り前進する
    (§3.3.2)。新 leader の当選には majority 投票が必要で、LSU まで fortify している quorum は
    投票しないから、LSU 以前に新 leader は生まれない (§3.3.2)。
  - follower の support 期限切れ・epoch 前進を leader が検知したら、その follower を LSU 計算から
    除外し re-fortification を試みる (§3.3.1)。
  - De-fortification: follower が自分の term より高い term のメッセージを受けたら暗黙に停止。
    leader が退位する場合は明示的に MsgDefortify を全 follower が ack するまで(またはより高い
    term のコミット済みエントリを観測するまで)周期送信。これをしないと follower が旧 leader を
    support し続けて選挙に参加できず liveness を失う (§3.3.3)。
  - Leadership transfer: fortified leader(term T_i)が follower に T_{i+1} への立候補を指示。
    立候補メッセージに「T_i の leader の指示による」というメタデータを付け、fortification の
    promise 下にある replica も投票できるようにする (§3.3.4)。
  - Configuration change への追加制約: leader は LSU = MaxLSU(過去に計算した LSU の最大値)を
    満たすまで次の構成変更を提案できない。連続する replica 追加で「古い低 LSU の quorum」が
    MaxLSU 以前に新 leader を選出し、旧 leader の read を無効化する write を通す危険を塞ぐ
    (§3.3.5, Fig. 3)。
  - **Raft heartbeat の廃止**: fortified leader は「LSU まで交代しない」ことと「quorum と接続して
    いる(でなければ fortified でなくなる)」ことを Liveness Fabric から知れるため、per-group の
    Raft heartbeat を止め、node(store)数にスケールする Liveness Fabric メッセージに置き換える。
    未 fortify の follower への周期的 MsgFortifyLeader が従来の heartbeat の役割も兼ねる。従来の
    CockroachDB が heartbeat 抑制のために持っていた coalescence / quiescence 最適化のコード
    複雑性も動機の一つ (§3.3.7)。
- [paper] **Leader Leases(lease 層, §3.2)**: Leader Lease は fortified leadership の薄いラッパで、
  Raft leader のみが保持でき leadership term に紐づく。LSU をそのまま lease 期限に使うので、
  lease 延長の per-Range コストはゼロ(期限は per-node heartbeat で伸びる Liveness Fabric epoch
  から導出される)(§3.2)。
  - 非協調的取得: 選挙に勝った Raft leader だけが Leader Lease を提案できる。fortified な term は
    時間的に非重複なので、新 leader が選出できた時点で前の Leader Lease は期限切れ済み → lease
    disjointness が保たれる (§3.2.1)。
  - 協調的移譲: 出て行く leaseholder が lease の残りを放棄(終端 T_forfeited を一方的に選ぶ)し、
    T_incoming > T_forfeited の expiration lease を新 leaseholder に移す。leader と leaseholder が
    分離した状態になるので、leader は主体的に leadership を leaseholder へ移譲し、移譲後に Raft
    コマンドの複製で expiration lease を Leader Lease に変換する (§3.2.2)。leadership transfer は
    lease 移譲後にしか起きないため、暗黙の de-fortification は安全 (§3.3.4)。
- [paper] **正しさ (§4)**: Liveness Fabric の 2 性質 — Support Durability(A が B から期限 t の
  support を受けたら、epoch の見解が一致しているか、B のクロックが t を超えて撤回済みかの
  いずれか)と Support Disjointness(A のクロックが t 未満のうちは、A はより高い epoch の
  support を要求も受領もしない)— を TLA+ で形式検証(コードは GitHub 公開、ref [9])
  (§4.1)。この上に Lemma 4.2–4.5(fortified term ごとに非ゼロ LSU が存在/LSU は quorum が
  support を維持する限り前進/fortified leader の term 終了 ⟺ majority の support 喪失/新 leader
  当選時のクロックは過去の fortified leader の最大 LSU を超える。投票応答が運ぶ HLC timestamp が
  上界を与える)を立て、Theorem 4.7(lease 非重複)を導く (§4.2, §4.3)。

## Evaluation
- Setup [paper]: pre-release CockroachDB v25.4.0。全 lease 方式で lease duration 3s・更新間隔 1s に
  統一(公平性のため。expiration / centralized の本番デフォルトは通常 6s だが、Leader Leases の
  本番デフォルトを 3s にチューニングして failover latency で不利にならないようにしたと明記)。
  特記なき値は独立 20 回の平均、エラーバーは標準偏差 (§5)。
- **Failover (§5.1, Fig. 5)**: GCP 上 6 ノード(n2-standard-8)。システム Range はノード 1–3、
  ユーザ Range は 4–6 に配置制約、クライアントはノード 1 経由。故障注入 4 種(node crash /
  full partition / partial partition = ユーザ Range ノードを他の 2 ユーザ Range ノードから切断しつつ
  システム Range ノードとの接続は維持 / disk stall)、各 300 回で P50/P95/P99 を報告。
  - 構造的性質: Leader Leases の failover は「lease failover → leadership failover」が直列に起きる
    ため他 2 方式(両者が並行)より約 1–2 秒遅い。実装では fortification support 失効後、hung
    election 防止のため最大 2 秒のランダム待ちを入れて立候補する (§5.1)。低遅延 failover が
    要る workload には Raft tick 頻度の引き上げで対処可能と述べる (§5.1)。
  - node crash / full partition (Fig. 5a, 5b): expiration / centralized は median 3.0–3.9s、P99 3.7–4.5s。
    Leader Leases は median 4.0–4.7s、P99 6.5s。
  - partial partition (Fig. 5c): expiration median 3.65s / P99 4.3s、Leader Leases median 4.3s /
    P99 5.8s。**centralized は復旧しない**: 部分隔離された leaseholder が liveness Range への
    heartbeat で lease を延長し続ける一方、follower quorum に heartbeat できず Raft leadership を
    維持できない。不可用は partition が続く限り持続 (§5.1)。
  - disk stall (Fig. 5d): expiration では stall した leader が Raft heartbeat は送れるので leadership を
    保持するが、lease 更新は durable write を要するため Range 不可用に(実際は 20s 超の stall を
    検知した node が自殺して復旧)。centralized は liveness Range の leaseholder が stall すると
    クラスタ全体の epoch 延長が止まり全 Range 不可用。Leader Leases は (1) heartbeat 送信前の
    同期ディスク書き込みにより stall 時は heartbeat 自体が止まって lease が失効、(2) leadership と
    leaseholdership の failure detector が Liveness Fabric に一本化されているため、両方が同時に
    別 replica へ failover する (§5.1)。
- **Lease 維持の CPU (§5.2, Fig. 6)**: idle workload、3 ノード(n2-standard-8)で Ranges を
  10K→100K に増加。expiration は 10K で 15% → 80K で 90% 超(per-Range タイマーと Raft tick が
  支配。lease を長くすれば減るが failover が同程度遅くなる)。centralized は全域 5% 以下
  (node 単位維持 + idle Range の quiescence)。Leader Leases はゼロ近くから始まり全域 15%
  未満 — follower は quiescence で休むが leader replica は LSU 維持のため tick を続けるので
  centralized よりやや高い。leader quiescence は future work で、実装すれば無負荷 CPU は
  centralized に並ぶと期待 (§5.2)。
- **TPC-C (§5.3, Fig. 7)**: 5 ノード(n2-standard-16)固定、wait=false で warehouse 数を掃引
  (warehouse 増 = Range 増)。expiration は 25K warehouses で 100K tpmC から始まり、100K
  warehouses でほぼ 20% 低下(profiling では leaseholder の CPU 上昇が原因)。centralized は
  100K warehouses でもピーク比 5% 以内。Leader Leases は centralized に肉薄し、高 warehouse 数
  での小さなオーバーヘッドは lease 更新でなく tick する replica の増加による (§5.3)。
- **Liveness Fabric の CPU (§5.4, Fig. 8)**: ノード 5→150(各ノード 12 store = 12 インスタンス、
  計 60–1800 stores)。使用コア数は store 数に線形で、600 stores で約 0.073 コア、1200 で
  0.15、1800 でも約 0.225 コア(n2-standard-8 の 8 vCPU の約 2.8%)(§5.4)。
- [inference] 評価がカバーしていないもの:
  - abstract・§1 は「数百万 consensus group」を掲げるが、実測は 100K Ranges(§5.2)/
    100K warehouses(§5.3)/1800 stores(§5.4)まで。百万 group 規模は §6 のコスト解析
    (O(N²) fabric vs per-shard heartbeat / O(N^{k+1}) grouping)による外挿で、
    直接の実験は無い。
  - §1 の「up to 85% less CPU for lease management」に対応する数字は Fig. 6 の系列から
    読み取る形で、本文には 85% の導出(どの Range 数での比較か)が明示されていない。
  - 非対称(単方向)リンク故障の実験が無い。有向エッジ単位の検知は設計上の主張 (§3.4)
    だが、§5.1 の partial partition はノード集合間の(双方向)切断であり、片方向だけ届く
    ケースの failover は測られていない。
  - 構成変更の LSU=MaxLSU 前提条件 (§3.3.5) が、support が不安定な状況で reconfiguration を
    どれだけ遅らせるかは未評価。re-fortification の頻度・コストも数値が無い。
  - read-heavy workload での foreground 性能(lease 方式間で read latency に差が出ないことの
    確認)は無く、負荷実験は TPC-C のみ。ベースラインは CockroachDB 内の 2 方式のみで、
    Spanner / Yugabyte 型 lease との比較は §6 の定性議論に留まる。

## Limitations
- Stated [paper]:
  - failover は expiration / centralized より約 1–2 秒遅い(lease failover と leadership failover が
    直列のため)。故障が稀でスケーラビリティ便益が大きいので通常は問題ないとし、必要なら
    Raft tick 頻度を上げよと述べる (§5.1)。
  - leader replica の tick が残るため、無負荷 CPU は centralized lease より高い(leader quiescence
    は future work)(§5.2)。
  - store 単位 heartbeat は node 単位より総 heartbeat 数を増やす(同一 node 宛の heartbeat の
    best-effort バッチングで緩和)(§7.3)。
  - Liveness Fabric のメッセージコストは O(N²)(N = store 数)。placement 柔軟性を保つ
    grouping 方式(O(N^{k+1}))に対しては漸近的に安いが、per-shard heartbeat
    (N × 40K shards × k=5)との比較では 20TiB ディスク・512MiB/shard の想定で
    約 20 万 store 規模まで O(N²) の方が安い、という条件付き (§6)。
  - 過渡的な disk stall で不要な leadership 交代が起きないよう、lease duration 3s・heartbeat 1s
    (交代には最低 2 回の heartbeat 失敗が必要)という調整に依存 (§7.2)。
- Inferred [inference]:
  - 全 heartbeat が送信前に同期ディスク書き込みを要求する (§7.2) ため、liveness がディスク
    レイテンシに結合する。stall には至らない「遅いディスク」(クラウドボリュームの遅延
    スパイク等)で support が失効・epoch が前進すると、影響はその store 上の全 Range の
    leadership に波及する。この感度(書き込みレイテンシ分布 vs 誤検知率)は定量化されて
    いない。
  - support 撤回が epoch 単位で永久 (§4.1) + 再起動時に max_requested / max_withdrawn を
    クロックが超えるまで待つ (§3.4.2) ため、node 再起動後は最大で要求済み期限(数秒)の
    lease 取得不能期間が構造的に生じるはずだが、再起動シナリオの復旧時間は測られていない
    (§5.1 の node crash は process kill 後の他 replica への failover を測るもの)。
  - heartbeat 対象は「consensus group を共有するノード」(§3.1) なので、O(N²) の実効係数は
    replica placement の広がりに依存する。placement が広く分散した大クラスタでは mesh が
    ほぼ全対全になる一方、locality の強い placement では疎になる — このトポロジ依存性は
    論じられていない。
- [question] §3.4 は「monotonic clock のみに依存」と述べるが、再起動処理は永続化した
  max_requested / max_withdrawn を自クロックが「超える」まで待つ (§3.4.2)。再起動を跨いで
  比較可能なクロックは boot ごとにリセットされる純粋な monotonic clock では実現できない
  はずで、実際にはメッセージが運ぶ HLC(wall clock ベース)との併用が前提に見える。
  wall clock の大きな逆行(VM 移行等)時に Support Disjointness がどう守られるかは本文からは
  読み取れない。

## Relations
- 本文中の比較対象 (§6): Spanner の Paxos Leader Leases(10s、write での暗黙延長付き expiration
  lease 相当)、Chardonnay、Yugabyte leader-leases(Raft 複製で更新する expiration 型)、Raft
  dissertation の leasing(clock drift 上界依存 + per-group heartbeat)、TiDB(Raft leadership 上の
  lease)、OceanBase PALF(group 集約で複製コストを償却するが placement 柔軟性と blast radius
  を犠牲にする)。著者らは「数万 shard 規模での leasing と leadership を明示的に扱う研究は
  知る限り無い」と主張 (§6)。
- [[2026-sigmod-webber-riot.md]](RIOT: DAG 合意): 同じ「consensus の調整オーバーヘッド削減」
  でも、RIOT が順序付け(ordering)側を緩和するのに対し、本論文は ordering には触らず
  liveness / lease 側を group 数から切り離す。leader ベース SMR の周辺コストをどこで削るかの
  対照例として好対照。本論文が補完的と位置付ける leadership stability 研究(Omni-Paxos 等)
  への言及 (§6) も RIOT ノートの文脈と重なる。
- [[2026-cidr-zarkadas-rose.md]](Rosé: primary-backup 複製 / failover): failover 時間の測り方
  (P50/P95/P99、故障注入の種類)を比較する相手として直接的。本論文の「centralized lease は
  partial partition で無期限に不可用」(§5.1, §7.1) は、consensus 複製系の failover 特性を
  論じる際の具体的な反例データになる。
- [[2026-pvldb-kuschewski-btrlog.md]](BtrLog: クラウド WAL サービス): §6 の PALF 議論
  (複製 group の集約はコストを server 数スケールにするが placement 柔軟性を失う)は、
  多数のログストリームを持つ shared-storage / WAL サービス設計と同じトレードオフ空間に
  ある。abstract-only 時代の idea seed(Liveness Fabric の BtrLog への転用)は本文精読後も
  成立: 転用対象は「per-stream keepalive の per-node 集約 + 有向エッジ検知」の部分。

## Idea seeds
- [inference] 「group 数に依存しない failure detector から lease 期限を導出する」という構図は
  consensus に限らず、多数の細粒度リソースに lease が要る系全般(例: disaggregated memory 上の
  lock service。コーパスでは 2026-eurosys-cai-rdma-locks.md が扱う RDMA lock)に持ち込める
  可能性がある。lock ごとの lease 更新を node 間 support に集約し、lock の有効性を
  SupportFrom で判定する設計。最初の検証: lock 数 × 更新頻度のメッセージ数モデルを作り、
  Liveness Fabric 型(O(N²))と per-lock 更新(O(locks))が逆転する境界を出す。
- [question] 上記 Limitations の monotonic clock vs 再起動処理の疑問(§3.4 と §3.4.2 の整合)。
  公開されている TLA+ 仕様(urls.code)にクロックがどうモデル化されているかを読むのが
  最短の検証手段。仕様で wall clock の逆行が扱われていなければ、それ自体が仮定の
  ドキュメント化されていないギャップになる。
- [inference] §5.1 の「lease failover → leadership failover が直列で 1–2s 追加」は leader と
  leaseholder を統合した設計の構造的コスト。fortification の promise を破らずに follower が
  投機的に選挙準備(投票集めの事前交渉)だけ進める変種で直列コストを圧縮できるかは
  開いた問題に見える。検証第一歩: Raft シミュレータで「support 失効と同時に投票が完了して
  いる」理想ケースの failover 下界を測り、現行実装の 2s ランダム待ち (§5.1) との差を分解する。
- [inference] §6 のコスト解析(O(N²) fabric vs O(N^{k+1}) grouping。加えて per-shard
  heartbeat との比較では 40K shards/store・k=5 の想定で 20 万 store まで O(N²) が有利)は、
  shared log / multi-log サービス(BtrLog、PALF)の keepalive 設計にも
  適用できる評価枠組み。BtrLog ノートのアーキテクチャ記述に当てはめ、per-stream の
  liveness 通信を per-node に集約した場合のメッセージ数を試算するところから始められる。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: 検証パスによる修正(Relations の「consensus/replication を扱うノートはコーパスに無い」という誤った記述を訂正。RIOT・Rosé の既存ノートが該当するため、「lease protocol / failure detector を主題とする最初のノート」に範囲を狭めた)
- 2026-07-06: full-text 格上げ(status: abstract-only → read。手動取得した PDF 全文を読解し全節を執筆)
- 2026-07-06: 検証パスによる修正(§6 コスト比較の帰属を訂正: 「約 20 万 store まで」の条件は O(N^{k+1}) grouping との比較ではなく per-shard heartbeat(N×40K×5)との比較に付く。Limitations・Evaluation [inference]・Idea seeds の 3 箇所)
