---
title: "A Multi-tenant Relational OLTP Database at Salesforce"
authors: [Vaibhav Arora, Subho Chatterjee, Terry Chong, Thomas Fanghaenel, Pat Helland, Jamie Martin, Kaushal Mittal, Nat Wyatt]
venue: "CIDR '26 (16th Annual Conference on Innovative Data Systems Research)"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/cidr/AroraCCFHMMW26"}
urls: {paper: "https://vldb.org/cidrdb/2026/a-multi-tenant-relational-oltp-database-at-salesforce.html", pdf: "literature/pdfs/2026-cidr-arora-salesforce-oltp.pdf", code: ""}
status: read
read_date: 2026-07-06
tags: [lsm-tree, oltp, multi-tenant, secondary-index, range-filter, tombstone, compaction, mvcc, production-system, shared-storage]
---

## TL;DR
Salesforce の multi-tenant CRM を支える自社 RDBMS「SalesforceDB」(Postgres fork +
LSM ストレージ)で、read-dominated な OLTP ワークロードに対する LSM 読み取り性能を
改善する本番投入済みの3技法を報告する産業論文。① location cache(secondary index →
base table のルックアップを LSM 多段プローブから数百 ns の直接参照に短縮)、
② CRaFT(SuRF 系トライ range filter をデータファイル内に分割永続化。レベル横断
スキャンの 86.45% をフィルタ)、③ early tombstone pruning + tombstone-aware
compaction(トンブストーンの 61% を最下層到達前に除去)。全て production fleet の
実トラフィック計測で効果を示す。

## Problem & motivation
- [paper] Salesforce は multi-tenant CRM ワークロードをベンダー DB で回すことが
  困難になり、public cloud 移行と併せて自社 RDBMS を開発。アーキテクチャは
  「Postgres の fork + LSM ストレージ/アクセス」(§1, p.1)。
- [paper] LSM を選んだ理由: immutable data file が update-in-place を排除し、
  shared storage 構成でのノード間協調を減らし、B-tree split・ページ更新起因の
  破損/並行性ボトルネックのクラスを丸ごと除去し、POSIX 準拠でない S3 のような
  単純ストレージ IF を使え、multi-tenancy のユースケースを助けるため(§1, p.1)。
- [paper] しかしワークロードは read-dominated(single-record probe + range scan)で、
  LSM の多レベル構造が読みに不利(§1, p.1)。具体的な3課題:
  1. non-covered index scan: index entry → base table record のフェッチが LSM
     レベル横断のプローブになり高コスト。インデックスの利点を減殺(§1, p.1)。
  2. short-range scan: スキャン結果の処理ではなく「スキャン開始位置の特定」
     (レベルごとのスキャンセットアップ)がコストを支配。多くのサブスキャンが
     0 行を返すのにセットアップ費だけ払う(§1, p.1-2)。
  3. queue-organized table のトンブストーン: dequeue が過去の削除の
     トンブストーン群をスキャンして読み飛ばすため時間とともに劣化(§1, p.2)。
- [paper] Bloom filter・fence pointer・leveled compaction という既知の読み最適化は
  導入済みだが、これらのワークロードには不十分(abstract, §1, p.1)。

## System model & assumptions
- [paper] ワークロード: 極めて多様で read-heavy。大量の小さな read-write
  トランザクション+一部の大きなトランザクション+リアルタイム分析+ページロード/
  API 向けの大量の targeted operational query。顧客が書く SOQL クエリを SQL に変換して
  object-relational platform 上で実行(§2.1, p.2)。
- [paper] スキーマ特性: secondary index を多用。カラム数が非常に多い wide table が
  存在し index access の恩恵が大きい(§1, p.1; §3, p.2)。
- [paper] ストレージモデル: multi-tenant データベース全体を **単一の LSM** に格納し、
  リレーショナルデータを key-value に写像。base table と index は別リレーション
  (standalone secondary index)として同じ LSM に格納。base/index とも
  index-organized table。index key は「index カラム値 + 対応 base 行の主キー」の
  composite key(§1 p.1, §2.2, §3, p.2-3)。index は eager に維持され、読み時の
  追加検証を避ける(§7, p.7)。
