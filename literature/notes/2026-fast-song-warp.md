---
title: "Characterizing and Emulating FDP SSDs with WARP"
authors: [Inho Song, Shoaib Asif Qazi, Javier González, Matias Bjørling, Sam H. Noh, Huaicheng Li]
venue: "FAST '26 (24th USENIX Conference on File and Storage Technologies)"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/fast/SongQ0BNL26"}
urls: {paper: "https://www.usenix.org/conference/fast26/presentation/song", pdf: "literature/pdfs/2026-fast-song-warp.pdf", code: "https://github.com/MoatLab/FEMU"}
status: read
read_date: 2026-07-06
tags: [fdp, ssd, write-amplification, garbage-collection, flash, emulation, femu, data-placement, characterization, over-provisioning, cachelib, f2fs]
---

## TL;DR
NVMe Flexible Data Placement (FDP) SSD の初の系統的クロスデバイス特性評価と、初の
オープン FDP エミュレータ WARP(FEMU 拡張、upstream 済)。商用 FDP SSD 2 台の測定で、
FDP は RUH 分離がデータ寿命と整合すれば WAF≈1 を維持するが、誤分類・RUH 間干渉・
一様ランダム無効化で崩壊し、ベンダ間で挙動が大きく異なることを示す。WARP は実機の
WAF 傾向を再現しつつ、実機では不可視の per-RUH 動態(未報告現象 Noisy RUH /
Save Sequential)と設定ノブ(II/PI、RU サイズ、OP 比、GC 方策)を公開し、
II と PI の優劣が OP 依存でクロスオーバーすること、小 RU 割当でハードウェアの
FDP(WAF 1.37)を超える 1.16 まで下げられることを示した。

## Problem & motivation
- [paper] WAF(GC による余剰書き込み)は SSD 寿命・交換コスト・環境負荷に直結し、
  hyperscale では WAF の一桁の変化が数百万ドル規模のコスト差になる (§1, p.2)。
- [paper] Google / Meta などの hyperscaler が主導した FDP は NVMe 標準
  (TP4146)として批准され、主要ベンダが FDP SSD を出荷し始めた。ホストは書き込みを
  reclaim unit handle (RUH) という論理グループにタグ付けし、似た寿命のデータを
  一緒に回収させることで WAF を 1.0 に近づける (§1, §2, p.2–3)。
- [paper] しかし FDP は保証ではなく best-effort インタフェース: OpenChannel / ZNS と
  違い GC は完全にデバイス管理のままで、reclaim 方策はソフトウェアから不透明かつ
  デバイス固有。ワークロードの寿命が RUH 分離と整合しないと利得は消える (§1, p.2)。
- [paper] 商用 FDP SSD は同じ NVMe FDP インタフェースを露出しながら、RU サイズ・
  over-provisioning (OP) 比・RUH 数・Initially Isolated (II) か Persistently
  Isolated (PI) かをベンダごとにハードコードしており、ホストから不可視。同じ
  ワークロードがあるデバイスでは理想的 WAF、別のデバイスでは崩壊しうる。この
  仕様と実際の乖離が FDP 採用の最大の障壁と位置付ける (§1, p.2)。
- [paper] 既存研究は CacheLib への FDP 統合(production trace で near-ideal WAF)や
  NVMe ドライバパッチ・F2FS の FDP ヒントなど単一アプリスタックに留まり、デバイス
  横断・ワークロード横断の特性評価がなく、商用ドライブが不透明なため「なぜ効く/
  効かないか」を説明できない (§1, p.2)。
- [paper] 本論文の 3 つの問い: FDP はいつ near-1 WAF を達成し、いつ失敗するか。
  どのベンダレベル構成が差を生むか。デバイス間の差異を説明する内部機構は何か (§1, p.2)。

## System model & assumptions
- [paper] FDP の 3 抽象: Reclaim Unit (RU) = GC の粒度(通常 NAND superblock)、
  Reclaim Group (RG) = まとめて管理される RU の集合(通常 NAND die 単位)、
  RUH = ホスト書き込みを特定 RU へ誘導する論理 ID (§2, Fig. 1)。
