---
title: "Getting the MOST out of your Storage Hierarchy with Mirror-Optimized Storage Tiering"
authors: [Kaiwei Tu, Kan Wu, Andrea C. Arpaci-Dusseau, Remzi H. Arpaci-Dusseau]
venue: "FAST '26 (24th USENIX Conference on File and Storage Technologies)"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/fast/TuWAA26"}
urls: {paper: "https://www.usenix.org/conference/fast26/presentation/tu", pdf: "literature/pdfs/2026-fast-tu-most.pdf", code: ""}
status: read
read_date: 2026-07-06
tags: [tiered-storage, mirroring, load-balancing, storage-hierarchy, flash-cache, cachelib, ssd-endurance, data-migration, write-allocation, hot-cold-separation]
---

## TL;DR
性能デバイスと容量デバイスの性能差が縮んだ現代のストレージ階層では、migration
ベースの tiering(HeMem / Colloid 系)は動的ワークロードへの追従が遅く device write を
浪費し、複製ベース(mirroring / caching / Orthus NHC)は容量を浪費し write に弱い。
MOST は「ホットデータのごく一部だけを両デバイスにミラーし、ルーティングで負荷分散する」
tiering + mirroring のハイブリッド。CacheLib のストレージ管理層 Cerberus として実装し、
静的ワークロードで SOTA 比最大 2.34× のスループット・P99 最大 75% 減、動的ワーク
ロードで Colloid 比 device write 最大 84% 減を主張 (§1)。

## Problem & motivation
- [paper] NVM・低レイテンシ SSD・NVMe/SATA Flash・NVMeoF / disaggregated SSD / EBS
  などの登場で、性能デバイスと容量デバイスの特性が重なり、厳格な階層に並べると
  ストレージシステムのピーク性能が出ない (§1, §2.1)。
- [paper] 性能比は小さく、かつワークロード依存: 16KB read の帯域比は Optane :
  PCIe3.0 NVMe で 1.5:1、local : remote PCIe4.0 NVMe で 1.25:1 に過ぎず、4KB read
  だと Optane : PCIe3.0 は約 2.2:1 に変わる。比はアクセスサイズ・write 比率・並行度に
  依存する (§2.1, Table 1)。
- [paper] single-copy 系の限界 (§2.2, Table 2): striping は最遅デバイス律速か、
  ワークロード依存の重み付けが必要。hotness tiering(HeMem)はホットデータを性能
  tier だけから供給するため高負荷時に容量 tier の帯域を使えない。BATMAN は固定
  帯域比の migration で、比が変動する階層に適応できない。Colloid は動的 migration で
  容量デバイス帯域を使うが、負荷分布の調整に大量の migration が必要で時変
  ワークロードを扱えない。exclusive caching は hotness tiering と同様の挙動。
- [paper] multiple-copy 系の限界 (§2.2, Table 2): mirroring(全複製)は read の負荷
  分散は効くが write は両コピー更新で遅い方に律速され、容量利用率も低い。inclusive
  caching は性能デバイスの容量を複製で浪費し、容量デバイスの性能を引き出せない。
  Orthus(NHC)は過負荷時に read を容量デバイスへ振り向けるが、①性能デバイス全体を
  複製に使うため space-inefficient、②read ルーティングに clean コピーが必要なため
  write に弱い(write-through は追加 write + 容量デバイスの write 帯域律速、
  write-back/around は dirty コピーにしか read を送れない)。
- [paper] ストレージ階層はメモリ階層と違い、(a) データセットが大きく migration での
  収束が遅い、(b) write 帯域が細く収束がさらに遅い、(c) write が read 性能を大きく
  乱す(バックグラウンド migration が前景性能を毀損)、(d) migration が SSD の寿命を
  削る、(e) アクセスが 10–500µs と遅いためブロック位置決定をソフトウェアで行えて、
  動的・選択的な mirroring を実装しやすい (§2.3)。
