---
title: "Scalable RDMA-accelerated Distributed Locks with Shared Stream Abstraction"
authors: [Miao Cai, Junru Shen, Xiaojian Liao, Rong Gu, Yanchao Zhao, Hao Han, Bing Chen, Baoliu Ye]
venue: "EuroSys"
year: 2026
ids: {doi: "10.1145/3767295.3803598", arxiv: "", dblp: "conf/eurosys/CaiSLGZHCY26"}
urls: {paper: "https://doi.org/10.1145/3767295.3803598", pdf: "literature/pdfs/2026-eurosys-cai-rdma-locks.pdf", code: ""}
status: read
read_date: 2026-07-06
tags: [distributed-locks, rdma, locking, networking, shared-receive-queue, readers-writer-lock, fcfs-fairness, fault-handling]
---

## TL;DR
RDMA データパスのスケーリングを阻む分散ロックを「要求順序付け」と「所有権移転」に
解剖し、既存方式は前者が atomic RDMA verb(RDMA_CAS/FAA)による NIC 競合で、後者が
ポーリングによるネットワーク輻輳でスケールしないと特定 (§1, §2.2)。提案の **StreamLock**
は、RNIC の Shared Receive Queue (SRQ) のラインレートなパケット受信を「共有ストリーム」
= 集中待ち行列として転用してハードウェアに順序付けをオフロードし、所有権移転は
ロック保持者からの peer-to-peer 通知(UD)に置き換える (§3)。Rust 2,852 行で実装し
(§5)、4 種の RDMA ロック比で ordering throughput を 14.17%〜7.33× 改善、移転レイテンシを
12.5%〜80.42% 削減、TPC-C / TATP で最大 14.85× / 9.51×、Redis / Octopus を最大 5.7×
高速化と主張 (§1)。FCFS・安全性・starvation/deadlock freedom の証明付き (§4.5)。

## Problem & motivation
- [paper] データセンタは高速 RDMA(ConnectX-7 で 400Gbps・往復 ~2μs)を受容し、
  分散 FS・クラウドネイティブ DB(PolarDB、Meta RocksDB)・オンライントランザクション等が
  性能クリティカルなデータパスを RDMA ファブリックへオフロードしている (§1, p.1)。
- [paper] その主要障壁が非スケーラブルな分散ロック。動機実験では、RDMA データパス自体は
  一桁 μs レイテンシだが、競合したロックが最大 100μs のレイテンシスパイクを起こす (§1, p.2)。
- [paper] Issue#1(要求順序付け): 既存ロックは順序付けに atomic RDMA verb を使う
  (CASLock/DSLR/HOCL は 64-bit 共有インジケータへの RDMA_CAS / RDMA_FAA、ShiftLock は
  Ext_CAS ベースの lock-free queue)(§2.2, Table 1)。atomic RDMA verb は NIC 内部ロック +
  直列化された PCIe トランザクションで実行されるため NIC 競合が激しく、順序付け
  スループットは CASLock で ~2.4 Mops/s、Ext_CAS / FAA 系でも ~3.5 Mops/s(CAS 比 +45%)に
  頭打ちで、ロック無し RDMA_WRITE ベースラインに大きく劣る (§2.2, Fig. 1a)。
- [paper] 皮肉なことに、readers-writer ロックで並列 reader を増やすと atomic reader カウンタ
  更新の並列度が上がって NIC 競合が悪化し、順序付けレイテンシはむしろ上がる (§2.2, Fig. 1b)。
- [paper] Issue#2(所有権移転): 既存方式は client-active なポーリング(グローバル
  インジケータ/チケットの読取・CAS リトライ)で、移転 1 回あたりのネットワーク IO が
  CASLock / DSLR で 12〜18 回に達する (§2.2, Fig. 1c)。ShiftLock は writer 間は MCS 的
  handover(RDMA_SEND 2 回)だが、reader-writer 間は Epoch / RelCnt のポーリングで
  スケールしない (§2.2, Fig. 1d)。
- [paper] 解決方針: 分散ロックプロトコルと RDMA ネットワークの co-design。核となるのが
  shared stream 抽象(SRQ の共有キュービューをロック待ち行列に転用)(§1, §3)。

## System model & assumptions
- [paper] ハードウェア: 市販 (off-the-shelf) RNIC のみを前提とし、プログラマブルスイッチ等の
  特殊機器は不要(in-switch ロックとの対比)(§1, §6)。評価は dual-port Mellanox
  ConnectX-5 100Gb NIC / PCIe v4.0 (§5)。
