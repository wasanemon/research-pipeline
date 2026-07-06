---
title: "Cylon: Fast and Accurate Full-System Emulation of CXL-SSDs"
authors: [Dongha Yoon, Hansen Idden, Jinshu Liu, Berkay Inceisci, Sam H. Noh, Huaicheng Li]
venue: "FAST '26 (24th USENIX Conference on File and Storage Technologies)"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/fast/YoonILINL26"}
urls: {paper: "https://www.usenix.org/conference/fast26/presentation/yoon", pdf: "literature/pdfs/2026-fast-yoon-cylon.pdf", code: "https://github.com/MoatLab/FEMU"}
status: read
read_date: 2026-07-06
tags: [cxl, cxl-ssd, emulation, femu, qemu, kvm, ept, dram-cache, nand-flash, eviction, prefetching, tiered-memory, hw-sw-codesign, dax]
---

## TL;DR
CXL-SSD(小さな DRAM キャッシュ + 大容量 NAND を CXL.mem の load/store で露出する
デバイス)の研究は、不透明な実機プロトタイプ(Samsung CMM-H)と、遅すぎる・忠実で
ないシミュレータの間で手詰まりになっている。Cylon は FEMU ベースのフルシステム
エミュレータで、Dynamic EPT Remapping(DER)により cache hit を VM-exit 無しの直接
load/store(~150ns)で、cache miss は EPT violation で FEMU にトラップして NAND
タイミング込み(数十µs)で再現する hybrid access path を提案。CMM-H 実機との検証で
レイテンシ分布・帯域遷移・アプリ性能傾向の再現を示し、プラガブルな eviction/prefetch
ポリシーとアプリレベル制御 API で co-design 研究の基盤を狙う。著者ら Virginia Tech
(Yoon と Idden が co-lead)。

## Problem & motivation
- [paper] CXL-SSD は SSD を CXL 越しの byte-addressable tier として接続する: 小さな
  DRAM キャッシュが sub-µs でホットデータを供し、NAND が multi-TB 容量を数十µs の
  miss で提供する。memory-like なプログラマビリティを storage-like なコストで
  実現する狙い (§1)。
- [paper] しかしコミュニティには「数十µs の miss がフルソフトウェアスタック越しに
  end-to-end のストールにどう変換されるか」「どのキャッシュ管理・prefetch ポリシーが
  有効か」「HW/SW をどう co-design すべきか」を体系的に調べる基盤が無い (§1)。
- [paper] 研究基盤としての3課題: (a) 不透明なプロトタイプ — CMM-H はキャッシュ管理が
  firmware 制御でポリシーのノブが無く、意味のある探索にはハードウェア改造が要る。
  (b) memory-semantic なモデリング — ブロックデバイスと違い byte-addressable メモリ
  として DRAM/NAND 非対称性と細粒度 load/store 並行性を捉える必要。
  (c) full-system コンテキスト — キャッシュ管理の有効性は実 OS・実アプリとの高速な
  相互作用に依存 (§2 "Challenges in CXL-SSD research")。
- [paper] 既存基盤の不足 (§3, Table 1): QEMU の upstream CXL サポートは CXL プロトコル
  機能のみで DRAM cache や SSD 内部をモデル化せず、全アクセスが MMIO + VM-exit を
  経由してレイテンシが ~15µs に膨張。trace-driven シミュレータ(MQSim-CXL, ESF)は
  未修正ソフトウェアスタックとの動的相互作用を捉えられず、極めて遅く、実機検証も
  無い。cycle-accurate 系(CXL-SSD-Sim, CXL-DMSim; gem5 統合)は忠実だが遅すぎて
  ワークロード縮小を強いる。OpenCXD は FPGA ハードウェアに依存し公開拡張性が無い。
  CXLMemSim は CXL.mem タイミングのみで SSD セマンティクスが無い (§3)。
- [paper] 必要なのは (1) full-stack 実行、(2) near bare-metal 速度(sub-µs hit と
  数十µs miss の再現)、(3) 正確なデバイスモデリング(DRAM cache 動態 + NAND
  タイミング)の3つの同時達成であり、既存はどれも部分集合しか満たさない
  (§2 "The need for Cylon", §3 "Summary of limitations")。