- [paper] 主張: 少量のホットデータの mirror を tiering に足すと、①ルーティング変更
  だけで負荷変化に即応できる、②動的ワークロード下の device write を削減できる、
  ③デバイス性能の揺らぎ(tail latency 劣化、SSD 内部のバックグラウンド活動)に
  対して過剰な migration を防げる (§1)。

## System model & assumptions
- [paper] 対象は性能デバイス(高価・小容量・高速)+容量デバイス(安価・大容量・
  低速)の2層階層。議論の単純化のための設定で、multi-tier への拡張は将来課題
  (§2.1, §5)。
- [paper] MOST はブロックレベルで透過的に動くストレージ管理層で、リクエストが
  どのテナントのものかは関知しない(QoS/fairness はヒント導入による将来拡張)(§5)。
- [paper] 実装 Cerberus は CacheLib のストレージ管理層(flash cache エンジンと
  ストレージ階層の間)であり、ブロックインタフェースと大きなアドレス空間を提供
  (§3.3, Fig. 3)。上位は DRAM cache / flash cache(LOC = 2KB 以上のオブジェクト用
  ログ + DRAM index、SOC = 4KB バケットハッシュ表)(§3.3, Fig. 3)。
- [paper] メタデータは全て in-memory: 2MB セグメント単位で 76B(id、両デバイス上の
  addr[2]、invalid/location の bitset ポインタ、clock、read/write カウンタ、rewrite
  カウンタ類、flags、storageClass、mutex)(§3.3, Table 3)。
- [paper] 一貫性保証は現状スコープ外: mapping 更新(migration 起因など)の WAL 化で
  強い一貫性へ拡張「できる」とし、詳細は future work (§5)。
- [paper] デバイスのレイテンシ計測は Linux block layer の統計カウンタを 200ms 間隔で
  読み、EWMA で平滑化する。事前のデバイス特性・ワークロード知識は不要という設計
  目標 (§3, §3.3)。
- [inference] 評価は全てローカル接続デバイス(Optane / NVMe / SATA)であり、Table 1
  や §2.1 で動機付けに使われた remote NVMe(RDMA/NVMeoF)や EBS 的なリモート
  ストレージ階層では検証されていない。ネットワーク越しではレイテンシ計測の
  ノイズ・輻輳起因の変動が加わるため、feedback ループ(θ=0.05, 200ms)の安定性は
  自明ではない。
- [inference] Cerberus はキャッシュ(CacheLib)の下の層であり、クラッシュ後の
  メタデータ(Table 3 は in-memory)喪失はキャッシュとしては許容されうるが、本文には
  クラッシュ時の挙動の記述自体がない。durable な DB ストレージの下に置くには §5 の
  WAL 拡張が前提になる。

## Approach
- [paper] **ハイブリッドデータレイアウト (§3.1, Fig. 1)**: データを mirrored class
  (両デバイスに複製、高速な負荷分散用)と tiered class(単一コピー、空間効率用)に
  分ける。最もホットなデータを mirrored class に、warm を tiered class の性能
  デバイスに、cold を tiered class の容量デバイスに置く。低負荷時は mirrored data への
  要求を性能デバイスに送り classic tiering と同様に動作、高負荷時は mirrored class を
  拡大し要求の一部を容量コピーへルーティングする。
- [paper] **アーキテクチャ (§3.2, Fig. 2)**: tiered class への要求は所在デバイスへ
  そのまま転送。mirrored class への要求は load switch(balancer)が割合ベースで両
  デバイスに振り分ける。割合の計算は Optimizer、class 間・デバイス間のデータ移動は
  Migrator が担う。