- [paper] II は GC コピーを共有 GC-RUH へリダイレクト(元のタグを破棄)、PI は
  GC コピーを元 RUH 内に保持して GC 跨ぎの分離を維持する (§2, Fig. 1d–e)。
- [paper] 先行インタフェースとの位置付け: OpenChannel は配置と GC をホストに委譲
  (高複雑性)、ZNS は sequential zone write とホスト管理 reset を強制(侵襲的な
  アプリ変更が必要)、Multi-streamed SSD は軽量タグのみで物理分離の保証なし。
  FDP はブロックインタフェース後方互換・アプリ変更不要の中間で、GC は不透明な
  ベンダ管理のまま (§2, p.4)。
- [paper] FDP には optional の可視化機能もある: RU 空き容量クエリと、RU 割当・
  remap・一部 GC 統計を記録するイベントログ (§2, p.3)。
- [paper] ソフトウェアエコシステムは未成熟: Linux は NVMe I/O passthrough 経由で
  RUH を渡す early driver support のみで、正式なブロック層統合は無く、主要
  ファイルシステム・アプリは未対応 (§2, §3.1)。
- [paper] 実機テストベッド: 異なるベンダの SSD_A (7.68TB, U.3) と SSD_B (3.84TB,
  E1.S)。共に PCIe Gen5・NVMe 2.1 準拠・RUH 8 本・シーケンシャル書き込み
  ~5GB/s。サーバは Xeon Gold 5416S (2.0GHz) + 500GB DRAM、Linux v6.8 + FDP
  パッチ (§3.1, Table 1)。実機の内部構成は非開示 (Fig. 3 caption)。
- [paper] WAF は「ホスト書き込みデータ量をデバイス容量で正規化した量 (rHMW =
  Host Media Written / Device Capacity)」の関数として報告する (§3.2, Fig. 3 caption)。
- [paper] 今日の商用デバイスは II セマンティクスのみを露出する(II は legacy FTL
  への変更が最小で済むため初期設計で採用されたと説明)(§4.2, §7)。Table 2 でも
  SSD_A / SSD_B は共に II と記載される (Table 2)。
- [paper] WARP は FEMU 上に構築された userspace (QEMU) エミュレータで、FEMU の
  デフォルト SSD 構成(8 channel × 8 die/channel、4KB ページ、FEMU の NAND
  タイミング)を維持し、その上に FDP 抽象を重ねる (§4.6, §5, §6.2)。
- [inference] 対象はあくまで単一デバイス内の WAF 動態。RG(die 単位のグルーピング)は
  §2 で定義されるが、以降の実験の操作変数としては現れず、RG レベルの配置効果は
  本論文のスコープ外に見える。

## Approach
### 実機特性評価 (§3)
- [paper] 3 種のワークロード: FIO 合成マイクロベンチ(1–3 ストリーム、各ストリームを
  別 RUH + 互いに素な LBA 範囲に割当)、Meta の CacheLib production trace
  (kvcache / cdn / twitter; 大オブジェクト LOC と小オブジェクト SOC を別 RUH に
  マップ)、F2FS 上の Filebench(Fileserver / OLTP; F2FS のデータ分類で RUH 割当)
  (§3.1, §3.2, Table 1)。
- [paper] SSD_B は評価中の過剰書き込みで故障したため部分的な結果のみ提示 (§3.2)。
- [paper] 1 ストリーム 128KB 一様ランダム書き込み(FDP なしのベースライン相当):
  WAF は理想 1.0 から急上昇しデバイス固有の定常値で頭打ち — SSD_A ≈2.0、
  SSD_B ≈3.5。ベースライン WAF はベンダのジオメトリと GC 方策で決まる (§3.2, Fig. 2)。