- [paper] LSM 構成: read 最適化の leveled LSM、fanout 5・8 レベル。partial compaction を
  採用し、compaction プロセスはレベルごとにクラスタ内の複数ノードで実行
  (水平スケール)(§2.2, p.2)。
- [paper] データファイル(SSTable)は 2GB、64KB 固定サイズブロックに分割。
  data blocks / block index / Bloom filter blocks / CRaFT range-filter blocks /
  trailer block(メタデータ)から成る(§2.2, Fig. 1, p.2)。ブロック内はスロットに
  key 順で格納され slot directory で二分探索可能(§2.2, p.2)。
- [paper] 各ノードは interval-tree ベースの in-memory index でキー(範囲)に重なる
  データファイルを特定し、64KB ブロック単位の read-only block cache を持つ(§2.2, p.2)。
- [paper] 一貫性: MVCC をサポートし、全ての read は特定 snapshot 時点として実行
  (§1, p.1; §3, p.3)。
- [paper] 規模: DB サイズは数十〜数百 TB を想定し、3技法ともこの規模にスケール
  することが設計要件(§1, p.2; §4, p.4)。
- [paper] queue-organized table: メッセージを priority と FIFO(到着順)で処理する
  ためにアプリが多用。レコード寿命が短く turnover が激しい。delete は削除マーカー付き
  の新バージョン(tombstone record)を追記する方式(§5, p.5)。
- [inference] 障害モデル・レプリケーション・トランザクション処理(CC プロトコル)の
  詳細は本論文には書かれていない(「journey の詳細は別発表」と明言 §1, p.1)。
  本論文は read 最適化3点に意図的にスコープを絞った産業報告である。
- [inference] 「単一 LSM に全テナント」という設計は、テナントごとの物理分離ではなく
  キー空間内の論理分離を意味するはずだが、テナント分離(セキュリティ・per-tenant
  キー配置)の機構は本文に記述がない。

## Approach

### 1. Location cache(§3)
- [paper] 課題: LSM では index→base lookup が DB サイズに対数的
  (interval-tree 探索 → 各レベルで block index 探索 → ブロック内探索、を複数レベルで
  実行)。RID による直接ポインタ参照ができる従来型 DB と対照的(§3, p.3)。
- [paper] 解: 主キー → 「最新版レコードの物理位置(data file, block, slot)」を持つ
  in-memory の direct-key lookup cache。主キーをハッシュして固定長 location descriptor
  (64-bit)の単純配列を引く。ハッシュ衝突による false positive は、指した先の
  レコードキーと照合して排除(§3, Fig. 2, p.3)。ヒットすれば対数的操作を全て回避し、
  secondary index 経由のレンジアクセスが線形時間になる(§3, p.3)。
- [paper] キャッシュはミス時(フル LSM プローブ後)に populate。指すのは永続化済みの
  最新版のみで、それより古い版を読むケースは恩恵を受けないが少数派
  (最下層ほどデータが多く compaction 頻度=位置変化頻度が低いため)(§3, p.3)。
- [paper] 読み取りは同期フリー: populate/invalidate 側だけが同期し、即時挿入できない
  read は populate をスキップする(ブロックしない)。read は snapshot 指定付きなので、
  読んだ後にレコードの snapshot 妥当性を無協調で検証できる(§3, p.3)。
- [paper] invalidation: flush 時は新規書込レコード分のみ即時無効化。compaction は
  位置だけ変え内容を変えないので、旧ファイルが recycle される前であれば **lazy** に
  無効化してよい。ファイルの GC 時にキャッシュをスキャンして一括無効化
  (SIMD 利用、descriptor が 64-bit 固定なので高速)(§3, p.3)。
- [paper] サイズは block cache サイズの関数として設定。location cache ヒットの大半は
  block cache 内ブロックを指すため物理 I/O を伴わず、フルレコード像を持つ必要がない
  (block cache との相乗効果)。経験的に block cache の 10% で hit ratio 75% 超
  (§3, p.3)。