- [paper] **read 負荷分散 (§3.2.1, Algorithm 1)**: 確率ルーティング(offloadRatio の
  確率で容量デバイスへ。[69] = Orthus 由来)。Optimizer は tuningInterval ごとに
  end-to-end レイテンシを測り、L_P > (1+θ)L_C なら offloadRatio += ratioStep(既に
  最大なら mirrored class を拡大 or その hotness を改善し、migration は容量デバイス
  向きのみ許可)、L_P < (1−θ)L_C なら offloadRatio −= ratioStep(0 なら性能デバイス
  向き migration のみ)、ほぼ等しければ全 migration 停止。両デバイスのレイテンシが
  均等になるまで offload する feedback 制御 (§3.2.1)。
- [paper] **動的 write allocation (§3.2.2)**: 新規ブロックはまず tiered class に割当。
  classic tiering の割当は load-unaware(常に性能デバイス)だが、MOST は offloadRatio の
  確率で新規データを容量デバイスに割り当てる。性能デバイスが高負荷(高レイテンシ)
  なら容量側への割当が増え、軽負荷なら全て性能デバイスに置かれる。
- [paper] **mirror-class migration (§3.2.3)**: セグメント単位の read/write カウンタで
  hotness を追跡(HeMem 類似)。ミラー量が負荷分散に不足なら mirrored class を設定
  上限まで拡大(実験では総容量の 20% で十分)。mirror 化は「tiered class の性能
  デバイス上の最ホットセグメントを容量デバイス側へ複製するだけ」なのでデバイス間
  移動を最小化。上限到達後は tiered 最ホット > mirrored 最コールドならスワップ。
  空き容量が watermark(総容量の 2.5%)を切ると mirrored 最コールドの片コピーを破棄
  して回収。migration は「end-to-end レイテンシが高い方のデバイスからのみ追い出す」
  一方向規律で、レイテンシが拮抗したら全停止 (§3.2.3)。
- [paper] **write 負荷分散と subpage 管理 (§3.2.4)**: mirrored class への write は片方の
  コピーだけを更新して valid 部分を追跡する(両方更新すると write の負荷分散に
  ならない)。両コピー valid なら offloadRatio で確率ルーティング。セグメント内を
  デバイスのアクセス単位(例 4KB)の subpage に分け、subpage ごとに invalid bit +
  location bit(clean / invalid-on-performance / invalid-on-capacity の3状態)を持つ
  ことで、4KB 整列 write を read 同様の単純ルーティングで分散できる。メタデータは
  subpage あたり 2 bit で、2TB 階層で性能デバイス全ミラー(50% mirroring)の極端
  ケースでも 128MB (§3.2.4)。
- [paper] **selective cleaning (§3.2.4)**: 片コピーのみ valid なブロックをバック
  グラウンドスレッドが clean 化する。対象は rewrite distance(あるブロックの
  write 間の平均 read 回数)が大きいブロックのみ。rewrite distance が小さいブロックは
  すぐ再 write されるので clean しても無駄、という選択則。
- [paper] **tail latency 保護 (§3.2.5)**: 容量デバイスの tail latency が著しく悪い場合に
  備え、ユーザが offloadRatio の最大値を設定して mirrored(hot)データの容量デバイス
  への offload 量を制限できる。
- [paper] **実装 (§3.3)**: Cerberus は CacheLib に約 1.5k LOC を追加(HeMem 系 tiering
  ロジックを拡張)。Optimizer は専用 pinned thread 上で 200ms 間隔で動く。θ=0.05
  (tuning 系システムの慣用値 [64])、ratioStep=0.02(Orthus 等に倣う)で、fine-tuning
  不要の頑健な性能を示す = θ の選択への感度は低い、と主張。比較対象も同じ
  ストレージ管理層内に実装: Striping(CacheLib デフォルト)、Orthus(Wu らの提供
  実装 ~6K LOC)、HeMem(自前実装 ~0.7k LOC、quantum は原論文の 10ms から
  ストレージ向けに 200ms へ変更)、BATMAN(~0.4K LOC)、Colloid(HeMem 上に
  ~0.4K LOC)。Colloid は read しか均衡しないので write latency も考慮する Colloid+、
  パラメータ感度対策に θ=0.2, α=0.01 の Colloid++ も実装 (§3.3)。
