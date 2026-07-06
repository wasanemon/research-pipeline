---
title: "Scalable and Resilient Storage Tier for Azure SQL Hyperscale"
authors: [Alejandro Hernandez Saenz, Krystyna Reisteter, Sarika Iyer, Yu Wang, Shweta Raje, Swati Roy, Bhupesh Chawda, Kashish Goyal, Vishnu Das, Kinshuk Chopra, Rishita Chauhan, Prashanth Purnananda, Hanuma Kodavalla]
venue: "SIGMOD Companion"
year: 2026
ids: {doi: "10.1145/3788853.3803083", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3788853.3803083", pdf: "literature/pdfs/2026-sigmod-saenz-hyperscale-storage.pdf", code: ""}
status: read
read_date: 2026-07-06
tags: [disaggregated-storage, cloud-native, oltp, storage-tier, resiliency, write-behind, ssd-cache, checkpoint, striping, page-server]
---

## TL;DR
Azure SQL Hyperscale の Page Server ↔ Azure Storage 経路(耐久化とバルクデータ移動の
支配的パス)を再設計した Microsoft の産業システム報告。①論理-物理ファイル分離
(1論理ファイルを slice → cell → stripe に分割し、ストライドをラウンドロビンで複数
blob に散らして per-blob IO 上限を回避)と、②Write-Behind RBPEX(dirty page を
ローカル SSD キャッシュ RBPEX に書き、背景スレッドが集約して非同期に Azure Storage へ
反映。LocalState ≥ RemoteState 不変量で復旧を保証)の2戦略。TPC-C で Azure Storage
IOPS を 6717 → 2752(両方併用、Table 3)に削減し、production の Azure Storage
計画外障害時に write-behind が遅延したまま約 365 台の Page Server が可用であり続けた
(Table 4)ことを示す。

## Problem & motivation
- [paper] Hyperscale は Compute / Page Server (PS) / Log Service / Azure Storage を
  分離し 128TB までスケールするが、remote IO の境界が2つある: Compute↔PS と
  PS↔Azure Storage。本論文は後者に焦点を当てる。OLTP の耐久化・バルクデータ移動
  パスを支配するため (§1, Fig. 1)。
- [paper] 旧レイアウトでは1論理ファイル = 1巨大 blob(PS データファイルは歴史的に
  128GB〜1TB)で、per-blob スループット上限とスロットリングを招く。持続的 OLTP +
  スナップショット活動下で PS↔Azure Storage レイテンシ増、log redo 遅延、
  seeding/restore 長時間化として顕在化 (§1)。
- [paper] SQL Server の 8KB ページサイズは blob 層で断片化した write を生み、
  メタデータオーバーヘッドを増幅し write coalescence を下げる (§1)。
- [paper] PS の write が RBPEX(SSD キャッシュ)と Azure Storage の両方に同期結合
  されており、write クリティカルパスが長く、一過性ストレージ障害への耐性が低い (§1)。
- [paper] Azure Storage は安価なリモートストレージだが、受容可能な価格帯では
  スループット・レイテンシの保証がない (§2.2)。Standard storage の blob あたり
  IO は約 500–1000。超過するとスロットリングが始まる (§2.4.3)。
- [paper] backup/PITR 用の blob スナップショットは、大きな blob ではメタデータ複製と
  バージョンチェーン維持を伴いランダム IO を増やす。スナップショット蓄積で active
  データ + snapshot delta 両方への write が積み増しされ IOPS 消費が増幅、レイテンシ
  上昇とスループット不安定化を招く (§1, §2.4)。
- [paper] Failover: 1TB ファイルは単一 PS が管理するため、その SQL インスタンス障害時は
  新インスタンスを provisioning して RBPEX seeding(1TB 全体を Azure Storage から
  読む)が必要。blob 上限を容易に超過し、seeding は数時間に及びうる。seeding 中の PS は
  read 要求と log 適用を続けるが、read-heavy ワークロードのスループットが大幅低下し
  log 追随も阻害される(実測観察)(§2.4.1)。
- [paper] 論理ファイルサイズは顧客管理であり、非 Hyperscale 層から移行する既存 DB は
  1TB ファイルを複数持つことが多い。移行前の手動 shrink は数日かかり非現実的。
  ゆえに「ファイルのどの部分を各 PS が担当するか」をシステム側で制御する必要がある
  (§2.4.1)。
- [paper] Premium storage 層への移行は COGS への影響が大きく、スナップショット
  非対応などの制約もあるため不採用 (§2.4.3)。

## System model & assumptions
- [paper] アーキテクチャ: Compute Primary + Secondaries(クエリ実行・クライアント
  対面)、Page Servers(disjoint なページ集合を所有し、log 適用で最新に保ち、Compute へ
  オンデマンド供給)、Log Service(トランザクションログ管理)、Azure Storage(blob と
  してページファイルを永続化)(§1, §2.1, Fig. 1)。最大 128TB (§1, §2.1)。
- [paper] 読みパスは階層評価: Compute RBPEX → (miss) PS へリモート呼出 → PS buffer
  pool → PS の SSD-backed RBPEX → (miss) Azure Storage (XStore) へリモート read (§2.3)。
- [paper] RBPEX (Resilient Buffer Pool Extension) は Compute と PS の両方に存在する
  recoverable な SSD キャッシュ。MTTR を大幅短縮(マシン再起動などの一過性障害では
  リモートからの rehydration 不要でローカル SSD から復旧)(§2.2, §2.3)。
- [paper] PS 上の RBPEX はローカル SSD ファイル(ページサイズ 8KB の倍数の固定長)で、
  ページのみ格納。メタデータ(論理 DB セグメント → ファイル内位置のマップ)は PS
  インスタンス内のトランザクショナルな in-memory Hekaton テーブルが権威ソース (§2.3)。
  Hekaton 統合により RBPEX への read IO はローカル SSD 直接 IO と同速 (§2.3)。
- [paper] Write-Behind は「covering RBPEX」(全データページをカバーするモード。
  部分キャッシュではない)への拡張として実装される (§4)。
- [paper] 制約: トランザクション意味論と Compute↔PS アクセスモデルは変更しない。
  変更対象は PS↔Azure Storage パスのみ (§1)。
- [paper] 故障モデル: (i) 一過性障害(再起動)はローカル RBPEX から高速復旧 (§2.3)、
  (ii) PS をホストする SQL server 障害 = in-memory 状態喪失 → Write-Behind Recovery で
  復旧 (§4.1)、(iii) Azure Storage の停止・性能劣化は write パスが RBPEX に分離されて
  いるため PS の通常動作を阻害しない (§2.4.2)。
- [paper] 復旧の正しさは不変量 LocalState ≥ RemoteState(RBPEX 側の log 適用・
  checkpoint 進捗 ≥ リモート側に永続化された進捗)の維持に依存する (§4.1.1, Fig. 8)。
- [paper] RAI の OldestLsn より古いログは保存不要とされる (Table 2)。
  [inference] 裏返すと、write-behind の遅延分(RemoteState〜LocalState 間)のログは
  Log Service 側で保持され続ける前提であり、遅延が大きいほどログ保持コストが増える。
  Table 4 では 210GB 級の遅延が観測されており、この保持コストは本文で定量化されて
  いない。
- [inference] 耐久性モデルの暗黙の仮定: write-behind 有効時、remote 未反映ページの
  永続性は「PS ローカル SSD 上の RBPEX + Log Service のログ」の組に依存する。RBPEX
  (ローカル SSD)とその PS が同時に失われた場合は Azure Storage の古い状態 +
  RemoteState からのログ再生で再構築する設計と読めるが、その再構築時間の議論はない。

## Approach
### 戦略1: 論理-物理ファイル分離(file anatomization / Storage V2)
- [paper] 4段階の分割: ①1論理ファイルを file-slice 群に分割し各 slice を個別 PS が
  ホスト、②slice を cell に、cell を stripe に分割、③データは複数 stripe を跨いで
  ラウンドロビンの stride 単位で書かれ、④endpoint mapping により1論理ファイルを
  複数 PS に分散 (§3)。
- [paper] **Cell** = 新アーキテクチャの不可分ストレージ単位(旧来はこの役割が blob)。
  固定数の stripe から成り、各 stripe は均一サイズで別々の blob に格納。典型構成は
  StripeCount 4 / StripeSize 4GB / IOStride 1024KB で cell 合計 16GB。sequential write は
  1MB 境界で次の stride へ切替。stride 境界を跨ぐ IO は read/write の分割・結合が必要
  (§3.1, Table 1)。
- [paper] **Stripe** は単独では解釈不能: cell 内データは stride 粒度でラウンドロビンに
  interleave され、各 stripe は論理アドレス空間の N 個おきの断片のみを持つ。cell
  メタデータと他の stripe が揃って初めて論理ページ順を再構成できる(IO 並列性のための
  設計上の相互依存)(§3.2)。各 stripe は独自の 500 IO 上限を持つ blob に対応するため、
  stripe 数に応じて合計スループット上限が上がる (§2.4.3)。
- [paper] **Stride**: ラウンドロビン書込により read-ahead が毎 stride 異なる stripe を
  使うため読み性能に有利 (§3.3, Fig. 4)。stride 長は「十分長い read run」を確保して
  IO 分割・結合の頻度を抑えるよう選ばれる (§3.1)。
- [paper] **Slice** = SQL 論理ファイル内の連続レンジで、単一 PS が所有。Compute は
  connection map を引いてページを含む slice のホスト PS へ要求をルーティング (§3.4)。
  Slice = cells + メタデータ: メタデータブロックは JSON 文書で、cell 配列(cell 構成
  値と stripe の実位置 F1..F4)に加え、上に載る foreign file の属性(DB checkpoint
  関連情報)を保持。論理ファイルの Global File Header (GFH) も slice メタデータ
  ブロックに移設(任意サイズのファイルを等サイズ cell 列に分割すると slice ごとの
  ヘッダページを維持できないため)(§3.4, Fig. 5, Fig. 6)。
- [paper] 効果の説明: 各 PS の所有データが小さくなるため PS 再作成が大幅高速化し、
  log-redo も高速化(所有外ページへの変更は無視できる)(§2.4.1, §3.5.1)。write は
  複数 stripe/cell に分散され、個別 blob の一過性スローダウンの影響を緩和 (§3.5.2)。
  小ブロック write の並列化で単一点 IO 飽和を排除し、集約スループットは stripe 数に
  ほぼ線形にスケール(ネットワーク帯域や CPU など他のボトルネックが支配的になる
  まで)(§3.5.3)。

### 戦略2: Write-Behind RBPEX
- [paper] 中心アイデア: RBPEX が write IO を Azure Storage blob へ即時転送するのを
  やめ、in-memory バッファ(dirty-page bitmap。1 bit = 1 ページ)で「RBPEX には
  書かれたが Azure Storage 未反映」のページを追跡し、背景プロセスが非同期に RBPEX →
  blob へ移送する。これによりローカル checkpoint(buffer pool → RBPEX)とリモート
  checkpoint(RBPEX → Azure Storage)が分離される (§2.3, Fig. 3, §4, §4.1.1)。
- [paper] 構成要素は2つ: Write-behind Checkpoint(RBPEX → foreign file への flush
  専用スレッド)と Write-behind Recovery(PS ホストの SQL server 障害で in-memory
  状態を失った際に起動)(§4.1)。
- [paper] メタデータ管理: per-database で local log-apply メタデータ(RBPEX への
  ローカル checkpoint 進捗)と remote log-apply メタデータ(リモートファイルへの
  foreign checkpoint 進捗)を追跡。checkpoint 関連情報(foreign redo LSN /
  timestamp 等)は GFH に格納され、RBPEX 上の Hekaton テーブル = RBPEX-level Apply
  Information (RAI) にローカル版を保持。RAI の内容は AppliedLsn(永続化済ページは
  全て PageLSN ≥ AppliedLsn)、AppliedTime(スナップショット用)、OldestLsn(これより
  古いログは保存不要)、FileSize (§4.1.1, Table 2)。
- [paper] Checkpoint の順序規律: RAI は LocalState と RemoteState の2状態を持つ。
  ①現在の LocalState をスナップショット → ②その値でページ更新を Azure Storage へ
  flush → ③GFH を更新 → ④成功後に初めて RemoteState を更新。この順序が不変量
  LocalState ≥ RemoteState を保証し、復旧の成功とページ非破損の根拠になる
  (§4.1.1, Fig. 8)。
- [paper] Flush の並行性制御はページラッチを使わず bitmap で行う: checkpoint
  スレッドは RAI を読み、page modified bitmap を走査して一部の bit ずつ取り出し、
  動的サイズのチャンクで Azure Storage へ送る。IO エラー時は該当 bit を modified
  bitmap に戻して再 write 対象に残す (§4.1.1)。
- [paper] ラッチ回避のため3+1種の bitmap を併用: PagesInReadIO(write-behind
  スレッドの read 中ページ)、PagesInDoubt(RBPEX への write 進行中ページ)、
  PagesModified(write 完了時に InDoubt から移される)、PagesReadFailedIO(read 完了後も
  ReadIO bit が立っていた競合ページ)。read 完了後に ReadFailedIO / InDoubt を確認して
  必要なら read リトライ。これにより同一ページへの foreign redo と干渉せずに
  write-behind スレッドの read を発行できる (§4.1.1)。
- [paper] 全 dirty page の flush 完了後、GFH と checkpoint メタデータを更新・永続化
  して checkpoint を確定する (§4.1.1)。定期プロセスが RBPEX と Azure Storage 間の
  dirty page を同期し、local applied LSN までのページの bit をクリアして bitmap を
  リフレッシュする (§4.1.1)。
- [paper] Recovery は RBPEX local recovery と Write-Behind recovery に分離され、独立・
  並行に実行される (§4.1.2, Fig. 9)。local recovery はリモート RAI から foreign redo
  情報をロードし、LocalState を使ってログ適用の再開点を決めて PS のローカルキャッシュを
  DB 状態に追随させる。Write-Behind recovery は、まずリモート GFH を照会して
  RemoteState を同期(GFH が先行していれば追随)した後、startLSN = RemoteState、
  endLSN = LocalState のログスキャンを実行し、その範囲のページ更新に対応する bit を
  dirty page bitmap に立てる — ただしログは適用しない(RBPEX は該当範囲について
  既に最新のため)。通常のログスキャンは local RAI を起点に適用を再開する (§4.1.2)。
  完了後、write-behind checkpoint スレッドが通常サイクルを再開する (§4.1.2)。
- [paper] 要約された効果: 同期二重書きの排除で write レイテンシ短縮・スループット向上、
  IO 集約で Azure Storage への write 数削減と blob write 競合低下(結果として同時負荷
  下の GetPage read サービス改善)、Azure Storage の停止・遅延中も PS 動作を継続
  (耐久性は非妥協と主張)(§1, §4.1.2)。

## Evaluation
- Setup [paper]: 指標は「Azure Storage 上の IOPS」と「ワークロード実行中の Azure
  Storage スループット」の2つ。構成は4通り: baseline / 論理-物理分離のみ /
  Write-Behind のみ / 両方 (§5.1)。ワークロードは (i) HammerDB による TPC-C:
  8000 warehouse(約 1TB)、32 v-core Compute、256 仮想ユーザで 60 分、
  (ii) CDB(Microsoft の Cloud Database Benchmark。6 テーブルの合成ワークロード、
  1TB、32 v-core レプリカ)。PS に頻繁なページ更新を起こさせる update 重・read 集中の
  設計 (§5.1)。
- Headline numbers (Table 3, §5.1):
  - Baseline: TPC-C 6717 IOPS / 60.47 MB/s、CDB 7724 IOPS / 85.67 MB/s。
  - 分離のみ(8 slice): TPC-C 合計 7632 [954/slice = baseline 比 85.8% 削減/slice]、
    CDB 8504 [1063/slice = 82.3% 削減/slice]。
  - Write-Behind のみ: TPC-C 3874、CDB 3958(IO 集約が単独では最大の削減要因)。
  - 両方: TPC-C 2752 [344/slice] / 67.46 MB/s、CDB 2880 [360/slice] / 95.04 MB/s。
  - 論文の解釈: IOPS は低いほど良い(スロットリング回避)。各改善の追加で IOPS が
    下がり、併用時が最良 (§5.1)。
- [paper] Compute → PS の最大 read レイテンシも改善 (Fig. 10)。理由の説明: IO 分離で
  write が RBPEX 上で速く harden し、分離ストライピングで read が進行中 write と
  衝突しない (§5.1 末尾, Fig. 10)。
- [paper] Production 耐障害実績 (Table 4): Azure Storage の計画外障害中、約 365 台の
  PS で Write-Behind checkpoint が遅延(遅延量の分布: 30–60GB が 155 台、60–90GB が
  79 台、90–120GB が 29 台、120–150GB が 39 台、150–180GB が 61 台、180–210GB が
  2 台)しながら、PS は自身の RBPEX へのログ適用を続けて可用であり続けた (§5, Table 4)。
- [inference] 評価がカバーしていないもの:
  - エンドツーエンドのトランザクション性能(TPC-C の tpmC、レイテンシ分布)が無い。
    報告されるのはストレージ層の IOPS / MB/s と Fig. 10 の read レイテンシのみで、
    顧客可視のスループット向上幅は読み取れない。
  - §3.5.1 が主張する「replica 再作成の高速化」「seeding 時間短縮」の実測値が無い
    (旧構成で「数時間」(§2.4.1) との対比になる数字が示されていない)。
  - スナップショット/PITR 性能への効果(動機の一角、§1, §2.4)は未測定。
  - Table 4 は遅延量の分布のみで、障害の継続時間・復旧後のキャッチアップ時間・
    その間のログ保持量への影響が無い。
  - 分離のみの構成で合計 IOPS が baseline より増える(6717→7632、7724→8504)理由の
    分析が無い(per-slice の削減のみ強調される)。stride 境界での IO 分割 (§3.1) が
    寄与している可能性があるが本文に説明は無い。
  - cell 構成(4×4GB、1MB stride、Table 1)は単一設定のみで感度分析が無い。
  - Premium storage(却下された代替案、§2.4.3)とのコスト・性能比較の定量値は無い。

## Limitations
- Stated [paper]:
  - 新最適化が対処するのは性能変動であり、完全な fault isolation ではない。blob の
    完全な可用性喪失は依然 write 可用性に影響しうる (§3.5.2)。
  - ストライピングによる集約スループットの線形スケールは、ネットワーク帯域や CPU 等
    他のボトルネックが支配的になる点まで (§3.5.3)。
  - Azure Storage 自体は受容可能な価格でのスループット・レイテンシ保証が無い
    ストレージであり続ける (§2.2)。
  - Future work として hot/cold ストレージ階層の分化(COGS 削減目的)が残る (§7)。
- Inferred [inference]:
  - Write-behind は「リモート未反映ページがローカル SSD にのみ存在する」時間窓を
    意図的に広げる。Table 4 の実績では 210GB 級の遅延が生じており、この間の耐久性は
    RBPEX(単一 PS のローカル SSD)+ Log Service のログ保持に依存する。PS の SSD
    喪失と Azure Storage 遅延が重なった場合の再構築時間・ログ再生量は分析されて
    いない(OldestLsn の意味 (Table 2) から、遅延分のログ保持が必須になるはず)。
  - bitmap ベースのラッチフリー flush 協調 (§4.1.1) は4種の bitmap とリトライ規則の
    組合せで正しさを担保するが、本文の記述は手順の列挙であり、競合順序の網羅的な
    正当性議論(または形式的検証)は示されていない。
  - 1論理ファイルを 8 slice に分けると管理対象 blob 数は stripe 分(cell あたり 4)
    倍増し、slice ごとの JSON メタデータブロックも増える。メタデータ管理・
    スナップショット対象オブジェクト数の増加という運用コストは論じられていない。
  - 効果測定は Microsoft 内部ベンチマーク(CDB)と自社基盤上の TPC-C のみで、
    構成の詳細(Azure Storage の冗長構成、PS 台数、リージョン)が部分的にしか
    開示されておらず、外部再現は不可能(産業報告としては通例だが)。

## Relations
- [[2026-sigmod-arkhangelskiy-aurora-limitless.md]](Aurora Limitless): 同じ SIGMOD
  Companion のクラウドベンダ製 production OLTP 報告。本論文 §6 は Aurora(SIGMOD'17/18
  の quorum ベースストレージ + redo オフロード)を明示的に対比し、Hyperscale は
  quorum/共有メモリ協調ではなく「並列化(ストライピング)と分離(write-behind)」で
  スケールする設計選択だと位置付ける (§6)。Aurora Limitless 側は水平スケール
  (router + シャード)の話であり、ストレージ層の対比は Aurora'17 論文経由の間接的な
  ものである点に注意。
- [[2026-pvldb-kuschewski-btrlog.md]](BtrLog): 構図が対になる — BtrLog は WAL を
  ローカル NVMe にステージングして非同期に S3 へ退避、本論文はデータページを
  ローカル SSD (RBPEX) に harden して非同期に Azure Storage へ反映 (§4)。
  「安価だが保証の無いリモートストレージ (§2.2) をローカル永続層 + 非同期背景転送で
  覆う」というクラウド DB の共通パターンの、ログ側とページ側の実例。
- [[2026-sigmod-chen-cloudjump3.md]](CloudJump III): DB カーネル内でローカル SSD /
  リモートストレージの階層配置を制御する engine-integrated 設計という点で同型。
  本論文の future work(hot/cold 階層の分化による COGS 最適化、§7)は CloudJump III が
  既に扱う領域に踏み込む予告であり、Azure 側の後続報告と比較する価値がある。
- [[2026-icdew-park-hotpage-checkpointing.md]](hotpage checkpointing): checkpoint の
  冗長 writeback 削減という共通テーマ。本論文の Write-Behind bitmap は flush までに
  同一ページが複数回 dirty になっても remote write を1回に集約する (§4.1.1) 点で、
  hot page の flush 遅延と同じ効果をリモート IO 層で得ている。[inference] 「どの層で
  writeback を抑制するか(buffer pool vs SSD キャッシュ→リモート)」という設計軸で
  対比できる。
- [[2026-edbt-krause-disaggregated-survey.md]](disaggregated survey): 同 survey が
  第1部で構造化する「産業界のストレージ分離の歴史」の 2026 年時点の現在地。
  Socrates(本論文 ref [2]、Hyperscale の原型)からの進化の実データ点として接続する。
- [[2026-pvldb-zhang-terark-ds.md]](Terark-DS): compute-storage 分離環境での
  リモート IO 起因の性能問題への産業側対処という主題レベルの共通性(あちらは
  LSM/KV、こちらは page-based SQL DBMS の storage tier)。abstract 時点の推測より
  つながりは浅く、直接の技術的対応関係は無い。

## Idea seeds
- [inference] **Write-behind lag の一級市民化**: Table 4 は障害時の lag 分布
  (30–210GB)を示すが、lag とログ保持コスト・キャッチアップ時間・再 seeding
  リスクの関係は未分析。lag に上限を課す適応的スロットリング(lag が閾値を超えたら
  ローカル checkpoint を減速)の設計空間は開いているように見える。最初の検証:
  write-behind を模したシミュレータ(ローカル SSD + 帯域制限付きリモート)で、
  lag サイズ vs ログ再生キャッチアップ時間の関係を測る。
- [question] 分離のみの構成で Azure Storage への合計 IOPS が増える(Table 3:
  TPC-C 6717→7632)のはなぜか。スロットリング解消でより多くの IO が通るためか、
  stride 境界での IO 分割 (§3.1) のためか、本文に説明が無い。検証: ストライピング
  有無で IO 分割・結合回数を数えるマイクロベンチマーク(MinIO 等の blob 互換
  ストアで stride/stripe をパラメタ化して再現)。
- [inference] **「どの IO パスをローカル化/非同期化したか」の系統比較**(abstract-only
  時代の seed の更新版): 本論文はページ側 (PS↔Azure Storage) のみを対象とし、
  Log Service 側と Compute↔PS 側は明示的にスコープ外 (§1)。BtrLog(ログ)・
  CloudJump III(tiering)・本論文(ページ)を「同期リモート IO がまだ残っている
  パス」で表にすると、Compute↔PS 境界の GetPage レイテンシ(Fig. 10 で改善はするが
  依然リモート)が残余ボトルネックとして浮かぶ。検証: ideas/ に比較表を起こし、
  各システムの未カバー IO パスを列挙する。
- [question] §4.1.1 の4-bitmap 協調(PagesInReadIO / PagesInDoubt / PagesModified /
  PagesReadFailedIO + リトライ)は、foreign redo との競合下で lost update や stale
  read を全ケースで防げるのか。本文は手順の記述のみで正当性議論が無い。小さな
  TLA+ モデル(ページ1枚 + redo/write-behind/checkpoint の3プロセス)で不変量
  LocalState ≥ RemoteState とページ整合性を検査するのは低コストな最初の一歩。

## Changelog
- 2026-07-06: created (status: abstract-only)
- 2026-07-06: full-text 格上げ(status: abstract-only → read。手動取得した PDF 全文を読解し全節を執筆)