- [paper] memory-resident なワークロードでは、ヒット時にプロセッサキャッシュミスが
  250 超→10 未満になり、key lookup が 10-15 µs → 数百 ns に短縮(§3, p.3)。

### 2. CRaFT range filter(§4)
- [paper] 課題: index nested loop join 等で、0〜1 行しか返さない inner scan が大量発生。
  スキャンの3段階(該当ファイル特定 / block index 二分探索によるスキャンセットアップ /
  データブロック走査+レベル間マージ)のうち Step 2 が支配的で、L0 ファイルは
  キー空間が広く多くのレンジと重なるため無駄なセットアップが頻発(§4, p.4)。
- [paper] 解: データファイルごとの range filter「CRaFT」(Counting and Range Filter
  Tries; p.2 では Counting Range Filter Tries 表記)。SuRF の LOUDS トライ符号化を
  採用し、可変長キー・可変長クエリをサポート(SalesforceDB の要件)(§4, p.4)。
- [paper] 永続化設計が肝: フィルタを 64KB 固定サイズブロックに分割してデータファイル
  自体に埋め込む。①フィルタとデータの永続化が一体化し、特別なメモリ管理・補助
  永続化物・追加リカバリ処理が不要、② block cache に必要なブロックだけ載せられる
  (TB 級 DB で in-memory filter は不成立)、③ immutable file 単位なので更新との協調が
  不要(global filter との差)(§4, p.4)。
- [paper] 2 レベル構造: CRaFT metadata block(各トライパーティションの StartKey・
  パーティション番号・キー数・対応する block index の開始/終了ブロック番号を持つ
  sorted array)+ 独立トライの CRaFT trie block 群(LOUDS-Sparse: LOUDS/Has-Child
  bit vector、Label/Suffix vector、トライノード数 n・prefix ノード数 m・Rank/Select
  メタデータをブロック内に永続化)。1 ファイルあたり metadata 1〜2 ブロック +
  数百 trie ブロックが典型(§4, §4.1, p.4; Fig. 3, Fig. 4, p.5)。
- [paper] 構築: flush/compaction でのファイル生成時、キーがソート順に届くことを利用し
  前後キーから prefix/suffix を決定(トライの root からの navigate 不要)。トライが
  ブロックサイズを超えたら Rank/Select を確定して永続化し metadata に追記(§4.2, p.5)。
- [paper] クエリ: metadata 上の二分探索で startKey/stopKey の属するパーティションを
  特定。別パーティションに跨がれば range は存在。同一パーティションなら SuRF 同様の
  bit vector 走査で判定。不在ならそのファイルのスキャンを丸ごと回避、存在するなら
  metadata の block index 範囲でセットアップの探索範囲を絞る(存在時も無駄にならない)
  (§4.3, p.5)。false positive はあるが false negative はない(§4, p.4)。
- [paper] CRaFT はレンジ内キー数(count)も返し、compaction でレベル間のキー範囲
  重複を見積もって compaction 対象キー空間の選択に使う(詳細はスコープ外)(§4, p.4)。

### 3. Early tombstone pruning + tombstone-aware compaction(§5)
- [paper] 課題: 伝統的 LSM ではトンブストーンは最下層に到達するまで除去できず、
  大規模 DB では長時間残留。dequeue(最古 K 件のスキャン→処理→削除)が過去の
  トンブストーンを大量に読み飛ばし、その dequeue 自体がさらにトンブストーンを追加
  して悪化する(§5, p.5; Fig. 5, p.6)。
- [paper] Early tombstone pruning: SQL 意味論により INSERT 実行時の存在チェックの
  副産物として「このバージョンがそのキーの初期(最古)バージョンである」ことが分かる。
  このメタデータを維持し、compaction 時に「初期レコード〜対応トンブストーン」の
  バージョンチェーン全体が揃えば、**最下層でなくても任意のレベルで** チェーンごと
  破棄できる(従来 LSM compaction からの大きな逸脱と自己評価)(§5.1, Fig. 6,
  Fig. 7, p.6)。短命レコードがツリー深部へ伝播することを防ぐ(§5.1, p.6)。