- [paper] 依存する NIC 機能: InfiniBand の SRQ(複数 SQ が 1 つの RQ を共有し、共有キュー
  ビューを提供。線形 = ハードウェアによる並行パケットの順序付け、高速 = 毎秒数百万
  in-flight パケット処理)(§3.1)。トランスポートは RC / UD / XRC を使い分ける
  (§2.1, §3.3, §4.1.2)。
- [paper] SRQ の重要な性質:「in-order WQE consuming, out-of-order packet delivery」。
  WQE は RDMA_RECV の post 順に消費されるが、DMA エンジンの RECV バッファへの書込みは
  順不同で着地する (§3.1)。正しさ(Invariant 2)は前者の in-order WQE 消費保証に依存 (§4.5)。
- [paper] WQE の循環リンクは「商用 RNIC の SRQ 実装が WQE next ポインタで WQE を
  リンクしている」ことを利用し、最後の WQE の next を先頭に繋ぎ替えて作る(参照 [7] は
  Mellanox Adapters PRM)(§3.1)。[inference] つまり順序付け機構はベンダ固有の WQE
  内部形式に依存しており、可搬性は Mellanox/NVIDIA 系 NIC の範囲に限られる可能性が高い。
- [paper] 同一 QP 上の 2 つの RDMA 要求は RNIC により順序どおり配送される、という性質を
  バリアとして利用(unlock 時の GetReq が先行 CleanReq のバリアを兼ねる)(§4.3)。
- [paper] クライアント数は有界で既知: WQE 数 > 最大クライアント数に設定し、キュー容量は
  クライアント総数 N に対し 2N(待ち行列スロットの上書き防止の根拠)(§3.1, §4.5
  Invariant 2)。クライアントが増えたら WQ エントリを追加し RECV バッファ配列を
  再 post する (§4.1.1)。[inference] LockReq の client ID は 14 bit (§4.1, Fig. 3a) なので
  1 ロックあたりのクライアント上限は 16384。
- [paper] ロック 1 個 = SRQ 1 個。RC ベースだと k ロック × n クライアントで kn 個の QP が
  要るため、XRC (eXtended Reliable Connection) で QP 数を k に削減 (§3.3)。
- [paper] ノードは 3 種: leader ノード・follower ノード・lock ノード(全ロック要求を
  格納)。**lock ノードは常に健全と仮定**。故障モデルは (i) ネットワーク輻輳による
  パケットロスと (ii) fail-stop(HW 故障・SW バグ・電源断。誤動作はしない)のみで、
  fail-stop 発生時のネットワーク分断は無いと仮定 (§4.4)。
- [paper] 所有権移転の通知は UD(unreliable datagram)。コネクション維持が無く RC より
  大幅にスケールするが、パケットロスがあり得る。「現代 RDMA 網は 50PB 転送で
  パケットロスゼロ」という先行研究 [24] を引いてロスは極めて稀と位置付け、ロス時は
  タイムアウト + RC ベースの Timeout / LeaderChange メッセージで回復する (§4.1.2, §4.4)。
- [paper] 保証: 線形化可能 (linearizable) な要求順序付け (§3.1)、グループ(writer 単体
  または連続 reader 列)単位の FCFS + 相互排除 (Lemma 1)、安全性 = 「単一 writer XOR
  複数 reader」(Theorem 1)、starvation-free / deadlock-free (Theorem 2) (§4.5)。
- [paper] CQ は depth 1 に設定し CQE オーバーフローを無視。専用スレッドが WQE カウンタを
  周期的にリセット(CPU オーバーヘッドは無視できると主張)(§3.1)。
- [inference] 対象はロックプリミティブ単体であり、ロック対象データの配置・永続性・
  トランザクション回復は範囲外。TPC-C 評価も「行 = ロック」の 2PL ハーネスであって
  完全な DBMS ではない (§5.4 の記述からの推論)。

## Approach
- [paper] **Shared stream 抽象** = ロック取得要求をネットワークパケットとして lock ノードの
  SRQ に着地させ、RNIC のハードウェア受信順序をそのままロックの集中待ち行列として使う。
  これで order 付けから CPU と atomic verb を排除する (§3, Fig. 2b)。