- [paper] セグメントサイズの根拠: 4KB セグメントだと 512 倍のメタデータ + 小粒度
  I/O で帯域低下、大きすぎると性能 tier の利用効率が落ちる。2MB が両者のバランスで、
  他システムの選択とも一致 (§3.3, Table 3)。

## Evaluation
- Setup [paper]: 2階層 — Optane(性能)/NVMe(容量)と NVMe(性能)/SATA(容量)。
  デバイスは 750GB Intel Optane SSD P4800X、1TB Samsung 960 NVMe、1TB Samsung 870
  SATA(特性は Table 1)。サーバは 40-core Xeon Gold 5218R @2.1GHz、64GB DRAM、
  Ubuntu 20.04 (§4)。
- **静的 micro-benchmark(ストレージ管理層を単離、§4.1, Fig. 4)**: 20% hot set に
  90% の確率でアクセスする skew。負荷 1.0× = 性能デバイス帯域が飽和する最小負荷。
  Optane/NVMe、working set 750GB。
  - Random read-only: Orthus は Cerberus と同等スループットだが 690GB を複製
    (Cerberus は 50GB)。HeMem は 1.0× で頭打ち(飽和後に容量デバイスへ offload
    しない)。BATMAN は高負荷のみ良好。Colloid はバックグラウンド活動由来の
    レイテンシスパイクが migration を誘発し 2.0× で大幅劣化、Colloid++ で改善する
    ものの、Colloid / Colloid++ は Cerberus の 2.68× / 1.24× の migration トラフィックを
    発生(2.0× で 134 / 62 GB vs Cerberus 50GB)(§4.1, Fig. 4a とキャプション)。
  - Random write-only: Orthus は静的 write-back で write を分散できずスケールしない。
    BATMAN は read と write で必要な割当比が違い高負荷で崩れる。Colloid は write
    非分散で HeMem 並み、Colloid+/++ は分散するが migration オーバーヘッドが残る。
    Cerberus は mirrored class 内で write を分散しレイテンシスパイクにも頑健 (§4.1,
    Fig. 4b)。
  - Sequential write(flash cache / FS / DB のログ構造トラフィックを模擬): Colloid+/++
    は demote されたブロックが再アクセスされないため migration が全て無駄になり
    むしろ悪化。Cerberus は性能デバイス飽和時に新規 write を容量デバイスへ直接
    割り当てる (§4.1, Fig. 4c)。
  - Read latest(write 50%、新規ブロックの 20% が 90% の確率で read される):
    migration したブロックがすぐ cold 化するため Colloid 系は 1.0× 超で HeMem より
    悪い。Cerberus は動的 write allocation で両デバイス帯域を使う (§4.1, Fig. 4d)。
- **動的バーストワークロード (§4.2, Fig. 5)**: 1000 秒の高負荷 warm-up 後、15 分ごとに
  2 分バースト。Optane/NVMe、working set 1.2TB。
  - read-only: 負荷低下時、Colloid は hot set を性能デバイスへ promote し直す大量
    トラフィックでスループットを毀損。Cerberus は 10 秒以内にルーティングだけで
    再均衡。バースト時は容量デバイスも使い HeMem 比 1.53×(低負荷時は HeMem と
    同等)(§4.2, Fig. 5a)。write-only では subpage による 4KB write 分散で高負荷時
    HeMem 比 1.48× (§4.2, Fig. 5b)。
  - device write: 3 ワークロード平均で Colloid(Fig. 5 キャプションの個別値は
    Colloid++)は性能 tier へ 252GB + 容量 tier へ 229GB を migration するのに対し、
    Cerberus は容量 tier への平均 86GB のミラーのみ (§4.2, Fig. 5 キャプション)。
    read-only を1日続けると migration は 6.6 / 3.1 DWPD 相当: 30 DWPD・5年保証の
    性能 tier デバイス寿命は Cerberus 5.0 年 vs Colloid 4.1 年(−18%)、0.37 DWPD・
    3年定格の 1TB 容量 tier は Colloid の 3.1 DWPD で 3.0 年 → 129 日(−88%)(§4.2)。
  - 収束時間: migration レート制限 100MB/s(5 DWPD)だと Colloid は負荷増への適応に
    800 秒超。Cerberus は 10 秒未満で、hot set サイズにも非依存(ミラー済みなら
    migration 不要)(§4.2, Fig. 6a, 6b)。