- [paper] 2 ストリーム: ブロックサイズ違い (16KB vs 256KB) のシーケンシャル 2 本では
  NoFDP が ~1.1(進行のずれによる部分充填ブロックが GC を誘発)、FDP は ~1.0。
  シーケンシャル+ランダム混合では NoFDP が 90:10 でも 2.3 超、50:50 で 2.4 の
  ピーク。FDP は全ミックスで near-ideal を維持 (§3.2, Fig. 4)。→ Observation #1。
- [paper] 3 ストリーム(シーケンシャル+ランダム+overwrite; overwrite は Zipfian
  α=1.2/2.2 または 80/20)。MixedFDP 設定はシーケンシャルと overwrite を故意に
  同一 RUH に置き、誤分類・静的 RUH 割当をモデル化する (§3.2)。SSD_A では FDP が
  Zipfian 両方で ~1.0 を維持するが 80/20(更新が LBA 空間に広く分散)で崩壊。
  SSD_B は FDP でも歪んだワークロードで 1.3–1.5、80/20 で 3.0 超。MixedFDP は
  歪みが強い (Zipf 2.2) と FDP 並みだが 80/20 で NoFDP に収束 (§3.2, Fig. 3)。
  → Observation #2(RUH 内の寿命異質性・誤分類が FDP を無効化する)。
- [paper] 最悪ケース: overwrite を一様ランダム無効化ストリームに置き換えると GC に
  最適化の余地がなく、SSD_A は FDP/MixedFDP/NoFDP がほぼ一緒に上昇して 4× 容量で
  2.58×、SSD_B は FDP でも 4.49×(本研究での最大 WAF)(§3.2, Fig. 5)。
- [paper] CacheLib: SOC (BigHash; 2KB 以下、4KB バケットを更新のたび全書換え =
  ランダム書き込み源) と LOC (BlockCache; 16MB セグメントのログ追記 = デバイス
  フレンドリー) を別 RUH にマップ。SOC を SSD 容量の 4/20/40% で走らせ、結果は
  SSD_A + CacheLib v20240621 (§3.3)。kvcache では NoFDP の WAF が約 8TB 書き込み後に
  上昇し 20% で 1.64、40% で 1.85(4.6TB 超の内部再書き込み)。FDP では全割当で
  ~1.0(20% で 1.08)(§3.3, Fig. 6)。ヒット率は FDP/NoFDP とも高 SOC で約 82% と
  保存され、FDP は「ヒット率 vs 耐久性」のトレードオフを破る (§3.3, Fig. 8)。
- [paper] cdn / twitter trace は元々アクセスパターンがデバイスフレンドリーで両構成とも
  ~1.0。FDP は利得がない場合も退行しない(安全なデプロイ特性)(§3.3, Fig. 7)。
- [paper] マルチテナント模擬(CacheLib 60% + 雑多なアクセスの他アプリ 40%):
  NoFDP では kvcache の WAF が 1.28 から約 3.0 へ悪化。FDP ではノイジーテナントの
  寄与が小さく最大でも 2.6 に留まる (§3.3, Fig. 9)。→ Observation #3(マルチテナントで
  WAF を最大 50% 削減)。
- [paper] F2FS はデータ種別と温度で最大 6 ハンドルにタグ付けするが、Fileserver
  (200 スレッド、540KB ファイル 1000 万個、256KB I/O、10 時間で 28TB 書き込み)でも
  OLTP でも FDP の改善はゼロ(両ドライブとも 2.3–2.5 で安定)(§3.4, Fig. 10)。
  eBPF での I/O ヒント追跡により、ユーザデータの 99% が WARM → 汎用
  WRITE_LIFE_NOT_SET にラベルされ、ほぼ全書き込みが単一 RUH に集中して FDP が
  NoFDP に退化していることを特定 (§3.4, Fig. 11)。node / metadata セグメントの分離
  だけでは不十分で、ユーザデータのより細かい分類が必要 (§3.4)。→ Observation #4。