## System model & assumptions
- [paper] 代表デバイスモデル = Samsung CMM-H: 48GB DRAM キャッシュ(cacheline は
  4KB)+ 1TB NVMe SSD バックエンドを Intel Agilex FPGA コントローラが PCIe Gen5 上で
  調停するハイブリッド CXL メモリプロトタイプ。DRAM は write-back キャッシュ
  (LRU 置換、または MRU 挿入)で、prefetch も持つがポリシーは不透明 (§2)。
- [paper] 用語規約: 本論文の "cache" は CXL-SSD 内部の DRAM キャッシュを指し、CPU
  キャッシュや SSD 内部機構ではない (§1 末尾)。
- [paper] ゲストから見える形: エミュレートされた CXL-SSD は標準の CXL 2.0 Type-3
  デバイスとして DAX region または CPU-less NUMA node に見える。ゲスト可視容量 =
  バックエンド SSD 容量で、DRAM キャッシュは隠蔽され透過管理される(CMM-H 同様の
  hardware-managed cache を忠実にエミュレート)。ゲストドライバ変更は不要 (§4.2)。
- [paper] 仮想化基盤: Intel EPT(GPA→HPA 変換)の leaf entry (EPTE) を KVM が操作する
  ことが前提。DER はアーキテクチャ標準の EPT permission bit のみを操作するため、
  AMD NPT / ARM Stage-2 page table にもマップできると主張 (§4.3.1 Safety)。
- [paper] hit レイテンシの決まり方: ホストの remote-NUMA DRAM アクセス時間(~150ns)で
  固定される。CMM-H の実測 hit(~800ns、FPGA コントローラのオーバーヘッド)より低く、
  「プロトタイプ固有のアーティファクトからキャッシュポリシー効果を分離した理想化
  ベースライン」という位置付け。hit レイテンシの独立した設定は現状不可(較正遅延
  注入は future work)(§4.8 "Cache-hit latency")。
- [paper] バックエンド SSD データはホスト DRAM に格納(速度と実装単純性を優先)。
  エミュレート容量はホストメモリに制限される。SPDK ベースの NVMe バックエンドへの
  置換で multi-TB 化する拡張は ongoing work (§4.8 "Backend Storage and Capacity")。
- [paper] NAND タイミングは FEMU の検証済みモデルを再利用: channel/die/plane 並列性、
  read/program/erase レイテンシ、キューイングと GC 干渉、FTL 状態依存レイテンシ。
  固定 miss 遅延は使わない (§4.8 "NAND timing and parallelism")。
- [paper] 永続性・順序: dirty eviction ではキャッシュデータを先に SSD モデル(FEMU)へ
  書き戻し、完了後にのみ EPTE をクリアし TLB を無効化する。これで実 CXL-SSD に期待
  される memory ordering と durability セマンティクスに一致させる (§4.3.1 Transitions)。
- [paper] 性能問題の構造: CPU は MSHR で追跡できる outstanding miss 数が限られる
  ため、長レイテンシ miss 1つでもパイプラインが停止し、miss が蓄積すると独立命令まで
  待たされるカスケードが起きる。キャッシュ管理はこの二重問題(miss レイテンシ +
  ストールによる CPU スループット喪失)への対処 (§4.4)。

## Approach
- [paper] **全体構成** (Fig. 1, §4.2): 3ドメイン = 未修正ゲスト VM / 軽度修正のホスト
  カーネル(KVM)/ ホストユーザ空間の FEMU。アクセス経路は2分岐:
  hit では EPTE が DRAM キャッシュを直接指し VM-exit 無しで DRAM 速度(図中 150ns)。
  miss では EPTE が trap 状態で VM-exit → KVM の EPT page fault handler → QEMU の
  CXL エミュレーションが GPA を SSD オフセットにマップ → FEMU からフェッチ(図中
  fill 40µs)→ キャッシュ挿入(必要なら eviction)→ EPTE を Direct 化して以後の
  アクセスは VM-exit をバイパス。eviction されたページは Trap 状態に戻る。
