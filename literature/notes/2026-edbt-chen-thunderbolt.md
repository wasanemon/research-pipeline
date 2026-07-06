---
title: "Thunderbolt: Concurrent Smart Contract Execution with Non-blocking Reconfiguration for Sharded DAGs"
authors: [Junchao Chen, Alberto Sonnino, Lefteris Kokoris-Kogias, Mohammad Sadoghi]
venue: "EDBT '26 (24-27 March 2026, Tampere, Finland)"
year: 2026
ids: {doi: "10.48786/EDBT.2026.07", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.48786/edbt.2026.07", pdf: "literature/pdfs/2026-edbt-chen-thunderbolt.pdf", code: "https://github.com/apache/incubator-resilientdb/tree/Thunderbolt"}
status: read
read_date: 2026-07-06
tags: [blockchain, bft, dag-consensus, sharding, smart-contract, concurrency-control, occ, deterministic-database, reconfiguration, distributed-transactions]
---

<!-- 読解に使用した PDF: https://openproceedings.org/2026/conf/edbt/paper-29.pdf
     (PDF p.1 に "EDBT '26, Tampere (Finland)" / DOI 10.48786/edbt.2026.07 を確認)。
     著者所属 (p.1): Chen・Sadoghi = Exploratory Systems Lab, UC Davis;
     Sonnino = Mysten Labs + UCL; Kokoris-Kogias = Mysten Labs。
     urls.code は本文 p.12 "Artifact Availability" 記載の公式 artifact URL。 -->

## TL;DR
DAG ベース BFT 合意上でスマートコントラクトをシャーディング実行する既存手法は、2PC 等の
追加調整フェーズと read/write set の事前宣言を要し、後者は実行するまでアクセス先が
分からない Turing-complete コントラクトと相容れない。Thunderbolt は「1 replica = 1 shard
(shard proposer)」とし、single-shard TX は EOV(preplay → DAG 合意 → 並列検証)、
cross-shard TX は OE(合意で全順序を決めてから決定的並列実行)で処理し、DAG の
predetermined leader を使って両者の順序を追加コーディネータ無しで一貫させる。さらに
read/write set 不要・非決定的順序付けの concurrent executor(CE)と、DAG 構築・合意を
止めずにシャード割当をローテーションする non-blocking reconfiguration(Shift blocks)を
導入。SmallBank・64 replicas で serial 実行の Tusk 比 50× を主張。

## Problem & motivation
- [paper] Order-Execute(OE)型システムは依存グラフによる決定的並行制御で並列化するが、
  read/write set の事前知識を要し、動的なスマートコントラクトと非互換。逆に
  Execute-Order-Validate(EOV)型(Hyperledger Fabric)は高い conflict 率に直面し、
  高度な競合解決を要する(§1 Challenge 1, p.1)。
- [paper] コントラクトのコードは EVM 内で実行されるため、read/write set は実行前には
  不確定(§2, p.2)。実行時のコード解析による遅延がコントラクト採用の障害(§1, p.1)。
- [paper] cross-shard 原子性の既存解(relay ベースの Sharper / BrokerChain / SharDAG、
  伝統的 2PC)は shard 間調整による大きな遅延を持ち込む。multi-shard consensus は
  2PC の限界を緩和するが、高競合の大規模ネットワークでスケーラビリティを犠牲にする
  (§1 Challenge 2, p.2)。
- [paper] 問い: read/write set の理解にも追加コーディネータにも依存しない sharding
  システムは設計可能か(§1, p.2)。
- [paper] 鍵となる観察(実行例): 到着順に縛られず実行時状態で並べ替えれば abort を
  避けられる。T1: A=B+1 と T2: A=A+1 で、T1 の Write A を T2 の Write A の後ろに
  リスケジュールすれば両方とも正しい結果で commit できる(Fig. 1, §1)。
- [paper] 貢献の位置づけ: DAG ベースプロトコル上で OE と EOV を組み合わせ、追加
  コーディネータ無しで Single-shard TX と Cross-shard TX の順序を決める初の sharding
  合意機構と主張(§1, p.2)。

## System model & assumptions
- [paper] n 個の replica、n = 3f+1、最大 f 個が Byzantine(任意の挙動)。残りは honest で
  常にプロトコルに従う(§3.1, p.3)。
- [paper] 各ノードは三役を兼ねる: ①shard proposer(自 shard の Single-shard TX を独立に
  管理・提案)②合意に参加する replica ③Cross-shard TX を全順序で commit する leader
  (§3.1, p.3)。shard としては distinct なデータパーティションを保持し、replica としては
  transaction log のコピーを保持(§3.1, p.3)。
- [paper] client は信頼されない。client が自分のトランザクションに関係する全 shard に
  送信することは期待しない(§3.1, p.3)。
- [paper] ネットワークは eventually synchronous(GST は replica に未知)。replica 間は
  公開鍵署名付きの認証済み point-to-point チャネル(§3.1, p.3–4)。
- [paper] データモデル: 各トランザクションは「sender の shard 内データにアクセスする
  関数を持つコントラクトコード」を含む。操作は <Read,K> と <Write,K,V> の 2 種。
  コードは Turing-complete で、実行しなければ何の情報も得られない。コントラクトの
  関数は冪等(idempotent)と仮定(§3.1 Data model, p.4)。
- [paper] 各 key には shard ID(SID)が事前に割り当てられ、全 shard が認識している。
  SID はトランザクションのルーティングと shard 間並列処理の両方に使う。パーティション
  分割の方法自体は本研究と直交(既存手法を利用可能)(§3.1, p.4)。
- [paper] 合意層: 総ブロック順序を確立する任意の DAG 型 dissemination 層と統合可能
  (§4, p.4)。DAG の vertex = data payload(トランザクション + 前 round の 2f+1 個以上の
  certificate への参照)+ certificate(2f+1 署名)。Tusk では round r の leader vertex は
  round r+2 で commit 可能(round r+1 の 2f+1 vertex 受信 + leader vertex が round r+1 の
  f+1 vertex 以上から参照されること)(§2, Fig. 2, p.3)。DAG は Validity / Consistency /
  Completeness を提供(§2, p.3)。従来の「replica を分離グループに分割して別々の合意を
  走らせる」sharding と異なり、全 replica が単一の統一合意プロトコルを維持(§3, p.3)。
- [inference] 1 replica = 1 shard の固定対応なので、shard 数 = replica 数 n。shard を
  増やすことは合意参加者を増やすことと等価で、shard 数と BFT 合意コストが分離できない。
- [question] §3.1 は shard = 「distinct なデータパーティション」としつつ、replica は
  transaction log の完全コピーを持ち、block commit 時に「replica が preplay 結果を自分の
  storage に適用する」(§4, p.4)。検証も read set の再実行照合を要する(§4, p.4)ため、
  状態が本当に partition されるのか実質全複製なのか、他 shard の状態無しに validation が
  できるのかは本文から一意に読み取れない。

## Approach
### Single-shard TX𝑠: EOV(preplay → 合意 → 並列検証)(§4)
- [paper] 3 コンポーネント: preplay、execution scheduling、validation(§4, p.4)。
- [paper] Preplay: shard proposer が concurrent executor(CE)でバッチを事前実行し、
  ①実行中にアクセスした read/write sets ②実行結果 ③scheduled execution order(その順で
  実行すれば結果が再現される決定的直列順序)を含む block を生成する。read/write sets は
  事前に決められず、preplay によってのみ得られる(§4, Fig. 3, p.4)。
- [paper] Execution scheduling: 各 round r で proposer が CE 生成 block を DAG に提案し、
  前 round の自 vertex を含む先行 vertex 群にリンクする(§4, p.4)。
- [paper] Validation: block を受信した replica は block 内の read/write sets から local
  dependency graph を構築し、逐次検査ではなく並列にトランザクションを検証する。同一
  proposer については round r−1 の block を round r より先に検証。再実行で計算した
  read set の値が block 記載値と一致するかを確認し、valid な依存グラフなら read-set の
  一貫性と各 key の最終状態の一致が保証される。不一致なら block を invalid として破棄
  (§4, p.4)。
- [paper] block が commit されるまで preplay 結果は local storage に保持され(cross-shard
  処理や DAG 再構成に使用)、commit 後に storage へ適用される(§4, p.4)。

### Cross-shard TX𝑠: OE(合意で全順序 → 決定的並列実行)(§5)
- [paper] Cross-shard TX は複数 shard に跨るため、実行前に合意で全順序を確立する必要が
  あり、preplay 最適化は使えない(§5, p.4)。
- [paper] 順序ルール(DAG の predetermined leader を利用、コーディネータ不要):
  G1) leader L が Single-shard TX と Cross-shard TX の両方を commit する場合、
  Single-shard TX を先に commit。G2) round i の leader L_i が Cross-shard TX X を
  commit したら、round j > i の leader L_j が commit する Single-shard TX Y は X の
  finalize まで実行できない(§5.1, p.4)。
