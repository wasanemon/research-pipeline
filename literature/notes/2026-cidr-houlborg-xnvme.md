---
title: "Flexible I/O for Database Management Systems with xNVMe"
authors: [Emil Houlborg, Andreas Nicolaj Tietgen, Simon A. F. Lund, Marcel Weisgut, Tilmann Rabl, Javier González, Vivek Shah, Pınar Tözün]
venue: "CIDR"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/cidr/HoulborgTLWR00T26"}
urls: {paper: "https://vldb.org/cidrdb/2026/flexible-io-for-database-management-systems-with-xnvme.html", pdf: "literature/pdfs/2026-cidr-houlborg-xnvme.pdf", code: "https://github.com/itu-rad/nvmefs"}
status: read
read_date: 2026-07-06
tags: [nvme, io-paths, io_uring, spdk, fdp, duckdb, storage-engines, olap, write-amplification, posix]
---

## TL;DR
Samsung 製の統一 NVMe I/O フレームワーク xNVMe を DuckDB に「非侵襲的に」統合する
filesystem 拡張 nvmefs を提案。ファイルではなく LBA を直接管理することで、単一の
コードで io_uring_cmd (I/O Passthru) / SPDK / FDP SSD を切り替え可能にする。
デフォルトの POSIX 同期 I/O 比で、I/O 集約的クエリ(TPC-H・集約ベンチマーク)は
最大 50% 短縮、I/O 非集約的ケースは同等性能 (abstract)。CIDR らしい
「統合の実践報告+ロードマップ」型の論文で、新アルゴリズムの提案ではない。

## Problem & motivation
- [paper] NVMe SSD は ZNS / FDP / KV SSD など多様化し μsec 級レイテンシを提供する
  一方、それを叩く I/O パス(libaio, io_uring, SPDK)も乱立。API・セマンティクス・
  性能が大きく異なり、OS 差(Linux/FreeBSD/Windows/MacOS)も掛け算で効いて
  ソフトウェア開発を複雑にし、NVMe エコシステムの普及を妨げている (abstract, §1)。
- [paper] モダンストレージ向け DB 最適化研究や POSIX 抽象のボトルネックを示す研究は
  多数あるのに、実世界のデプロイの大半は依然 pread/pwrite に保守的に依存 (§1)。
- [paper] POSIX ストレージ API は約 50 年前の低速・小容量デバイス時代の設計で、
  OS ごとに API とセマンティクスが分裂(fracture)した。要因は (1) 高速ハードウェアと
  カーネル API のオーバーヘッド顕在化(SPDK 等ユーザ空間ライブラリとの性能差)、
  (2) 同期 API の限界(aio_* は移植性・普及・性能で失敗、io_uring は SPDK より
  オーバーヘッドが大きくカーネル知識を要求)、(3) FDP・computational storage・
  QoS・NVMe over CXL など POSIX の read/write 抽象を超える新機能の登場 (§3.1)。
- [paper] ベンダは新機能を低レベル NVMe ドライバか SPDK 等ユーザ空間ライブラリで
  露出せざるを得ず、どちらでも POSIX API は事実上放棄される (§3.1)。
- [paper] xNVMe 自体の性能は fio ベースのマイクロベンチマークで実証済みだが、
  DBMS への統合は著者らの知る限りほぼ未探索 (§1)。

## System model & assumptions
- [paper] 対象 DBMS は DuckDB(in-process の分析特化 DBMS、out-of-core クエリ実行を
  サポート、デフォルトは POSIX I/O)。コア本体を軽量・依存フリーに保つ設計原則が
  あるため、本体改造ではなく community extension(動的リンクライブラリ)として
  統合する。移植性(portability)を生の性能より優先する設計選択で、DuckDB の
  buffer manager を xNVMe と co-design する Ottosen et al. [36] とは対照的 (§1, §4)。
- [paper] DuckDB のファイルは 3 種類のみ: database ファイル(1 個)、WAL(1 個)、
  temporary ファイル(buffer pool から溢れた中間結果のスピル先、複数)。ブロック
  サイズは database がデフォルト 256 KiB、temporary は 32 KiB〜256 KiB でサイズ別に
  別ファイル (§4.1)。→ [inference] この「ファイル数が少なく構造が単純」という
  DuckDB の性質が、nvmefs の LBA 直接マッピング(start LBA + current LBA だけで
  database/WAL を管理)を成立させている。ファイルが多数・動的な DBMS では
  メタデータ管理が本論文の設計より重くなるはず。