### WARP の設計 (§4)
- [paper] 3 つの提供能力: (1) NVMe 定義の II / PI 両セマンティクスの明示的実装
  (両対応のオープンエミュレータは初)、(2) RU サイズ・OP 比・RUH 数・GC
  ヒューリスティクス・lazy 閾値・block remapping を実行時ノブ化、(3) per-RUH の
  カウンタ・イベントログによる可観測性 (§4.1)。設計契約: RUH マッピングは決定的、
  isolation セマンティクスは一貫執行(II = GC コピーを共有 GC-RUH へ、PI = 元 RUH
  内に保持)、RU 粒度は実行開始時に固定 (§4.1)。
- [paper] インタフェース: FEMU を拡張して NVMe コマンド中の FDP placement hint を
  パースし、タグ付き書き込みを RU(NAND ブロックの論理グループ、例: superblock)へ
  マップ。各 RUH は active RU への write pointer を 1 本以上持つ。PI モードでは
  追加の per-RUH GC write pointer でホスト/GC データを厳密分離(ただし OP 空間を
  断片化する)(§4.2)。
- [paper] GC を 2 つの決定に一般化: ①どの RUH から回収するか(greedy = 最も圧の
  高い RUH、pressure-based = live/free 比)、②その RUH 内のどの RU か(greedy =
  valid ページ最少、cost-benefit = (1−u)/u × age、LFS 由来)(§4.3)。
- [paper] エンタープライズ SSD 相当の最適化も実装: Lazy GC(RU の valid 占有率が
  閾値 5–10% を下回るまで回収延期)、background GC(RU 割当 ~90% で起動)と
  foreground GC(~99% の枯渇間際)の区別、block remapping(victim RU 内の全 valid
  ブロックは移動なしで宛先 RU に再マップ)(§4.3)。
- [paper] ジオメトリノブ: RU サイズ(例: 128/256/512MB)、OP 比(1–28%)、RUH 数
  (§4.4)。
- [paper] テレメトリは 3 レベル: デバイス(host bytes / media bytes / 全体 WAF)、
  RUH(host bytes、GC コピー bytes、remap 済みブロック、割当・追い出し、回収時
  平均 valid ページ数)、GC イベント単位(victim RUH・対象 RU・宛先 RUH・適用
  方策・live/コピーページ数・所要時間)。構造化ログとして出力し、実機との検証と
  再現性を担保 (§4.5)。
- [paper] キャリブレーション手順: ジオメトリと GC 閾値を実機の定常 WAF プラトーに
  一致するまで調整し、その後 multi-stream / trace ワークロードで検証する (§4.5)。
- [paper] コードは FEMU に upstream 済み (https://github.com/MoatLab/FEMU) (§1, p.3)。

## Evaluation
- Setup [paper]: WARP の較正済みデフォルトは RU=256MB、OP=10%、lazy GC 閾値 5%、
  block remapping 有効、RUH 8 本。FEMU デフォルトの 8ch×8die・4KB ページ・NAND
  タイミングを使用 (§5)。
- 忠実性検証 [paper]:
  - 1 ストリーム 128KB ランダム: 7 つの WARP 構成のうち WARP_2–7 が実機 2 台の
    スプレッド 2.0–3.5 の範囲に収まる(WARP_1 は例外)。WAF は固定的性質ではなく
    ジオメトリ+ファームウェア方策の創発的な結果であることを確認 (§5.1, Fig. 12)。
  - CacheLib kvcache202206: SSD_A が 40% SOC で 1.85 (NoFDP)→1.27 (FDP) と改善する
    のに対し WARP は 2.00→1.37 と同方向の改善を再現。4%/20% SOC の near-ideal
    (1.0–1.1) も一致 (§5.1, Fig. 13, Table 2)。
  - 3 ストリーム: WARP は FDP ≈1.0 / MixedFDP 1.3–1.6 / NoFDP →2.0 という SSD_A の
    序列と傾きを再現し、SSD_B の高増幅傾向(FDP ~1.3、NoFDP >2.5)も一致。絶対値は
    実機と 0.2–0.3 以内 (§5.1, Fig. 14, Fig. 15, Table 2)。→ Observation #5。
- Noisy RUH [paper]: per-RUH 分解(WARP_A、5× rHMW)で、シーケンシャル
  ストリームの RUH0 が 4.42–4.45× 容量分のトラフィック(書き込みの 88%)を吸収し、
  RUH1(ランダム)と RUH2(無効化)は各 5–6%。Zipfian では増幅のほとんどが RUH0
  由来で RUH1/RUH2 は無視できるが、80/20 ではトラフィック量がほぼ不変のまま
  RUH1 が全体の 26% (0.131)、RUH2 が 14% (0.070) の増幅を寄与する。犯人は RUH2 の
  無効化ストリームで、GC を攻撃的にし RUH1 の WAF を間接的に押し上げ、RUH 分離を
  破る。同じパターンは実機 (Fig. 3c, f) にも現れており、現行 FDP 実装の一般的性質と
  結論 (§5.2, Fig. 16)。→ Observation #6。
- Save Sequential [paper]: RUH0 はシーケンシャルであるにもかかわらずワークロード
  依存で 0.131–0.264 と WAF の過半を寄与する。本来 self-invalidate して増幅をほぼ
  生まないはずが、限られた OP と GC ヒューリスティクスにより「まもなく上書きされる
  データ」が早期回収される (§5.2, Fig. 16b)。→ Observation #7(WAF の見かけの
  被害者はしばしばノイジーな RUH ではなく容量支配的な RUH)。
  - [question] §5.2 の本文では 80/20 の RUH1 寄与が 0.131 とされる一方、Save
    Sequential の段落では RUH0 の寄与範囲が 0.131–0.264 と書かれており、抽出テキスト
    からは同じ 0.131 がどちらの RUH に帰属するのか一意に読み取れない(Fig. 16b の
    数値ラベルの帰属を PDF の図で再確認したい)。