- [paper] 提案ルール P1–P6(§5.1, p.4–5):
  - P1: Cross-shard TX は CE をバイパスして直接 DAG に提出。
  - P2: leader はバッチ内の全 Single-shard TX を Cross-shard TX より先に finalize。
  - P3: proposer ≠ 当該 round の leader なら、leader の提案を待ってから preplay。leader の
    履歴内に conflict する未 commit Cross-shard TX があれば自 TX を Cross-shard TX に変換。
  - P4: 先行 leader の未 commit Cross-shard TX(round q < r)と conflict する Single-shard
    TX は Cross-shard TX に変換。
  - P5: leader が shard A に関係する Cross-shard TX を commit する際、A の round r−1 の
    提案を欠いていれば、A とその後続提案の commit を延期(不完全な集合の除外で G2 違反を
    防ぐ。後続 leader が後で finalize)(§5.1, §5.3, p.5)。
  - P6: leader の提案が timeout を超えて遅延したら、proposer は自分の Single-shard TX を
    Cross-shard TX に変換して直接 DAG へ(§5.1, §5.3, p.5)。
- [paper] 実行: Cross-shard TX は sharding metadata(SID)を保持し、QueCC のような
  決定的並行制御で SID メタデータから依存グラフを構築、shard 間一貫性を保ったまま
  並列実行する(§5.2, p.5)。