- [paper] xNVMe の想定: デバイスハンドルは OS パス / PCIe アドレス / NVMe-transport
  エンドポイントで開き、バックエンドは実行時に利用可能なものから libxnvme が自動
  選択(opts.be.async で明示指定も可)。バッファはデバイスの I/O 制約(DMA 等)に
  合わせて xnvme_buf_alloc で整列確保。非 NVMe デバイスには fallback shim が NVMe
  コマンドを OS の I/O 操作へマップする (§2)。
- [paper] 評価ハードウェアは FDP SSD(3.76 TB、ブロック 4 KiB)を積んだ Samsung
  Memory Research Center 提供のサーバ 1 台(2× Xeon Gold 6342、24 コア/48 スレッド、
  RAM 500 GB、CentOS Stream 9、カスタム Linux 6.13.0)。FDP SSD はデータセンタでは
  デプロイ済みだが単体購入は不可 (Table 1, §5)。
- [paper] ソフトウェアは xNVMe 0.7.5、SPDK 22.09、DuckDB 1.2.0。DuckDB は明示した
  buffer pool サイズとスレッド数以外デフォルト設定 (§5)。
- [inference] 障害モデル・耐久性の議論は本文にない。nvmefs の LBA マッピング
  (特に Temporary File Metadata Manager)がクラッシュ後どう回復されるか、WAL 経由の
  リカバリが LocalFileSystem と同等に機能するかは記述がなく、評価もされていない。
- [inference] ワークロード想定は読み中心・大きめシーケンシャル I/O の OLAP。
  著者ら自身が §6 で認める通り、書き込みが多くランダムアクセス優位の OLTP は
  スコープ外(未評価)。

## Approach
- [paper] **xNVMe プログラミングモデル (§2, Fig. 1)**: コマンド中心のメッセージ
  パッシング API。xnvme_cmd_ctx にオペコード・デバイス・キューを詰めて
  xnvme_cmd_pass で送る。同期(ブロッキング)と、キュー+コールバックによる
  非同期の両方を同一 API で提供。サポートする I/O パスは POSIX aio、libaio、
  Windows IOCP/IORING、io_uring、io_uring command、psync、block-layer IOCTL、
  NVMe driver IOCTL、加えてユーザ空間ドライバの SPDK と libvfn。同じ C API が
  無変更で全パスに通る。C 実装で Python/Rust バインディングあり (§2)。
- [paper] **設計原則 (§3.2)**: (1) 多様な I/O パス横断の効率的・スケーラブルな
  非同期 API、(2) 下層ストレージパスのネイティブ性能を維持、(3) 汎用的な概念
  抽象ではなく明確な API とセマンティクス(最小主義と拡張性)。
- [paper] **nvmefs (§4.2, Fig. 2)**: DuckDB の FileSystem 抽象を継承した community
  extension。パス接頭辞 `nvmefs://` で起動。ファイルの下でデータを直接 LBA に
  マップする。バックエンド選択は設定ファイル(DuckDB SECRETs manager で永続化)
  から読み、未指定なら xNVMe が実行時に自動選択。
- [paper] **LBA マッピング (§4.2, Fig. 2)**: I/O Passthru や SPDK は OS レイヤを
  バイパスするので、nvmefs 自身が各ファイルの LBA を追跡する。database と WAL は
  各 1 ファイルなので start LBA + 現在の書き込み LBA で十分。temporary ファイルは
  多数で LBA 範囲が交錯し得るため、Temporary File Metadata Manager がファイル名 →
  LBA 範囲リスト(非連続可)を管理し、Temporary Block Manager が空きブロックを追跡。
- [paper] **NVMe キュー (§4.2)**: DuckDB ワーカースレッドごとに専用 xnvme_queue を
  作成し、キュー共有時の同期を排除(NVMe デバイス利用時の常套最適化と明記)。
