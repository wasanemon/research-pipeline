---
title: "Lockify: Understanding Linux Distributed Lock Management Overheads in Shared Storage"
authors: [Taeyoung Park, Yunjae Jo, Daegyu Han, Beomseok Nam, Jaehyun Hwang]
venue: "FAST '26 (24th USENIX Conference on File and Storage Technologies)"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/fast/ParkJHNH26"}
urls: {paper: "https://www.usenix.org/conference/fast26/presentation/park", pdf: "literature/pdfs/2026-fast-park-lockify.pdf", code: "https://github.com/skku-syslab/lockify"}
status: read
read_date: 2026-07-06
tags: [distributed-lock-manager, shared-disk-filesystem, gfs2, ocfs2, nvme-of, locking, storage-disaggregation, metadata-performance, linux-kernel]
---

## TL;DR
共有ディスクファイルシステム(GFS2 / OCFS2)を支える Linux カーネル DLM は、
ファイル・ディレクトリ「作成」時のロック取得が、ロック競合が無くてもクライアント数と
ともに劣化する(5 クライアント・単一アクティブでスループット最大 86% 低下、
レイテンシの 47% が DLM 操作 = 主に directory node との通信)。Lockify の洞察は
「新規オブジェクトには所有者がまだ居ないので、作成ノードが自分を owner と宣言できる」
こと。self-owner notification(問い合わせず通知)と wait-list による非同期所有権管理で
directory node との往復待ちをクリティカルパスから外す。Linux kernel 6.6.23 に実装し、
カーネル DLM 比で最大 ~6.4× のスループット向上、エミュレートした RDMA ベース DLM の
87–88% の性能を専用ハードウェア無しで達成と主張。

## Problem & motivation
- [paper] NVMe-oF 等によるストレージ分離がクラウドで普及し、複数クライアントが
  共有ストレージへ同時アクセスするために GFS2 / OCFS2 / VMFS のような共有ディスク
  ファイルシステム + DLM が配備される (§1)。
- [paper] 分散ロックは高競合下で性能を落とすため、競合が管理されたシナリオ
  (例: HA 構成では通常運用時 primary のみがロックを要求)で使われるのが典型。
  先行研究の報告では 76.1%–97.1% のファイルは複数クライアントから滅多に
  アクセスされない (§1, ref [29])。ゆえに DLM は競合を避けられ有効なはず、が期待。
- [paper] しかし実測では低競合(5 クライアント中 1 つだけがアクティブ)でも、
  ファイル・ディレクトリ作成のスループットはクライアント数の増加で最大 86% 低下
  (§3, Fig. 2b)。一方、通常のファイル I/O(4KB seq/rand read/write)はクライアント数に
  ほぼ不感 — I/O オーバーヘッドがロック取得より遥かに大きく、ロックを要するのが
  1 クライアントのみのため (§3, Fig. 2a)。通常 I/O が影響を受けるのは高ロック競合時で、
  それは既存研究の焦点だった (§3)。
- [paper] レイテンシ内訳(5 クライアント・ディレクトリ作成): DLM 操作(Fig. 1 の
  step 2–6)が全体の 47%、ファイルシステムの create 操作が 53%。DLM 47% のうち
  directory node / owner node との通信を除いた純粋なロック取得処理は 15% のみ
  → 通信レイテンシが主ボトルネック (§3, Fig. 3)。
- [paper] ロック取得時間の PDF: 1 クライアントなら常に 20µs 未満(自ノードが
  directory node かつ owner node になるため)。クライアント数が増えるとハッシュ関数が
  リモートノードを directory node に割り当てる確率が上がり、ロック取得レイテンシが
  伸びる (§3, Fig. 4)。
- [paper] この現象は特定の FS-DLM 組合せに固有ではない: OCFS2 + O2CB / OCFS2 +
  カーネル DLM でも同傾向 (§3, Fig. 5)。O2CB は directory node を持たない設計のため、
  新規ロックオブジェクトの owner 決定に全クライアントとの通信が必要で、カーネル DLM
  (directory node と高々 1 往復)よりさらに悪い (§3, Fig. 5)。

