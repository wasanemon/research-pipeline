---
title: "FUR: Fast and Unlimited Reads on Persistent Memory Transactions"
authors: [João Barreto, Daniel Castro, Paolo Romano, Alexandro Baldassin]
venue: "EuroSys '26 (21st European Conference on Computer Systems)"
year: 2026
ids: {doi: "10.1145/3767295.3769343", arxiv: "", dblp: "conf/eurosys/BarretoCRB26"}
urls: {paper: "https://doi.org/10.1145/3767295.3769343", pdf: "literature/pdfs/2026-eurosys-barreto-fur.pdf", code: "https://github.com/inesc-id/FUR"}
status: read
read_date: 2026-07-06
tags: [persistent-memory, htm, read-only-transactions, transaction-processing, snapshot-isolation, opacity, durability, redo-logging, ibm-power9, cxl]
---

## TL;DR
Persistent Memory (PM) 上の Persistent Hardware Transactions (PHT) で看過されてきた
Read-Only (RO) トランザクションの2大ボトルネック — ①並行 update の永続化完了を待つ
post-commit の durability wait、②商用 HTM の read capacity 制限 — を、HTM の
「アクセストラッキング suspend/resume 命令」を軸に両方排除する設計 FUR。
RO は HTM の外で計装ゼロで実行し(read 無制限)、durability wait は「自分の開始前に
HTM コミット済みの update」だけに刈り込む (pruned RO durability wait)。update 側に
新たに課される isolation wait の待ち時間には redo log flush と論理 durTS 取得を重畳し、
durMarker の全順序要求を部分順序に緩めて相殺する。IBM POWER9 + TPC-C で、
SPHT / Pisces / SpecPMT をピークスループットで最大 3.68× / 3.99× / 6.17× 上回る
(§1)。例外は 100% update の小 footprint ワークロード(payment)で、SpecPMT が
FUR 最良変種を 1.31× 上回る (§4.3)。

## Problem & motivation
- [paper] CXL の登場で高容量・高スループット PM への移行が進行中。CXL 2.0 で最初の
  商用 PM デバイスが開発中、近い将来 CXL 3.0 ベースの disaggregated PM が現実になる (§1)。
- [paper] HTM は低い同期オーバーヘッドから PM 上の並行トランザクション処理に魅力的
  だが、既存 HTM 実装はコミット済みトランザクションの更新を揮発 CPU キャッシュから
  PM へ atomically に転写することを保証しない。PHT 提案群は市販 HTM をソフトウェア
  機構で拡張してクラッシュ一貫性を確保する (§1)。
- [paper] RO トランザクションは多くの実世界ワークロードで支配的であり、PHT 設計は
  その性能を優先すべき。しかし PHT の state of the art は update のスケーラビリティ改善
  (SPHT)に注力し、RO の低性能をほぼ看過してきた (§1, §2.3)。
- [paper] 動機実験 (Fig. 1): POWER9 32 コア上で、可変数スレッドが TPC-C orderstatus
  (RO)を実行し、1 スレッドが payment (update) を回し続ける。観測は3点:
  ① HTM は容量が足りる限り(〜32 スレッド)STM より速い。② 容量が落ちる
  (SMT 同居でスレッドあたり容量が約半減する)と read set が HTM に収まらず、
  capacity abort の thrashing と Single Global Lock (SGL) fallback に陥る。③ HTM
  フレンドリーな領域でも SPHT はかなりのオーバーヘッドを課し STM (Pisces) 以下に
  なる (§1, Fig. 1)。
- [paper] ③の原因が RO durability wait: クラッシュ一貫性のため、実行を終えた RO
  トランザクション R は「R が観測した可能性のある write が全て durable になる」まで
  アプリケーションに戻れない。SPHT では R より前 or 並行に実行した update 全ての
  永続化(or abort)を待つ (§1, §2.3)。この RO durability wait に取り組んだ先行 PHT は
  著者らの知る限り無い (§2.3)。