- [paper] **Dynamic EPT Remapping (DER)** (§4.3.1):
  - 2状態: Direct = EPTE を [HPA | DIRECT_MASK] に設定(read または read+write 許可、
    execute クリア、memory type = Write-Back)し、EPT walk がトラップ無しで完了して
    DRAM キャッシュ内 HPA を直接指す。Trap = R=W=X=0 で任意アクセスが EPT violation。
    この状態では PFN フィールドはハードウェアに無視されるので、sentinel HPA と対応
    SSD アドレスを記録しておき miss 処理に使う。
  - 遷移プロトコル: fill = データをキャッシュへコピー → EPTE を Direct 化 → INVEPT
    (single-context または range)で stale TLB をフラッシュしてからゲスト再開。
    clean eviction = write-back 無しで破棄、EPTE を R=W=X=0 に戻し targeted INVEPT。
    dirty eviction = 先に FEMU へ書き戻してから EPTE クリア(前述)。
  - Invalidation: 遷移ごとの global TLB shootdown はスケールしないので、INVEPT
    (ページ/レンジ無効化)と INVVPID(ゲストコンテキスト横断の一貫性)という
    ハードウェア支援プリミティブを使い、さらに batching / coalescing(prefetch burst
    のように状態フリップが密集する場合、少数の invalidate にまとめる)(§4.3.1)。
  - スケーラビリティ: (1) ページフリップ毎に shootdown しない batching、(2) バッファの
    特定 GPA レンジのみの range invalidation、(3) EPT invalidation は miss パス限定。
    broadcast コストはコア数と共に増えるが 40µs の NAND フェッチに比べ無視できる。
    CMM-H での検証は 4 スレッドで性能飽和し、支配的ボトルネックはホストのコヒーレンス
    ではなくデバイス並列性の不足であることを確認したと主張 (§4.3.1 Scalability)。
  - 安全性: VM 生成時に2つの不変領域(DRAM キャッシュ用に pin されたホスト物理
    レンジ、FEMU 管理のバックエンド SSD を表す全ゲスト物理レンジ)を KVM に登録し、
    residency 遷移はこの2領域間の EPTE フリップに制約。範囲外の EPTE インストールは
    拒否。更新時に可変なのは PFN セレクタと R/W/X ビットのみで、memory type と
    予約ビットはカーネル管理。EPTE 毎のロックで並行更新(eviction と prefetch の
    競合)を直列化 (§4.3.1 Safety)。
- [paper] **Shared EPT Memory** (§4.3.2): fill/eviction 毎に FEMU が KVM ioctl() を呼ぶ
  素朴な設計は、(1) syscall のカーネル/ユーザ空間横断(単純な更新でも µs 級)、
  (2) EPT ページが lazily 割当てられ散在するためカーネル内データ構造の walk が必要、
  という2重のオーバーヘッドがあり、EPTE 更新遅延によるエミュレーション不正確さも
  生む。Cylon は VM 初期化時に全 leaf EPTE を単一の連続領域に事前割当てし、カーネル
  空間とユーザ空間 QEMU/FEMU の双方にマップ。EPTE は論理ページ番号(LPN = SSD
  アドレス)の配列インデックスで直接参照でき、遷移あたり O(1) の lookup/update に
  なる。FEMU は raw EPTE を直接書かず、<index, desired state, cookie> 形式の
  ディスクリプタを共有メモリに発行 → カーネルが検証し不正フィールドをマスクして
  適用(変更可能なのは PFN セレクタと R/W/X のみ)。密集した更新は KVM が単一の TLB
  invalidation に coalesce。さらにこの EPTE 配列インターフェースを通じてキャッシュ
  状態をゲスト VM に開示でき、アプリのデータ配置判断に使える (§4.3.2)。