- [paper] Preplay recovering: P3/P4 で Cross-shard 化すると preplay の性能利得を失う。
  proposer は conflict する Cross-shard TX が先行 leader により finalize される(round r+1 で
  2f+1 certificates を受信し、かつ当該 leader block が round r+1 の f+1 block 以上から参照
  される)まで skip block を DAG に出し続け、その後 EOV(preplay)に復帰する
  (§5.4, Fig. 5, p.5)。Fig. 4 の実行例: S10 は S9 の leader 履歴との依存で C1 に変換(P3)、
  C1 が round 5 まで未 commit のため S13/S14 が C4/C5 に変換(P4)、round 5 の leader
  S18 は S11 欠落により C2 以降を skip(P5)、round 7 で S24 は leader S23 の提案を受信
  できず S4 を C9 に変換(P6)(Example 1, Fig. 4, p.5)。

### Non-blocking shard reconfiguration(§6)
- [paper] 動機: 各 replica が 1 shard 全体を握るため、侵害された proposer はその shard を
  麻痺させられる(message drop、リスケジュール、DDoS、提案停止などの censorship 攻撃)
  (§6, p.5–6)。round-robin で shard proposer を rotate: ①leader が K rounds 提案しない
  場合に on-demand、②固定間隔 K′ rounds ごと(K′ > K)。目的は重複トランザクション
  (DDoS)対策の local dedup の維持と censorship の窓の限定(§6, p.5)。
- [paper] shard X の現 proposer が R_i なら次は R_(i mod n)+1(§6, p.5)。新 proposer が
  round r−1 の commit 済み提案を受け取れない場合は、safety のため block が届くまで
  停止する(§6, p.5)。
- [paper] Shift blocks: replica R は次の条件で round r に Shift block を broadcast する:
  (1) round r−K 以降ある shard proposer から block を受信していない、(2) 少なくとも
  K′ rounds 分 block を提案済み、(3) round r−1 に distinct な replica から f+1 個の Shift
  block を受信、(4) 自分はまだ Shift block を出していない(§6, p.5–6)。