- [paper] **FDP 統合 (§4.2)**: FDP はホストがデータの配置を間接的に誘導し、寿命の
  似たデータを同じ erase block にまとめて GC の再書き込みを減らし write
  amplification (WA) を下げる NVMe base spec 収載技術。nvmefs はデバイスオープン時に
  get-feature API で FDP 有効を確認し、有効なら write コマンドに database データと
  temporary データで異なる placement identifier を付与(temporary はクエリ寿命、
  database は長期という寿命分離)。実装は xNVMe の I/O Passthru バックエンド経由で、
  生の io_uring_cmd を直接叩くより煩雑さと事故りやすさを避けられると主張 (§4.2)。

## Evaluation
- Setup [paper]: 比較は DuckDB LocalFileSystem(ext4 + 同期 I/O)= baseline vs
  nvmefs の 3 バックエンド: io_uring_cmd (= xnvme)、+FDP (= xnvme-fdp)、
  SPDK (= xnvme-spdk)。ベンチマークは TPC-H と Kuiper et al. [23] の集約
  ベンチマーク(lineitem 上、中間結果がディスクにスピルする状況を作る)(§5, Table 1)。
- [paper] **TPC-H (§5.1, Fig. 3)**: SF100(DB 26 GB)と SF1000(265 GB、DuckDB の
  圧縮込み)、buffer pool 20 GB、16 スレッド。DB が buffer pool に収まらず中間結果
  スピルも発生する設定。Q9 と Q13 が I/O Passthru と FDP で顕著に改善、Q12 は FDP で
  実行時間が半減(図には非掲載、本文記述)。他のクエリは baseline の ±10% 程度 —
  著者らはこれを OS ページキャッシュの効果で説明(I/O Passthru は OS のファイル
  システムバッファリングもバイパスするため)。SF1/SF10(buffer pool に収まる)では
  有意差なし。
- [paper] 本節の全実験で WA ≈ 1(分析ワークロードの書き込みがほぼシーケンシャルな
  ため)。したがって xnvme-fdp は大半のクエリで他と同等 (§5.1)。
- [paper] **集約ベンチマーク (§5.2, Fig. 4)**: SF128(DB 22 GB)、buffer pool 20 GB、
  16 スレッド。thin 変種(グループ化カラムのみ選択)は I/O 圧が足りず利得なし。
  wide 変種(全カラム選択、スピル多発)は平均 ~20% の実行時間短縮。SF32 は SF128 と
  同傾向、SF8/SF2 は I/O 圧不足で差が出ない。
- [paper] **SPDK (§5.3, Fig. 5)**: 集約ベンチマーク wide、SF32(DB 5.3 GB)、
  buffer pool 2 GB、1 スレッド。xnvme-spdk は baseline 比 4〜30% 改善。一方
  io_uring_cmd は大半のクエリで実行時間をほぼ半減させ、SPDK を一貫して上回る。
  著者らは SPDK 側の未最適化(結果受け渡しバッファの事前確保など)を明記し、
  out-of-the-box でも利得がありユーザを SPDK の設定地獄から解放する点を強調。
- [paper] ヘッドライン: I/O 集約的クエリで最大 50% の実行時間短縮、非集約的
  ケースは同等 (abstract, §1)。
- [inference] 評価がカバーしないもの:
  - 書き込み集約・ランダムアクセスのワークロード(OLTP)が皆無。WA ≈ 1 の環境
    しか測っていないため、**FDP の本来の売り(GC 削減・WA 低減)は実質未検証**。
    §5.1 の「xnvme-fdp が他と同等」はこの弱い条件下の結果に過ぎない。
  - baseline は ext4+同期のみ。カーネル経由の io_uring(ファイルシステム越し・
    非 passthru)や libaio との比較がなく、「passthru/LBA 直叩きの寄与」と
    「非同期化の寄与」が分離されていない。
  - co-design アプローチ(Ottosen et al. [36])との性能比較がなく、「拡張の移植性
    と引き換えに失う性能」が定量化されていない。
  - SPDK 実験は 1 スレッド・2 GB buffer pool・SF32 のみで、マルチスレッド時の
    SPDK vs io_uring_cmd の関係は不明。
  - サーバ 1 台・FDP SSD 1 機種(Samsung 提供)での評価。ZNS / KV SSD は動機
    (§1)に挙がるが評価はない。
  - クラッシュリカバリ・耐久性(WAL 経由復旧が nvmefs 上で機能するか)の実験なし。