- [paper] **設定可能キャッシュフレームワーク** (§4.4): eviction(FIFO, S3FIFO, CLOCK
  等)と prefetch(next-line 等)をプラガブルモジュールとして初期化時に選択。
  ポリシーは「何を保持/追い出し/prefetch するか、いつロジックが起動するか、何の
  統計を集めるか」を定めるクリーンなインターフェースで定義され、新ポリシーの実装が
  容易 (§4.4)。
  - Observability: cache hit は直接 load で完了しエミュレータに痕跡を残さないため、
    (1) EPT accessed bit の周期クリア + Linux DAMON 基盤でのタッチ記録(粗いが低
    コスト)、(2) Intel PEBS 等のハードウェア支援サンプリング(高精度だが高コスト。
    1/1000 程度のレートなら実用的)の2機構を併用 (§4.4 Observability)。
- [paper] **アプリレベル制御インターフェース** (§4.5): OpenChannel-SSD の host-managed
  FTL と同じ精神で application-managed CXL-SSD を研究可能にする control plane。
  コマンドは (i) 明示的 prefetch / pin / evict、(ii) 動的なポリシー選択・パラメータ
  調整、(iii) 細粒度統計のクエリ。実装は共有メモリ上の ring queue(低レイテンシ)+
  未修正ゲスト向けの kernel 経由 ioctl() パス、薄いユーザ空間ライブラリで API 化。
  例: DB が join 前にテーブルを prefetch、graph engine が frontier を pin、学習
  パイプラインが次 epoch の mini-batch を prefetch (§4.5)。
- [paper] **CMM-H を超える拡張性** (§4.6): CXL–NVMe 統合(NVMe-oC のコヒーレント
  共有)、低レイテンシフラッシュ(Kioxia)、CXL–FTL 統合(NVMe queue pair を介さず
  SSD コントローラが CXL.mem を直接採用し、NAND channel/die/plane 並列性をホストに
  透過的に露出)、マルチデバイストポロジ、host/device 混合管理、elastic memory pool
  的抽象、DAX 上のファイルシステムや新ランタイム等の探索を、キャッシュ層の再構成・
  バックエンドフラッシュモデルのカスタマイズ・API 拡張で支援すると主張 (§4.6)。
- [paper] **実装** (§4.8): FEMU (v8.0.0) に約 6,282 行、Linux kernel (v6.4.6) に 1,261
  行の追加。DRAM キャッシュはブートパラメータ "memmap=[size]![offset]" で NUMA
  node 1 に物理連続領域として確保し、ゲスト vCPU を node 0 に pin して hit を
  remote-NUMA レイテンシ(~150ns)にする。EPTE 共有には新 KVM memslot フラグ
  KVM_MEMSLOT_DUAL_MODE を導入し、EPT_VIOLATION 処理でフォルトアドレスが Cylon の
  memslot に属す場合はカスタムハンドラが EPT ブロックを割当ててユーザ空間領域に
  マップ。QEMU の CXL Type-3 デバイス (ct3d) が MMIO 要求を FEMU 側ハンドラに転送し、
  専用 FTL スレッドが buffer management・NAND エミュレーション・GC を実行。
  コードは FEMU に upstream 済み (§1 contributions, §4.8)。

## Evaluation
- Setup [paper] (§5.1):
  - エミュレーションホスト: dual-socket Intel Xeon Gold 6242、384GB DDR4(ソケットあたり
    192GB)。Intel MLC 実測で local 90ns / remote 150ns。Ubuntu 20.04 + 修正カーネル
    v6.4.6。ゲスト: Ubuntu 22.04(vanilla v6.4.6)、8 vCPU、96GB ローカル DRAM。
    Cylon は 96GB の CXL DAX デバイス(DRAM キャッシュ 4.8GB + NAND 96GB)を露出。
    NAND タイミングは read 40µs / write 200µs / erase 2,000µs(ベンダデータシートと
    先行研究由来)(§5.1.1)。
  - 実機検証テストベッド: dual-socket Intel Xeon 6710E、512GB DDR5。CMM-H は 1TB の
    CPU-less NUMA node として認識。Ubuntu 24.04 + kernel v6.13.0 (§5.1.1)。
  - 公平性: CMM-H とはキャッシュ・NAND 容量が大きく異なるため、working-set size
    (WSS) を各システムの DRAM キャッシュ容量で正規化して比較 (§5.1.2)。
  - ワークロード: Intel MLC(レイテンシ・帯域)、MIO(sequential/random/stride の
    pointer chasing)、Redis + YCSB workload C(100% read、1KB レコード)、GAPBS
    (グラフ解析、scale factor で WSS 調整)(§5.1.2)。
  - ベースラインは QEMU-CXL のみ(未修正ゲスト OS を動かせる唯一のオープンソース
    full-system CXL エミュレータのため。他は trace-driven / gem5 依存 / FPGA 依存で
    直接比較不能)(§5 冒頭)。