- [paper] **ハードウェアオフロード順序付け (§3.1)**:
  - 課題 1 = SRQ の RECV バッファ補充が CPU 駆動でボトルネック化する。解決 = circle-based
    RECV buffer: RECV バッファ配列を事前確保し、WQE を円環にリンク。全 WQE 消費時は
    先頭へラップアラウンドし、新規 post 不要。パケット処理経路に CPU 介入ゼロ。
  - 課題 2 = out-of-order packet delivery により in-flight パケットの着地時点が不明。
    解決 = barrier request handling: RECV バッファ配列に head ポインタを導入。head は
    「先行バッファが全て処理済みである最初の空バッファ」を指し、空バッファが非空に
    なったら(in-flight が着地 or 新着)処理して head を前進させる。
- [paper] **Peer-to-peer 所有権移転 (§3.2)**:
  - 課題 1 = RDMA_SEND は自分の要求が入った RECV バッファアドレスを返さないため、
    後継者特定に全キュー読取が要る。解決 = owner ポインタ(現ロック保持者の RECV
    バッファ配列 index)。解放時に owner+1 で後継要求を 1 個読むだけでよく、移転の
    本質的 1 RTT に加えて次バッファ読取の 1 RTT のみ。
  - 課題 2 = shared lock では複数 reader への一斉通知が要る。解決 = leader-follower 設計:
    leader は待機中 writer または reader 列から選出された reader。保持者 L1 は後継が
    writer なら unicast、reader 列なら leader L2 と全 follower へ broadcast。follower は
    解放時に L2 へ FollowerExit を送り、L2 が全 follower 分を受けてから次の待機者へ
    通知する (§3.2, §4.1.3)。現行ポリシーは待ち行列末尾の reader を leader に選出
    (§4.3, Alg. 2)。
- [paper] **データ構造 (§4.1, Fig. 3)**: LockMeta = 2B の head のみ。LockReq = valid 1 bit +
  mode(reader/writer)1 bit + client ID 14 bit。構成要素は order manager(SRQ 管理・
  要求ディスパッチ)、ownership manager(UD 通知)、client(Fig. 4)。クライアント要求
  プリミティブは MakeReq(RDMA_SEND で要求投入)/ CleanReq(RDMA_WRITE でバッファ
  ゼロ化)/ GetReq / GetHead / SetHead / CleanHead の 6 種 (§4.1.1)。メッセージは
  LeaderEnter{owner, num_followers} / FollowerEnter{leader_id} / FollowerExit /
  LeaderChange{new_leader} / Timeout の 5 種で、Leader / Follower 各ロールの
  WAIT / LOCK / UNLOCK 状態遷移を駆動 (Fig. 3b, Fig. 5)。
- [paper] **lock 手順 (Alg. 1, §4.2)**: MakeReq と GetHead を doorbell batching で並列送信 →
  head の指す先頭要求を GetReq → 自分でなければ CQ を poll して通知を待つ(タイムアウトで
  fault パスへ)。head が自分の(未着地だった)要求を指せばロックは未使用で即取得し、
  CleanHead で head の上書き事故を防ぐ。取得後は自分のスロットを CleanReq で非同期
  ゼロ化(解放後の自スロット不可視化 = Invariant 2 の根拠)。
- [paper] **unlock 手順 (Alg. 2, §4.3)**: LeaderEnter 保持者は owner+1 から最大
  MAX_FOLLOWERS 件の後続要求を読み(この GetReq が先行 CleanReq のバリアを兼ねる)、
  follower がいれば全員の FollowerExit を待つ。後継が writer なら 1 通知、reader 列なら
  末尾 reader を新 leader にして broadcast。後継無しなら SetHead(owner+1) するが、succs
  読取後に in-flight 要求が着地する競合があり得るため再 GetReq で確認し、非空なら
  通知する(これを怠ると starvation になると本文は述べる)。follower は leader へ
  FollowerExit を送るのみ。
- [paper] **fault 処理 (§4.4, Alg. 3–4)**: leader 故障 = 最初の待機者が共有キューを読んで
  保持者を特定し、RC の Timeout でタッチ。ACK があれば UD パケットロスと判断して続行、
  無ければ fail-stop と判断してバッファを掃除し、follower 無しなら自分が直接取得、
  有りなら先頭 follower を新 leader とする LeaderChange を broadcast。follower 故障 =
  leader が所定時間待った後、キューを走査して未応答 follower を Timeout でタッチし、
  到達不能なら pending から除外・バッファ掃除、ACK ならパケットロスなので再待機。