- [paper] 2f+1 個の Shift block を含む最初の commit block の round を現 DAG の ending
  round と定め、全 replica が同じ ending round から新しい DAG を開始する(安全性の根拠は
  「2f+1 honest replica が同一 round で同一 block を commit する」という DAG の性質)。
  reconfiguration には 2f+1 Shift blocks が必要なので、悪意ある proposer 単独では発動
  できない。DAG 構築も合意も停止しない(§6, Fig. 6, Example 2, p.6)。
- [paper] ending round で未 commit のトランザクション(leader commit の 2 round 遅延の
  ため、最後の 2 round 分と leader が除外した分)は破棄され、client が自動再送する
  (§6 Uncommitted Transactions, p.6)。

### Concurrent Executor(CE)と Concurrency Controller(CC)(§7–§8)
- [paper] CE = 複数 executor + concurrency controller(CC)。トランザクションは
  execution phase(操作処理)と finalization phase(commit/abort 決定)の 2 段階を通る
  (§7, Fig. 7, Table 1, p.6)。
- [paper] CC は「現在発行された操作」だけから依存グラフを維持し、read/write set の
  事前知識を一切要求しない。全結果はグラフ内に保持し disk IO を回避(§7.1, p.6)。
- [paper] 非決定的順序付け: 到着順ではなく実行時状態に基づき順序を決める。conflict する
  2 TX の順序は依存が生じる(read-write conflict の発生、または両者の commit)まで
  未確定で、どちらの順序も有効(§7.1, p.6–7)。
- [paper] uncommitted data の読み取りを許す(依存グラフ経由で他 TX の未 commit 書き込み
  値を直接取得。例: T2 が time 2 で T1 の未 commit 書き込み D=3 を読む)。書き込み元が
  後から値を更新すると outdated read となった TX は abort され再実行される(例: time 5 で
  T1 が D=5 を書き T2/T3 を abort)(§7.1, Table 1, p.6)。
- [paper] finalization: executor が全操作完了を CC に通知し、CC は全依存先が commit
  された後に結果を非同期で storage に反映し execution order を割り当てる。conflict で
  打ち切られた TX は abort して executor が再実行(§7.2, p.7)。
- [paper] 依存グラフ G(V,E): node = トランザクション、edge e(u,v,k) = key k 上の依存
  u →_k v。key k に incoming edge を持たない node へは root node R(write node 扱い)から
  edge を張る。G が acyclic ならトポロジカル順序から直列順序を生成でき、「どのトポロジカル
  順序から生成した直列順序も同じ結果を生む」場合のみ G は valid(§8.1, Fig. 8, p.7)。
- [paper] node 内には conflict 追跡に必要な最小限として key ごとに最大 2 操作(最初の
  read と最後の write)のみ保持(§8.1, p.7)。
- [paper] 新規 write 操作: key K 上で outgoing edge を持たない read-only node 群を選んで
  そこから新 node へ edge を張る(先行 TX が先に commit する想定で root 直結を回避)
  (§8.2, Fig. 9a, p.7)。新規 read 操作: 最新の write node から値を取得(無ければ root =
  storage から)。write node u を選んだ場合、他の全 write node が u への path を持つよう
  調整して read-after-write の正しさを保証(§8.2, Fig. 9b, p.7)。既存 node への操作追加は
  node 内の記録から直接値を返すか、新規操作と同じ手順で先行 node を選ぶ(§8.3, Fig. 9c,
  p.8)。
- [paper] conflict 検出: 既存 node への追記は「read 済みの値の再更新」や「常に最新 write
  から読むことによる別 key 経由の依存サイクル」を生みうる。サイクル時はまず ancestor
  (root 等)からの読み直しを試み、それでも conflict なら abort。abort 処理は (1) 当該
  node が read のみなら自 TX のみ abort、(2) write を含むなら cascading abort(例: T1 の
  write が T2 の read を壊すと T2, T3 が連鎖 abort)(§8.4, Fig. 10, p.8)。