## Limitations
- Stated [paper]:
  - 統合は preliminary であり、さらなるコード最適化が可能(mutex ベースの同期点を
    atomic に置き換える再設計、I/O パスのチューニングノブ探索、FDP placement
    オプションの実験など)(§6)。
  - SPDK バックエンドはバッファ事前確保などの最適化で更に性能を出せる余地がある
    (§5.3, §6)。
  - FDP サポートは「preliminary support」と自己申告 (§5.1)。
  - OLTP ワークロード・OLTP 最適化 DBMS での効果は今後の課題(FDP の恩恵は
    OLTP の方が大きいはずと予想のみ)(§6)。
- Inferred [inference]:
  - temporary データの placement identifier 分離は DuckDB のファイル 3 種構造に
    強く依存した粗粒度の寿命分類(database vs temporary の 2 値)。LSM ツリーの
    レベル別寿命のような細粒度分離には設計拡張が必要なはず。
  - nvmefs は OS ファイルシステムを完全に置き換えるため、ページキャッシュの利得も
    失う。I/O 非集約ケースで「同等」なのはキャッシュ喪失と非同期化の利得が相殺
    した結果とも読め(§5.1 の著者説明の裏返し)、メモリ潤沢・再読の多い環境では
    baseline に負けるケースがあり得るが、その境界条件は示されていない。
  - デバイス 1 台を nvmefs が専有する形のデザインに見え(LBA 範囲を静的に割当、
    Fig. 2)、複数 DB ファイル・他アプリとのデバイス共有の扱いは記述がない。

## Relations
- [paper] Ottosen et al. [36] "DuckDB on xNVMe"(arXiv:2512.01490)が直接の対照:
  あちらは DuckDB buffer manager と xNVMe の co-design、本論文は portability 優先の
  extension アプローチ (§1)。
- [paper] I/O Passthru は Joshi et al. FAST'24 [20]、集約ベンチマークは Kuiper et al.
  ICDE'24 [23]、FDP for flash caches は Allison et al. EuroSys'25 [1] に依拠 (§1, §4, §5)。
- [[2026-pvldb-lee-how-to-write-to-ssds]]: 同じく SSD の write amplification と
  データ配置を扱う。本論文の FDP 統合(寿命ベースの placement identifier 分与)は、
  あちらの WA 最適化の議論に対する「ホスト側インターフェース」の具体例。本論文は
  WA ≈ 1 の OLAP でしか測っておらず、WA が問題になるワークロードでの FDP 効果の
  検証はあちらの視点と組み合わせる余地がある。

## Idea seeds
- [inference] 「非同期化の利得」と「OS バイパス(ページキャッシュ喪失込み)の
  利得/損失」の分離実験は本論文の明確な空白。同一 nvmefs 上で backend を
  psync / io_uring(FS 経由)/ io_uring_cmd / SPDK と振るだけで取れるはずで
  (xNVMe は backend 切替が設定 1 行)、CIDR 論文の追試として低コスト。DuckDB +
  公開コード(github.com/itu-rad/nvmefs)で即着手可能。
- [question] FDP の placement identifier を DuckDB の 2 値(database/temporary)より
  細粒度にする余地: temporary ファイルはブロックサイズ別(32K〜256K)に分かれて
  おり (§4.1)、サイズ ≒ スピル種別 ≒ 寿命の相関があるなら placement をサイズ別に
  分けるだけで WA が変わるか。WA ≈ 1 の OLAP では測れないので、更新混在
  (HTAP 的)ワークロードでの検証が必要。
- [inference] nvmefs の Temporary File Metadata Manager は「ファイル抽象を保ちつつ
  LBA を直接管理する」最小構成のミニ FS であり、クラッシュ一貫性が未定義に見える。
  「extension として後付けした user-space FS の永続性セマンティクス」を検証する
  テストハーネス(WAL 復旧の fault injection)は、統合の実用化に直結する小粒で
  検証可能なテーマ。

## Changelog
- 2026-07-06: created (status: read, CIDR 2026 公式 PDF を読解)