- [paper] §2.4 予備実験(第一の貢献): SPHT + SI-HTM の素朴な結合(unlimited reads と
  durability の直接結合)は prohibitive。95% orderstatus + 5% payment、warehouse 分離・
  SMT 無効の設定で、SPHT+SI-HTM は SPHT よりかなり低スループット。RO の
  durability wait が SPHT 比最大 7× に伸びる — isolation wait の注入で update の HTM
  コミットが遅くなり、それを待つ RO の durability wait も伸びるカスケード効果。update
  側も isolation wait + 延びた durability ルーチンで強くペナルティを受ける (§2.4, Fig. 4)。

## System model & assumptions
- [paper] HTM モデル: 市販 HTM(Intel / ARM / IBM)は per-core キャッシュでアクセスを
  追跡するため、①footprint がトランザクショナルキャッシュ容量を超えると abort
  (SGL fallback 頼み)、②コミット時に更新が PM へ atomically flush されない、という
  2つの根本制限を持つ (§2.1)。
- [paper] suspend/resume 命令の前提: IBM POWER が最もリッチな命令群を提供
  (トランザクション中の任意時点で任意アクセスの追跡を suspend/resume 可能。
  load のみの全期間 suspend は htmBegin のフラグで指定でき、この種のトランザクションは
  Rollback-Only Transactions (ROT) と呼ばれる)。Intel TSX 最新版は load 追跡の
  suspend のみ(XSUSLDTRK / XRESLDTRK)。ARM TME は追跡制御が一切不可 (§2.1)。
  FUR 本体は POWER の最リッチセットを前提とし (§2.1)、update の durability 最適化
  (§3.2.2, §3.2.3)は any-access tracking suspension に本質的に依存する (§5)。
- [paper] suspended mode の挙動仮定: suspend 前にトランザクションが触れていない
  cache line に限り、suspended window 内で untracked write と(無効化を伴わない)
  write-back が許される。これは IBM POWER の挙動 (§3.2.2)。
- [paper] 永続性ドメイン: ADR(CPU キャッシュは揮発)を対象。eADR のような
  より強いドメインは対象外(PM 文献の大半と同じ立場)(§2.3, §5)。
- [paper] 正しさ基準: FUR は opacity と(より弱い)Snapshot Isolation (SI) の両方を
  サポートし、working process 起動時の引数で選択する。トレードオフ: opacity では
  RO のみ unlimited reads、SI では全トランザクションが unlimited reads (§1, §3)。
- [paper] SI 選択時のワークロード仮定: 評価の TPC-C は SI の一貫性アノマリー
  (write skew 等)を起こさない B-tree 実装を使う (§4.1)。[inference] つまり FUR-SI の
  正しさはアプリケーションが SI 安全であることに依存し、この検証責任はユーザ側にある。
- [paper] クロック仮定: pruned durability wait は完全同期したハードウェアタイムスタンプ
  カウンタを仮定(先行研究同様、クロック間の最大偏差オフセットを考慮した一般化が
  可能)(§3.2.1)。
- [paper] アーキテクチャ: working process(並列ワーカースレッドがアプリを実行)と
  log replayer (LR) の2プロセス構成。PM 上のデータファイルを mmap private(CoW)で
  マップし、変更ページを DRAM に透過複製した volatile snapshot 上でトランザクションを
  実行。redo log 用にもう1つの persistent heap を shared mode でマップし、OS ページ
  キャッシュをバイパスして PM に直接伝播 (§3)。LR は復旧時に起動するほか、通常処理中も
  background(ログ剪定)または同期的(ログ容量枯渇時)に実行される (§3)。
- [paper] 実行環境の制約: POWER9 では HTM は VM 内からのみ使用可能で、suspend/resume
  命令は KVM ハイパーバイザへの trap でソフトウェア実装される。両命令を連続実行する
  コストは 1 スレッドで 350ns、64 スレッドで 1500ns (§4.1)。
- [paper] 故障モデル: システムクラッシュ後、durable な redo log を replay して persistent
  heap を再構築 (§2.3, §3)。htmCommit 後の memory fence により、durMarker は必ず
  redo log エントリより後に永続化される — fence 完了前のクラッシュなら当該
  トランザクションの redo エントリは一切 replay されない (§3.2.2, Alg. 1 ln.36)。