- 実行パスの分解 (Fig. 2, §5.2): hit 率 100% / 0% に固定し NAND レイテンシ 0 で
  エミュレーションオーバーヘッドのみを測定。100% hit で Cylon は 0.16µs =
  remote-NUMA 相当(host local 0.10µs / remote 0.14µs)。QEMU の MMIO ベース設計は
  14.74µs で実 DRAM の2桁超遅い。miss パスは Shared EPT 版(Cylon-S)16.27µs vs
  ioctl 版 DER(Cylon-I)23.04µs で、kernel-userspace 横断の排除が効く。現実的な
  NAND レイテンシ(数十µs)を入れればこの追加コストは無視できる規模になる (§5.2)。
  QEMU のデフォルト CXL サポートは TCG(バイナリ変換)依存で帯域は数 MB/s に留まる
  (§4.3)。
- レイテンシ分布 (Fig. 3, §5.2): MIO pointer chasing、WSS 8GB(> 4.8GB キャッシュ)、
  FIFO eviction、NAND レイテンシ 0。Cylon は bimodal — hit は sub-µs(平均 977ns)、
  miss は数十µs 域。QEMU は全アクセスが単一の膨張モード(平均 14.6µs)に潰れ sub-µs
  hit が存在しない (§5.2)。
- CMM-H 特性化 (Fig. 4, §5.3): sequential pointer chasing で 4/20/40/60GB バッファを
  掃引。48GB キャッシュを大きく下回る 4/20GB では ns 域に密集、40GB では冒頭の高
  レイテンシが漸減、60GB では NAND 落ちが頻発し数十µs が持続 (§5.3)。
- Cylon vs CMM-H レイテンシ (Fig. 5, §5.3): MIO 4 スレッド、正規化 WSS 0.33 / 2.10 の
  CDF 比較。miss 時は Cylon の方が高レイテンシ、hit 時は Cylon の方が低レイテンシ。
  CMM-H は FPGA プロトタイプの内部オーバーヘッド(メタデータ管理、コントローラ
  レベル prefetch)で hit ~800ns。Cylon は「プロトタイプ固有アーティファクトではなく
  意図されたアーキテクチャ挙動」をモデル化する理想化ベースラインという整理 (§5.3)。
- 帯域 (Fig. 6, §5.4): prefetch 無効・FIFO。両者とも「キャッシュ内 WSS では
  near-memory 帯域 → キャッシュ飽和で NAND 帯域へ急落」の2相挙動。Cylon は 4.8GB
  キャッシュ満杯まで remote-NUMA 帯域(32GB/s)を維持。CMM-H はキャッシュ飽和前から
  劣化を始める(black-box のため原因究明は不能。内部 prefetch やメタデータ
  オーバーヘッドと推測、先行研究 [8] でも同様の報告)。キャッシュ超過後は両者とも
  同じ NAND バウンドのスループットに収束 (§5.4)。
- Redis (Fig. 7, §5.5): 正規化 WSS 0.33× で Cylon の CDF が左シフト(remote-NUMA hit
  vs CMM-H のコントローラオーバーヘッド)。1.06× では hit と NAND バウンド miss の
  混合で両者とも CDF が広がり、差は縮小。2.10× ではほとんどの要求が NAND に落ち、
  両デバイスとも数十〜数百µs に収束して CDF が重なる (§5.5)。
- GAPBS (Fig. 9, §5.5): Betweenness Centrality(kron)、メモリフットプリント
  10.2/20.4/40.8GB。グラフでは WSS を精密制御できないため Cylon のキャッシュサイズを
  CMM-H に合わせる。小フットプリントでは両者同等で Cylon が hit レイテンシ分やや
  速く、40.8GB では NAND miss が支配的になり両者とも実行時間が伸びる。全スケールで
  傾向が一致 (§5.5)。