- **In-depth (§4.3, Fig. 7)**: working set が総容量の 95% でもミラーは総データの
  1.8%(50% write・128 threads の高負荷)(Fig. 7a)。subpage 無しだと負荷急減
  (128→8 threads)時に 2MB セグメント全体の migration が必要になり収束が大幅に
  遅い (Fig. 7c)。selective cleaning: 非選択 clean はスループット −25% に対し clean
  ブロック率 +5% しか稼げない。選択則は高頻度 write データを除外し 30 秒周期の
  write だけを clean (Fig. 7d)。
- **CacheLib end-to-end(CacheBench、§4.4)**:
  - 静的: SOC(1KB KV、Zipfian、25M keys)では Colloid 系は特に NVMe/SATA(read/write
    干渉が Optane より激しい)で劣化。LOC(16KB、ログ構造 write + log head read)では
    HeMem / Colloid は飽和後に容量帯域を使えず、Cerberus は Optane/NVMe で最大
    1.36×、NVMe/SATA で最大 1.54× (§4.4.1, Fig. 8)。CPU オーバーヘッドは最良
    baseline(Colloid++)比 0–1.5% 増(256 threads、ミラー追跡+ルーティング分)
    (§4.4.1)。
  - Meta の本番トレース4本(Table 4: flat-kvcache / graph-leader は小 value で
    ランダム系、kvcache-reg / kvcache-wc は大 value でログ構造系): A・B は Colloid 系を
    僅差で上回り、C・D は動的 write allocation により大差。Colloid 比の平均スループット
    は Optane/NVMe で 1.24×、NVMe/SATA で 1.17× (§4.4.2, Fig. 9)。レイテンシは最良
    baseline 比で平均 avg −14% / P99 −19%(Optane/NVMe では −20% / −26%、
    NVMe/SATA は −6.6% / −12%)(§4.4.2, Table 5)。
  - 動的キャッシュ(180 秒ごと 60 秒バースト、95% GET): Colloid は migration
    トラフィックを撒き散らして追従できず、Cerberus は migration なしで適応 (§4.4.3,
    Fig. 10)。
  - YCSB(Zipfian θ=0.8、1KB value、lookaside 化拡張、E は CacheLib が range query
    未対応のため除外): 最良システム比 最大 1.43× スループット・P99 −30% (§4.4.4,
    Fig. 11)。
- [inference] 評価がカバーしていないもの:
  - リモート階層(NVMeoF / disaggregated SSD / EBS)は §2.1 で動機付けに使われるが
    実験は全てローカル 3 デバイス。ネットワーク変動下での feedback 制御は未検証。
  - 2 層・各層 1 デバイスのみ。multi-tier とデバイス複数台(RAID 的束ね)は §5 で
    future work と明言される通り実験なし。
  - §3.2.5 の tail latency 保護(offloadRatioMax の手動設定)の効果を直接検証する
    実験は見当たらない。P99 の改善は報告される (Table 5) が、保護ノブの感度分析は
    ない。
  - HeMem / BATMAN / Colloid は著者らによる CacheLib 層への再実装(かつ Colloid は
    本来メモリ tiering 向けで quantum 等をストレージ用に改変)であり、原実装との
    忠実性は Colloid+/++ という派生を作っている点からも論文内で完結した検証は
    できない。
  - micro-benchmark の skew は 20%/90% 固定(§4.1)。hot set が mirrored class 上限
    (総容量 20%)を大きく超えるワークロードでの挙動は Fig. 7a(working set 掃引)は
    あるが、hotness が平坦な(skew の弱い)ワークロードの明示的な掃引はない。
  - 電源断・クラッシュ時のメタデータ(in-memory 76B/segment)復旧の実験なし。

