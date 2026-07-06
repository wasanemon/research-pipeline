---
title: "Cloudspecs: Cloud Hardware Evolution Through the Looking Glass"
authors: [Till Steinert, Maximilian Kuschewski, Viktor Leis]
venue: "CIDR '26 (16th Annual Conference on Innovative Data Systems Research)"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/cidr/SteinertKL26"}
urls: {paper: "https://vldb.org/cidrdb/2026/cloudspecs-cloud-hardware-evolution-through-the-looking-glass.html", pdf: "literature/pdfs/2026-cidr-steinert-cloudspecs.pdf", code: "https://github.com/TUM-DIS/cloudspecs/"}
status: read
read_date: 2026-07-06
tags: [cloud-economics, hardware-trends, instance-selection, cost-performance, aws, nvme, networking, graviton-arm, benchmarking, interactive-tools, duckdb]
---

## TL;DR
2015〜2025 の AWS を中心にクラウドハードウェアの進化をコスト正規化(性能/ドル)で
追跡した測定・分析論文。ネットワーク帯域はコスト正規化でも 10× 向上した一方、
CPU は約 3×(Graviton 抜きなら約 2×)、DRAM はほぼ停滞、NVMe の I/O 性能/ドルは
2016 年の i3 が今も最良という強い非対称を示す。加えて中小クラウドがハイパー
スケーラーをコモディティ VM で最大 5 倍下回る価格比較を提示し、ブラウザ内で
完結する対話的分析ツール Cloudspecs(DuckDB-WASM + WebR)を公開する。

## Problem & motivation
- [paper] データベースシステムのパブリッククラウド(AWS / Azure / GCP)への移行が
  進み、性能・スケーラビリティ・コストは利用可能なインスタンスタイプとその価格に
  制約される (§1)。
- [paper] クラウドで重要なのはピーク性能ではなく性能/ドル。CPU・RAM・SSD・
  ネットワークの相対価格次第で、キャッシュするべきか、compute / caching / storage
  層に分離(disaggregate)するべきかが変わる。コスト効率の良い設計にはクラウド
  ハードウェア地形の深い理解が要る (§1)。
- [paper] その地形は巨大かつ多次元: AWS のインスタンスタイプ数は 2015 年の 52 から
  1,057 に増加 (Fig. 1, §1)。Google Cloud は 400 超、Azure は 1,000 超 (§1)。