## Approach
### 背景となる2つの構成要素
- [paper] SI-HTM [Filipe+ PPoPP'19]: update トランザクションを load 追跡なしで実行
  (read 無制限)、RO はトランザクショナルコンテキスト外で実行(HTM オーバーヘッド
  ゼロ)。孤立性は isolation wait で守る: update は CommitTx 到達時に、その時点で
  active な全並行トランザクションが active でなくなるまで待ってから HTM コミット。
  これにより Property 1「並行する2トランザクションは互いの write を読めない」が
  成立し、SI が保証される (§2.2, Fig. 2)。opacity が欲しければ update を full HTM で
  走らせる(ただし update の unlimited reads は失われる)(§2.2)。
- [paper] SPHT 系 PHT の共通バックボーン: CoW volatile snapshot 上で実行、write は
  per-thread redo log(PM 上)に記録、HTM コミット直前に物理タイムスタンプ durTS を
  取得(HTM 内で取得するため durTS 順序は HTM の serialization 順と一貫)。コミット後、
  redo log を flush し、durability wait(自分より小さい durTS を持つ全トランザクションの
  永続化/abort を待つ)を経て durMarker を flush して初めて durable になる (§2.3, Fig. 3)。
  スレッドは開始時に保守的に低い durTS を置くため、durability wait は「write を観測して
  いない後発/abort するトランザクション」まで偽って待つことがある (§2.3, Fig. 3 の W4/W5)。
  RO は redo log / durMarker の flush は不要だが durability wait は必要 (§2.3)。

### FUR の3つの新規技法
- [paper] **① Pruned RO durability wait (§3.2.1)**: Property 1 の系として、R は自分と
  並行に実行した update から読むことは決してない。従って durability wait を「R の開始
  時点で未 HTM コミットのトランザクションを全てバイパスする」形に刈り込める。
  DurabilityWait ルーチンは全スレッドの state を走査し、「non-durable 状態かつその
  タイムスタンプが自分の beginTime より小さい」スレッドだけ spin-wait する
  (Alg. 1 ln.45–49)。刈り込み後の待ち対象は「先にコミット済み」のものだけなので、
  R が durability wait に入る頃には既に durable である可能性が高く、待ちは実質消える
  (§3.2.1, Fig. 5)。さらに state を2配列に分解(active か否か / non-durable か否か)し、
  DurabilityWait は update しか書かない第2配列だけを走査することで、RO 支配的
  ワークロードでのキャッシュ無効化 thrashing を防ぎ、大半の read を L1 から供給 (§3.2.1)。
- [paper] **② Opportunistic redo log flushing (§3.2.2)**: isolation wait は suspended mode で
  実行されるので、この窓を使って redo log の flush を前倒しする。HTM 内で書いた
  redo エントリは write-set の一部で suspended mode でも flush できないため、実行中は
  volatile redo log(実際にはアドレスのみ格納)に書き、suspended window で persistent
  redo log にコピーしてそちらを flush する。flush 命令は非同期発行し、CPU が背景で
  flush する間に isolation wait を進める — flush レイテンシは isolation wait に隠蔽される
  (§3.2.2)。htmCommit 後の memfence (Alg. 1 ln.36) が redo エントリ → durMarker の
  永続化順序を保証する (§3.2.2)。
- [paper] **③ Partially-ordered durability markers (§3.2.3)**: update も RO と同じ pruned
  durability wait を行い、その後すぐ durMarker を flush できる (Alg. 1 ln.37–38)。従来
  PHT が前提としてきた durMarker の全順序を、軽量な部分順序に緩める — 並行
  トランザクション {W2,W3,W4} の durMarker は任意の順序で flush してよく、読んだ
  可能性のある先行者(W1)の後でだけ順序付けられればよい。SPHT の複雑な group
  commit 的協調はこの段階では不要になる (§3.2.3, Fig. 5)。正しさは Property 1 の系:
  durability wait を終えた update T は「T が読んだ可能性のある全トランザクションが
  既に durable」なので安全に durable になれる。クラッシュで並行 update の任意の部分
  集合だけが durable になっても、失われた並行トランザクションの write を生き残った
  durable トランザクションが読んでいることはあり得ない (§3.2.3)。
- [paper] durTS は物理でなく**論理**タイムスタンプ: suspended window 内から
  atomicInc(globalOrderTs) で取得 (Alg. 1 ln.31)。atomic increment は HTM に追跡され
  ないので conflict を作らず、そのレイテンシも(通常より長い)isolation wait に重畳
  される。グローバルクロックをトランザクショナル load/store で増分する既知の
  スケーラビリティ問題を回避 (§3.2.3)。

### 実行フロー (Alg. 1, §3.1)
- [paper] スレッドごとの state(inactive / active / non-durable + 物理タイムスタンプ)を
  共有配列で公開。RO: BeginTxReadOnly は state を active にするだけで HTM を開始
  しない。CommitTx では state を inactive にして DurabilityWait を呼ぶだけ (ln.14–18,
  24–25)。write ルーチンの呼び出しは RO には禁止(assertion で強制可能)だが、私的
  揮発領域への store は可 (§3.1)。
- [paper] update: SI 構成なら htmBegin(noLoadTracking)、opacity 構成なら
  htmBegin(trackAnyAccess) (ln.10–13)。CommitTx では: any-access tracking を suspend
  (ln.27) → inactive を公開 (ln.28) → 【suspended window 内で】volatile redo log を
  persistent log にコピーして非同期 flush (ln.30) → atomicInc で durTS 取得 (ln.31) →
  IsolationWait (ln.32) → non-durable 状態を公開 (ln.33) → tracking を resume (ln.34) →
  htmCommit (ln.35) → memfence → DurabilityWait → durMarker flush (ln.36–38)。
  SI-HTM が isolation wait の前に1回だけ状態遷移したのに対し FUR は wait 後にもう
  1回必要なので、suspended window を両遷移をカバーするよう引き伸ばす(2回
  suspend/resume するより効率的なことを実証済みと主張)(§3.1)。
- [paper] IsolationWait では state のタイムスタンプにより「同じスレッドがまだ同じ
  トランザクションを実行中」か「前のを終えて新しいの(より大きいタイムスタンプ)を
  開始した」かを曖昧性なく判別する (§3.1)。

### Log replayer (§3.3)
- [paper] 従来 PHT の LR は次に replay すべきトランザクションを見つけるため全 per-thread
  log を走査する必要があり、既知のボトルネック。唯一の回避策 SPHT の log linking は
  全順序 durMarker に依存し FUR とは非互換 (§3.3)。
- [paper] FUR は global な circular durMarker array を使う: 論理 durTS が配列インデックスを
  兼ね、durTS を取得したトランザクションが対応エントリのオーナーになる。エントリは
  redo log の開始アドレス・エントリ数・durTS を含む。LR は配列を順に辿って各 redo log を
  逐次 replay するだけ。バッチ replay 後に tail を進めてエントリを解放。配列サイズが
  「replay 前に durable になれる update 数」の上限を決める (§3.3)。
- [paper] 穴 (hole) の処理: durTS 取得後に abort したトランザクションは abort handler で
  abort marker を(非同期に)該当エントリへ書いて穴を塞ぐ (Alg. 1 ln.50–53)。クラッシュ
  起因の unmarked hole は null エントリ or 期限切れ durTS(circular array の前世代)で
  検出できる。最後の有効 durMarker より前に unmarked hole は最大 n−1 個しか存在し得ない
  ことが示せるので、LR は n 個の unmarked hole を見たら停止してよい (§3.3, p.8–9)。

## Evaluation
- Setup [paper]: dual-socket IBM POWER9(DD2.3、2.3–3.8GHz、1TB DRAM、CPU あたり
  16 コア + SMT)。POWER9 の HTM は VM からのみ使えるため QEMU/KVM VM
  (64 仮想コア = 32 物理コア × SMT 2、8GB DRAM)で実行。suspend/resume は KVM
  trap のソフト実装で、連続実行 350ns(1 スレッド)〜1500ns(64 スレッド)。PM は
  POWER 向けに存在しないため、CXL 接続の Optane 風 PM の write レイテンシを
  「cache line flush ごとに 310ns の spin loop 注入」でエミュレート(文献値ベース、
  先行研究と同様の手法)(§4.1)。
- 比較対象 [paper]: FUR-opa / FUR-SI(C ライブラリとしてフル実装、read/write 計装は
  手動)、SPHT(forward log linking 有効のフル版)、Pisces(reader 最適化 PSTM、
  durable SI)、SpecPMT の speculative logging + TinySTM(durably opaque PSTM。
  SpecPMT 単体は durability のみで isolation は別途 CC が必要)、参考値として素の
  HTM + SGL fallback。全て共通フレームワークで実装。非同期 log replay 対応の系
  (FUR / SPHT)は処理中 LR を無効化(先行研究と整合)。HTM 系は 10 リトライで
  SGL へ。結果は 5 秒 × 3 回の平均 (§4.1)。ソースコードは公開
  (https://github.com/inesc-id/FUR) (§4.1)。
- ワークロード [paper]: TPC-C フル実装(SI アノマリーを起こさない B-tree)+
  red-black tree の IntSet(要素 10K、TM 文献の定番)。STAMP は「begin 時点で RO と
  分かるトランザクションが無い」ため除外 (§4.1)。footprint は Table 1: stocklevel
  read 平均 122K / write 無し、orderstatus 650 / 無し、delivery 86K / 30、payment 97 / 5、
  neworder 7.5K / 141、RBT lookup 28、insert/remove 44 / 6。
- **RO ワークロード (§4.2, Fig. 6)**:
  - stocklevel(read 122K)は full HTM では常に capacity abort → SPHT / HTM は壊滅。
    FUR の RO は HTM 外で走るので 64 スレッドまでスケールし、64 スレッドで
    Pisces 比 18%、SpecPMT 比 84% 上回る(PSTM は read ごとに lock table 参照の
    ソフトウェア計装が入るのに対し FUR は read 計装ゼロ)(§4.2)。
  - orderstatus(read 650)は 32 スレッドまでは per-core キャッシュに収まり unlimited
    reads の出番は無いが、それでも htmBegin/htmCommit を発行しない分 FUR が
    SPHT/HTM に 30% 勝つ。32 スレッド超は SMT 同居で容量半減し stocklevel と
    同じ傾向に (§4.2)。
- **Update-only ワークロード (§4.3, Fig. 7)**: 下段プロットは commit したトランザク
  ションの各 durability ステップのオーバーヘッドを「plain execution 時間比 %」で表示。
  - payment(小 footprint、capacity abort 無視可能)は FUR の worst case: unlimited
    reads の利得ゼロで isolation wait のコストだけ目立つ。SpecPMT が FUR 最良変種を
    ピークで 1.31× 上回る(update 特化の logging と TinySTM のスケーラビリティ)。
    それでも FUR-opa / FUR-SI は SPHT に平均 15% / 13% 勝つ。SPHT の durability
    オーバーヘッドは 8 スレッド超で急増し 64 スレッドで plain execution の約 150×
    (主因は durability wait)。FUR の durability オーバーヘッドは 64 スレッドで SPHT の
    最大 1/5。ピーク(8 スレッド)での redo log flush オーバーヘッドは FUR 1% vs
    SPHT 55%、durability wait は FUR 60–76% vs SPHT 174% (§4.3, Fig. 7)。
  - FUR-opa は abort 率が高いのに FUR-SI より高スループット: 早期に conflict を検出する
    ため rolled-back トランザクションに費やす時間が大幅に少ない(abort コード分析は
    extended technical report [4] 参照)。高競合・小トランザクションでは FUR-opa が
    優位かもしれないと示唆 (§4.3)。Pisces は update 支配では最下位の永続系 (§4.3)。
  - delivery(read 86K + write 30)は capacity abort 地獄: 1 スレッドでも full HTM で
    update を走らせる系(FUR-opa / SPHT / HTM)は abort 率 81%。FUR-SI は update
    にも unlimited reads を与えるため capacity abort が大幅に減り(それでも write
    capacity で約半分 abort)、劇的なスループット差で isolation wait のコストを隠す。
    Pisces / SpecPMT は 12 スレッドまでは full-HTM 系に勝つが、計装コストで FUR-SI
    には大差で負ける (§4.3)。neworder は payment と同様の観測になるため省略 (§4.3)。
- **Mixed ワークロード (§4.4, Fig. 8)**:
  - Read-dominated(85% RO = stocklevel/orderstatus 均等、15% update): SPHT の RO は
    durability wait に plain execution の最大約 10× を費やす。FUR の pruned wait は
    実質コストゼロ(典型呼び出しは L1 上の state 配列を見て待ち対象なしと判明)。
    副作用として、少数の update が多数の RO を isolation wait で待つため、FUR の
    update 単体のオーバーヘッドは SPHT より高くなるが、全体スループットでは勝つ。
    Pisces は 8 スレッドまで FUR に追随。SpecPMT は 28 スレッドまでは Pisces や
    FUR-opa よりスケールするがそれ以上は伸びず、FUR は伸びる (§4.4)。
  - Update-dominated(TPC-C 標準ミックス: 85% が payment/neworder、RO は 10%、
    capacity abort を起こしやすい型は 15%): FUR に不利な設定だが FUR-SI が最も
    競争力がある。要因は payment/neworder に対する §4.3 と同じ + RO durability wait の
    節約。FUR-SI > FUR-opa の決め手は capacity abort の少なさ (§4.4)。
  - 技法別の寄与: read-dominated では pruned durability wait が支配的。update-dominated
    では opportunistic log flushing と partially-ordered durMarkers が共に高い効果、絶対
    削減量は後者が最大(Fig. 8 のオーバーヘッド内訳で確認)(§4.4)。
  - Red-black tree(update 1% / 10% / 50%、Fig. 9): 木が浅く capacity abort は無視可能
    なので unlimited reads の利得はここでは非評価。FUR 両変種は3ワークロードとも
    同等のピークで、全永続ベースラインよりかなり上。STM の計装オーバーヘッドは
    低スレッド数で顕著。SPHT は durability wait のせいで STM 系と同程度 (§4.4, Fig. 9)。
- **Log replay (§4.5, Fig. 10)**: SPHT 論文と同じ方法論。100% update の合成アプリ
  (書き込み 1–20 個一様ランダム、log と heap 各 128MB)でログを充填後、停止して
  シングルスレッド LR(重複 write フィルタ無効)で replay スループットを測定。従来
  PHT(cc-HTM / DudeTM / NV-HTM)の LR はワーカースレッド数増で per-thread log
  走査がボトルネック化して劣化。SPHT(log linking)と FUR(global durMarker array)は
  同等の性能で、高スレッド数でも効率を維持 (§4.5, Fig. 10)。
- [inference] 評価がカバーしていないもの:
  - 実 PM デバイスでの測定が無い(flush ごとに 310ns spin 注入のエミュレーションのみ、
    §4.1)。PM の read レイテンシは模擬されないが、実行は DRAM 上の CoW snapshot な
    ので設計上 read が PM に当たるのは復旧/replay 経路に限られるはず。
  - suspend/resume が KVM trap のソフト実装(350–1500ns)である環境での結果のみ。
    ハードウェア実装ならさらに有利になる可能性がある一方、trap の無い環境(ベアメタル
    POWER8 等)での検証は無い。
  - スループット実験は LR を無効化して測定 (§4.1)。LR が background で並走する
    定常状態での干渉(PM 帯域・durMarker array の tail 進行)は測られていない。
    durMarker circular array のサイズと同期 replay 発動(ログ容量枯渇時, §3)の頻度の
    関係も未評価。
  - スケールは 64 SMT スレッド(32 物理コア)まで。isolation wait / durability wait は
    全スレッド state の O(N) 走査なので、より大きいコア数での挙動は外挿できない。
  - FUR-SI の正しさ前提(SI 安全なワークロード)を破るアプリケーションでの
    opacity 変種とのコスト比較は TPC-C(SI 安全な B-tree)と RBT のみで、write skew を
    含むワークロードでの FUR-opa の実用性は別問題として残る。

## Limitations
- Stated [paper]:
  - HTM の write capacity 制限は回避しない — 大きな write footprint には不向き (§5)。
    実際 delivery では FUR-SI でも write capacity で約半数が abort (§4.3)。
  - FUR-opa では、beginTx で明示的に RO とフラグされたトランザクションだけが
    unlimited reads を得る。レガシープログラムでは問題になり得る(FUR-SI は透過的)(§5)。
  - Intel TSX 最新世代とは非互換(load 追跡の suspend しか無く、update の durability
    最適化は any-access suspension に本質依存)。RO を利する部分(unlimited reads +
    pruned durability wait)は「isolation wait を RO の state だけ走査する」形に適応可能
    だが、実機 TSX での設計・性能トレードオフの検証は future work (§5)。
  - suspend/resume の HTM サポートはキャッシュコヒーレンスプロトコルの複雑性と
    コストを上げることが既知で、ハードウェアメーカーの採用はソフトウェア側の需要
    次第という共進化問題がある(本論文はその需要の証拠を提供すると位置づけ)(§5)。
  - エミュレートした persist レイテンシ(+310ns)は将来の CXL ベース PM(NAND
    ベースの memory-semantic デバイスは persist 推定 600ns)を過小評価している可能性。
    ただしレイテンシが高いほど pruned RO durability wait の隠蔽効果が効くので FUR には
    有利方向。他レイテンシの探索は future work (§5)。
  - ADR ドメイン前提。eADR(キャッシュも永続ドメイン)は対象外 (§5)。
- Inferred [inference]:
  - 可搬性の崖: FUR フルセットが動く商用 HTM は現状 IBM POWER 系のみで、その
    POWER9 ですら HTM は VM + KVM trap 経由でしか使えない (§4.1)。ARM TME は
    追跡制御ゼロ (§2.1)。「一部の現代 HTM の高度命令」という abstract の表現より、
    実際の依存先はかなり狭い。
  - isolation wait は「その時点で active な全トランザクションの完了」を待つため、
    長い RO が1本でも走っていると update のコミットがその RO の長さに律速される。
    read-dominated mix で update オーバーヘッドが SPHT 超えになった観測 (§4.4) は
    その兆候で、stocklevel 級の長大 RO が常時複数走る HTAP 的な状況では update
    レイテンシのテールが大きく伸びるはず(論文はスループットのみ報告し、この状況の
    レイテンシ分布は示していない)。
  - 論理 durTS + circular durMarker array は「グローバル atomic counter への increment」を
    全 update のコミットパスに置く。isolation wait に隠蔽されるとはいえ、コア数が
    増えれば cache line 競合そのものは残る。64 スレッド超での globalOrderTs の
    スケーラビリティは未検証。
  - abort marker の書き込みは非同期 (Alg. 1 ln.53) なので、durTS 取得後に abort した
    スレッドがマーカー書き込み前に長時間止まる(スケジューリング等)と、LR の
    replay 進行(tail 前進)がその穴で塞がれ、durMarker array 枯渇 → 同期 replay 停止に
    つながり得る。この back-pressure 経路の挙動は論じられていない。
  - extended technical report は執筆時点で匿名参照 [4](公開後に開示予定)で、abort
    コード分析等の詳細は本文からは検証できない。

## Relations
- 競合 baseline(本文 §4): SPHT [FAST'21](PHT・log linking)、Pisces [ATC'19]
  (reader 最適化 PSTM・durable SI)、SpecPMT [ASPLOS'23] + TinySTM。構成要素と
  して SI-HTM [PPoPP'19] の isolation wait と suspend/resume 活用を継承・改築 (§2.2, §3)。
- [[2026-eurosys-lopes-pim-txn.md]](PIM-TIDE): 同じ EuroSys '26、かつ著者が重複
  (Daniel Castro / Paolo Romano は両論文の共著者。PDF p.1 の著者ブロックで確認)。
  同一グループ(INESC-ID)が「新奇メモリハードウェア上のトランザクション実行」を
  PIM(UPMEM)と PM+HTM の両面から攻めている構図。あちらは決定的実行で DPU 間
  協調を回避、こちらは suspend/resume で HTM の追跡を選択的に無効化 — 「ハードウェア
  機構の制約を悲観的に受け入れず、実行を制約側に合わせて変形する」共通スタイル。
- [[2026-arxiv-egorov-flintkv.md]](NVM スキップリスト): 同じ PM/NVM 永続化領域
  だが、FUR はトランザクション実行層(汎用 TM ライブラリ、§4.1)、FlintKV は
  データ構造層でレイヤが異なる、という旧ノートの見立ては本文で確認できた。FUR の
  redo log + CoW snapshot 方式は index 構造非依存。
- [[2026-edbt-lee-cxl-pools.md]] / [[2026-edbt-krause-disaggregated-survey.md]]: FUR の
  動機は CXL 2.0 商用 PM デバイスと CXL 3.0 disaggregated PM の到来 (§1) であり、
  §5 は memory-semantic CXL デバイス(persist 約 600ns)への感度まで論じる。実機
  CXL プール(揮発)を評価した lee-cxl-pools、disaggregated memory を体系化する
  krause サーベイと「CXL メモリ階層で DB/トランザクション処理をどう作り直すか」
  という軸で接続する。FUR は同軸の「永続 CXL メモリ + 単一マシン TM」側の点。
- 注意(旧ノートから引き継ぎ): 本文の比較対象 "Pisces"(PSTM, ATC'19)は既存ノート
  [[2026-pvldb-weng-pisco.md]](分離バグ縮約フレームワーク Pisco)とは**無関係の
  別システム**。名前が酷似しているため検索・参照時に混同しないこと。

## Idea seeds
- [inference] **Pruned durability wait の原理は HTM 固有ではない。** 核は「SI 型の隔離
  (Property 1)下では、reader は並行 writer の書き込みを観測し得ないので、RO の
  commit 前 durability 待ちは『自分の開始前にコミット済みの write の永続化』まで
  刈り込める」という論理で (§3.2.1)、これは WAL ベース DBMS の group commit 待ちや
  レプリケーション下の read-only レプリカの「安全に返せる読み」の議論にそのまま
  移植できそうに見える。最初の検証: スナップショット読みを行う WAL ストレージ
  エンジンで、RO クエリの応答条件を「全先行 txn durable」から「begin 時点でコミット
  済みの txn のみ durable」に緩めた場合のレイテンシ差をモデル化・測定する。
- [inference] **「協調待ちの窓に永続化 I/O を重畳する」パターンの一般化。** FUR は
  isolation wait という強制待ち時間を redo log flush と durTS 取得の隠蔽に使った
  (§3.2.2, §3.2.3)。DBMS 側にも commit 順序決定と WAL flush の重畳(early lock
  release、async commit)という近縁があり、「どの待ちに、どの永続化ステップを、
  どの順序保証を壊さずに重ねられるか」を系統立てる設計空間整理は Phase 2 の
  課題候補になり得る。まず FUR / SPHT / 主要 DBMS の commit パスを共通の
  タイムライン記法で並べる作業から。
- [question] 旧ノートの疑問「suspend/resume を提供する HTM はどの程度あるか」は
  本文で解決: フル機能は IBM POWER のみ、Intel TSX は load のみ、ARM TME は無し
  (§2.1)。ただし著者ら自身が「Intel の load 追跡 suspend 導入の流れを any-access に
  一般化すべき」という HW/SW co-design の提言を出している (§1, §5)。では逆に、
  any-access suspension が無い環境で FUR の RO 側サブセット(§5 の TSX 適応案:
  isolation wait を RO state の走査に限定)だけでどこまで利得が残るか — 公開コード
  (github.com/inesc-id/FUR)ベースで isolation wait の走査対象を切り替えるだけなら
  検証コストは低い。
- [question] 旧ノートの疑問「100% update で FUR は同等か劣化か」も解決: 小 footprint の
  payment では SpecPMT に 1.31× 負けるが SPHT には 13–15% 勝つ。read footprint の
  大きい update-only(delivery)ではむしろ FUR-SI が最良 (§4.3)。残る開きは「update の
  レイテンシ分布」: read-dominated mix では update 単体のオーバーヘッドが SPHT より
  悪化する (§4.4) ので、長大 RO と update が混在する HTAP 風ワークロードで update
  テールレイテンシがどう壊れるかは公開コードで測定可能な未踏の穴。
- [inference] 論理 durTS を index にした circular durMarker array + abort marker による
  穴埋め (§3.3) は、並列 WAL / パイプライン化された commit ログの「ticket 方式 +
  hole 許容 replay」の単一マシン版と見なせる。分散ログ(例: 既存ノート群の複製系)
  との構造比較で「hole の検出可能性(null / epoch 期限切れ)を何が保証するか」を
  切り出すと、単一マシン PM と分散ログの設計原理の対応表が作れそう。まずは
  本ノートと [[2026-cidr-zarkadas-rose.md]] 等の複製ノートの replay 節を突き合わせる
  机上比較から。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: full-text 格上げ(status: abstract-only → read。手動取得した PDF 全文を読解し全節を執筆)