## Limitations
- Stated [paper]:
  - multi-tier への一般化はより高度な最適化ポリシーが必要で future work (§5)。
  - 強い一貫性保証は未提供。mapping 更新の WAL 化という方向性のみ提示 (§5)。
  - テナント非認識のブロックレベル管理であり、performance isolation / QoS はヒント
    導入による将来拡張 (§5)。
  - CPU 使用率が最良 baseline 比 0–1.5% 増(ミラー追跡・ルーティングロジック)
    (§4.4.1)。
  - cleaning が必要になるのは「write スパイク後に頻繁に read される」タイプの
    ワークロードに限られ、選択則は rewrite distance ヒューリスティクスに依存 (§3.2.4)。
- Inferred [inference]:
  - offloadRatio という単一スカラーが「mirrored read の振り分け」「新規 write の割当」
    「migration 方向」を全て駆動する (§3.2.1, §3.2.2, §3.2.3)。read と write で最適な
    振り分け比が異なるワークロード(BATMAN が §4.1 でまさにこれで崩れる)では、
    end-to-end レイテンシの均衡という単一目的が read/write 個別の SLO と乖離する
    可能性がある。読み書き別の offloadRatio を持たない理由は本文に議論がない。
  - mirrored class の効果は「ホットデータが小さい」ことに依存する。Fig. 7a は
    working set 掃引で総データの 1.8% ミラーを示すが、これは 20%/90% skew の下での
    結果であり、skew が弱いと mirrored class 上限(総容量 20%, §3.2.3)まで拡大しても
    ルーティング可能なトラフィック割合が小さく、classic tiering との差が縮むはず。
  - 空き容量 watermark 2.5% (§3.2.3) はミラー用の余剰容量が常に確保できる前提。
    容量がほぼ満杯のシステムでは mirrored class が実質確保できず、MOST の利点が
    消える(Table 2 で MOST の CapacityUtilization を High とする主張は「ミラーが
    小さい」ことに依存)。
  - レイテンシ計測は Linux block layer カウンタの 200ms EWMA (§3.3)。SSD 内部 GC の
    ようなミリ秒〜秒スケールのスパイクへの頑健性は Colloid との比較で示されるが、
    より短周期の振動(200ms 未満)や計測とルーティングのフィードバック発振の
    安定性解析はない。

## Relations
- 競合 baseline(本文 §2.2, §4): HeMem(hotness tiering)、BATMAN(固定比 tiering)、
  Colloid(レイテンシ均衡 tiering)、Orthus(non-hierarchical caching)、striping。
  Orthus は同一グループの前作で、確率ルーティング (§3.2.1 [69]) と ratioStep の
  選択 (§3.3) を MOST が引き継いでいる。
- [[2026-sigmod-chen-cloudjump3.md]](CloudJump III: クラウド DB の tiered storage):
  同じ「ホット/コールドの階層配置」問題を、CloudJump III は DB カーネル内の
  エンジン可視メタデータ(ページ種別・LSN 等)で解くのに対し、MOST/Cerberus は
  エンジン非依存のブロック層でレイテンシ feedback により解く。[inference] 「配置の
  知識はどの層が持つべきか(エンジン内 vs 汎用ブロック層)」という対立軸で読み
  合わせる価値がある。MOST 自身がテナント/上位非認識を limitation として認めている
  (§5)。