- PI モードの per-RUH WAF [paper]: Per-RUH-WAF = (RUH_i の GC データ)/(RUH_i の
  書き込みデータ) と定義し、80/20 では RUH1・RUH2 の per-RUH WAF が 3.8× まで
  上がる (Fig. 17)。
- II vs PI の OP トレードオフ [paper](80/20、5× rHMW = 224GB)(§5.3, Fig. 18, 19):
  - RU 256MB: OP 3% で II 2.921 vs PI 3.809、OP 5% で II 2.187 vs PI 2.365 と II 優位。
    クロスオーバーは OP 7–9% 付近で、OP 10% では II 1.338 vs PI 1.181 と PI が逆転。
  - RU 128MB: OP 3% で II 2.521 vs PI 2.781、OP 5% でも II 1.740 vs PI 1.908 と II
    優位が続き、OP 10% でほぼ拮抗(II 1.129 vs PI 1.091)。小さい RU ほど PI が
    理論下限を発揮するのに多くの OP 予算を要する (§5.3, Fig. 18b)。
  - 機構の説明: PI は GC コピーまで RUH ごとに隔離するため spare pool を断片化し、
    OP が乏しいと各 RUH の slack が枯渇して GC が頻発。II は GC-RUH に spare を
    プールしてストリーム横断で GC コストを平準化できるため OP 逼迫時に強い。OP が
    潤沢なら PI の隔離が効いて II より低い WAF に到達する (§5.3)。
  - PI の脆さ: RUH 数の増加やワークロードの異質化に対し、PI は優位維持に不釣り合いに
    大きな OP を要求し、条件次第で II より悪化する。II は下限こそ高いが GC-RUH が
    競合を吸収するため頑健 (§5.3, p.13)。→ Observation #8。
  - [question] 本文は RU 128MB で「クロスオーバー点は上方にシフトする」と述べる
    (§5.3) が、Fig. 19 のキャプションは RU 128MB のクロスオーバーを 5–7% OP
    (RU 256MB の 7–9% より低い)と記しており、原文内で記述が食い違って見える。