## System model & assumptions
- [paper] カーネル DLM のモデル: 各ロックオブジェクトに owner node(アクセス許可と
  ロック剥奪を担当)と directory node(オブジェクト名のハッシュで決定。現 owner を
  lock-owner table で追跡し要求をルーティング)が割り当てられる (§2, Fig. 1)。
- [paper] ファイル・ディレクトリ作成時はまだ所有権が確立していないため、directory
  node は要求ノードを owner に指名でき、以後のロック取得(Fig. 1 step 5–6)は
  ローカル処理になる (§2, Fig. 1)。
- [paper] 対象は「完全分散型 DLM」(Linux カーネル DLM 等): 集中メタデータサーバを
  排して単一障害点を避け、ローカルが所有権を持つ場合は調整をバイパスできる。
  Lustre / Ceph のような集中型は分散 directory node を持たないためこの問題自体が無いが、
  別のスケーラビリティ問題(単一競合点)があり得る — それは本論文のスコープ外 (§2)。
- [paper] ネットワーク仮定: 各クライアントは共有 NVMe SSD に NVMe-over-TCP で接続し、
  カーネル DLM も TCP で通信 (§3)。Lockify は「TCP しか選択肢のないクラスタ環境」を
  主対象とする設計 (§5.5)。
- [paper] FS セマンティクス仮定: 共有ディスク FS では子エントリ作成前に親ディレクトリを
  排他ロックしなければならない。Lockify は self-ownership 開始時点でこのロックが
  既に保持されていることを前提にする (§4.4)。
- [paper] 故障モデル: ノード/ネットワーク障害で confirmation が届かない場合はタイマー
  満了で通知を再送 (§4.3)。クラッシュ回復や mount/unmount で directory node の役割が
  別ノードに移った場合、未確認の通知を新 directory node に再送できる (§4.3, §4.4)。
- [inference] 便益はワークロード仮定に強く依存する: 「作成が多く、かつ低競合(単一
  アクティブクライアント)」という HA 型シナリオ (§1, §5.3) が前提。作成後に別ノードが
  そのファイルへ頻繁にアクセスする(owner が creator であることが不利になる)パターンは
  本文では分析されていない。

## Approach
- [paper] 鍵となる洞察: owner node の lookup は DLM の基本動作だが、新規ファイル・
  ディレクトリの作成では「作成を開始したノードが自分自身を owner に指名」でき、
  他ノードへの問い合わせは不要 (§1)。
- [paper] **Self-owner notification (§4.1, Fig. 6)**: DLM は存在しないファイルの lock
  owner を追跡していないことを利用し、directory node に「問い合わせる」代わりに
  自己所有を「通知」する(step 3)。confirmation を待たずに直ちに制御を FS に返して
  ロック取得を完了する(step 4)。directory node は通知を受けて lock-owner table を
  更新し confirmation を返す(step 5)。table lookup のオーバーヘッドも回避されるため
  CPU 効率も良いと主張 (§4.1)。
- [paper] **拡張ロック取得インターフェース (§4.2)**: FS は「これが新規オブジェクトの
  作成か」を判断するコンテキストを持つため、`dlm_lock(..., NOTIFY)` という NOTIFY
  フラグ付き API を追加し、FS が明示的に指定する(FS 側の改修を最小化)。既存ファイル
  なら所有権が既に割り当てられている可能性が高く lookup が必要なので、NOTIFY 無しの
  標準パスに従う。作成以外では通信レイテンシは I/O オーバーヘッドに比べ相対的に小さい
  (§4.2, §3)。
- [paper] **非同期所有権管理 (§4.3, Fig. 6)**: DLM レベルの所有権一貫性を保つため、
  ロック要求ごとに wait-list にエントリを挿入し(step 2)、confirmation の受領を追跡。
  規定時間内に届かなければ(ノード/ネットワーク障害)該当 directory node に再送。
  confirmation 受領でエントリを削除(step 5)。directory node の役割が移った場合は
  未確認通知を新 directory node に再送 (§4.3)。