- [paper] **正しさ (§4.5)**: Invariant 1(head は未解放の先行者を飛び越えない)、
  Invariant 2(待機/保持中クライアントのスロットは上書きされない。容量 2N + in-order
  WQE 消費 + 取得時の能動的スロット掃除が根拠)、Invariant 3(連続グループ間で所有権
  移転は直列化)から Lemma 1(グループ単位 FCFS + 相互排除)、Theorem 1(安全性)、
  Theorem 2(starvation-free / deadlock-free)を導く。out-of-order 着地した stale 要求が
  通知を誤誘導する例外ケース (Fig. 6) は Invariant 2 で排除される。
- [paper] **multi-lock**: XRC で 1 QP を複数 SRQ に対応させ、パケットの SRQ 振り分けを
  NIC 側で行う (§3.3)。**deadlock 検出**: 集中待ち行列なので全キューから wait-for
  graph を構築でき、分散型ロックより検出が容易になる、と論じる(実装・評価は無し)(§3.3)。

## Evaluation
- Setup [paper]: CloudLab の 4 サーバノード(各 32-core AMD 7452 / 128GB DDR4 /
  480GB SATA SSD ×2 / dual-port Mellanox ConnectX-5 100Gb, PCIe v4.0)、Dell 100GbE
  スイッチ、Ubuntu 20.04。StreamLock は Rust 2,852 行。比較対象は CASLock(DrTM 系の
  RDMA_CAS ロック [42])、HOCL(hierarchical locking [38] = Sherman の階層ロック、§6)、
  DSLR(分散チケットロック [45])、ShiftLock(分散 MCS ロック [17])。マイクロベンチは
  空クリティカルセクションで unlock 直後に lock を再発行 (§5)。
- 要求順序付け (§5.1, Fig. 7): StreamLock はクライアント数に対しほぼ線形にスケールし、
  順序付け無しベースラインに肉薄する peak 10.33 Mops/s(HOCL は 4.29 Mops/s)(Fig. 7a)。
  128 クライアント・writer-only で P90 24μs(ShiftLock 38μs、HOCL 44μs、CASLock は
  P90 が StreamLock の 2.67×)。20%/80% writer/reader 構成では ShiftLock / DSLR の
  writer P90 が 64μs 超に悪化(reader の atomic カウンタ更新による NIC 競合)(Fig. 7b)。
- 所有権移転 (§5.2, Fig. 9): 160 クライアント・reader 比 0〜80%。reader 0% で CASLock /
  HOCL の移転レイテンシは StreamLock の 5.11× / 2.11×、移転あたり RTT 数は 9.15× /
  3.35× (Fig. 9a, 9b)。DSLR は reader 比によらず移転あたり ~21 RTT。StreamLock の writer は
  定常 2 RTT(先頭要求読取 1 + 後継通知 1)、reader も leader 比率 ~1.5% のため約 2 RTT
  (leader 3 / follower 2)(§5.2)。
- 感度分析 (§5.3, Fig. 8): multi-lock は XRC ベースが CPU ディスパッチ比最大 9.37×
  (CPU 版はロック 1000 個超で CPU 100%)(Fig. 8a)。クリティカルセクション長 5〜40μs の
  掃引では、短い CS ほど順序付け・移転オーバーヘッドが上がり、DSLR はポーリング輻輳で
  悪化、StreamLock は輻輳が無く CS 長に比例 (Fig. 8b)。Zipf 競合(100 万ロック・256
  クライアント)では α=0 で 3 者同等、競合が強まると最大 2.21× 優位 (Fig. 8c)。
- TPC-C / TATP (§5.4, Fig. 10): 12 ワークロード、テーブルを全ノードに均等シャーディング、
  行数 60,000 / 600,000、**行ごとに 1 ロック**、2PL、スキューあり、計 4〜256 / 32〜256
  クライアント、Tokio 系軽量コルーチン使用。write 系では StreamLock が ShiftLock 比で
  TPC-C 最大 +22.00% / TATP 最大 +24.08%。read 系では +65.96% / +61.20%(read 系は
  順序付けもストレスするため差が拡大)。CASLock は 16(TPC-C)/128(TATP)クライアント/
  ノードで RNIC IOPS をほぼ使い切り頭打ち。DSLR は write 系 TPC-C / TATP で CASLock 比
  1.28×〜3.9× / 44.94%〜1.64×、HOCL 比 55.56%〜1.57× / 16.46%〜34.34% 良い。
  イントロの集約値は「合わせて TPC-C / TATP で最大 14.85× / 9.51×」(§1)。
  [inference] §5.4 の対 ShiftLock 差は最大 66% なので、14.85× / 9.51× は最弱ベースライン
  (CASLock)比と読むのが自然だが、本文 §1 は比較対象を明示していない。