- [paper] 正しさ: safety =「conflict する 2 TX の実行順序が全 honest replica で一致」を、
  同一 DAG 内(Theorem 1)、Single-shard × Cross-shard 混在(Theorem 2、P4/P5 の
  ルールによる矛盾の排除)、DAG 再構成跨ぎ(Theorem 3、同一 ending round からの移行)で
  証明。liveness は 2f+1 Shift blocks による新 DAG 移行で保証(§9, p.8)。CC の
  serializability は Read-Complete(Def. 4)/ Write-Complete(Def. 5)を定義し、valid な
  依存グラフの下で両性質が成り立ち(Theorem 6)、両性質から serializable(Theorem 7)と
  証明(§10, p.9)。

## Evaluation
- Setup [paper]: 全 baseline を Apache ResilientDB (Incubating) 上に実装し、フレームワークを
  揃えて比較(§11, p.9)。評価は 2 部構成: CE 単体(§11)とシステム全体(§12)。
- CE 単体評価 [paper]: baseline = OCC(local 実行 + central verifier の version 照合)と
  2PL-No-Wait(central controller がロック、競合時は全ロック解放して再実行)。AWS
  c5.9xlarge(36 vCPU / 72GB DDR3)、storage は LevelDB。SmallBank(6 TX 種のうち
  SendPayment と GetBalance を使用)、10,000 accounts、Zipfian θ=0.85(高競合)、
  GetBalance 比率 P_r、各実験 50 回平均(§11.1–11.2, p.9)。batch size は b300 / b500(§11.3, p.10)。
  - 読み書き均衡(P_r=0.5): 2PL-No-Wait は 8 executor 超で abort 急増により 24K→18K TPS
    に低下。Thunderbolt と OCC は 12 executor でピークに達し安定、Thunderbolt-b500 =
    43K TPS vs OCC-b500 = 35K TPS(Fig. 11a, §11.3, p.10)。
  - update-only(P_r=0): OCC / 2PL は 4 executor で頭打ち(約 22K TPS)、Thunderbolt は
    12 executor で 28K TPS(Fig. 11b, §11.3, p.10)。
  - abort 数: Thunderbolt-b500 は全実験で OCC-b500 比 50% 減、2PL-No-Wait-b500 比
    90% 減(Fig. 11, §11.3, p.10)。
  - θ 掃引(0.75–0.9, P_r=0.5): θ=0.75 では OCC と同等、θ=0.9 で OCC は大幅低下する一方
    Thunderbolt は高スループットを維持。2PL はロック戦略により安定推移(Fig. 12a–b, p.10)。
  - P_r 掃引(θ=0.85): P_r=1(全 read)は全プロトコル同等(OCC が non-blocking local
    実行によりわずかに優位)。write 比率が上がるほど Thunderbolt が OCC を上回り、
    write-only でも優位(Fig. 12c–d, p.10)。
- システム評価 [paper]: Thunderbolt(CE + 並列検証)vs Thunderbolt-OCC(CE を OCC に
  置換 + 並列検証)vs Tusk(OE、全順序後に逐次実行)。replica ごとに CE 16 executors、
  batch 500、post-consensus 検証用 validator 16。replica 数 8–64。SmallBank P_r=0.5、
  アドレスは 1,000 users から θ=0.85 で選択(高競合)。デフォルトでは K′ を十分大きくして
  rotation を無効化(§12, p.11)。
  - LAN: 64 replicas で Thunderbolt 500K TPS vs Tusk 11K TPS(論文は 50× speedup と
    表記)。Thunderbolt-OCC は 8 replicas では同等だが 64 replicas で 400K TPS に留まる。
    latency は Thunderbolt 5 秒 vs Tusk 100 秒(Fig. 13, §12, p.11)。
  - WAN: 同傾向だが latency は増加し、WAN 遅延が支配的になるため Thunderbolt と Tusk の
    latency 差は縮小(Fig. 13, §12, p.11)。
  - Cross-shard 比率(16 replicas、P% の TX を 2 shard 跨ぎに設定): P=0 で両システム
    100K TPS。P=8% で Thunderbolt 64K TPS vs Thunderbolt-OCC 16K TPS(後者は Tusk の
    約 10K TPS に接近)。P=100% でも Thunderbolt は 19K TPS。高競合下の latency は
    Thunderbolt 24 秒 vs Thunderbolt-OCC 約 50 秒(Fig. 14, §12, p.11)。
  - Reconfiguration 周期(8 replicas): K′=10 で 80K TPS(DAG 移行コスト)、K′>1000 で
    180K TPS。平均 latency は K′ 10→5000 で 1.9 秒→1.7 秒(Fig. 15, §12, p.11)。
    K′=300 での 100 round ごとの平均 runtime は 0.07–0.1 秒/round で、reconfiguration 中も
    停止しないことを確認(Fig. 16, p.11–12)。
  - 故障(16 replicas、f 個の replica を停止): f=1 で 78K TPS(P=0)/ 17K TPS(P=100)、
    f=2 で 66K / 15K TPS。DAG プロトコルの leader rotation により latency は安定
    (Fig. 17, §12, p.11–12)。