- Eviction ポリシー比較 (Fig. 8, Table 3, §5.6): 1スレッド、Seq/Rand/Stride-512/1024/
  4096。NAND は 40µs/200µs/2,000µs 設定。hit 率: Seq = FIFO 97% / LIFO 99% / CLOCK
  97% / S3FIFO 99%。Rand は全ポリシー ~24.3% に収束(LIFO 21%)し 1億超 miss。
  Stride-4096 では FIFO/CLOCK 0%、S3FIFO 18% に対し LIFO 60%(LIFO は最新挿入分以外
  を追い出さないため少なくとも 4.8GB 分の古いページが常駐し続ける)(§5.6, Table 3)。
- Redis での eviction (Fig. 11, §5.6): YCSB-C、Zipfian、8 スレッド、1KB レコード。
  0.33× WSS では全ポリシー同一(cold miss のみ)。フットプリント 12.8GB(図の表記は
  2.67× WSS)では LIFO が最低レイテンシ — LIFO は古いキーを常駐させ続けるため
  Zipfian の偏ったアクセスで高 hit 率を維持 (§5.6, Fig. 11)。
- Prefetch (Fig. 10, Table 2, §5.6): S3FIFO + next-N prefetch(N=0〜8)。空間局所性が
  ある Seq/Stride 系では N 増加で miss が劇的に減り、レイテンシが sub-10µs 域に圧縮。
  hit 率は Stride-4096 で N=0 の 18% → N=8 の 86%、Stride-1024 で 80%→96%。Rand は
  N を増やしても ~25% で変化なし (Table 2)。Redis 1スレッド (Fig. 12) では WSS <
  キャッシュで prefetch 効果なし、WSS 大では prefetch 度の増加がレイテンシを改善。
- [inference] 評価がカバーしていないもの:
  - 忠実性の検証は CDF の形・帯域遷移・アプリ傾向という定性比較で、定量的な誤差
    指標(例: hit 率誤差、レイテンシ分布の距離)は提示されない。hit レイテンシは
    意図的に CMM-H と異なる(150ns vs ~800ns)理想化なので、「CMM-H を較正再現する
    エミュレータ」ではなく「アーキテクチャ意図の再現」である点は利用時に注意。
  - write-heavy ワークロードが無い。Redis は YCSB-C(100% read)、GAPBS も解析系で、
    dirty eviction 経路(write 200µs / erase 2,000µs + FEMU の GC 干渉)がテールに
    与える影響はアプリレベルで検証されていない。
  - スレッドスケーラビリティ: ゲストは 8 vCPU 構成だが、TLB shootdown コストの
    コア数スケーリングは「40µs に比べ無視できる」という議論と CMM-H の 4 スレッド
    飽和観測 (§4.3.1) に依拠し、多コアでの掃引実験は示されない。
  - §4.5 のアプリレベルヒント API(prefetch/pin/evict)を実際にアプリから使う
    co-design 実験は無い(§5.6 はデバイス側ポリシーの構成変更のみ)。
  - エミュレート容量はホスト DRAM 制約で 96GB。CMM-H の 1TB 級で顕在化しうる効果
    (FTL メタデータ、大容量 GC)は正規化 WSS 手法では観察できない。

## Limitations
- Stated [paper]:
  - hit レイテンシはホストの remote-NUMA 時間に固定され、独立に設定できない(較正
    遅延注入は future work)(§4.8)。
  - バックエンドがホスト DRAM 格納のため、エミュレート容量はホストメモリまで。
    SPDK NVMe バックエンドは ongoing work (§4.8)。
  - CMM-H の早期帯域劣化の原因は black-box デバイスのため検証不能(prefetch や
    メタデータオーバーヘッドと推測に留まる)(§5.4)。
  - CMM-H は firmware が進化中の第一世代 FPGA プロトタイプであり、比較は
    プロトタイプ固有のオーバーヘッドを含む (§5.3)。