- 分散キャッシュ (§5.5, Fig. 11): Redis + RedLock(集中ロックマネージャ)との比較。
  TATP GET_SUBSCRIBER_DATA、NURand スキュー、ノードあたり Redis 16 worker、60 万
  ロック。RedLock はマネージャ CPU がボトルネックで P50 48ms / P90 110ms、StreamLock は
  P50 5.5ms / P90 16ms。
- 分散 FS (§5.6, Fig. 12): NVM 最適化分散 FS の Octopus の per-file ロックを差し替え。
  4 ノード × 4 worker、read/write 80%/20%、I/O 256B。128 クライアントで ShiftLock 比
  +25.25%、DSLR 比 +45.93%。イントロの集約値は Redis / Octopus 最大 5.7× 加速 (§1)。
- [inference] 評価がカバーしていないもの:
  - 規模は 4 ノード・1 スイッチ・最大 256 クライアントのみ。lock ノード(SRQ ホスト)への
    受信集中がどのクライアント数・ロック数で NIC 受信側の限界に達するかの測定は無い。
  - §4.4 の fault 処理(leader / follower 故障、パケットロス)は設計記述のみで、故障注入・
    回復時間・タイムアウト閾値感度の実験が無い。「pre-defined period」の具体値も不明。
  - §3.3 の deadlock 検出(wait-for graph)は実装・評価されていない。TPC-C 2PL 評価で
    デッドロック・abort がどう扱われたかの記述も無い。
  - in-switch ロック(NetLock / FissLock)は §6 で議論されるが baseline に含まれない。
    「市販 NIC のみ」という土俵の違いはあるが、絶対性能の比較は不明のまま。
  - NIC は ConnectX-5 のみ。WQE 円環リンクのベンダ非依存性(他社 NIC / 新世代 NIC での
    再現性)は未検証。
  - マイクロベンチは空クリティカルセクション + 即時再取得という最大ストレス設定で、
    実アプリの保持時間分布での定常挙動は §5.3 の CS 長掃引(5〜40μs)に限られる。

## Limitations
- Stated [paper]:
  - lock ノードは常に健全という仮定。fail-stop 時のネットワーク分断も無いと仮定 (§4.4)。
  - 所有権移転の UD 通知はパケットロスし得る(タイムアウト + RC タッチで回復。ロスは
    [24] を根拠に稀とする)(§4.1.2, §4.4)。
  - multi-lock を CPU ディスパッチで実現するとロック数 1000 超で CPU 100% になり
    スケールしない(XRC 対応 NIC が前提になる)(§3.3, §5.3, Fig. 8a)。
  - reader 増加は StreamLock でも NIC 競合を増やす(ただし RTT 数が少ないため移転
    レイテンシの上昇は緩やか)(§5.2)。
- Inferred [inference]:
  - lock ノードはロックごとの単一障害点かつ直列化点。待ち行列(RECV バッファ配列 +
    LockMeta)は lock ノードのメモリにのみ存在し、複製・fail-over は設計されていない。
    「lock ノードは常に健全」(§4.4) は DB のロックマネージャ用途では強すぎる仮定。
  - 故障判定の根拠が RC の ACK である点は危うい。RC の ACK はトランスポート層
    (RNIC)が返すため、プロセスがハングしても NIC が生きていれば「パケットロス」と
    誤診断され、待機者は再待機し続ける可能性がある(fail-stop 仮定の外側だが、実運用では
    GC 停止・OS ハング等で起こり得る)。§4.4 は「owner state に応じて行動する」と
    述べるのみで、プロセス生存性と NIC 生存性の区別は論じられていない。
  - FCFS は「lock ノードの SRQ への着地順」に対する公平性であり、クライアントの発行順や
    ネットワーク距離の差は補正されない。近いクライアントが系統的に有利になり得る。
  - 1 グループで一括通知される reader 数は MAX_FOLLOWERS で上限される (Alg. 2)。巨大な
    reader 列での挙動(グループ分割による直列化)は分析されていない。
  - キュー容量 2N はクライアント総数 N の事前知識を要する。クライアントの動的参加は
    WQ エントリ追加 + 再 post (§4.1.1) だが、その最中の順序保証・コストは論じられて
    いない。membership / cid 割当の管理機構も本文に無い。