- [inference] 評価がカバーしていないもの:
  - 外部システムとの比較が無い。baseline は Tusk(逐次)と自作の Thunderbolt-OCC のみで、
    §13 で挙げられる Block-STM / CHIRON(非決定的実行)や Sharper / SharDAG / 2PC 系
    (cross-shard)との直接比較が無い。「既存 sharding は調整で遅い」という動機
    (§1 Challenge 2)は自システム内の変種比較でしか裏付けられていない。
  - ワークロードは SmallBank の 2 TX 種のみ。動機は「Turing-complete で実行するまで
    access set が不明なコントラクト」(§2, §3.1)だが、評価のコントラクトは read-modify-
    write の送金のみで、複雑なコントラクト(長い実行、多 key アクセス)での preplay /
    validation コストは未測定。system 評価のホットセットは 1,000 users と極端に小さい。
  - Byzantine 挙動の実験は「f replica の停止」のみ(Fig. 17)。reconfiguration の動機である
    censorship 攻撃(選択的 drop、偏った選択)や equivocation の注入実験は無い。
  - cross-shard は常に「2 shard 跨ぎ」設定で、3 shard 以上に跨る TX の評価は無い。
  - 50× の由来: Fig. 13 の 500K vs 11K TPS は算術的には約 45× であり、abstract / §12 の
    「50×」との差の説明は本文に無い。
  - LAN で 5 秒、cross-shard 高競合で 24 秒という latency の絶対値は大きいが、その内訳
    (バッチ待ち / 合意 round / 検証)の分析は無い。

## Limitations
- Stated [paper]:
  - 頻繁な reconfiguration はコスト大: K′=10 で 80K TPS に低下(K′>1000 の 180K 比)
    (Fig. 15, §12, p.11)。
  - reconfiguration の ending round で未 commit の TX(最後の 2 round 分)は破棄され、
    client の再送に依存する(§6, p.6)。
  - Single-shard TX が P3/P4 で Cross-shard TX に変換されると preplay の性能利得を失う
    (skip block による復帰手順が必要)(§5.4, p.5)。
  - cross-shard 比率の増加で性能は大きく低下する(P=0 の 100K → P=100 の 19K TPS)
    (Fig. 14, §12, p.11)。
  - 高競合ワークロードでは executor を増やしても(どのプロトコルも)大きな利得は無い
    (§11.3, p.10)。
