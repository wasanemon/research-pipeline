---
title: "Aurora PostgreSQL Limitless Database: Building a Highly Scalable OLTP Database"
authors: [Dmitry Arkhangelskiy, Saikiran Avula, Sachit Batra, Jin Chen, Radwan Deeb, Alexey Gotsman, Upendra Gowda, Haritabh Gupta, Benoit Hudzia, Rishabh Jain, Kaumudi Kaushik, Aravind Kumar Kumar, Sergey Melnik, Saleem Mohideen, Sharique Muhammed, Davor Prugovecki, Sanjay Shanthakumar, Sagar Shedge, Anand Kumar Thakur, David Wein]
venue: "SIGMOD Companion"
year: 2026
ids: {doi: "10.1145/3788853.3803089", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3788853.3803089", pdf: "literature/pdfs/2026-sigmod-arkhangelskiy-aurora-limitless.pdf", code: ""}
status: read
read_date: 2026-07-06
tags: [distributed-transactions, snapshot-isolation, external-consistency, mvcc, two-phase-commit, hlc, clock-synchronization, sharding, serverless, cloud-native, oltp, postgresql, production-system]
---

<!-- 著者・会議情報は PDF ヘッダ(p.1 の ACM Reference Format ブロック、
     "SIGMOD Companion '26, May 31-June 05, 2026, Bengaluru, India")で照合済み。
     著者はアルファベット順(p.1 脚注 ∗)。Gotsman は IMDEA Software Institute 所属、
     Gupta / Melnik / Wein は "work done while at AWS"(p.1 脚注 †)。 -->

## TL;DR
Amazon Aurora PostgreSQL を水平スケール可能にした production 分散 OLTP システムの
産業論文。router 群(クエリ分配・2PC 駆動)+ PostgreSQL shard 群 + Aurora 分散
ストレージ(3 AZ 複製)の3層で、アプリ側シャーディングを不要にする。核は、
Amazon Time Sync の有界クロック誤差(CEB)を使って PostgreSQL の xid 集合
スナップショットをスカラータイムスタンプに置換した time-based MVCC(Clock-SI 系
+ shard ごとの HLC で read delay を排除)と、状態を router ではなく lead shard に
永続化する non-blocking 2PC の統合。RC / RR(=SI)+ external consistency を提供し、
serializability は非対応。Serverless V2 による垂直スケールと shard split(512 table
slices + copy-on-write clone)による水平スケールを併用。HammerDB(TPC-C 派生)で
最大 2.89M NOPM を報告。

## Problem & motivation
- [paper] 単一 primary の DB アーキテクチャは write throughput・ストレージ容量・
  同時接続数で限界に達する。アプリ側シャーディングやインフラ管理なしで
  数百万 TPS・ペタバイト級に伸ばしたい (§1, p.1)。
- [paper] PostgreSQL の xid ベーススナップショット(xmin / xmax / xip_list)は
  実行中トランザクション全記録が必要で CPU-intensive、高スループット PostgreSQL の
  既知の contention 源であり、単一ノードが全実行中トランザクションを把握できない
  分散環境には根本的に不向き (§5.1, p.5)。
- [paper] 設計目標は5点: ①中央集権トランザクションマネージャに依存しない write
  scaling、②multi-shard トランザクションでも PostgreSQL のトランザクション意味論を
  保存、③well-sharded なアクセスパターンで単一システム同等の性能、④シームレスな
  水平スケーラビリティ、⑤単一システム同等の管理体験 (§1, p.1)。
- [paper] 提供する isolation は Read Committed と Repeatable Read を external
  consistency [10] で拡張したもの (§1, p.1)。
- [paper] AWS で1年超 production 稼働。最大構成 32 routers / 64 shards、最頻構成
  4 routers / 8 shards (§1 p.2, §4 p.4)。

## System model & assumptions
- [paper] スコープは単一 AWS region 内・3 Availability Zone 横断。geo(cross-region)
  分散は対象外で、その分の最適化を明示的に選択(Paxos / Raft 等の合意プロトコルを
  持たず、Aurora ストレージの cross-AZ 複製に耐久性を委ねる)(§3.1, §9 p.12)。
- [paper] ストレージモデル: Aurora 分散ストレージはボリュームをセグメント分割し
  各書き込みを 6 レプリカ(AZ あたり 2)に複製。AZ 全損 + 他 AZ の1レプリカ損失でも
  durable、AZ 全損でも write 可用。セグメント故障は自動検出・修復 (§3.1, p.3)。
- [paper] Aurora ストレージは1ボリュームへの書き込みを同時に1つの PostgreSQL
  インスタンスからしか受け付けない。この性質を shard failover の split-brain 防止
  (zombie fencing)の土台に使う (§6, p.8)。
- [paper] データプレーン: router fleet + shard fleet = shard group。各 router / shard は
  それぞれ自分のストレージボリュームを持つ PostgreSQL クラスタ (§3.2, Fig. 2)。
  shard がデータを所有し、router はデータを持たずメタデータ(トポロジ・スキーマ・
  placement mapping)のみ保持。スキーマ定義と placement mapping は router が
  authoritative source、トポロジは control plane のメタデータサービスから同期 (§3.2)。
- [paper] 接続モデル: クライアントは DNS ベース負荷分散で router に接続し、セッションは
  その router に固定。router-shard 間は複数接続をトランザクション粒度で多重化し、
  セッション状態(認証・ロール・変数)は session-context passing で維持 (§3.2, p.3)。
- [paper] テーブルモデル: sharded(shard key のハッシュで水平分割。session パラメータ
  limitless_create_table_mode / _shard_key で指定、CREATE TABLE 構文は不変)、
  reference(全 shard に全量複製。join 頻度が高く小さいテーブル向け)、standard
  (単一 shard に配置。従来 PostgreSQL からの移行入口で、後から sharded / reference に
  変換可能)。同一 shard key のテーブルは co-locate 可能で join を単一 shard に閉じる
  (§2, Fig. 1, p.2)。
- [paper] クロックモデル: Amazon Time Sync が now() = (t, CEB) を返し、真の時刻が
  [t−CEB, t+CEB] に入ることを保証(冗長な衛星接続原子時計 fleet)。典型 CEB は
  全 region で 1ms 未満、一部 region では数十 µs [21]。API はオープンソースの
  ClockBound デーモン [3] 経由 (§5.1, p.5)。
- [inference] プロトコルの正しさ(Property 1、external consistency、lease fencing)は
  すべて「CEB が真の誤差の上界である」ことに依存する。CEB 違反(クロック障害)時の
  安全性は本文で論じられていない。
- [paper] 故障モデル: router は同質で専用 standby なし(コスト削減)。故障時は DNS で
  他 router に流し、復旧は分オーダーになり得る — これが 2PC 状態を router に置かない
  動機 (§3.4 p.3, §5.4 p.6)。shard は顧客設定で 0–2 standby(別 AZ)を持て、故障時は
  standby がストレージボリュームごと引き継ぐ (§3.4)。
- [paper] ワークロード仮定: production では read-only と single-shard トランザクションが
  支配的で、これらは 2PC を回避する fast path に乗る (§5.4, p.6–7)。single-shard クエリが
  システムの sweet spot (§7, p.10)。
- [paper] isolation は RR(PostgreSQL では SI)と RC のみ。serializability は顧客需要が
  限定的なこと、PostgreSQL の SSI 実装 [31] では serialization order が commit order と
  一致しないことから見送り (§5 p.5, §10 p.12)。
- [paper] 容量単位: 1 ACU ≈ メモリ 2GB + 対応する CPU・ネットワーク資源。shard group の
  最大 ACU から初期ノード数が決まる(例: 最大 1200 ACU → 4 routers + 8 shards、
  Table 1)。standby は容量バジェット外 (§4, Table 1, p.4)。
- [paper] shard key の選択は「one-way door」で、reshard にはデータ移行が必要という
  運用上の前提 (§10, p.12)。

## Approach
### スケーリング (§4)
- [paper] 垂直: 各ノードが Serverless V2 [1,7] で min–max ACU 間を伸縮。バジェットは
  当初均等割りし、以後は各ノードの実消費 ACU に比例して min / max を再配分
  (dynamicMinACU_i = shardGroupMinACU · consumedACU_i / Σ_j consumedACU_j、max も
  同形。多く使うノードほど成長需要が高いという観察に基づく)(§4.1, p.4)。shard の
  スケール契機は compute 利用率、router は memory 利用率(shard は buffer cache を、
  router は分散クエリの中間結果用 heap を多く使うため)。scale-up は即応・scale-down は
  保守的という非対称レート (§4.1)。
- [paper] 水平: shard の2分割と router 追加。顧客手動(非同期ワークフロー)に加え、
  heat-management service が垂直スケール後も ACU / ストレージ閾値を超える shard を
  自動分割するモードあり (§4.2, p.4)。新ノードの容量は shard group の空き容量から
  割り当て、不足時はリクエスト拒否 (§4.2 Capacity management)。
- [paper] table slices: 各 shard が持つハッシュレンジをテーブルあたり典型 512 slice に
  細分し、shard は自分の担当分を slice = パーティションの PostgreSQL partitioned table
  として表現。slice が移行の最小単位で、co-located テーブルの対応 slice は一緒に移行
  (join 最適化を保存)。standard テーブルは分割されない。自動分割時の分割点は
  heat-monitoring の hot slice 情報で決める (§4.2 Table slices, p.4)。
- [paper] shard split は4フェーズ: ①Aurora の copy-on-write clone [4] でボリュームを
  ストレージ層で複製(過負荷 shard から読み出さないので最大負荷中でも分割可能)、
  ②clone 中の更新を source の redo log 再生で追いつき、③switchover: 移行対象 slice を
  持つテーブルを全 router・shard でロックして新規 write を遮断(競合ロックを持つ
  実行中トランザクションは強制終了)、redo 再生を完了させ、router の slice→shard
  マッピングを更新、source は移行 slice を DETACH PARTITION、④両 shard が不要 slice を
  バックグラウンド削除。顧客影響は switchover 中の DDL・対象 slice への更新ブロックと
  一部トランザクション終了のみ (§4.2 Shard-split workflow, p.4–5)。
- [paper] router 追加は既存 router の clone → トポロジ登録 → DNS 登録 (§4.2, p.5)。

### 並行性制御とコミット (§5)
- [paper] スナップショット: トランザクション T の最初のクエリ時に router が
  startTs = now().latest を割り当て、shard への全クエリに piggyback。可視性の規範は
  Property 1: T′ の変更が T のスナップショットに入る ⟺ T′.commitTs ≤ T.startTs
  (§5.1, p.5)。
- [paper] 多版管理: 行バージョンの可視性判定を xid 比較から
  xmin.commitTs ≤ T.startTs < xmax.commitTs に置換。行フォーマットは変えず、
  xid → commitTs の対応表を既存の PostgreSQL commit log(clog)構造に統合して保持
  (§5.2, p.5–6)。
- [paper] write-write 競合: PostgreSQL と同じく変更行の排他ロックをコミットまで保持。
  ロック取得後、行の全既存バージョンが自分のスナップショットに覆われているか確認し、
  新しいバージョンがあれば abort(first-updater-wins、RR のみ)(§5.3, p.6)。
- [paper] time-aware 2PC(Fig. 3): コミット要求を受けた router は、更新 shard の中から
  lead shard を1つ選び、他の更新 shard に lead shard id 付き PREPARE TRANSACTION を
  送る。各 shard は prepare timestamp を計算(§5.5 の HLC 込みで max{C, now().latest})、
  prepare 情報 + lead shard id を自ボリュームに永続化して router に返す。router は
  prepare timestamp の最大値を lead shard に送り、lead shard は
  commitTs = max(受領値, 自身の提案) を決めて永続化・ローカルコミットし router に
  ACK。router はクライアントに応答し、他 shard へは COMMIT PREPARED を非同期送信
  (§5.4, p.6)。prepare 失敗時は router が全 shard に ROLLBACK PREPARED (§5.4)。
- [paper] router 故障時の non-blocking 性: 2PC 状態は router でなく lead shard に永続化
  される(router は standby なしで置換に分単位かかり得るが、lead shard は standby で
  秒単位で置換可能)。router 故障時、どこにも prepare されていないトランザクションは
  abort、prepare 済み未コミットは lead shard の状態が authoritative で、他 shard が
  lead shard に照会(lead がコミット済みなら全 shard でコミット、さもなくば abort)
  (§5.4, p.6)。
- [paper] fast path: read-only トランザクションは router が即コミット。単一 shard のみ
  更新するトランザクションはその shard に転送してローカルにコミット時刻を決めさせ、
  2PC を回避(複数 shard から読んでいても適用可)(§5.4, p.6–7)。
- [paper] クロックスキュー対応(Clock-SI との差分): startTs が shard のローカル時刻より
  未来の場合、Clock-SI [17] は読みを遅延させるが、本システムは shard ごとの hybrid
  logical clock C を T の read ごとに max{C, T.startTs+1} に進め、prepare / single-shard
  commit の timestamp を max{C, now().latest} で計算する。これで「T が読んだ後にその
  shard がコミットするトランザクションは必ず commitTs > T.startTs」となり、遅延なしで
  即読める (§5.5, p.7)。
- [paper] prepared 状態の行の読み: T が読む行を prepare 済み(prepareTs < T.startTs)の
  分散トランザクション T′ が更新している場合、shard は T′ の lead shard に T.startTs 付き
  で照会。コミット済みなら commitTs が返り可視性を判定。未コミットなら lead shard が
  自分の C を max{C, T.startTs+1} に進めて応答し、T′ の commitTs > T.startTs を保証して
  T に不可視化する (§5.5, p.7)。
- [paper] COMMITTING 状態: コミット時刻は決まったがログ flush 未完のトランザクション
  T′ が更新した行を、T′.commitTs ≤ T.startTs の T が読む場合は T′ の確定まで待つ
  (T′ は storage write 失敗で abort し得るため)(§5.5, p.7)。
- [paper] real-time order / external consistency: 「T2 が(non-read-only の)T1 の
  クライアント応答後に開始すれば T2.startTs > T1.commitTs」という strong SI を保証。
  lead shard が commitTs 決定後、now().earliest > commitTs になるまで待ってから router に
  ACK する commit wait [11] で実現。脚注では更に強い external consistency [10]
  (T2 が T1 完了後にコミット開始すれば T2.commitTs > T1.commitTs)を保証すると主張
  (§5.6 + footnote 1, p.7)。commit wait はコミットログの storage 書き込みと並行実行され、
  storage write レイテンシが CEB(典型 <1ms)を上回ることが多いため、クリティカル
  パスにはほぼ乗らない (§5.6, p.7)。
- [paper] DDL: PostgreSQL 意味論を踏襲し、DDL + DML を単一トランザクションに同梱可能。
  多くの DDL は対象テーブルを持つ全 shard に加え全 router で heavyweight lock
  (例: ALTER TABLE の ACCESS EXCLUSIVE)を取り、コミットは全 router も参加する
  2PC 変種で行う — クラスタ全体で DDL がアトミックに可視化される (§5.7, p.7–8)。
  グローバルシーケンスは1 shard に永続オブジェクトを作り、router 群に互いに素な
  レンジを事前配布して shard 非接触で採番、枯渇時のみ補充 (§5.7, p.8)。
- [paper] 分散デッドロック: 顧客設定のタイムアウト超過で疑い、1つの router が各 shard
  から waits-for グラフを収集して合併グラフの閉路を検査、ランダムな犠牲者を abort
  (§5.8, p.8)。DDL 同士のデッドロックは「必ず distinguished node で先にロック取得 →
  成功したら残りへ並列送信、失敗なら abort」という順序付けで回避(DDL に1往復追加)
  (§5.8)。
- [paper] Read Committed: 文ごとに now().latest で新スナップショットを計算(文単位で
  より新しいスナップショットが見える)。write-conflict 検査は無効化(排他ロックは
  取るが、first-updater-wins の abort はしない)(§5.9, p.8)。

### Failover・バックアップ (§6)
- [paper] read lease: 各 shard は storage への書き込み成功で lease を確立・更新する。
  各 write に shard のクロック値 t をタグ付けし、成功すれば t+TTL まで lease が有効。
  lease は「スナップショット時刻 ≤ t+TTL の read の提供」を許す。更新に複数回失敗した
  shard は自分を zombie と判断して自己終了 (§6, p.8)。
- [paper] failover: 新インスタンスはボリュームから最後の lease 開始時刻 t_last を回復し、
  now().latest > t_last + TTL まで待ってから新 lease を取得して処理開始。TTL は典型的な
  failover 時間より短く設定するので通常は追加待ちなし。根拠: prepare timestamp は
  now().latest 由来で commitTs ≥ prepare timestamp なので、待ち後に新インスタンスが
  コミットするトランザクションは commitTs > t_last+TTL となり、zombie が lease 内で
  返し得る read は「見えるべきでないものを見逃すだけ」で正当 (§6, p.8)。
- [paper] バックアップ: shard group 全体(全 shard + router)のバックアップは Time Sync
  タイムスタンプ t に紐付き、「commitTs ≤ t のトランザクション全て、どの shard で
  コミットされたかに依らず」を正確に反映する。実装は、全ログレコードにコミット
  プロトコル由来のタイムスタンプをタグ付けし(コミットレコードには commitTs)、
  バックアップには全ボリュームの timestamp ≤ t のログエントリのみを含める。復元時、
  commitTs ≤ t で一部 shard は committed・一部は prepared のままの分散トランザクションは
  router 故障時と同じく lead shard 照会で解決 (§6, p.8–9)。

### クエリ処理 (§7)
- [paper] router は sharded テーブルを「ハッシュ空間の分割を鏡写しにした PostgreSQL
  partitioned table」として持ち、各パーティションはカスタム FDW 経由で shard 上の
  実データを指す foreign table。reference / standard テーブルも foreign table 表現
  (脚注2: shard 側も slice 単位の partitioned table なので、全体では2層の
  パーティショニング)(§7, p.9)。
- [paper] multi-shard クエリは PostgreSQL プランナのパーティション別サブプランを
  そのまま shard へ送って並列実行(Async Foreign Scan)し、router で append・後処理。
  可能な限り部分集約・ソートを shard へ push down(count(*) が PARTIAL count(*) の
  木になるプラン例)(§7, p.9)。
- [paper] 述語は foreign(組み込み演算・IMMUTABLE 関数のみ → shard で評価)と
  local(STABLE / VOLATILE / definer 関数 → router に取り寄せて評価)に分類 (§7, p.9)。
- [paper] join pushdown: co-located sharded 同士の inner join は shard ごとに並列実行し
  router で結合結果を append。PostgreSQL コストモデルはデータが shard にあることを
  知らないため修正した。sharded × reference の join も push down するが、適用可能なのは
  直積・inner join・reference 側が null-padded の outer join のみ(sharded 側が
  null-padded の outer join と anti-join は不可)。standard 同士はその shard へ、
  standard × 他タイプは現状 router で実行 (§7, p.9)。
- [paper] 関数分散: 単一 shard のデータしか触らない SQL 関数を、shard key に対応する
  引数を宣言して(rds_aurora.limitless_distribute_function)shard へ push down (§7, p.10)。
- [paper] 単一 shard クエリは partition pruning で検出して丸ごと push down。往復が減り
  低レイテンシで、システムの sweet spot。shard key 選択と関数の distributed 宣言が
  性能チューニングの主レバー (§7, p.10)。

## Evaluation
- Setup [paper]: us-east-1、router / shard とも Serverless V2(最大 256 ACU ≈ メモリ
  512GB)。ベンチマークは HammerDB(TPC-C 派生)をカスタマイズ: customer, stock,
  history, warehouse, order_line, new_order, orders, district を各 id 列で shard 化、
  item は reference table、単一 shard で完結する処理は distributed function 化。
  warehouse 数 12,000、分散トランザクションはワークロードの約 10%。1000 同時
  仮想ユーザ、計 1000 万イテレーション、各構成 1 時間(20 分の ramp-up 除く)。
  構成は Table 2 の5つ: r1 = 2R/4S/1536ACU、r2 = 4R/8S/1536、r3 = 8R/16S/1536、
  r4 = 4R/8S/3072、r5 = 8R/16S/3072 (§8, Table 2, p.10)。
- 垂直スケーリング [paper] (§8.1, Fig. 4–5):
  - r3→r5(8R/16S、1536→3072 ACU): スループット +41.6%(2,042,201 → 2,891,718
    NOPM)、NEWORD 平均レイテンシ −40.8%(16.42ms → 9.72ms)。
  - r2→r4(4R/8S、1536→3072 ACU): スループット +4.7%(2,012,763 → 2,107,539
    NOPM)にとどまるが、レイテンシは −37.7%(21.06ms → 13.13ms)。
  - ACU 割り当て(Fig. 6–7)は負荷開始で上昇・ピークで安定・終了で漸減という
    serverless の自動追従を示す。
- 水平スケーリング [paper] (§8.2, Fig. 4–7):
  - r1→r2(1536 ACU 固定、2R/4S → 4R/8S): スループット +58.7%(1,268,350 →
    2,012,763 NOPM)、レイテンシ −29.1%(29.70ms → 21.06ms)。r1 では shard 間の
    ACU が 150–200 と不均衡で最重負荷 shard が律速(総 ACU は上限未満)、r2 では
    125–140 に均衡 (Fig. 6)。
  - r4→r5(3072 ACU 固定、4R/8S → 8R/16S): 本文は「+41.6%(2,042,201 →
    2,891,718 NOPM)、レイテンシ −26%(13.13ms → 9.72ms)」と記述。r4 の shard は
    ピーク 130–160 ACU、r5 は 85–100 ACU でより均等 (Fig. 7)。
  - [inference] この r4→r5 の記述は §8.1 と数値が食い違う: §8.1 では r4 =
    2,107,539 NOPM であり、2,042,201 は r3 の値。r4 基準なら増加率は約 +37% の
    はずで、§8.2 の 2,042,201 / +41.6% は r3 の数値の誤流用(論文内不整合)と見られる。
- [inference] 評価がカバーしていないもの:
  - 他システムとの比較が一切ない(Citus / CockroachDB 等は §9 で定性比較のみ)。
    ベースラインは自システムの構成間比較だけで、single-node Aurora PostgreSQL との
    オーバーヘッド比較すらない。
  - スケーリング遷移中の性能が未測定: shard split の switchover による書き込み
    ブロック・トランザクション強制終了の頻度や持続時間 (§4.2) を定量化する実験が
    ない(abstract-only 時点のノートで立てた論点はやはり未回答)。
  - failover / lease(§6)・router 故障時の 2PC 復旧(§5.4)の障害注入実験がなく、
    復旧時間の実測値もない。
  - 分散トランザクション比率は約 10% 固定で、比率を掃引したときの 2PC + commit wait
    のコストカーブが見えない。CEB(<1ms 〜 数十 µs)への感度も未測定。
  - レイテンシは NEWORD の平均のみで、tail(P99)がない。
  - abstract の「millions of transactions per second」に直接対応する実測は本文にない
    (§8 の最大値は 2.89M NOPM = 毎分の New Order 数であり、毎秒ではなく指標も
    異なる。TPS 主張は production 一般の記述と読むべき)。

## Limitations
- Stated [paper]:
  - serializability 非対応。顧客需要の少なさと、PostgreSQL の SSI [31] では
    serialization order が commit order と一致しない [30] ことが理由 (§10, p.12)。
  - shard split の switchover 中は対象 slice への更新と DDL がブロックされ、競合する
    実行中トランザクションは強制終了される (§4.2, p.5)。
  - DDL は対象 shard 群 + 全 router でのロック取得と router 参加の 2PC 変種を要し、
    デッドロック回避のための distinguished-node 先行ロックが1往復を追加 (§5.7–5.8, p.8)。
  - join pushdown の適用範囲に制限(sharded 側が null-padded の outer join・anti-join は
    不可、standard × 他タイプは router 実行)(§7, p.9)。
  - スタンドアロン PostgreSQL からの移行が最大の顧客課題: パーティション可能性の
    見極め・スキーマ再設計・クエリ移植が必要で、shard key 選択は reshard に
    データ移行を要する one-way door (§10, p.12)。
  - PostgreSQL 自体の近代化が必要な点として、schema versioning / canarying /
    スキーマの MVCC [6] の欠如、community PostgreSQL では commit 順と可視化順が
    一致せず read replica 構成でアノマリーを生むこと [26] を挙げる(本システムは
    両順序をタイムスタンプで一致させた)(§10, p.12)。
  - hybrid scaling は性能・コスト便益を出すのに注意深いチューニングが要る (§10, p.12)。
- Inferred [inference]:
  - 正しさが Time Sync の CEB 保証に単一依存する。CEB が破れた場合(衛星時計障害・
    デーモン異常)の検出・縮退の議論がない。commit wait も lease fencing も CEB 前提。
  - reference table への書き込みプロトコルが記述されていない。全 shard 複製の更新を
    どう原子的に見せるか(DDL 用の router 参加 2PC を使うのか、通常の 2PC で全 shard
    参加になるのか)は本文から読み取れない。
  - lead shard 方式は router 故障には non-blocking だが、standby を持たない lead shard が
    故障した場合の in-doubt トランザクションの扱い(standby 0 台設定時は
    再プロビジョニングまでブロックするはず)は明示されていない。
  - DDL が全 router 参加の 2PC になるため、router fleet が大きい構成(最大 32 routers)
    では DDL のコミットが fleet サイズに比例して遅く・脆くなる可能性がある。
  - RC で write-conflict 検査を切るのは PostgreSQL 準拠だが、分散環境では文ごとの
    スナップショット前進と併せて lost update 系のアノマリー面積が単一ノードより
    大きく見える可能性がある(アノマリーの分析はない)。
  - 産業論文(13 ページ、SIGMOD Companion)であり、プロトコルの正しさは informal な
    議論のみで機械検証・形式証明への言及がない。

## Relations
- 競合・比較(本文 §9): Citus(分散トランザクションに SI なし)、Greenplum
  (中央 coordinator が xid 割り当て → ボトルネック)に対し「中央 coordinator 排除 +
  垂直/水平両スケール」で差別化。Spanner(TrueTime + commit wait の借用元)、
  Clock-SI(SI アルゴリズムの土台)、CockroachDB / YugabyteDB(HLC。Time Sync
  なしでは最大スキューを数百 ms で保守的に設定する必要があり、CockroachDB は
  external consistency を一般には保証しない)、Aurora DSQL(OCC・multi-region)、
  PolarDB(RDMA timestamp oracle または HLC)(§9, p.11–12)。
- [[2026-sigmod-kettaneh-leader-leases.md]](CockroachDB Leader Leases): 同じ SIGMOD
  Companion '26。両者とも「lease による read の安全なローカル処理 + fencing」を扱うが、
  対照的: CockroachDB は合意(Raft)上の lease 維持コストが問題で Liveness Fabric を
  導入、Aurora Limitless は Aurora ストレージの単一 writer 性質 + Time Sync 時刻で
  lease を実装し、合意プロトコル自体を持たない (§6, §9)。「合意ベース vs ストレージ
  fencing ベースの lease」は横断比較軸。
- [[2026-sigmod-saenz-hyperscale-storage.md]](Azure SQL Hyperscale storage tier):
  Aurora 分散ストレージ (§3.1) の直接の競合にあたる Azure 側の disaggregated storage
  産業報告。Limitless が前提として依存する storage 層(3 AZ 複製・単一 writer・
  copy-on-write clone)の設計選択を比較する材料。
- [[2026-sigmod-chen-cloudjump3.md]](CloudJump III / Alibaba): 同じくクラウド DB の
  産業論文。Limitless §9 が commit timestamp 方式で比較する PolarDB [38] と同じ
  製品系列で、「クラウド DB のスケールアウト(本論文)vs ストレージ階層化
  (CloudJump III)」という補完関係。
- [[2026-cidr-arora-salesforce-oltp.md]](SalesforceDB): 同時期の Postgres 系
  production OLTP 報告。Salesforce は storage engine を LSM に置換して multi-tenancy に
  対応、Aurora Limitless は heap / MVCC を保ちスナップショット機構と commit protocol を
  置換してシャーディングに対応 — 「PostgreSQL をクラウドスケールさせる際にどの層を
  作り替えるか」の対照事例。

## Idea seeds
- [inference] shard split の switchover(§4.2)がワークロードに与える影響は本論文でも
  未測定のまま(abstract-only 時点の論点が本文で確認された)。HammerDB 実行中に
  split を誘発し、ブロック時間・強制終了トランザクション数・NOPM の落ち込みを
  時系列で測る再現実験は AWS 上でそのまま実施可能。Citus 等の reshard と横並び比較
  すれば「オンライン resharding の顧客影響」という評価軸を業界横断で規格化できる。
- [question] reference table の更新はどのプロトコルで全 shard に原子的に反映されるのか。
  本文に記述がなく、DDL 用の「全 router 参加 2PC」(§5.7)の類推が効くのかは不明。
  実機で reference table 更新の並行可視性(更新中に各 shard から読む)を観察するのが
  第一歩。
- [inference] commit wait は「storage flush が CEB より遅いから隠れる」(§5.6) という
  主張だが、CEB が数十 µs の region と <1ms の region、また高速ログデバイスの組み合わせ
  では顕在化条件が変わるはず。CEB × ログ書き込みレイテンシの2次元で 2PC コミット
  レイテンシをモデル化・実測すると、「クロック精度がどこまで分散 DB の性能に効くか」
  という一般的な問いに答えられる(CockroachDB 系 HLC の保守的スキュー設定
  (§9) との定量比較を含む)。
- [inference] lead shard の選択規則は「router が更新 shard から1つ選ぶ」(§5.4) とのみ
  記述され、選択方針(最初に更新した shard? 負荷最小?)が tail latency に与える影響
  (commit wait・prepared-inquiry の集中)は開いた設計空間に見える。分散
  トランザクション比率を 10% から掃引しつつ lead 選択ポリシーを変える実験が最初の
  検証になる。
- [question] §8.2 の r4→r5 のスループット基準値(2,042,201)は §8.1 の r3 の値と同一で、
  r4 の値(2,107,539)と矛盾する。正しい増加率(約 +37%?)の確認は著者照会か
  図(Fig. 4)の精読が必要 — 本ノートの数値引用時は注意。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: full-text 格上げ(status: abstract-only → read。手動取得した PDF 全文を読解し全節を執筆)
- 2026-07-06: 検証パスによる修正(§5.4 / §5.5 / §5.6 / §5.7 の 4 箇所のページアンカーを原文の実ページに合わせて修正。数値・システム名・主張は全件ソース照合済みで訂正なし)
