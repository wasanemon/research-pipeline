---
title: "RIOT: Replicated Independently-Ordered Transactions"
authors: [Jim Webber, Georgios Theodorakis, Hugo Firth, Natacha Crooks]
venue: "SIGMOD Companion"
year: 2026
ids: {doi: "10.1145/3788853.3803094", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3788853.3803094", pdf: "literature/pdfs/2026-sigmod-webber-riot.pdf", code: "https://github.com/hyhjh211/TwoPhaseProtocol"}
status: read
read_date: 2026-07-06
tags: [consensus, leaderless, generalized-consensus, replication, distributed-transactions, graph-database, sharding, neo4j, txdag]
---

> **urls.code 注記**: 上記 code URL は RIOT 実装ではなく、第三者(Junhao Hu)による
> RIOT プロトコルの TLA+ 形式証明リポジトリ(本文 ref [15]、§3.8 で引用)。
> Neo4j 統合実装そのもののコードは公開されていない(本文中に実装公開の記述なし)。

## TL;DR
Raft/Paxos 型の単一リーダー + 全順序ログによる SMR は、通常運転時も故障時もリーダーが
ボトルネックになる (§1)。RIOT は中央リーダーとログ複製を廃し、各サーバが
トランザクション履歴の DAG(TxDAG)を独立に育てながら、「leading edge(コミット済みで
コミット済み子を持たないノード集合)」の相互交換で履歴互換性を検証する leaderless な
一般化コンセンサスプロトコル (§3)。可換性判定は下層 DB(Resource Manager)の CC に
委ね、RIOT 層は順序合意のみを担う layer 分離が特徴 (§3, §4.1)。Neo4j に統合し本番 Raft
実装と比較して、クライアント 100 以下(AuraDB の大半のインスタンスに相当)で
スループット +32〜250%、p99 最大 2.3× 低減。ただし leading edge サイズが並行
トランザクション数に線形に伸びるため、500–1000 クライアントでは Raft を最大 25%
下回る (§5.2)。マルチシャード実行(interposed coordinator + 各シャード内多数決の連言)を
設計として持つが、性能評価は単一シャードのみ (§3.7, §5.2)。

## Problem & motivation
- [paper] Raft 等の単一リーダー型 SMR は正しさの議論を単純化するが、リーダーが通常
  運転時の系統的ボトルネックであり、故障・回復時はさらに悪化する (§1)。Neo4j は現在
  この方式(単一サーバ + Raft 複製)を採用しており、格納データ量も単一マシン容量に
  制限される (§1)。
- [paper] 定量的裏付け: AuraDB(Neo4j のクラウドサービス)の実測で、Raft リーダー
  選出は数万クラスタのフリート全体で平均 1.47–1.77 回/日発生し、選出中は書き込み
  性能が 17 秒間急落する (§5.3, Fig. 10)。
- [paper] グラフワークロードは read-dominant で低競合: AuraDB では書き込みは日次
  クエリの 30% 未満、abort に至る書き込み競合は約 700 トランザクションに 1 回
  (§2, §3.4)。低競合最適化プロトコルの利得が大きいことを示唆 (§2)。
- [paper] 既存 leaderless プロトコル(EPaxos, CAESAR, Tapir, Janus, Basil)の共通戦略は
  read/write set を事前解析して依存関係を導出することだが、グラフ DB はクエリ実行中の
  トラバーサルで keyset が動的に構築されるため適さない。密な部分グラフに当たると
  アクセス keyset が爆発的に増える (§1, §6)。Accord は依存を DAG で表現する点で
  最も近いが、やはり実行前の keyset 解析で DAG を構築する (§1, §6)。
- [paper] シャーディング時の固有課題 = reciprocal consistency: LPG モデルでは全エッジが
  両端ノードに接続され双方向に同コストで辿れる必要があり、シャードを跨ぐエッジの
  更新・削除は全パーティションに整合的に適用されねばならない。これを守らない
  JanusGraph 型の eventually-consistent ストアでは dangling edge と修復不能な
  データ破損が生じる (§1, §2)。Spanner Graph は 2PC + MultiPaxos で守るが、
  典型的にリレーションシップの 30% がシャードを跨ぐため高価な 2PC パスが常用される
  (§2)。

## System model & assumptions
- [paper] 故障モデル: non-Byzantine。N 台の同一サーバ(一意 ID 付き)、非同期
  メッセージパッシング。メッセージ遅延あり、サーバの進行速度は不均一。共有メモリも
  グローバルクロックも仮定しない (§3.1)。サーバはクラッシュ故障し得るが、過半数
  ((n+1)/2)は稼働し続けると仮定 (§3.1)。
- [paper] クォーラム: 通常パスは単純多数決。fast path(1 往復での決定)には
  ⌈3n/4⌉+1 のより大きなクォーラムを要求し、fast quorum の決定が再現可能
  (以後の全決定と整合)であることを保証する (§3.1, §3.3.2)。
- [question] fast quorum の表記が §3.1・§3.3.2 では ⌈3n/4⌉+1、§3 冒頭の
  プロトコル概観(「supermajority of ⌊3n/4⌋+1 servers」)では ⌊3n/4⌋+1 と
  floor/ceiling が揺れている(§3.3.1 の 7a 自体は単純多数 ⌈N/2⌉+1 のみ言及)。N=3 だと
  ⌈3N/4⌉+1 = 4 台となり 3 台クラスタでは成立しない。どちらが正か TLA+ 仕様
  (ref [15])で要確認。
- [paper] サーバローカル状態: TxDAG G_S=(V_S, E_S)(エッジ = prepare 時に宣言された
  祖先関係)+ 2 つの集合 — LE(leading edge: コミット済みでコミット済み子を持たない
  トランザクション集合。「システムの現在バージョン」を表すフロンティア)と
  P(prepared トランザクション → コミット済み祖先集合のマップ)(§3.1, Fig. 1)。
  コミット済みノードは immutable、prepared は葉として追加され後に committed 化
  または除去される (§3)。
- [paper] コマンド形式: ⟨VERB, TID, [PREDICATE]⟩。VERB は PREPARE/COMMIT/ABORT と
  その応答、TID はクライアント生成の一意 ID、PREDICATE は要求祖先などの条件。
  実際には read-write 操作もペイロードに含まれる(脚注 1)(§3.1)。
- [paper] 可換性の定義: 2 コマンドの結果が実行順に依存するなら非可換(競合)、
  さもなくば可換で任意順・並行実行可。可換なら TxDAG 上で同じ祖先を共有(兄弟)、
  非可換なら多数決で一方が進み他方が abort (§3.1)。
- [paper] トランザクションモデル・CC への仮定なし: RIOT は DAG エントリを
  トランザクションのプレースホルダとして扱い、DB 統合時は各 Resource Manager (RM)
  が自身の CC・isolation ポリシーで prepare/commit の最終決定を下す(RM が最終
  арbiter)(§3, §4.1, §4.2)。正しさは DB が競合トランザクションを abort すること
  (悲観ロック、または write intent 付き MVCC 等の標準機構)に依存する (§4.1)。
- [paper] 一貫性目標: serializability(グローバルに一貫した順序 = 何らかの直列実行と
  等価)(§1, §3.8)。シャード跨ぎエッジには reciprocal consistency (§1, §3.7)。
  一般化コンセンサス(Lamport)の non-triviality / stability / liveness / consistency を
  満たすと主張 (§3.1)。
- [paper] 各サーバの履歴は「互換だが常に厳密同一とは限らない」。TxDAG は全サーバで
  isomorphic であり、実行順は equivalent(equal とは限らない)。可換トランザクションは
  サーバごとに異なる物理順で prepare/commit されてよい (§3, §3.2)。
- [paper] メンバーシップ: Raft 類似の joint consensus(新旧両構成での多数決合意で
  トポロジ変更コミット、split-brain 排除)。変更は TxDAG エントリとして通常
  トランザクション同様に処理。離脱サーバは joint 構成コミットまで参加継続、新規
  サーバは non-voting learner として snapshot 同期後に昇格。FLP により故障下の進行は
  保証されない (§3.9)。
- [paper] 耐久性: コミット時にトランザクションと依存関係を durable に記録
  (Alg. 3 で WAL に追記)(§3.3.1)。評価ではデータセットはメモリに収まるが
  ディスクへの永続化は行う (§5.1)。
- [inference] クライアントは一意 TID を生成し outcome を待つ「closed-loop」モデルが
  評価の前提 (§5.1)。leading edge サイズが並行トランザクション数に比例する以上
  (§5.2)、open-loop 到着や大量コネクション環境ではモデル前提が性能を直接規定する。

## Approach
- [paper] **TxDAG と leading edge**: 各サーバはコミット済み + prepared の履歴を
  TxDAG として保持。leading edge(LE)= コミット済みでコミット済み子を持たない
  ノード集合。定義上 LE の要素は多数決コミット済みなので、他サーバの LE を受け取った
  サーバは、そこに含まれる自分の prepared トランザクションを追加調整なしに即
  コミットできる (§1 [contribution], §3, Fig. 1, Fig. 2)。
- [paper] **合意フロー(two-phase, Alg. 1–3, §3.3.1)**:
  1. クライアントは任意のサーバに送信、受信サーバがそのトランザクションの
     coordinator になる。coordinator は自分の現在 LE をトランザクションの祖先として
     束縛し、ペイロード(Cypher クエリ)+ LE を PREPARE で全 RM(ローカル含む)に送る。
  2. participant は (a) 既知 TID なら現在の status と祖先を即返答、(b) 宣言された
     祖先が全てローカルで PREPARED/COMMITTED であることを検証(欠けていれば
     INCOMPATIBLE を返す)、(c) 受信 LE 中の PREPARED 祖先を追加調整なしにコミット
     (GC 用参照カウンタをインクリメント)、(d) ローカル DB で beginTx + prepare を
     試み、成功なら PREPARED として TxDAG に追加(コミットハンドルを保存)、失敗なら
     ABORTED (Alg. 2)。
  3. participant は qualifier = {tx | tx ∈ ローカル履歴 ∧ tx ∉ 受信 LE} を計算し、
     準備中トランザクションを qualifier のトランザクションにも接続して
     happened-before を明示化(coordinator と participant の committed state が同一なら
     qualifier は空)。PREPARED 応答に qualifier を自分の LE として載せて返す —
     この「qualified vote の双方向交換」が独立進化する TxDAG の安全な収束を保証する
     (§1 [contribution], §3)。
  4. coordinator は各 qualifier のトランザクションが自履歴に存在するかを検証
     (checkValidLeadingEdge。欠けていれば PREPARED を論理的に ABORT に変換)。
     supermajority(fast quorum)なら追加作業なし、単純多数なら第 2 フェーズへ、
     どちらも満たさない/自分が乖離しすぎなら ABORT (§3, Alg. 1)。
  5. commit フェーズ: coordinator は多数決合意済み祖先集合を付けた COMMIT を
     投票者だけでなく**全 RM** に送る。RM は PREPARED 状態を確認(祖先が
     coordinator の LE に含まれなければ catch-up を先に実行)し、DB commit 成功で
     durable 記録(WAL)、LE から祖先を除去して新トランザクションを追加、祖先の
     参照カウンタをデクリメント(LE 外のゼロカウントエントリは GC 可)(Alg. 3)。
     commit 応答が多数決に達しなければ HEURISTIC(プロトコル違反シグナル、ユーザ
     による調停を要し得る)(§3.3.1)。
- [paper] **Single-phase(fast path, §3.3.2)**: 故障・競合・乖離が少なければ
  ⌈3N/4⌉+1 の fast quorum で 1 往復決定しクライアントに即応答。RIOT は two-phase
  パスで競合トランザクションの並べ替え(reorder)をしない設計で、実行と回復が
  単純になる代わりに abort 率がやや上がる。その分 Fast Paxos(回復時 reorder 許容)
  より厳しい fast quorum を要求する (§3.3.2)。
- [paper] **ステータス体系 (§3.3)**: UNKNOWN / PREPARED / COMMITTED / ABORTED に加え、
  INCOMPATIBLE(遅延・stale な履歴での参加を明示的に弾く abort 種別)、
  HEURISTIC(多数決に反する outcome)、ABORTED_AFTER_REPLAY(回復中に失敗した
  トランザクションの再コミットによるコミット順改変を防ぐ)。ABORT/INCOMPATIBLE は
  エラーではなくプロトコルの基本要素で、恒久的乖離を防ぐ異議申し立て機構 (§3.4)。
  ローカル outcome とグローバル outcome の組合せは Table 1: local commit + global
  abort → abort、**local abort + global commit → 「潜在的乖離、他サーバからの回復を
  検討」** (Table 1, §3)。
- [paper] **abort と再試行 (§3.4)**: RM は LE 互換でもデッドロック等の DB 都合で
  local abort し得る(全サーバで一様に現れるとは限らない)が、最終 outcome は
  厳密に多数決。RIOT は自動再試行せず、INCOMPATIBLE/HEURISTIC を受けた
  クライアントが文脈に応じて再送を判断する。
- [paper] **catch-up (§3.5)**: 乖離は LE 不一致で検出 — (i) coordinator が未見コミットを
  含むリモート LE を受信、(ii) participant が未 prepare または祖先非互換の commit を
  受信。乖離サーバは自 LE をシャード内ピアに送り、解決可能なピアが「供給 LE +
  並行トランザクション + 双方の全子孫(自分の現 LE = TxDAG の葉まで)」の部分グラフを
  返す。乖離サーバは root→葉の BFS 順で適用。乖離が大きすぎる、または TxDAG の GC で
  ローカル解決不能なら、フルスナップショットコピーで追い付く。
- [paper] **coordinator 故障回復 (§3.6)**: 全サーバは自分の PREPARED 応答(LE メタ
  データ込み)の immutable コピーをトランザクション完了まで保持。coordinator 故障を
  疑ったサーバは RECOVER_PREPARED をシャード内の他の全サーバに送る(単独決定は不可、多数決 outcome が
  確定できるまで待つ)。受信側は当該トランザクションを prepare 済みなら元の PREPARED
  応答の写しを返し、未知なら ABORTED と応答してその事実を恒久記憶。可能な帰結は
  3 つ: ①既存の多数決 COMMITTED/ABORTED を学習、②互換 PREPARED の多数決が集まり
  COMMITTED を推定、③故障 coordinator 抜きでは互換多数決が組めないことが確定し
  ABORTED を推定。回復フェーズでは全サーバが独立に動き、新 coordinator は
  立てない。復帰した元 coordinator は PREPARED/ABORTED/COMMITTED(あるいは
  RECOVER_PREPARED)を誠実に処理し、遅れが大きければ catch-up を実行する。
- [paper] **マルチシャード (§3.7, Fig. 3)**: 2 層構成。受信サーバが primary
  coordinator となり、リモートシャードに interposed coordinator を任命して
  シャードローカルのプロキシとして機能させる(primary が全関与サーバと直接調整する
  必要を排除し、シャード間トラフィックを最小化)。**conjunction of majorities**:
  トランザクションは全シャードが commit に投票した場合のみ成功、ただし各シャード内は
  ローカル多数決だけでよい。マルチシャードコミットは全シャード一致を要求して
  atomicity を守る (§3.8)。リモートシャードのサーバは、interposed coordinator の
  故障を疑ったら RECOVER_PREPARED をローカルピアと発信元シャードのメンバー双方に
  送れる (§3.7)。
- [paper] **正しさ (§3.2, §3.8)**: 証明スケッチ — Lemma 1(多数決の交差により矛盾
  決定は不可能。fast quorum は全多数決と交差)、Lemma 2(相互互換な LE の
  down-closure はコミット済み集合として両サーバで等しい)、Lemma 3(prepare/PREPARED
  交換により祖先 = version vector 的前提条件が全サーバで一致し構造が決定的)。
  定理: 相互互換な LE を持つ 2 サーバの down-closure 上の誘導部分グラフは同一
  (対応はトランザクション ID 上の恒等写像)。互換性が確認できない場合は形状を
  非整合に拡張せず abort する。安全性・正しさは別作業の TLA+ で形式的に確立済み
  (ref [15]; 謝辞によれば Junhao Hu / Michael Cahill / Alan Fekete による形式モデル化)
  (§3.8, §8)。
- [paper] **アーキテクチャ (§4, Fig. 4)**: Neo4j の Raft 実装と同じ commit hook 経由で
  統合(Neo4j 内部の大改造を回避)。コンポーネントは Coordinator(Quorum Checker +
  LE Checker)、RM(Database + WAL。トランザクションメタデータをクラッシュ回復用に
  記録)、Topology Manager(クラスタメンバーシップ)、Suspicion Map(非互換 LE や
  未応答を記録。通常メッセージにピギーバックし、interposed coordinator の選択バイアスと
  catch-up 起動に利用)、Monitoring Manager(実験用メトリクス)。サーバ間通信は
  gRPC(ロードバランス・圧縮・keepalive 最適化)(§4.1, §4.2)。
- [paper] 実験のため Neo4j の Forseti lock manager を「競合時に即 abort」に小改造
  (競合生成の制御用。無改造 Neo4j には影響しない)(§4.1)。プロトタイプはクエリ
  プランナを持たないため、クライアントが対象シャードを明示する必要がある
  (RIOT ではなくプロトタイプの制約)(§4.2)。
- [inference] 旧ノートの疑問「可換性を誰がどう判定するか」への本文の回答: 明示的な
  可換性宣言や静的解析は無く、RIOT 層は LE 互換性(履歴の包含関係)のみを検査し、
  実データ上の競合検出は各レプリカの RM(ロック/MVCC)に委ねる分業である
  (§3.1 の可換性定義 + §4.1)。つまり「可換 = どのレプリカの RM でも競合しなかった」
  という操作的定義に近い。

## Evaluation
- Setup [paper]: AWS EC2 m5.2xlarge(8 vCPU / 32 GiB)クラスタ、Amazon Linux 2023
  (kernel 6.1)。ベースラインは Neo4j Enterprise v5.26 + 本番 Raft(Corretto JDK 17)、
  RIOT 統合版は virtual threads 利用のため OpenJDK 23 (§5.1)。公平性のため RIOT の
  fast path は**無効化**(有効なら最大 40% 性能向上、Raft の propose-notify モデルに
  合わせる措置)(§5.1)。データセットはメモリに完全収容(ディスク I/O ボトルネック
  排除)だが永続化は実施 (§5.1)。
- Workload [paper]: 合成書き込み負荷 MERGE (person:Person id: $id)。id に索引を作成し、
  同一ノードを繰り返しアクセスするクエリで競合を注入。競合率 0/5/10%(AuraDB 運用
  経験に基づく現実的な値)。クライアント数 1/10/50/100/500/1000、別マシンから
  closed-loop で発行。指標はスループット (tx/s) と p99 レイテンシ。DB 抜きで
  プロトコル単体を測る RIOT (NoDB) 構成も測定 (§5.1, §5.2)。
- 3 ノード(単一シャード、エンタープライズ Neo4j の常用構成)(Fig. 5, Fig. 6, §5.2):
  - AuraDB の大多数のインスタンスはクライアント接続 100 未満であり、その範囲で
    RIOT は Raft 比スループット +32〜250%、p99 最大 2.3× 低減(平均レイテンシは
    2.5× 低減)(§5.2)。
  - 500–1000 クライアントでは逆転: RIOT のスループットは Raft 比最大 25% 低下、
    テールレイテンシ最大 2.3× 悪化(平均は同等)。原因は高並行時(アクティブ
    トランザクション ≈ クライアントの 6 割)に交換される leading edge の肥大化 —
    現実装では LE サイズがアクティブ並行トランザクション数に線形に成長し、
    メッセージサイズと処理コストを押し上げる (§5.2)。緩和策として LE 圧縮や
    backpressure、実務ではミドル層のコネクションプーリングが並行度を抑え LE を
    小さく保つ、と論じる (§5.2)。
  - 競合 5–10% では競合率に比例して劣化するが、100 クライアントまでは
    スループット・レイテンシとも Neo4j を上回る (§5.2)。
- ネットワーク (Fig. 9, §5.2): クライアント ≤10 では Raft と同等のトラフィック。
  Raft はリーダーがフォロワーの約 6× のトラフィックを処理するのに対し RIOT は
  全ノード均等。10 クライアント超では増大し、大クライアント数で Raft の最大 13×
  (MB/s)。ただし本質的コストではなく LE 圧縮・並行度制御で削減可能と主張。
- 5 ノード (Fig. 7, Fig. 8, §5.2): ≤100 クライアントで約 +15〜240% スループット、
  平均・テールとも 2× 超低いレイテンシ。それ以降は 3 ノードより早く劣化 —
  サーバ追加は並行作業増による LE 肥大と、より大きな多数決の両面でトラフィックを
  増幅する (§5.2)。
- 故障時 (Fig. 10, §5.3): 3 ノード・100 クライアント・競合なしで 19 秒時点に故障を
  注入。Raft はリーダー停止で新リーダー選出とクライアント再バインドの 17 秒間、
  書き込み性能が急落。RIOT はランダムに選んだサーバを kill しても無停止で処理継続
  (耐故障余裕と処理能力は低下)。フリート全体で選出が日に 1.47–1.77 回起きる
  AuraDB の実態と併せ、可用性ジッタ源の除去を主張 (§5.3)。
- [inference] 評価がカバーしていないもの:
  - **マルチシャード性能が皆無**。§3.7 の interposed coordinator / conjunction of
    majorities は設計記述と Fig. 3 のみで、実験は全て単一シャード(3 ノード実験は
    明示的に「単一シャード」構成、§5.2)。reciprocal consistency を要するシャード跨ぎ
    エッジ更新という動機のワークロードそのものが未測定。
  - 比較対象は Neo4j Raft のみ。§6 で対置される EPaxos / CAESAR / Accord / Tapir 等の
    leaderless 系との直接比較なし。
  - ワークロードは単一パターンの合成書き込み(MERGE 1 種)のみ。読み取り性能・
    LDBC 等の標準グラフベンチマーク・トラバーサルを含む現実クエリは未評価
    (read-dominant が動機 §1 なのに read は測っていない)。
  - fast path(single-phase)は無効化されており「最大 40% 向上」(§5.1) の根拠データは
    提示されない。single-phase 変種の abort 率・quorum 到達率も不明。
  - 回復系(RECOVER_PREPARED のコスト、catch-up / フルスナップショットの所要時間、
    HEURISTIC の発生頻度)は未測定。故障実験は 1 台 kill の可用性観察のみ。
  - 競合率は最大 10%。逆転点探し(高競合で DAG 維持が逐次ログより高く付く領域)は
    行われていない。
- [inference] 数値表記の揺れ: abstract と §7 は「最大 2.5× スループット」、§5.2 本文は
  「32–250% higher」。「250% higher」を文字通り読めば 3.5× であり、著者は「250%
  higher = 2.5×」の意味で使っていると思われるが、本文からは確定できない。

## Limitations
- Stated [paper]:
  - LE サイズがアクティブ並行トランザクション数に線形成長し、高並行(500–1000
    クライアント)で Raft を下回る(スループット −25%、テール 2.3× 悪化)。実用化には
    LE 圧縮か backpressure が必要 (§5.2)。
  - ネットワークトラフィックが大クライアント数で Raft の最大 13× (Fig. 9, §5.2)。
  - サーバを増やすと LE 肥大 + 多数決サイズ増でむしろ劣化が早まる(5 ノード vs
    3 ノード)(§5.2)。
  - two-phase パスで競合トランザクションを reorder しないため abort 率が僅かに増える
    (代償として実行・回復が単純化、fast quorum は厳格化)(§3.3.2)。
  - commit 多数決不成立時の HEURISTIC はプロトコル違反シグナルであり、ユーザによる
    調停を要し得る (§3.3.1)。
  - 高競合を集中させる病的ワークロードは可能(ただしグラフでは非典型と主張。
    例外はノード削除のような本質的に広スコープの操作)(§3.4)。
  - プロトタイプ制約: クエリプランナ非搭載でクライアントがシャード指定 (§4.2)。
    実験用に Forseti lock manager を即 abort 化 (§4.1)。
- Inferred [inference]:
  - conjunction of majorities (§3.7) は「全シャードの commit 投票」を要求するため、
    シャード跨ぎトランザクションの可用性・レイテンシは最も遅い/不安定なシャードに
    律速される。シャード数を増やすほど全シャード一致の確率は下がるはずだが、
    シャード数に対する abort/レイテンシのスケーリングは論じられていない。
  - Table 1 の「local abort + global commit → 潜在的乖離、回復を検討」は、RM の
    非決定的挙動(デッドロック犠牲者選択等)が正常運転中でもレプリカ乖離と回復
    パスを誘発し得ることを意味する。この経路の発生頻度・回復コストは未評価。
  - TxDAG の GC(参照カウント、LE 外ゼロカウント回収)は catch-up と干渉する —
    GC 済みエントリが要るとフルスナップショットに退化する (§3.5)。GC の積極性と
    catch-up コストのトレードオフに関する指針がない。
  - fast quorum の floor/ceiling 表記の不整合(§3.1/§3.3.2 vs §3 冒頭の概観)。N=3 での
    fast path 成立性が本文からは判定できない(評価は fast path 無効なので露見しない)。
  - 各レプリカが同じ Cypher クエリを独立に実行する構成 (§3, §4.2) なので、クエリの
    非決定性(内部順序、時刻・乱数依存)があるとレプリカ状態が分岐し得る。決定性の
    要件・保証は本文で明示されていない。
  - HEURISTIC・INCOMPATIBLE をクライアントに返して再送判断を委ねる設計 (§3.4) は、
    exactly-once セマンティクスをクライアント側の TID 再利用規律に依存させる。
    再送時の TID の扱い(同一 TID 再送か新 TID か)は記述がない。

## Relations
- [[2026-sigmod-kettaneh-leader-leases.md]](CockroachDB の Leader Leases、同じ
  SIGMOD Companion '26): リーダーボトルネックへの対照的な 2 アプローチ。
  leader-leases がリーダー維持コスト(lease 更新・heartbeat)を failure detector の
  共有で削る「リーダー温存」路線なのに対し、RIOT はリーダーと全順序ログ自体を廃する。
  RIOT §5.3 の実測(選出 1.47–1.77 回/日、17 秒の書き込み急落)は leader-leases が
  解こうとする回復時間問題の定量的裏付けとしても読める。
- [[2026-cidr-zarkadas-rose.md]](Rosé: パーティション化 DB の柔軟レプリケーション):
  同じ「パーティション化/シャード化 DB のレプリケーション」問題圏で、Rosé は
  非同期 primary-backup に monotonic prefix consistency を与える弱一貫・低コスト側、
  RIOT はコンセンサスベースで serializability + reciprocal consistency を守る強一貫側。
  シャード跨ぎ書き込みの整合性(Rosé の cross-partition atomicity 問題と RIOT の
  reciprocal consistency)は同型の課題であり、一貫性/コストのスペクトラム上の対照。
- [[2026-sigmod-arkhangelskiy-aurora-limitless.md]](Aurora Limitless、シャード化
  クラウド OLTP): RIOT §2 が批判する「シャード跨ぎ 2PC + シャード内リーダー複製」
  (Spanner Graph 型)のアーキテクチャ系譜に属するシステムとして、conjunction of
  majorities(§3.7)との方式比較の素材になる。
- 本文中の直接の競合プロトコル(ノート未作成): EPaxos / CAESAR / Accord / Tapir /
  Janus / Basil (§1, §6)。特に Accord(依存 DAG を keyset 解析で構築)は RIOT の
  最近傍で、トランザクション粒度 vs キー粒度の DAG というトレードオフで対置される
  (§6)。

## Idea seeds
- [inference] **Leading edge 圧縮はそのまま研究テーマになる**: LE サイズ線形成長が
  唯一の主要スケーラビリティ障壁として本文自身が特定している (§5.2)。LE は「コミット
  済みフロンティア」なので、interval/watermark 表現や Bloom/Merkle 要約で対数〜定数
  サイズに落とせる可能性がある(要約化すると §3.2 の同一性証明がどこまで保てるかが
  核心)。第一実験: RIOT (NoDB) 相当のプロトコルハーネスを自作し、クライアント数 vs
  メッセージサイズ/スループット曲線を LE 表現(完全列挙 / delta / 要約)別に比較。
- [question] fast quorum の ⌈3n/4⌉+1 と ⌊3n/4⌋+1 の不整合はどちらが正しいのか。
  N=3(本文のエンタープライズ常用構成)で fast path は成立するのか。検証: 公開
  TLA+ 仕様(https://github.com/hyhjh211/TwoPhaseProtocol, ref [15])のクォーラム定義を
  読み、N=3,5 でモデル検査する。fast path 無効の評価 (§5.1) しかない現状、
  single-phase 変種の実効性自体が open。
- [inference] 「RM が最終 arbiter」という層分離 (§4.1) の一般性検証: §7 は他の
  トランザクショナル DB への統合が容易と主張するが、根拠は Neo4j 1 例。決定的
  実行系や MVCC 系 KV に RIOT を載せ、Accord 系(事前 keyset 解析)との交差点
  (keyset が静的に分かるワークロードではどちらが勝つか)を測る比較研究が考え
  られる (§6 のトレードオフ主張の実証)。第一歩: §6 の主張「粗粒度 DAG は可換性
  機会を犠牲にメタデータを削る」を、keyset 予測可能な YCSB 型負荷と動的トラバーサル
  負荷の 2 極で定量化。
- [question] Table 1 の「local abort + global commit → 潜在的乖離」は実運用でどの
  頻度で起き、回復コストはいくらか。RM のデッドロック犠牲者選択はレプリカ間で
  非決定的なはずで、正常時でも乖離→catch-up が回る。検証: Forseti 即 abort 改造
  (§4.1) を逆手に取り、デッドロック多発負荷で local/global outcome 不一致率と
  catch-up 起動回数を計測する再現実験。
- [inference] マルチシャード評価の欠落 (§5.2 は単一シャードのみ) は、本論文の動機
  (reciprocal consistency)に照らすと最大の未検証領域。シャード跨ぎエッジ比率
  (本文引用値: 約 30%、§2)を振りながら conjunction of majorities の abort 率・
  レイテンシがシャード数にどうスケールするかを測る実験は、Spanner Graph 型
  (2PC + シャード内リーダー)との正面比較として論文 1 本分の価値がある。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: 検証パスによる修正(Relations の「直接関係する既存ノート無し」は誤り —
  leader-leases ノート(consensus / replication)等が既存のため訂正)
- 2026-07-06: full-text 格上げ(status: abstract-only → read。手動取得した PDF 全文を読解し全節を執筆)
- 2026-07-06: 検証パスによる修正(⌊3n/4⌋+1 の出典位置を §3.3.1/Alg.1 → §3 冒頭の概観に訂正(2 箇所)、contribution の anchor §2 → §1、RECOVER_PREPARED の宛先を「シャード内の他の全サーバ」に精密化)