- Inferred [inference]:
  - shard = replica の固定結合により、shard の追加は BFT 合意参加者の追加を意味する。
    1 shard の書き込み処理能力は単一 proposer の CE に上限づけられ、shard 内の
    スケールアウト手段が無い。
  - client は untrusted(§3.1)なのに、TX が single-shard か cross-shard かの判定は client の
    ルーティングに依存して見える。preplay 中に sender の shard 外の key(別 SID)に触れる
    コントラクトをどう検出・処理するかの明示的な記述が無い。[question] validation の
    read-set 照合(§4)で他 shard アクセスの single-shard 偽装は弾けるのか、それとも
    preplay 時に SID チェックで cross-shard へ昇格するのか。
  - 「コントラクト関数は冪等」(§3.1)は abort→再実行(§7.1, §7.2)と再実行ベースの
    validation(§4)を安全にするための強い仮定に見えるが、一般のコントラクト(外部
    可視の副作用や非冪等な更新を持つもの)への適用範囲は論じられていない。
  - cascading abort(§8.4)は高競合でチェーン状に伸び得るが、連鎖の深さ・再実行コストの
    分析は abort「回数」の測定(Fig. 11)のみで、最悪ケースの議論が無い。
  - 検証が read set の再実行照合(§4)である以上、全 replica が全 shard の block を検証する
    ように読める。その場合、sharding が削減するのは「実行の総量」ではなく「提案と
    スケジューリング(preplay)の直列ボトルネック」であり、状態・検証は事実上全複製の
    可能性がある(System model の [question] と同根)。
  - eventually synchronous 前提(§3.1)の下で P6 / Shift の timeout(K)の設定指針が無く、
    GST 前の誤検知で不要な cross-shard 変換や reconfiguration が多発した場合の性能は
    未評価。

## Relations
- 本文中の直接の系譜 [paper]: DAG 合意は Tusk / Narwhal 系(実装は Tusk 上、§11–12)、
  proposer rotation は Sui の epoch switching に着想(§1, p.2)、cross-shard 実行の決定的
  並行制御は QueCC を利用(§5.2, p.5)、実装基盤は Apache ResilientDB(§11, p.9)。
  競合として relay 系(Sharper / BrokerChain / SharDAG)、2PC 系、非決定的実行系
  (Block-STM / CHIRON)を挙げる(§1, §13)。
- [[2026-sigmod-webber-riot.md]](RIOT: leaderless な TxDAG ベース一般化コンセンサス):
  「単一 leader + 全順序ログを崩し、DAG 構造の履歴 + conflict 依存で順序を決める」と
  いう軸で正面から比較できる。[inference] 相違点: RIOT は crash モデルで順序合意と CC を
  layer 分離(可換性判定は下層 DB に委譲)するのに対し、Thunderbolt は Byzantine
  モデルで CE が順序・read/write set・結果まで生成し合意層はそれを検証する(EOV)。
  「CC を合意の下に置くか上に置くか」の設計空間の両端として対照的で、cross-shard 処理も
  RIOT は interposed coordinator、Thunderbolt はコーディネータ排除(DAG leader 利用)と
  逆方向。

## Idea seeds
- [inference] CE の「到着順に依存しない実行時リスケジューリングによる abort 回避」
  (Fig. 1, §7–8)は blockchain 固有ではなく、単一ノード DB の OCC validation の abort
  削減にそのまま持ち込める可能性がある。CE を単体ライブラリとして切り出し、古典 OCC /
  2PL-No-Wait に加えて既存の順序再割当系 CC と高競合 YCSB / TPC-C で比較する実験が
  第一歩(artifact が ResilientDB tree に公開されているため着手コストは低い)。
- [question] 1 replica = 1 shard(shard 数 = n)の制約を外し、replica あたり複数 shard や
  shard あたり複数 proposer に一般化した場合、leader 依存の順序ルール(G1/G2, P3–P6)は
  維持できるか。K′ ローテーションとの整合(shard 割当の consistent hashing 化など)も
  含めて設計余地がある。
- [question] cross-shard 比率 P に対する急峻な性能低下(100K→64K(P=8%)→19K(P=100%)、
  Fig. 14)の内訳は、G2 による Single-shard TX の finalize 待ちブロッキングか、OE 実行
  そのもののコストか。P を固定して conflict 率だけ変える実験で分離できるはず。
- [inference] 「検証 = 全 replica での再実行」だとすると、実行総量は non-sharded と同じで
  スケールするのは preplay の並列度のみ。read set 照合を sampling 化・stateless 化した
  場合の安全性劣化(不正 block 見逃し確率)と性能の trade-off を定量化する研究は、
  この系(EOV × DAG)全体に効く。まず本論文の validator 数(16)を掃引して検証が
  ボトルネックになる点を特定するところから。

## Changelog
- 2026-07-06: created (status: read)