- WARP 誘導の最適化 [paper] (§6.1, Fig. 20): kvcache202206 の 40% SOC で、SOC 用
  ハンドル (RUH0) に小さな RU(単一チャネルにマップされた RU)を割り当てるだけで、
  WAF が NoFDP 2.0 / FDP 1.37 からさらに 1.16 へ低下。利得は ①小 RU は GC 1 回
  あたりの回収ページが少ない、②単一チャネル制約が SOC の並列 GC 活動を暗黙に
  スロットルし Noisy RUH 効果を抑制、の 2 点。効果は重い SOC (40%) で大きく、
  軽い SOC (4%) では最小。adaptive(動的)RU sizing や RUH を考慮した FDP-aware
  リクエストスケジューラという方向性を提示 (§6.1)。
- レイテンシ忠実性 [paper] (§6.2, Table 3): 4K ランダムリードで WARP 335K IOPS vs
  実機 SSD_A 460K。p50 は同一 70µs、p99 77µs vs 80µs、p99.999 457.4µs vs 967µs と
  中央値〜主要テールがほぼ一致し、GC 由来のテールスパイクも現実的。チューニングの
  要点は NVMe doorbell write を無効化して高価な VM-exit / MMIO を除去すること (§6.2)。
  - [question] §6.2 本文は「4KB high-queue-depth ワークロード」で 335K IOPS と
    述べるが、Table 3 のキャプションは「4K random read workload (QD=1)」であり、
    どの QD の測定なのか抽出テキストからは判然としない。
- [inference] 評価がカバーしていないもの:
  - 実機側の「クロスデバイス」は 2 台のみで、SSD_B は評価中に故障し部分結果
    (§3.2 は paper claim)。CacheLib / F2FS の主要実験や WARP 較正の基準は実質
    SSD_A 中心であり、ベンダ多様性に関する一般化(特に Noisy RUH が「現行 FDP
    実装の一般的性質」という主張)は 2 サンプルに基づく。
  - WARP の容量は 240–458GB、実機は 3.84–7.68TB (Table 2)。rHMW 正規化で傾向を
    比較するが、容量スケール自体が GC 動態(RUH あたり slack、GC 頻度)に与える
    影響の検証はない。
  - Table 2 では II デバイスとされる SSD_A に対し、検証構成 WARP_A は PI モードで
    一致を得ている(別行の WARP_A2 は II)。WAF 曲線の一致は内部構成の同定を
    意味しない(異なるノブの組合せが同じ WAF を生む equifinality)ため、WARP の
    キャリブレーションは curve fitting であり、実機ファームウェアの機構推定としての
    妥当性は別途保証されていない。
  - レイテンシ検証は 4K ランダムリードのみ (Table 3)。書き込みレイテンシ・混合
    負荷・GC 干渉下のテールの実機比較はない。スループットも 335K vs 460K IOPS と
    実機の約 73% で、性能忠実性は WAF 忠実性より粗い。
  - §6.1 の小 RU 最適化はスループットへの影響(単一チャネル化による帯域低下)を
    定量化しておらず、WAF 改善のみが示される(本文もスループット感度との相互作用を
    今後の課題として言及するに留まる)。