- [paper] **一貫性ケーススタディ (§4.4)**:
  - クラッシュ回復: 標準 DLM の回復機構(各クライアントが再割り当てされた directory
    node 群に所有権情報を送る)を拡張し、回復時に wait-list を確認して未確認の
    self-ownership 通知も再送。標準 DLM を超える通信オーバーヘッドは加えない。
  - 親ディレクトリロック競合: 複数クライアントが同一親ディレクトリ下の同名オブジェクト
    に同時に self-owner notification を送るコーナーケースは、親ディレクトリの排他ロックが
    前提で保護される。Lockify は (1) 所有権更新と (2) 対応するファイル操作(子の作成)の
    両方が完了して初めて親ディレクトリロックを解放する — 標準 DLM との違いは両ステップを
    「並行に」実行する点で、追加の通信オーバーヘッドは無い。

## Evaluation
- Setup [paper]: Lockify を Linux kernel 6.6.23 のカーネル DLM 上に実装し、GFS2 /
  OCFS2 + NVMe-over-TCP でバニラのカーネル DLM と比較。O2CB は評価シナリオで
  カーネル DLM に劣るため除外。DLM 非依存の共有 FS として NFS とも比較 (§5)。
  テストベッドは 5 サーバ(スケーラビリティ問題の実証には 5 台で十分と主張)、各
  dual Xeon Gold 5115(2.40GHz、20 コア/ソケット、HT 有効)、64GB RAM、250GB
  Samsung 970 EVO Plus NVMe SSD、56Gbps リンク、Ubuntu 18.04(kernel 6.6.23)(§5.1)。
- Workloads [paper]: mdtest(計 35,000 のファイル・ディレクトリをツリー状に作成)、
  Postmark(500 ファイル、1KB–4KB、500,000 トランザクション)、Filebench の
  fileserver(10,000 ファイル、ディレクトリあたり平均 20 エントリ、ガンマ分布
  平均 128KB、50 スレッド、I/O 1MB、append 平均 16KB)と webproxy(10,000 ファイル、
  平均幅 1,000,000 のディレクトリ構造、平均 16KB、100 スレッド)(§5.1, §5.3)。
- 低競合 micro-bench (Fig. 7, §5.2): 1 クライアントでは自ノードが全ロックの directory
  node 兼 owner node になる理想ケースで、Lockify の利得はゼロ。5 クライアントでは
  通信レイテンシ排除により OCFS2 で ~2.9×、GFS2 で ~6.4× の改善。NFS は
  クライアント・サーバモデルなのでクライアント数に不感だが、1 クライアントでも
  極端に低スループット(FS 側オーバーヘッドが支配的)。
- 高競合 micro-bench (Fig. 8, §5.2): 5 クライアント全員が同一親ディレクトリ下で
  mdtest を実行。親ディレクトリロックの所有権は既に割り当て済みで Lockify では
  緩和できず、OCFS2 の改善は 1.09–1.11× に留まる。一方 GFS2 はロック要求の内部
  キューで親ディレクトリへの重複要求を抑制する最適化を持つため、Lockify の新規
  作成分の削減が効いてディレクトリ作成 5.2× / ファイル作成 5.4×。
- レイテンシ内訳 (Fig. 9, §5.2): GFS2 で DLM レイテンシの割合は 1 クライアント 4.4%
  → 5 クライアント 46.7% に跳ね、Lockify は 8% まで削減(1 クライアントの理想に接近)。
  35,000 作成のストレス下でも wait-list 維持コストは測定可能なペナルティ無し
  (wait-list を持たない 1 クライアント GFS2 と同等)。評価は背景トラフィック無しで
  実施しており、輻輳下ではカーネル DLM の通信レイテンシはさらに悪化する一方、
  Lockify は非同期に confirmation を待つ間 FS 操作を進められるため影響を受けにくい、
  と主張(測定は無し)。