- [paper] Tombstone-aware compaction policy: データファイルごとのトンブストーン数を
  trailer block に永続化し、閾値ベースのトリガでトンブストーン密度の高いキー範囲の
  compaction を優先。トンブストーン情報がデータファイル内にあるため、複数ノードで
  実行される compaction からアクセスでき、DB サイズにスケールする(§5.2, p.6)。
- [paper] 両者は相乗的: aware compaction がトンブストーンを早く下層へ押し込んで
  初期レコードに出会わせ、early pruning がその場で除去する(§5.2, p.6)。

## Evaluation
- Setup [paper]: production クラスタ群で実トラフィックを処理中の DB から週次
  (1 週間の実行期間)で収集した定期メトリクスを集計。3技法は個別ベンチマーク済み
  だが、本論文はデフォルト設定(3技法すべて有効)の大規模 production fleet 横断の
  実測を示す(§6, p.6-7)。結論部では「数千の DB インスタンスからの計測」と記述
  (§8, p.8)。
- [paper] Location cache: block cache 640GB に対し location cache 64GB(本文は
  「10% of the block size」と表記 — [inference] 前後関係から block cache size の
  誤記と思われる)。時間平均ヒット率は p50 78% / p90 56% / p95 45%。index→base
  lookup はキャッシュ非経由の平均 13.5 µs に対し、経由時は数百 ns(§6.1, p.7)。
- [paper] CRaFT: LSM レベル横断の 4,170 億スキャンのうち 86.45% を CRaFT が
  フィルタ。L0 ではスキャンの 95.34% が空でフィルタされた。false positive 率は
  全レベルで 4.17%。マイクロベンチマークでは in-memory ワークロードで空データ
  ファイルのスキャン時間を 30% 削減(§6.2, p.7)。
- [paper] トンブストーン2技法の組合せで、全テーブル・インデックス平均で
  トンブストーンの 61% が最下層到達前に prune された(§6.3, p.7)。
- [inference] 評価が示していないもの:
  - エンドツーエンドのクエリレイテンシ/スループット改善(TPC-C 等の統制された
    ベンチマークも、技法 ON/OFF の A/B 比較も無い)。提示されるのは各技法の
    内部メトリクス(ヒット率・フィルタ率・prune 率)のみ。
  - コスト側の計測: CRaFT の構築コスト・ファイルサイズ増、location cache の
    invalidation コスト、tombstone-aware compaction による write amplification の
    増加はいずれも数値が無い。
  - 他システム・他手法(SlimDB/Chucky/GRF/Next 等 §7 で定性比較したもの)との
    定量比較は無い。
  - ヒット率のパーセンタイル(p50 78% > p90 56% > p95 45%)の意味は本文に定義が
    なく、低ヒット率テール側の分布と読めるが「robustness を示す」という主張の
    根拠としては解釈が開いている。[question] このパーセンタイルは何の分布の
    どちら側の裾か(インスタンス横断? 時間横断?)。

## Limitations
- Stated [paper]:
  - location cache のサイジングはそれ自体一つのテーマで、将来のワークロードでは
    異なるサイズが適切になり得る(§3, p.3)。
  - location cache は永続化済み最新版のみを指し、古い版の読みには効かない
    (少数派と主張)(§3, p.3)。
  - CRaFT の count を使った compaction 誘導の詳細はスコープ外(§4, p.4)。
  - システム全体の journey の詳細は別発表予定であり、本論文は読み最適化技法に限定
    (§1, p.1)。