- [[2026-pvldb-lee-how-to-write-to-ssds.md]](How to Write to SSDs: WA と寿命):
  MOST の §4.2 の DWPD ベースの寿命分析(migration write が容量 tier SSD の寿命を
  3.0 年 → 129 日に縮める)は、device write を第一級のコストとして扱う点でこの
  論文の問題意識と直結する。[inference] あちらは DB WAF × SSD WAF の乗算構造を
  扱うが、tiering の migration write はその上にさらに乗る「配置層 WAF」と見なせる。
- [[2026-eurosys-kumar-tierscape.md]](TierScape: 複数圧縮 tier のメモリ tiering):
  MOST が §2.3 で対比する「メモリ階層の tiering(migration ベースで成立)」側の
  最新例。[inference] MOST の主張(ストレージでは migration 依存が破綻する)が、
  TierScape のような TCO 主目的・コールドデータ中心の tiering にも当てはまるかは
  別問題(あちらは帯域負荷分散ではなく容量コスト最適化)。
- [[2026-eurosys-hombal-disagg-cache.md]](Ldc: レプリカキャッシュの論理分離):
  [inference] 方向は逆(Ldc は重複キャッシュの削減、MOST は少量の意図的な複製の
  追加)だが、どちらも「ホットデータの複製数を負荷とコストの均衡で動的に決める」
  機構(Ldc の R_opt 解析モデル vs MOST の mirrored class サイズ + offloadRatio
  feedback)を持ち、選択的複製のサイジングという共通軸で比較できる。

## Idea seeds
- [inference] MOST の rewrite distance(write 間の平均 read 回数、§3.2.4)はブロック層で
  観測できる代理指標に過ぎない。DB エンジンなら「このページはトランザクションで
  すぐ dirty 化する」ことを buffer manager が事前に知っている(CloudJump III の
  エンジン内 tiering と接続)。エンジンのヒント(ページ種別・checkpoint 周期)を
  Cerberus 的なミラー層に渡し、ミラーの無駄(複製直後の invalid 化)がどれだけ減るかを
  測る実験が第一歩。CacheBench ではなく TPC-C 系の write パターンで mirrored copy の
  invalid 化率を計測するところから。
- [question] durable な DB ストレージの下に MOST を置く場合、mapping(どちらの
  コピーが valid か)の永続化が必要になる(§5 は WAL 化を示唆するのみ)。subpage の
  2 bit 状態を write パスで journal するコストは、MOST が稼ぐ負荷分散利得を食い潰さ
  ないか。検証: invalid/location bit 更新を NVMe 上の小さなログに同期追記する
  プロトタイプを作り、Fig. 4b 相当の write-only 負荷で劣化幅を測る。
- [inference] offloadRatio が read ルーティング・write 割当・migration 方向を兼ねる
  単一制御変数である点 (§3.2.1–3.2.3) は、read SLO と write SLO が分かれる HTAP 的
  ワークロードでは制約になりうる。read 用と write 用の 2 変数制御(または要求
  クラス別 offloadRatio)にしたとき安定性が保てるかは開いた問題。検証: §4.1 の
  read latest 型ワークロードで read P99 制約を課し、単一変数と 2 変数の Pareto を
  比較するシミュレーションから。
- [question] 「性能比が 1.5:1 程度まで縮んだ階層」(§2.1, Table 1) が MOST の利得の
  前提に見えるが、逆に性能差が大きい伝統的階層(NVMe/HDD 等)では offload の利得が
  ほぼ消え、classic tiering と等価になるはず(Algorithm 1 上は offloadRatio≈0 に収束)。
  利得が有意になる性能比の境界はどこか。デバイス性能比を fio 等で人工的に絞りながら
  Fig. 4 相当を再現すれば特定できるが、Cerberus のコード公開の記述は本文に見当たら
  ない(再実装が必要)。

## Changelog
- 2026-07-06: created (status: read)