- 実ワークロード (Fig. 10, §5.3): 1 アクティブ + 4 アイドルの低競合構成。Postmark は
  5 クライアントで OCFS2 1.7× / GFS2 2.0×、理想(1 クライアント)スループットの
  93–96% を達成。fileserver は I/O 支配的で DLM 通信が隠れるが 1.07–1.14×。
  webproxy は GFS2 2.5× に対し OCFS2 は 1.08× に留まり、FS レベルのさらなる最適化の
  必要性を示すとする。
- クラッシュ一貫性 (§5.4): xfstests のうち NFS 向けに提案される 75 の generic テストを
  GFS2 / OCFS2 × カーネル DLM / Lockify で実行。GFS2 は両者とも 70/75 パス、OCFS2 は
  両者とも 67/75 パスで、Lockify の統合は共有ディスク FS 標準への準拠に悪影響なし。
- RDMA ベース DLM との比較 (Fig. 11, §5.5): RDMA ベースのカーネル DLM 実装が
  存在しないため、「単一クライアントで通信レイテンシゼロのカーネル DLM」+
  NVMe-over-RDMA 接続でエミュレート(低競合では RDMA レイテンシ < 1µs と仮定、
  ref [31])。Lockify(5 クライアント)は OCFS2 / GFS2 とも DLM-over-RDMA の
  87–88% のスループットを、専用ハードウェア無しで達成。
- [inference] 評価がカバーしていないもの:
  - クライアント数は最大 5(サーバ 5 台)。directory node がリモートになる確率は
    ノード数とともに漸近的に 1 に近づく一方、wait-list や再送の挙動を含む大規模
    クラスタ(数十ノード)での検証は無い。
  - 故障注入実験が無い: 再送タイマーの値も本文に明記されておらず、directory node
    障害中に wait-list が成長し続ける場合のメモリ挙動、再送(at-least-once)に対する
    directory node 側の重複通知処理は測定・記述されていない。§5.4 の xfstests は
    汎用テストであり、Lockify 固有の回復パス(未確認通知の再送)の正しさ・性能を
    直接叩くものではない。
  - 高競合で残る「親ディレクトリの owner lookup」ボトルネック (§5.2) への対策は
    評価されていない(OCFS2 では改善 1.09–1.11× 止まり)。
  - NOTIFY が効くのは作成のみで、削除・rename 等の他メタデータ操作の内訳分析は無い
    (webproxy には削除が含まれるが操作別の分解は示されない)。
  - ストレージは 250GB のコンシューマ NVMe SSD 1 台。複数デバイス・大容量構成での
    挙動は未評価。

## Limitations
- Stated [paper]:
  - 1 クライアント(理想ケース)では性能利得ゼロ (§5.2, Fig. 7)。
  - 既存ファイルへの操作では所有権 lookup が必要なため標準パスに従う。作成以外では
    通信レイテンシは I/O に比べ小さいという整理 (§4.2)。
  - 高競合では親ディレクトリの owner 識別が主ボトルネックとして残り、OCFS2 の改善は
    1.09–1.11× (§5.2, Fig. 8)。webproxy でも OCFS2 は 1.08× で、FS レベルの追加最適化が
    必要 (§5.3)。
  - 集中型アーキテクチャ(Lustre / Ceph)の抱える別種のスケーラビリティ問題は
    スコープ外 (§2)。
  - 単一ノード構成ではスケーラビリティ問題自体が再現されず Lockify の便益を実証
    できない(最低 2 ノードの共有ストレージ環境が必要)(Appendix A)。