- Inferred [inference]:
  - residency 管理の粒度は EPT ページ(4KB)であり、CMM-H の 4KB cacheline とは
    偶然一致するが、より細粒度(数百 B〜サブページ)のキャッシュ管理を行う将来
    デバイスは EPT permission flip では直接表現できないはず(§4.3.1 の機構はページ
    粒度の Direct/Trap 二値)。
  - hit パスは素の remote-NUMA DRAM アクセスなので、CXL リンク自体の帯域競合・
    デバイス側コントローラのキューイング(CMM-H で観測された hit 時 ~800ns や
    キャッシュ飽和前の帯域劣化)はモデル化されない。ポリシー比較には十分でも、
    絶対性能予測やテール解析には系統誤差が入る。
  - DER は Intel VT-x/EPT と修正カーネル(v6.4.6 に 1,261 行)が前提。AMD NPT /
    ARM への「マップできる」という主張 (§4.3.1) は実装・検証されていない。
  - hit 統計の observability はサンプリング(accessed bit / PEBS)依存 (§4.4) なので、
    ポリシー研究で使う hit/miss 統計のうち hit 側は近似値になる。

## Relations
- [[2026-pvldb-zhao-sidle.md]](SIDLE: CXL ヘテロメモリの木構造インデックス配置):
  対象とするレイテンシ体制が対照的 — SIDLE は CXL DRAM(fast 比 ~2× 遅延)への
  ノード粒度配置、Cylon がエミュレートする CXL-SSD は hit 150ns vs miss 40µs+ の
  1〜2桁非対称。[inference] SIDLE 型のインデックス配置研究を NAND バックエンドの
  CXL tier に拡張する場合、Cylon(DAX / CPU-less NUMA node として露出、§4.2)は
  そのまま実験基盤になり得る。
- [[2026-edbt-lee-cxl-pools.md]](CXL メモリプール実機評価): 方法論が相補的 —
  Lee らは実機(XConn スイッチ + Samsung CMM-D)で IMDBMS を測るのに対し、Cylon は
  実機プロトタイプの稀少性・不透明性 (§1, §2) をエミュレーションで回避する。
  Cylon §4.6 は CXL-SSD を elastic memory pool として扱う方向の探索も適用先に挙げて
  おり、プール系研究との接点がある。

## Idea seeds
- [inference] DB バッファマネージャとデバイス側 DRAM キャッシュの「二重キャッシュ」
  問題: larger-than-memory エンジンを CXL-SSD の DAX 上に置くと、DB バッファプールと
  デバイスキャッシュが同じホットセットを重複保持し容量を浪費しうる。Cylon の
  observability(hit/miss 統計、§4.4)と §4.5 の pin/evict ヒントで、DB 側がデバイス
  キャッシュを明示管理する co-design を定量評価できる。最初の実験: FEMU upstream の
  公開コードで、ストレージエンジンのバッファプールサイズと Cylon キャッシュサイズを
  掃引し hit 率の相互作用(重複度)を測る。
- [question] Zipfian で LIFO が最良 (Fig. 11)・Stride-4096 でも LIFO 圧勝 (Table 3)
  というのは、汎用デバイスポリシーの限界と「たまたま常駐が効く」ケースの混在では
  ないか。DBMS のアクセス知識(scan は洗い流し・index probe はホット)を §4.5 API で
  渡した場合、S3FIFO + ヒントが LIFO を安定的に超えるかは開いた問い。検証: YCSB
  ワークロード混合(C→A→E 遷移)でヒント有無の hit 率とテールを比較。
- [inference] write-heavy な DB パス(WAL、checkpoint、LSM flush)は本論文の評価に
  無い(YCSB-C は 100% read)。write 200µs / erase 2,000µs + FEMU の GC 干渉の下で
  dirty eviction (§4.3.1) がコミットレイテンシのテールにどう波及するかは、CXL-SSD を
  ログ/データ両方の tier に使う設計の成否を分けるはず。最初の検証: Cylon 上で
  write-intensive ワークロード(TPC-C 相当)を流し、eviction ポリシー別に write-back
  起因のテールを分解する。

## Changelog
- 2026-07-06: created (status: read)