## Limitations
- Stated [paper]:
  - FDP は best-effort であり、利得はワークロードと構成に依存する。誤分類・RUH 間
    干渉・敵対的アクセスで崩壊し、不透明な内部方策によりベンダ間で大きく異なる
    (§1, §2, §3.2 Observation #2, p.7 の総括)。
  - 一様ランダム無効化の最悪ケースでは FDP の優位はほぼ消え、従来 SSD の挙動に
    収束する (§3.2, Fig. 5)。
  - F2FS の FDP 対応は現状実質無効(99% のユーザデータが単一ヒントに集中)
    (§3.4, Fig. 11)。
  - Linux のブロック層 FDP 統合は未整備で、I/O passthrough が唯一の upstream 経路
    (§2, §3.1)。
  - 商用デバイスは II のみ露出しており、PI・ハイブリッド方策の実機検証は不可能
    (WARP でのみ可能)(§7)。
- Inferred [inference]:
  - WARP の忠実性主張は「WAF の傾向・序列の再現」(絶対値差 0.2–0.3)に基づく。
    per-RUH 現象(Noisy RUH / Save Sequential)の実機側の裏付けは WAF 曲線の形状
    一致 (Fig. 3c, f) による間接的なもので、実機の GC ログによる直接確認はない。
    §2 で言及される FDP の optional イベントログ(RU 割当・remap・GC 統計)を実機
    検証に使ったという記述もない。
  - II/PI・OP・RU サイズの知見は 80/20 という単一のストレスワークロード(+ Zipfian)
    での結果であり、production trace(CacheLib)上で II vs PI を比較した実験はない。
  - SSD の摩耗・エラー・wear leveling はモデル化の記述がなく、WAF と平均/テール
    レイテンシ以外のデバイス挙動(温度・スロットリング等)は扱われない。

## Relations
- [[2026-pvldb-lee-how-to-write-to-ssds.md]] (How to Write to SSDs): DB 層から
  Total WAF = DB WAF × SSD WAF を統合管理し FDP ヒント等で SSD WAF=1 を狙う
  アプローチ。WARP の特性評価はその前提「FDP ヒントが期待通り分離する」が破れる
  条件(誤分類、Noisy RUH、一様無効化、ベンダ差)をデバイス側から定量化しており、
  DB/SSD 協調設計の頑健性を試す反例集+実験基盤として直接接続する。
- [[2026-fast-bian-discard-gc.md]] (DisCoGC): WA = LWA × PWA の分解のうち、DisCoGC は
  分散ログ層の logical WA を discard で削る話、WARP はデバイス内 physical WA
  (SSD 内 GC)の観測・操作基盤。ログ層の discard/trim がデバイス GC に与える影響を
  制御実験する場として補完的。
- [[2026-cidr-houlborg-xnvme.md]] (xNVMe/nvmefs): FDP へのアクセス経路が NVMe I/O
  passthrough に限られるという同じエコシステム制約 (§2, §3.1) を上位(DBMS I/O
  抽象)から解こうとする論文。xNVMe が「FDP を叩く統一 API」、WARP が「FDP の
  中身を見るエミュレータ」で、フルスタック FDP 研究として相補的。

## Idea seeds
- [inference] DB エンジンの FDP 頑健性テスト: How-to-Write-to-SSDs 系の out-of-place
  B-tree(deathtime グルーピング + FDP ヒント)を WARP 上で走らせ、Noisy RUH /
  Save Sequential を誘発する条件(コロケーション、一様無効化、SOC 相当の小粒度
  更新)下で DB 側の分類がどこまで防御できるかを per-RUH カウンタで測る。実機では
  不可能な「DB WAF と SSD WAF の同時分解測定」が WARP なら可能で、Phase 2 の
  検証実験として着手コストが低い(WARP は FEMU に upstream 済み)。
- [inference] LSM-tree のレベル別ストリームを RUH にマップした場合の II vs PI × OP
  クロスオーバーの測定。LSM はレベルごとに寿命が階層化しており FDP の想定に近い
  一方、compaction のバースト的なシーケンシャル書き込みは Save Sequential (§5.2) を
  誘発しうる。最初の検証: RocksDB 系を WARP 上で走らせ、レベル→RUH マッピングを
  変えながら per-RUH WAF と GC イベントログを比較する。
- [question] 商用 FDP SSD の optional イベントログ (§2) から Noisy RUH / Save
  Sequential を実機上で直接観測できるか。可能なら WARP のキャリブレーションを
  「WAF 曲線の curve fitting」から「GC イベント列の機構同定」へ格上げでき、
  Table 2 の equifinality 問題([inference] 参照)にも答えが出る。
- [inference] adaptive RU sizing の具体化 (§6.1 が open direction として提示):
  RUH ごとの書き込みレート・無効化パターンから RU サイズを動的に決める firmware
  方策を WARP に実装し、静的な小 RU 割当の 1.16 (Fig. 20) を下回れるか、および
  単一チャネル化のスループット犠牲がどの程度かを測る。スループット vs WAF の
  トレードオフ定量化は本文が明示的に積み残した部分。

## Changelog
- 2026-07-06: created (status: read)
