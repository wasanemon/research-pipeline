---
title: "Exploring Dynamic Memory Allocation of CXL Memory Pools in Enterprise In-Memory Database Management Systems"
authors: [Donghun Lee, Minseon Ahn, Jungmin Kim, Jaemin Jung, Norman May, Daniel Ritter, Jongmin Gim, Heekwon Park, Changho Choi, Yang Seok Ki]
venue: "EDBT '26 (Industrial & Applications Paper), pp. 687-695"
year: 2026
ids: {doi: "10.48786/edbt.2026.58", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.48786/edbt.2026.58", pdf: "literature/pdfs/2026-edbt-lee-cxl-pools.pdf", code: ""}
status: read
read_date: 2026-07-06
tags: [cxl, memory-pooling, disaggregated-memory, in-memory-dbms, sap-hana, htap, far-memory, tco, fast-restart, tpc-ds]
---

## TL;DR
実機の CXL スイッチベースメモリプール(XConn スイッチ + Samsung CMM-D 128GB×2)を
SAP HANA プロトタイプに接続し、動的メモリ割当の3ユースケース — ①テーブルデータ /
HEX ヒープのプール配置、②独立電源プール+HANA NVM 機能による fast restart、
③SQLScript 中間結果(一時テーブル)のプール配置 — を TPC-C / TPC-DS で評価した
SAP+Samsung の Industrial paper。OLTP は劣化観測なし、OLAP はレイテンシよりバンド幅に
感応(×2 インターリーブで劣化1桁%)、再起動は preload 比 5.25×、2サーバ同時アクセスでも
スイッチ起因の干渉は観測されず。

## Problem & motivation
- [paper] 単一サーバのメモリスロット数の制約により、大容量データを扱う IMDBMS では
  高容量 DIMM への依存と scale-out コスト増で TCO が悪化する。データ増加とメモリ
  スケーラビリティの不均衡が、単一サーバ境界を超えるメモリ拡張を要請 (§1)。
- [paper] CXL はメモリプーリング(CXL 接続メモリの一部を複数ホストに動的割当)を
  サポートし、細粒度のメモリ弾力性と資源利用率向上、over-provisioning 最小化による
  TCO 削減を可能にする (§1)。
- [paper] 著者らの前研究 [2,3] は「直結 CXL メモリ」と Intel Flat Memory Mode を評価:
  OLTP(TPC-C)は CXL トラフィックが小さくトランザクション間同期オーバヘッドが
  支配的なため劣化なし、OLAP(TPC-DS)はメモリアクセスパターン次第で劣化幅が広い (§1)。
- [paper] 本論文の新規性はスイッチ経由の「プール」: CXL スイッチは追加ホップにより
  約100ナノ秒程度レイテンシを加え得るという懸念があり (§1)、その実機影響を
  エンタープライズ IMDBMS(SAP HANA)で検証する (§1)。
- [paper] 貢献: 実機 CXL スイッチプールの実践知見の共有 / SAP HANA 上での動的メモリ
  割当の評価 / ワークロード・アクセスパターン別の性能特性調査 / TCO を下げる
  ユースケース開発((1) システム全体: compute ノードと data ノードの分離、
  (2) クエリ単位: 大規模クエリ実行中の中間結果の動的割当)(§1)。

## System model & assumptions
- [paper] プーリング方式は **switch-based**(fabric 中心)を採用: 高 fan-out・柔軟な
  資源割当が得られる代わりに追加ホップと管理複雑性を払う。対比される multi-headed
  デバイス(device 中心)はスイッチレイテンシ不要だがポート数でスケーラビリティが
  制約される (§2.1)。
- [paper] ハード構成: XConn B2 CXL スイッチチップ(最大 256 PCIe Gen5 レーン)。
  ホスト2台が各 PCIe Gen5 x16 の upstream port で接続。downstream には Samsung
  CMM-D 128GB ×2(各: DDR5 5200MT/s DIMM 128GB + 内部メモリコントローラ +
  CXL→DDR5 変換 ASIC + PCIe Gen5 x8 インターフェース)。スイッチは upstream port
  ごとに HDM(Host-Managed Device Memory)を提供し、各ホストに 256GB HDM を割当。
  HDM マッピングは fabric manager が設定(XConn 独自実装)(§3.1, Fig. 1)。
- [paper] **動的割当はスイッチ層ではなく OS 層で実現**: fabric manager による HDM
  再マッピングは現行ハードの安定性懸念のため不採用。代わりに fabric 構成は静的
  (全 CMM-D を束ねた単一 256GB HDM 領域を各ホストに見せ、両デバイスとも技術的には
  各ホストからアクセス可能)とし、Linux カーネルのメモリ online/offline で容量を
  伸縮する (§3.2)。
- [paper] **共有はしない**: 本評価ではホストごとに互いに重ならない(disjoint)プール
  領域を設定し、複数ホストによるメモリアクセス違反を回避。プール内メモリ領域の
  複数サーバ間「共有」は future work(§3 p.3, §8 は今後の CXL 標準のキャッシュ
  コヒーレンシに期待と明記)。
- [paper] アプリからは標準 load/store(CXL.mem)で透過アクセスでき、OS が同一の
  メモリ抽象を提供するため、前研究 [3,13] と同じユースケース(テーブルデータ移動・
  操作用ヒープ割当)をそのまま適用できる (§3 p.3)。
- [paper] SAP HANA 側の前提: HTAP プラットフォームで、カラムナの read 最適化
  main storage + write 最適化 delta storage(定期的に delta merge)。操作用メモリ
  (operational memory)は HANA Execution Engine(HEX)が使う一時データ全般。
  本研究用プロトタイプに (a) far memory allocation(特定 NUMA ノードへの割当)、
  (b) SQLScript 処理中の中間結果を格納する一時テーブルを特定 NUMA ノードに割当てる
  新機能、を追加した。**これらが商用版 SAP HANA に入る保証はない** (§2.2)。
- [paper] レイテンシ階層モデル: local DRAM (t0) < ソケット間 UPI (t1) < CXL 直結
  (t2, プロトコル直列化)< CXL プール (t3, スイッチ通過+デバイスバッファリング)。
  バンド幅もリンク直列化と共有 fabric 競合で低下する (Fig. 2, §4)。
- [paper] アクセス特性の仮定: main storage のテーブルデータは圧縮カラムナで高空間
  局所性・逐次アクセス支配(スキャン+ベクトル化処理)。HEX ヒープはランダムアクセス・
  頻繁な書き込み・短寿命割当で低空間局所性・高時間変動。前者は帯域感応、後者は
  レイテンシ感応で local DRAM 向き (§4.1)。
- [paper] fast restart の前提: CXL メモリプールが独立電源を持ち、システム/DB 再起動を
  跨いでプール内容が保持される (§4.2, §6.2.1)。
- [paper] 評価配置の前提: レイテンシ影響を調べるため、直結 CMM-D もプールも意図的に
  **remote socket** 側に接続(Fig. 2 参照)(§5.1.1)。
- [inference] 障害モデルはほぼ論じられていない。fast restart 評価は「制御された
  シャットダウン」後の再起動のみ (§5.2) で、ホスト電源断・書き込み途中クラッシュ時の
  プール内 main storage の整合性検証は本文にない。
- [inference] 「動的割当」はホスト単位の容量再配分(online/offline)であって、
  DBMS 内部の自動配置ポリシーではない。どのデータをプールに置くかは fsdax /
  NUMA バインドによる静的・手動設定である(§5.1.1 の設定方法から)。

## Approach
本質は新プロトコルではなく、実機プールの統合方法とユースケース設計。
- [paper] **配置機構**: main storage をプールへ移す際は割当 CXL 空間上に fsdax
  ファイルシステムを構築して管理。HEX ヒープをプールに置く際は NUMA ライブラリで
  プール対応 NUMA ノードへ割当をバインド (§5.1.1)。
- [paper] **帯域×2 構成**: downstream デバイスごとに fsdax デバイスを作り、Linux
  device mapper で2デバイスをインターリーブしたマップドデバイスを構成(構成名末尾
  x2)(§5.1.3)。
- [paper] **ユースケース1 — テーブルデータ移動 / 操作用ヒープ割当**: 何をプールに
  移すべきかはアクセス特性(逐次 read 支配の main storage vs ランダム write の
  HEX ヒープ)で決まる (§4.1)。
- [paper] **ユースケース2 — fast restart**: HANA の既存 NVM(persistent memory)機能を
  使い main storage をプールに配置。再起動時、永続ボリュームからの再ロードの代わりに
  プール上の main data fragments を直接アタッチする (§4.2, §5.2)。
- [paper] **ユースケース3 — 大規模クエリの中間結果の動的割当**: SQLScript 実行中に
  生成される一時テーブルをプール領域に動的配置。一時テーブル総量は同時ユーザ数に
  線形に増え local DRAM を超えて OOM を招くため、プールをオンデマンドの容量拡張
  として使い、disk spill(DRAM-ストレージ間の大きなレイテンシ差による性能劣化)も
  OOM も回避する (§4.3)。
- [paper] 運用上の知見: Intel MLC と改変 TPC-DS SQL script による検証で、プールの
  メモリ領域のアタッチ/デタッチ/サイズ変更に測定可能な遅延はなく、システムや DB の
  再起動などライフサイクル操作も不要だった (§5.3.2)。

## Evaluation
- Setup(単一サーバ実験): Intel 第5世代 Xeon(Emerald Rapids)1ソケット、物理48コア
  (HT 有効で96)。8メモリチャネル × 128GB DDR5 4800MT/s = local DRAM 1,024GB。
  プールは商用グレード CXL メモリボックス(XConn スイッチ1 + CXL メモリデバイス2)。
  TPC-C 100 warehouses / TPC-DS SF100。CMM-D・プールとも remote socket 接続 (§5.1.1)。
- Setup(2サーバ実験): Server A = Emerald Rapids Xeon Platinum 8568 ×2(96論理コア/
  ソケット、128GB DIMM×8ch = 1TB DRAM/ソケット)、Server B = Emerald Rapids ×2
  (112論理コア/ソケット、64GB DIMM×8ch = 512GB/ソケット)。両サーバとも共有プール
  から 128GB を動的割当で拡張。ワークロードは一時テーブルフットプリント最大の
  TPC-DS 上位5クエリ由来の SQL script (§5.3.1, Fig. 7)。
- [paper] **TPC-C**: main storage / HEX ヒープを remote DRAM / remote CMM-D /
  remote M-pool に置く7構成すべてで観測可能な劣化なし(384スレッド時 baseline で
  正規化)。HEX Remote M-pool・288クライアントスレッド時のピーク CXL トラフィックは
  約 13GB/s でデバイス提供帯域を大きく下回り、帯域は律速でない (Fig. 3, §5.1.2)。
- [paper] **TPC-DS(main storage 移動)**: プール配置で顕著な劣化が出るが、逐次
  アクセス支配のためハードウェアプリフェッチがレイテンシを緩和し、**性能はレイテンシ
  よりも利用可能帯域に感応**。device mapper で帯域を2倍にすると baseline 比で
  劣化は1桁%に収まる (Fig. 4, Fig. 5, §5.1.3)。local socket 接続と remote socket
  接続のプール間にはわずかな差が残り、これは main storage 内 dictionary への少量の
  ランダムアクセス(レイテンシ感応)に起因 (§5.1.3)。
- [paper] **HEX ヒープのプール配置(OLAP)は非現実的として除外**: 前研究 [3,13] で、
  より低レイテンシの直結 CXL でもランダムアクセス支配により 50% 超の劣化が出るため、
  本研究では viable use case とみなさない (§5.1.3)。
- [paper] **fast restart**(TPC-DS SF100、制御されたシャットダウン後、delta は
  full merge 済みと仮定): preload 全有効・fast restart 無しの構成に対し、データ
  preload 時間を 87% 削減、再起動全体で **5.25×** 高速化。preload 無し構成との比較
  では再起動時間は 27% 増(整合性検証とローカルメモリ上のメタデータ再構築の初期化
  コスト)だが、再起動直後から全テーブルデータがメモリ内でアクセス可能 (Fig. 6, §5.2)。
- [paper] **一時テーブルのプール配置**: Server A 上で Baseline(local DRAM)/
  Remote DRAM / M-pool の3配置とも性能は実質不変。選択スクリプトが逐次アクセス支配で
  プリフェッチが効き、CXL トラフィックも小さく、リンク・デバイスキューは飽和に遠い
  (Fig. 8, Fig. 9, §5.3.2)。
- [paper] **サーバ間干渉**: Server A は第1デバイスの先頭 128GB、Server B は他方の
  デバイスの残り 128GB を使用し、全トラフィックが同一スイッチを通過する構成で、
  同時実行と個別実行を比較 → 顕著な劣化なし。スイッチが並列に転送できるため、
  デバイス帯域競合など他の資源競合がない限りオーバヘッドは無視できる (Fig. 10, §5.3.3)。
- [inference] 評価がカバーしないもの:
  - 全結果が正規化値で、絶対スループット(tpmC / queries/hour)や絶対レイテンシは
    本文に出てこない。スイッチの実測追加レイテンシ(§1 の「約100ns」の実測確認)も
    数値としては示されない。
  - 干渉実験は2サーバが**別デバイス**を使う構成のみ(§5.3.3)で、同一 CMM-D デバイスを
    奪い合う場合のデバイス帯域競合・QoS は未測定。著者ら自身が「デバイス帯域競合が
    あれば別」と留保している。
  - スイッチ層の動的 HDM 再マッピングは安定性懸念で未評価 (§3.2) なので、「プールの
    動的性」の実測は OS の online/offline 経路に限られる。
  - 規模は 2 ホスト・2 デバイス・計 256GB で、§2.1 で言及される CXL 3.x の大規模
    fabric(多段スイッチ・数千デバイス)とはギャップが大きい。
  - OOM 回避 (§4.3) はモチベーションとしては語られるが、実際に local DRAM を超過
    させて OOM が防がれることを示す実験はない(一時テーブル実験は性能不変の確認)。

## Limitations
- Stated [paper]:
  - fabric manager による HDM 動的再マップは現行ハードの安定性懸念で不採用 (§3.2)。
  - プール領域の複数サーバ間共有(中間結果・テーブルデータの共有)は future work
    で、今後の CXL 標準のキャッシュコヒーレンシに依存 (§1, §8)。
  - ランダムアクセス支配の重量ワークロードはプリフェッチが効かず CXL レイテンシが
    露呈するため local memory 推奨 (§6.1)。OLAP での HEX ヒープのプール配置は
    直結 CXL でも 50% 超劣化 (§5.1.3)。
  - プロトタイプに追加した far memory / 一時テーブル NUMA 配置機能は商用版に入る
    保証がない (§2.2)。
- Inferred [inference]:
  - TCO 削減は本論文の中心的主張 (§1, §6.2.3) だが、評価はすべて性能であり、コスト
    モデルや金額・容量削減率の定量化はない。TCO 効果は引用([9], [14])と定性論に
    依存している。
  - fast restart の 5.25× は「全テーブル preload をディスクから行う構成」との比較で
    あり、preload しない運用と比べれば再起動は 27% 遅い (§5.2)。つまり利得は
    「再起動直後から全データ在メモリ」という SLA を要する運用に限って大きい。
  - 一時テーブル実験のワークロードが「一時テーブルフットプリント最大の TPC-DS 上位
    5クエリ」(§5.3.1)に選別されており、かつ結果は逐次アクセス支配 (§5.3.2)。中間結果が
    ランダムアクセスされる演算(ハッシュ結合のビルド側 probe 等)での挙動は不明。

## Relations
- [[2026-pvldb-zhao-sidle.md]]: 同じく CXL メモリ階層の DBMS 利用だが軸が異なる —
  SIDLE は索引構造の CXL 配置、本論文はスイッチベースの「プール」をホスト間容量
  再配分・fast restart・一時テーブルに使う。両者を合わせると「何を(索引/main
  storage/一時テーブル)どの CXL 形態(直結/プール)に置くか」の設計空間が見えてくる。

## Idea seeds
- [inference] 本論文の干渉評価はサーバごとに別デバイスを割り当てた「スイッチ通過のみ
  共有」構成 (§5.3.3) であり、同一 CXL デバイスを複数ホストで奪い合うときの帯域競合・
  テールレイテンシは空白。OLTP(レイテンシ感応)と OLAP scan(帯域消費)を別ホスト
  から同一 CMM-D に当てて p99 を測るだけで、プールの QoS 分離(§2.1 が要件として
  挙げる quality-of-service isolation)の必要性を定量化できる。
- [question] 独立電源プール上の main storage は「制御された再起動」では 5.25× の
  高速化 (§5.2) だが、非制御クラッシュ(delta merge 中の電源断など)後にプール上の
  fragments が安全に再アタッチできる保証はどこまであるか。§5.2 の整合性検証・
  メタデータ再構築のコスト(+27%)がクラッシュ時にどう変わるかを、fault injection
  付き再起動実験で確かめる価値がある。
- [inference] 容量の動的伸縮は Linux online/offline で「測定可能な遅延なし」(§5.3.2)
  とされるが、実行中クエリへの影響(offline 対象ブロック上のページ移動・割当失敗時の
  挙動)は未評価。負荷実行中に online/offline を繰り返し、スループット/テールへの
  影響を測れば、「クエリ実行と連動した弾力的一時テーブル割当ポリシー」(月末バッチ等
  §6.2.2 のシナリオ)の実現可能性を検証する最初の一歩になる。

## Changelog
- 2026-07-06: created (status: read, OpenProceedings 公式 PDF を読解)