- Inferred [inference]:
  - self-ownership は「作成ノード = owner」を固定するため、作成ノードと以後の主要
    アクセスノードが異なるワークロードでは owner がリモートに居続けることになる。
    所有権の移動・再配置コストとの相互作用は本文に無い。
  - confirmation は非同期なので、「通知が directory node に届く前」に第三のノードが
    同じロックオブジェクトの owner を directory node に問い合わせた場合の処理手順は
    本文に明記されていない(§4.4 が扱うのは同名作成の競合のみで、それは親ディレクトリ
    排他ロックで直列化される。作成完了後・confirmation 前の他ノードからの lookup は
    別のケースに見える)。xfstests 通過 (§5.4) は挙動が正しいことの示唆に留まる。
  - 「輻輳下で Lockify は影響を受けにくい」(§5.2) は無測定の主張。再送タイマーとの
    相互作用(輻輳による confirmation 遅延 → 誤再送 → さらなるトラフィック)は
    論じられていない。
  - RDMA 比較 (§5.5) はエミュレーション(通信レイテンシゼロの単一クライアント実行)
    であり、実 RDMA DLM の CPU 消費・NIC 競合などの実装要因は反映されない。
    「87–88%」という数字の解釈には注意が要る。

## Relations
- 競合・比較対象(本文内): Linux カーネル DLM (ref [1])、O2CB (ref [7])、NFS (§5)、
  one-sided RDMA ベースの DLM 群(Citron ref [21]、SIGMOD'18 の分散ロック ref [42];
  §2 で高競合向けと位置付け、§5.5 でエミュレーション比較)。
- [[2026-eurosys-cai-rdma-locks.md]](StreamLock): 同じ「分散ロックのスケーラビリティ」
  を攻めるが軸が対照的。StreamLock は RDMA 環境の高競合データパス(順序付け・所有権
  移転の NIC 競合)を扱い、Lockify は TCP しか使えないクラスタの低競合・作成ヘビーな
  メタデータパス(owner lookup の通信往復)を扱う (Lockify §2, §5.5)。「どの競合水準・
  どのハードウェア前提でどの設計が効くか」の比較軸として両ノートは対になる。
- [[2026-fast-wei-dmtree.md]](DMTree): [inference] テーマ上の接点。DMTree の
  collaborative locking は lock フィールドを compute 側に移して memory server への
  RDMA 往復を削り、Lockify は所有権を作成ノード自身に置いて directory node への
  TCP 往復を削る — どちらも「ロックメタデータを要求側に寄せて リモート往復を
  クリティカルパスから外す」設計で、対象レイヤ(DM 上の索引 vs 共有ディスク FS の
  DLM)が異なる。

## Idea seeds
- [inference] 「新規オブジェクトには所有者が居ないので creator が自己指名できる」という
  洞察は FS に限らず、共有ストレージ上の DBMS(本文 §1 は Oracle RAC 等の DB を共有
  ストレージの用途として挙げる, ref [8])の新規ページ割り当て・新規レコード挿入の
  ロック/ラッチ取得にも写像できる可能性がある。最初の検証: 公開 artifact
  (https://github.com/skku-syslab/lockify, Appendix A)の NOTIFY パスを流用し、
  クラスタ LVM や共有ディスク上の DB 的ワークロード(挿入ヘビー)でロック取得内訳を
  Fig. 3 と同様に分解する。
- [question] directory node の割り当てが「名前のハッシュ」(§2) であることが根本原因なら、
  self-owner notification の代わりに「新規オブジェクトの directory node を creator 自身に
  する」局所性優先の割り当てでも同じ効果が得られるのではないか。何が壊れるか(他ノード
  からの lookup 経路、回復時の再構築)は開いた問い。検証: artifact でハッシュ関数を
  差し替えて Fig. 7 相当を再測定し、通知方式との差分(特に回復コスト)を見る。
- [inference] 「輻輳に強い」という §5.2 の無測定の主張は、そのまま再現実験の題材になる。
  背景トラフィックを注入しながら mdtest を回し、カーネル DLM / Lockify のスループットと
  再送回数を測る実験は artifact + 5 ノード相当の環境があれば低コスト。非同期所有権
  管理の再送タイマー設定と誤再送の感度分析まで含めれば、short paper 規模の追試になる。
- [question] 作成直後・confirmation 到達前の第三ノードからの owner lookup がどう
  解決されるのか(directory node はまだ owner を知らない)。コード
  (https://github.com/skku-syslab/lockify)を読んで、lookup が通知とレースした場合の
  直列化点を特定するのが第一歩。

## Changelog
- 2026-07-06: created (status: read)