- Inferred [inference]:
  - early tombstone pruning は「INSERT 時の存在チェックの副産物で初期バージョンを
    識別できる」という SQL 意味論に依存する(§5.1)。存在チェックを伴わない
    blind write / upsert 中心の API(純 KV 的インタフェース)には移植しにくい。
  - MVCC で任意 snapshot 読みを許す以上、チェーン破棄は「どの snapshot からも
    不可視」であることが前提のはず(§5.1 の pruning 定義は 'no longer accessible
    to queries' とだけ言う)。長寿命 snapshot(分析クエリ等)が early pruning を
    どれだけ阻害するかは論じられていない。
  - location cache の正しさは「旧ファイルが invalidation 前に recycle されない」
    という GC との順序保証に依存(§3)。cross-node compaction 環境でこの保証を
    どう強制するかの機構は記述がない。
  - フィルタ率 86.45% やヒット率 78% は fleet 集計値であり、テナント間・
    ワークロード間の分散(multi-tenant 論文なのにテナント別の内訳が無い)は不明。

## Relations
- [paper] 関連技術との対比(§7, p.7-8): Next(index を base と同一 SSTable に埋込 +
  in-memory global index)に対し、location cache は index 構築の容易さと
  リカバリ不要性で優位と主張。SlimDB/Chucky(cuckoo ベース global filter)に対しては
  「filter の置換ではなく cache」である点(全キー保持不要・更新破棄可能・lazy
  invalidation・衝突リスト不要)を差別化。GRF は partial merge policy と併用不可。
  SuRF/DIVA/ARF 系トライフィルタは in-memory 設計で TB 級には不適、CRaFT は
  その永続化・ブロック分割版。RocksDB partitioned index/filter は同様の2レベル構造。
  Lethe は TTL ベース、SalesforceDB は密度ベースのトンブストーントリガ。RocksDB
  single-delete は単一版限定で、チェーン全体に暗黙適用される early pruning より
  汎用性が低いと主張。
- [[2026-pvldb-liu-arcekv.md]]: 同じく LSM compaction 政策の研究。SalesforceDB の
  tombstone-aware compaction(密度トリガ+キー範囲優先度)と CRaFT count による
  compaction 誘導は、compaction スケジューリング設計空間の産業側データ点として
  対比できる。
- [[2026-pvldb-zhang-terark-ds.md]]: 分離(shared)ストレージ上の LSM という
  アーキテクチャ文脈が共通。SalesforceDB は immutability による cross-node
  coordination 削減・S3 的インタフェース利用を LSM 採用理由に挙げており(§1)、
  分離ストレージ×LSM の設計動機の比較材料になる。

## Idea seeds
- [inference] CRaFT の「count を compaction のキー範囲重複推定に使う」(§4)は
  本論文でスコープ外とされた空白。range filter を compaction スケジューラの
  統計源として使う一般化(フィルタ=軽量ヒストグラム)は研究として切り出せる。
  検証: RocksDB の partitioned filter に key count を付与し、compaction picker を
  count ベースにして write amp / read amp のトレードオフを測る。
- [question] early tombstone pruning と長寿命 snapshot(HTAP・バックアップ・
  タイムトラベル読み)の干渉は定量化されていない。snapshot の pin 時間分布を
  変えながら「prune 可能率 61%」がどこまで落ちるかを測る実験は、delete-aware LSM
  (Lethe 系)研究の現実的な追試になる。
- [inference] location cache は「正確性を snapshot 検証で事後担保するから、
  キャッシュ自体は不整合を許容できる(populate 破棄・lazy invalidation)」という
  設計原理に立つ。この "validate-after-read で hint 構造の同期を全部省く" パターンを
  MVCC-LSM の他の補助構造(fence pointer キャッシュ、レベル別 zone map 等)へ
  一般化できないか。検証: オープンソース LSM に同型の 64-bit descriptor cache を
  実装し、invalidation 遅延を意図的に伸ばして誤ヒット時の検証コストと得られる
  ヒット率の関係を測る。

## Changelog
- 2026-07-06: created (status: read, CIDR 2026 公式 PDF 抽出テキスト全文を読解)
- 2026-07-06: 検証パスによる修正(Fig. 3/4 は p.5、Fig. 5 は p.6 に掲載のため、図のページ表記を本文参照ページと区別して修正。数値・システム名・主張は全件ソースと一致を確認)