## Relations
- 本文内の系譜 (§2.2, §5, §6): baseline は CASLock [42](DrTM の RDMA_CAS ロック)、
  HOCL [38](§6 で「Sherman の hierarchical locking」と明記)、DSLR [45]、ShiftLock [17]。
  in-switch 系(NetLock [46]、FissLock [47])はスイッチへ、StreamLock は RNIC へ
  オフロードするという対比 (§6)。FORD の hitchhiked locking は「本研究と直交」と明言 (§6)。
- [[2026-fast-wei-dmtree.md]](DMTree: DM 上の B+-tree): 直接の接点。DMTree は leaf の
  RDMA_CAS ロックの IOPS 消費を「lock を compute 側に移す」ことで回避したが、順序付け
  自体は依然 CAS ベース。StreamLock は同じ問題(atomic verb の NIC 競合、§2.2)を
  「CAS を排して SRQ 受信順序を使う」ことで解く。さらに StreamLock の HOCL = Sherman の
  階層ロック (§6) は DMTree の主要 baseline でもあり、「DM 索引のロックパス」という
  共通の土俵で 3 方式(memory 側 CAS / compute 側 CAS / SRQ 順序付け)が比較可能。
- [[2026-edbt-krause-disaggregated-survey.md]](分離システムサーベイ): 同サーベイが
  open challenge に挙げる「RDMA/CXL 横断のロック抽象」に対し、本論文は RDMA 側の
  ロックプリミティブの具体解。ただし StreamLock はパケット受信(メッセージ)に依存する
  ため、load/store 型の CXL には直接は移植できない [inference]。
- [[2026-sigmod-kettaneh-leader-leases.md]](Leader Leases / Liveness Fabric): 対照的な
  故障検知設計。StreamLock は「分断無し + fail-stop + RC ACK タッチ」という強い仮定で
  ロック保持者故障を扱う (§4.4) のに対し、Leader Leases は分断(対称・非対称)まで含む
  故障検知基盤を lease に供給する。分散ロック/リースの liveness を何が保証するか、
  という軸で両ノートは補完的 [inference]。

## Idea seeds
- [inference] DM 索引のロックパス置換実験: Sherman / DMTree 系の leaf ロック
  (RDMA_CAS)を StreamLock 型の SRQ 順序付けロックに置き換えたときに、
  [[2026-fast-wei-dmtree.md]] が示した「locking の IOPS 消費」(update 期待値の
  48.1〜61.8%)がどこまで回復するかを測る。ロック粒度が leaf(数千万個)なので
  XRC でも SRQ をロックごとに持てるかが焦点 — StreamLock の multi-lock 評価は
  1 万ロックまで (Fig. 8a) で、索引規模(10^8 行)とは 4 桁の開きがある。第一歩:
  ロック数を 10^4→10^7 に掃引して XRC ベース StreamLock の QP / SRQ リソース消費と
  スループットの崩れる点を特定する。
- [question] lock ノードの可用性をどう補うか。共有ストリーム(RECV バッファ配列)は
  lock ノード上の生メモリであり、複製すると SRQ の「ハードウェア受信順序」という
  順序付けの根拠が複製間で一致しなくなるはず。順序付けだけ lock ノードで行い、
  確定した順序列を別ノードへ非同期複製する(WAL 的な)構成で fail-over 可能かは
  開いた問題。検証の第一歩: lock ノード kill 時に全クライアントがハングすることの確認と、
  順序列の複製レイテンシがクリティカルパス(2 RTT)に乗らない設計のスケッチ。
- [inference] 2PL ロックマネージャとしての完成度評価: 本論文の TPC-C は行=ロックの
  2PL ハーネスで、デッドロック検出 (§3.3) は未実装・abort 処理の記述も無い。集中
  待ち行列から wait-for graph を作る提案 (§3.3) を実装し、hot-row 競合(TPC-C
  NewOrder の warehouse 行)でのデッドロック検出レイテンシと、FCFS 保証が
  wound-wait 等の優先度ベース CC と両立するかを測る実験は、DB 側から見た本方式の
  実用性を直接検証できる。
- [question] Timeout の故障診断は「RC ACK = 生存」に依存する (§4.4) が、RC ACK は
  RNIC が返すのでプロセスハングを検出できないのではないか。プロセス生存確認
  (アプリ層 ACK)を足した場合に fault-free パスの 2 RTT が保てるか、公開実装が
  あれば注入実験で確かめたい(artifact URL は本文に見当たらず、要調査)。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: full-text 格上げ(status: abstract-only → read。手動取得した PDF 全文を読解し全節を執筆)