- [paper] 論文の目的は、現在のクラウド提供内容の分析と過去 10 年の進化の追跡に
  よってこの地形を「demystify」すること。主対象は最大手の AWS で、オンプレミス
  ハードウェアと他クラウドとも比較する。静的分析の限界を補うため対話的可視化
  ツール(https://cloudspecs.fyi)を提供する (§1)。図中のリンク記号は該当図の
  対話的再現インターフェースへのリンク (§1, p.1)。

## System model & assumptions
論文自体は測定・分析論文なので、ここでは「分析の前提と方法論」を列挙する。
- [paper] データソース: AWS の複数の重複・不完全な API / Web ページ(Describe
  Instances API、Price List API、インスタンスストレージ性能は Web ページのみ等)を
  統合。オープンソースの instances.vantage.sh クローラを、リリース日を持つ
  instancetyp.es 等で拡張し、キュレーション済みデータベースを全自動生成。データは
  2025 年 10 月時点 (§2)。
- [paper] ファミリーとスライス: AWS は同一物理サーバの「仮想スライス」を貸す
  (例: i3 の large〜16xlarge)。ファミリー内では価格とハードウェアがほぼ比例
  するため、コスト正規化指標(コア/ドル等)はファミリー内で等しい。等しくない
  指標(ネットワーク帯域等)は最大スライスを表示 (§2)。
- [paper] 対象選定: 一般的な DB ユースケースに焦点を当てるため、アクセラレータ /
  FPGA 付き(GPU の経済性は §2.5 で別扱い)と、共有 / オーバーコミット CPU の
  burstable t / flex インスタンスを除外。残りは 98 ファミリー 742 インスタンス
  (§2)。オンラインデータベースには全インスタンスが残る (§2)。
- [paper] 価格: us-east-1(最大かつ多くの場合最安のリージョン)の on-demand 価格で
  正規化。spot は短期変動が大きく、savings / reserved の割引率はインスタンス間で
  概ね一様なので、on-demand 使用は絶対額を一定係数過大評価するだけで価格構造は
  歪めない、と論じる (§2)。
- [paper] AWS は 2018 年以降どのインスタンスも on-demand 価格を下げておらず、
  変化は新インスタンス投入と旧型の緩やかな陳腐化で起きる (§2)。
- [paper] CPU 性能比較には自前ベンチマーク 3 種を使用: SPECint 2017、in-memory
  TPC-H(SF10、Umbra)、in-memory TPC-C(25 warehouses、Leanstore)。compute-
  optimized インスタンスの 2xlarge スライスで全ハードウェアスレッドを使用 (§2.1)。
  vCPU の意味はインスタンスにより異なる(多くの x86 = ハイパースレッド、全
  Graviton と c7a = 物理コア)(§2.1)。
- [inference] 「性能/ドル」はすべて名目ドルベース(on-demand 価格)であり、
  インフレ調整の有無は本文に記載がない。10 年スパンの「停滞」の程度は実質価格で
  見ると変わりうる。
- [question] 価格は us-east-1 のみで正規化しているが、リージョン間価格差(§2.6 で
  AWS DE が US 比 1.2× 高い例がある)がトレンド分析自体をどの程度動かすかは
  本文からは分からない。

## Approach & findings
分析論文なので「Approach」はトレンド分析の中身と知見を指す。

### CPU (§2.1)
- [paper] 最大インスタンス u7in-24tb.224xlarge は 448 コア。compute-optimized では
  c4(2015)の最大 18 コア → c7a(2023)の最大 192 コア(c7a.48xlarge)と 10 年で
  一桁増。ただしこれは性能/ドルの向上には直結しない (§2.1)。
- [paper] ベンダー多様化: Intel 単独から AMD・ARM ベースの AWS Graviton へ。
  2024 年以降、新規リリースの過半が Graviton (§2.1, Fig. 1)。
- [paper] c4 基準のコスト性能で、SPECint は 10 年で約 3× 改善。ただし大部分は
  Graviton 導入によるもので、それが無ければ 2× に近い。Snowflake 等の大手
  cloud-native システムが Graviton に移行しているのはこのため (§2.1, Fig. 2)。
- [paper] in-memory DB ベンチマーク(Umbra TPC-H / Leanstore TPC-C)の改善は
  さらに低く 2×〜2.5×。著者らは in-memory DB 性能がメモリ / キャッシュレイテンシに
  強く影響されるためと「推測」し、微視的アーキテクチャ分析は future work (§2.1, Fig. 2)。
- [paper] オンプレ比較: Moore の法則 + Dennard スケーリングが続いていれば 10 年で
  32×(5 回の倍増)のはず。AMD サーバ CPU(2017–2025)を定価・コア数・クロック・
  公表 IPC で分析すると AWS 内と同様の傾向(1.7×)であり、CPU コスト性能停滞は
  クラウド固有(ハイパースケーラーのマージン)ではなく技術的な地殻変動 =
  「Moore の法則の終わり」(§2.1)。

### Main memory (§2.2)
- [paper] コスト正規化 DRAM 容量はほぼ改善なし (Fig. 3)。唯一の大きな変化は 2016 年の
  memory-optimized(x プレフィックス)の追加で、最良の compute-optimized 比で約
  3.3× の GiB-hours/$。最大 32 TiB(u7in-32tb.224xlarge)の巨大インスタンスもあるが
  容量/ドルは x や r より著しく悪い (§2.2, Fig. 3)。
- [paper] メモリ帯域: AWS は仕様を公表しないため実測。単一 CPU ソケットの絶対帯域は
  93 GiB/s → 492 GiB/s(≈5×)だが、コスト正規化では 2× (§2.2, Fig. 5)。
- [paper] オンプレ比較: 過去 10 年でコモディティ DRAM 価格は約 3× 低下、オンプレの
  メモリ帯域/ドルも約 3× 改善。AWS のメモリ容量・帯域のコスト改善は非クラウドの
  サーバ市場の発展を「closely track」すると結論 (§2.2)。
- [question] Fig. 3 の本文記述は「コスト正規化 DRAM 容量はほとんど改善していない」で、
  オンプレは 3× 低下。これを「closely track」とまとめる §2.2 の結論との整合
  (2016 年の x 系 3.3× ジャンプを含めての比較なのか)は本文の記述だけでは
  一義に読めない。

### Networking (§2.3)
- [paper] 絶対帯域は 10 Gbit/s → 600 Gbit/s(60×)。コスト正規化でも 10× 改善。
  この改善は network-optimized(n サフィックス)インスタンスの導入によるもので、
  プロプライエタリな Nitro 仮想化技術に基づく最初の c5n は 2018 年 (§2.3, Fig. 4)。
- [paper] 非 network-optimized(c4, c5, c6a, c7g 等)のコスト正規化帯域はほぼ不変 (§2.3)。
- [paper] オンプレ比較: Mellanox の Ethernet NIC は 100 Gbit/s(ConnectX-4、2014)→
  400 Gbit/s(ConnectX-7、2022)。ただしデータセンターネットワーク機器(200GbE
  スイッチ等)の信頼できる現実的価格が見つからず、コスト正規化のオンプレ比較は
  不能。AWS が独自 Ethernet 技術を内製したのは経済的動機か、という問いを提起 (§2.3)。

### NVMe instance storage (§2.4)
- [paper] 現代の AWS インスタンスの多くは内蔵ストレージを持たずリモートブロック
  デバイス(EBS)に依存するが、本分析は NVMe SSD のインスタンスストレージに
  焦点を当てる(旧来ストレージより格段に速く DB に重要)(§2.4)。
- [paper] 初の NVMe ファミリー i3 は 2016 年、2025 年時点で 36 ファミリー。容量/ドルの
  断絶は 2019 年の i3en(最大 60 TB、容量/ドル 2 倍)のみで、以降は多数の新
  インスタンスにもかかわらずほぼ変化なし (§2.4, Fig. 6)。
- [paper] I/O 性能/ドルでは、2016 年導入の i3 が今なおほぼ 2× の差で最良。シーケンシャル
  リードスループットでもランダム 4KiB リードでも同様 (§2.4)。
- [paper] オンプレとの対比が顕著: 同期間にオンプレのコスト正規化 NVMe 容量は約 3×、
  I/O スループットは 5× 超改善。2018 年時点では AWS の NVMe は最先端だった
  (i3 vs Samsung PM983)が、2020 年以降オンプレは PCIe 4(Samsung PM1733)と
  PCIe 5(Kioxia CM7-R)で性能を 2 回倍増させた一方、AWS は停滞。1 デバイスの
  read IOPS 比較でギャップが拡大している (Fig. 7, §2.4)。発表済みの PCIe 6 世代
  (Micron 9650)はギャップをさらに広げる見込み (§2.4)。

### GPUs and accelerators (§2.5)
- [paper] CPU のコスト性能停滞はハードウェア特化が経済的になりうることを示唆。
  コスト正規化 FP32 演算で、GPU インスタンスは p3 → g6e で約 4.7× 改善 (Fig. 8, §2.5)。
- [paper] 2019 年以降 AWS は独自 ML アクセラレータ(ASIC)の inf / trn 系を 2 世代
  投入。trn2 はデバイスあたり FLOP/s が g6e の 2 倍、p3 比のコスト性能は 15.7× で、
  ハードウェア特化が現在有利であることを示す (Fig. 8, §2.5)。

### Cross-cloud comparison (§2.6)
- [paper] 参照構成(16 コア AMD CPU = 32 ハイパースレッド、128 GiB RAM、特殊機能
  なし)の税調整済み価格を米欧 7 クラウドで手動収集 (Table 1, §2.6)。
- [paper] Table 1(抜粋): AWS US m6a.8xlarge $1.3824/h、Google t2d-standard-32
  $1.3519、Azure D32as v5 $1.3760、AWS DE $1.6560、Oracle US $0.5920、STACKIT DE
  $1.5203、OVHCloud DE B3-128 $0.8554、Hetzner DE CCX53 $0.3548 (Table 1)。
- [paper] 三大ハイパースケーラーの価格・価格モデル・提供内容は互いに酷似(例外:
  AWS は c7gn/c8gn でネットワーク速度に優位、Azure は同一リージョン内 AZ 間通信が
  無料)(§2.6)。
- [paper] 「競争が基本インフラ価格を限界費用近くまで下げている」仮説は他クラウド
  との比較で反証される: Hetzner CCX53 は AWS m6a.8xlarge(us-east-1)比 3.9× 安く、
  AWS eu-central-1 比では 4.7×。Oracle と OVHCloud も大幅に安い。STACKIT は
  ハイパースケーラー水準 (§2.6)。abstract では「最大 5×」と要約 (abstract)。
- [paper] ただしハイパースケーラーには中小が真似しにくい利点(特化インスタンスの
  豊富さ、データセンター数)がある。中小は時間単位課金や低速ネットワークが多い。
  一方でハイパースケーラーの egress 課金は極端に高く、Hetzner の 20TB/月無料枠を
  無視しても AWS の egress はバイトあたり Hetzner の 50 倍 (§2.6)。

### Cloudspecs ツール (§3)
- [paper] 論文内の静的分析の限界を補う、オープンソースの対話的データ探索・可視化
  サイト。DuckDB-WASM と WebR 上に構築され、サーバ側計算なしに完全にブラウザ内で
  動作。AWS インスタンスのキュレーション DB への SQL インターフェースと R ベースの
  可視化を提供し、集約・window 関数・ネスト式・対話的プロット・R モデルフィットが
  可能 (§3, Fig. 9)。
- [paper] DB は自前ベンチマーク結果で強化され、前処理も実施(例: 「Up to 10 Gbit/s」
  表記を net_peak_gbitps(トークンバケットのバースト上限)と net_gbitps(保証
  ベースライン)に分割)。便利ビュー aws(§2 の対象集合)と aws_family(ファミリー
  ごとの最大非 metal インスタンス)を提供。DB は単一 DuckDB ファイルでオフライン
  分析用にダウンロード可能。クロール・前処理は全自動で、将来も維持予定。コードは
  GitHub で公開 (§3, ref [1])。
- [paper] デモシナリオ (§3.1): DynamoDB 類似の disaggregated KV ストアのストレージ
  ノードに対するコスト最適インスタンス選定。前提: ハードウェアは完全利用可能、
  値は固定長 ≤4KiB、全リクエストがローカルストレージにアクセス(バッファキャッシュ
  なし)、圧縮なし、CPU 仕事は無視可能で I/O が明確なボトルネック (§3.1)。
- [paper] 経済次元は (1) ストレージ容量/ドル、(2) I/O 操作/ドル。スループットは
  BW_eff = min(BW_storage, BW_network) で制限され、ストレージ帯域がボトルネック
  ならネットワーク帯域の高いインスタンスを選んでも無意味 (§3.1)。
- [paper] 手順: NVMe SSD インスタンスでフィルタ(287 候補)→ burstable networking を
  除外し aws_family ビューでファミリー最大インスタンスに絞る(36 候補)→ 2 次元
  散布図で Pareto 最適 4 インスタンスを特定: スループット最適の c7gd / c6gd と
  容量最適の is4gen / i8ge。4 つとも Graviton ベース。最終選択は顧客ワークロードの
  アクセス頻度に依存 (§3.1, Fig. 9)。結果は CSV/Excel/SVG エクスポートやダッシュ
  ボードリンク共有が可能で、リンクは新インスタンス投入後も自動更新される。論文中の
  リンクは再現性のため固定スナップショットを指す (§3.1)。
- [paper] Cloudspecs は静的ファイルサーバでホストでき外部依存なし。DB とサンプル
  クエリは容易に差し替え可能で、GitHub リポジトリには Cloudspecs 型サイトの構築
  コードとクリック可能図版用 LaTeX パッケージ例を含む。汎用の自己完結型対話的
  研究データ共有パッケージへ一般化できると主張 (§3.2)。

### Lessons(システム設計への含意)(§5)
- [paper] 特化の利得: 特定資源に最適化したインスタンス選択(ネットワークなら c8gn
  vs 汎用 c8g)は性能を 5× 改善しうる。ただしソフトウェアが全ハードウェア資源を
  使い切れることが前提 (§5)。
- [paper] スケールアップの機会: 448 コア / 32 TiB DRAM / 120 TB NVMe / 600 Gbit/s の
  インスタンスが存在し、大規模シングルノードシステムの設計を可能にする (§5)。
- [paper] ARM の台頭: Graviton は compute(c8g)だけでなくネットワーク帯域(c8gn)、
  メモリ容量(x2gd)、NVMe 容量(is4gen)でも最良の選択。開発者は ARM への移植を
  真剣に検討すべきだが、ベンダー多様性と価格への長期的影響は未確定 (§5)。
- [paper] ネットワーク帯域の爆発は「ネットワークが分散システムのボトルネック」
  という伝統的前提に挑戦する。ネットワークトラフィック最小化を狙って設計された
  AWS Aurora の OLTP アーキテクチャが、今日のハードウェアでも最良かは疑問と提起
  (§5)。CPU 速度停滞 × 帯域増加でパケットあたり CPU サイクル予算は減り続け、
  カーネルバイパス等の大きなシステム変更が必要になりうる (§5)。
- [paper] NVMe 停滞はサーバ市場全般を追うクラウドトレンドの中の大きな例外。
  Snowflake 等は NVMe をキャッシュに使うが、高速ネットワークを踏まえると S3 から
  直接読む方が経済的かもしれない (§5)。
- [paper] マルチクラウド: 代替クラウドの大幅な低価格は、データ移動コストを考慮した
  マルチクラウドアーキテクチャ最適化に大きな可能性があることを示す (§5)。
- [paper] Future work: 知見は現時点のスナップショットで急速に変わりうる(例:
  現行比 7× 帯域の PCIe 5 SSD 搭載インスタンスが出れば、ネットワーク専依存の
  アーキテクチャは一夜で陳腐化しうる)。Cloudspecs の維持・他クラウド追加・
  マイクロベンチマーク追加を計画。ClickBench 型リーダーボードについては、
  Cloudspecs 類似の対話的クエリ可能 DB・可視化を備えれば多次元の分析を支援
  「できるだろう」と提案する(著者らの計画としてではない)(§6)。

## Evaluation
本論文の「評価」は上記トレンド分析そのもの(§2 の各図表)と、§3.1 のデモによる
ツールの有用性提示。ここでは方法論のカバレッジを整理する。
- [paper] 一次データ: AWS 公式 API / Web の自動クロール(2025 年 10 月時点)+
  自前実測(SPECint / Umbra TPC-H / Leanstore TPC-C、メモリ帯域)+ 手動収集の
  他クラウド価格 (§2, §2.1, §2.2, §2.6)。
- [inference] 分析がカバーしていないもの:
  - EBS 等のリモートブロックストレージの性能・価格トレンドは対象外(ストレージ
    分析は NVMe インスタンスストレージのみ、§2.4)。クラウド DB の多くが EBS 系に
    載る現実を考えると、この欠落は「ストレージ停滞」の一般化可能性を限定する。
  - NVMe の I/O 性能/ドルの根拠はシーケンシャルリードとランダム 4KiB リード
    (§2.4)で、書き込み性能・耐久性(DWPD)・レイテンシ分布は示されない。
    write-heavy な OLTP/LSM ワークロードで i3 優位が保つかは開いている。
  - ネットワークは帯域のみでレイテンシのトレンドがない。OLTP のコミットレイテンシや
    分散トランザクションには帯域より RTT が効く場面が多いはず。
  - クロスクラウド比較は 1 参照構成(16 コア AMD / 128 GiB)のみで、著者ら自身も
    網羅的比較はスコープ外と明言 (§2.6)。NVMe・ネットワーク等の性能実測は他
    クラウドでは行っていない(future work、§6)。
  - spot / reserved を除外した on-demand 前提 (§2) は価格「構造」保存の議論付きだが、
    spot 主体の分析ワークロード(一時クラスタ)では結論が変わる余地がある。
- [question] 「AWS の NVMe 停滞」はハードウェア調達の停滞なのか、仮想化層 /
  課金設計(IOPS を EBS 等の別商品に誘導する動機)によるものなのかは本文では
  切り分けられていない(§2.3 では逆にネットワークについて独自技術の経済的動機を
  問うている)。

## Limitations
- Stated [paper]:
  - 論文内の静的分析は本質的に限定的で、ユースケース固有の問いには読者自身の
    経済分析が必要(それが Cloudspecs を作った動機)(§1, §3)。
  - 知見は現在のスナップショットであり、破壊的な新インスタンスで急変しうる (§6)。
  - クラウド間の網羅的比較はスコープ外 (§2.6)。真のコスト性能透明性には
    クラウド横断の性能/ドル比較が必要だが、プロバイダはベンチマーク結果を
    公表していない (§6)。
  - in-memory DB ベンチマークの改善が SPECint より低い理由は「推測」であり
    微視的分析は future work (§2.1)。
  - データセンターネットワーク機器の現実的価格が入手できず、ネットワークの
    コスト正規化オンプレ比較は不能 (§2.3)。
- Inferred [inference]:
  - ベンチマークは compute-optimized の 2xlarge のみ (§2.1)。メモリ最適化系や
    大スライスでの NUMA / ソケット数の影響は測っておらず、「ファミリー内で
    コスト正規化指標は等しい」(§2)という前提が性能実測にも及ぶかは未検証。
  - 中小クラウドの価格優位 (Table 1) は可用性・SLA・スポット供給量・サポート等の
    質の差を捨象した名目価格比較。税調整はしている (§2.6) が、同一負荷での
    実効性能/ドル(CPU 世代差: STACKIT は Epyc2、Hetzner は Epyc3/4 と Table 1 に
    幅がある)は測定されていない。
  - トレンドの多く(特に Fig. 2 の 3×)は Graviton という単一ベンダーイベントに
    依存しており、ARM 価格政策が変われば逆転しうる点は §5 でも「jury is still
    out」と認めるにとどまる。

## Relations
- [inference] [[2026-sigmod-arkhangelskiy-aurora-limitless.md]]: 本論文 §5 は
  「ネットワークトラフィック最小化のために設計された Aurora の OLTP アーキテクチャは
  今日のハードウェア地形でも最良か」と名指しで問うており (§5, ref [36])、Aurora
  系ノートの設計前提を経済面から再評価する視点を与える。
- [inference] [[2026-sigmod-chen-cloudjump3.md]](階層型クラウドストレージ):
  本論文の「NVMe 性能/ドル停滞 × ネットワーク 10× 改善で、NVMe キャッシュより
  S3 直読みが経済的になりうる」(§5) は、クラウドストレージ階層設計の損益分岐を
  動かす主張であり、階層化設計ノートと直接接続する(CloudJump 側の文脈は各ノート
  参照)。
- [inference] [[2026-sigmod-yu-lakemem.md]](disaggregated memory cache):
  本論文はクラウドの DRAM 容量/ドルがほぼ停滞していること (§2.2, Fig. 3) と
  キャッシュの経済性が相対価格に依存すること (§1) を示しており、クラウドでの
  キャッシュ層設計(five-minute rule の再訪 [10] を related work で言及、§4)の
  価格前提を与える。
- [inference] [[2026-edbt-krause-disaggregated-survey.md]](disaggregation survey):
  本論文の「compute / caching / storage への分離が割に合うかは相対価格次第」(§1) と
  ネットワーク帯域爆発 (§2.3, §5) は、disaggregation の成立条件そのものを扱って
  おり、survey ノートの技術分類に経済軸を足す関係にある。

## Idea seeds
- [inference] 「NVMe キャッシュ vs S3 直読み」の損益分岐を Cloudspecs の DB で
  定量化する。§5 は可能性の指摘にとどまるので、GET スループット/ドルを
  instance-local NVMe(c7gd / i3 系)と S3 + ネットワーク帯域で比較する式を立て、
  DuckDB ファイル上の SQL で全インスタンスに適用すれば、five-minute rule 型の
  「キャッシュすべき閾値」の 2026 年版が半日で出せるはず。公開 DB(単一 DuckDB
  ファイル、§3)があるため検証コストは極めて低い。
- [question] i3(2016)の I/O/ドル優位 (§2.4) は read 系メトリクスのみで示されて
  いる。write IOPS・耐久性・レイテンシ分布を含めた場合も i3 が Pareto 最適かは
  開いた問い。検証: i3 / i3en / 新世代(i7i, i8g 系)を借りて fio で write 混在
  ワークロードの性能/ドルを実測し、Cloudspecs の手法(§3.1)で再プロットする。
- [inference] 「パケットあたり CPU サイクル予算の縮小」(§5) は、log shipping や
  replication プロトコルの CPU コスト(シリアライズ・チェックサム・syscall)が
  新しいボトルネックになることを示唆する。WAL / replication 系の設計を「ネットワーク
  帯域は潤沢、CPU サイクルが希少」という 2026 年の価格ベクトルで並べ直す分析は、
  本ノート群(WAL・replication 系)を横断する Phase 2 の課題候補になる。最初の
  検証: 帯域飽和時の CPU 利用率をレプリケーションベンチで測る。
- [question] AWS の NVMe 停滞 (§2.4, Fig. 7) が技術要因か事業要因(EBS への誘導)かは
  本文で未解決。PCIe 5 SSD インスタンスが投入された時点で §6 の予言(ネットワーク
  専依存アーキテクチャの一夜の陳腐化)を検証できるよう、Cloudspecs のスナップ
  ショットを定点観測する価値がある。
- [inference] Cloudspecs の「単一 DuckDB ファイル + 静的ホスティング + ブラウザ内
  SQL/R」という研究データ共有形態 (§3.2) は、本パイプラインの literature DB /
  実験結果共有にもそのまま流用できる(GitHub Pages でホスト可能と明言、§6)。

## Changelog
- 2026-07-06: created (status: read)
- 2026-07-06: 検証パスによる修正(§6 の ClickBench 言及を著者らの「計画」から論文の「提案」に訂正)
