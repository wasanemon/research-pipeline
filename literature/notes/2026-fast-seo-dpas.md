---
title: "DPAS: A Prompt, Accurate and Safe I/O Completion Method for SSDs"
authors: [Dongjoo Seo, Jihyeon Jung, Yeohwan Yoon, Ping-Xiang Chen, Yongsoo Joo, Sung-Soo Lim, Nikil Dutt]
venue: "FAST '26 (24th USENIX Conference on File and Storage Technologies)"
year: 2026
ids: {doi: "", arxiv: "", dblp: "conf/fast/SeoJYCJLD26"}
urls: {paper: "https://www.usenix.org/conference/fast26/presentation/seo", pdf: "literature/pdfs/2026-fast-seo-dpas.pdf", code: "https://github.com/DongDongJu/DPAS_FAST26"}
status: read
read_date: 2026-07-06
tags: [ssd, nvme, io-completion, hybrid-polling, interrupts, polling, linux-kernel, latency-tracking, tail-latency, cpu-contention, rocksdb, ycsb]
---

## TL;DR
SSD の I/O 完了検出(割り込み / polling / hybrid polling)のうち hybrid polling の
sleep 時間推定を、実測 I/O 時間の統計ではなく「直近 2 I/O の二値 sleep 結果
(UNDER/OVER)」からのフィードバック制御で行う PAS を提案。さらに、hybrid polling が
原理的に苦手な状況(タイマーオーバーヘッド、CPU 過負荷時の timer failure)に対して、
classic polling / PAS / 割り込みをコアごとに動的に切り替える DPAS を構築。Linux 5.18 の
multi-queue block layer に実装し、4KB random read で PAS は Linux hybrid polling 比
CPU 使用率 −21 ポイント、CPU 競合 + I/O 干渉の同時発生下で DPAS は YCSB を
3D XPoint SSD で +9%、TLC NAND SSD で +5% 改善(vs 割り込み)と主張。

## Problem & motivation
- [paper] 超低レイテンシ SSD では割り込みの隠れコスト(context switch、cache pollution、
  CPU power state 遷移)が顕在化する。polling はそれらを除去できるが CPU を占有し、
  CPU 競合下で性能が大きく劣化する (§1)。
- [paper] hybrid polling は I/O 処理時間の一部を sleep で過ごし、残りを polling する
  折衷案。理想は I/O 完了と同時に起床することだが、完了時刻の予知が必要。sleep が
  短すぎる undersleeping は CPU を浪費し、長すぎる oversleeping はアプリ知覚
  レイテンシを増やす。oversleep 回避が優先(polling の利得を容易に打ち消すため)
  (§1, §2.1, Fig. 1)。
- [paper] Linux hybrid polling (LHP) は I/O 統計を 16 バケット(read/write × サイズ 8 区分:
  1, 2–3, 4–7, 8–15, 16–31, 32–63, 64–127, 128+ セクタ)で保持し、100ms ごとに更新、
  sleep = 直近 epoch の平均 I/O レイテンシの 1/2(50% 減衰を安全マージンとする)(§2.2)。
- [paper] LHP の 3 つの欠点: ①Promptness — epoch 固定なので急激なレイテンシ変化を
  次 epoch まで反映できない。②Accuracy — レイテンシが安定していると 50% マージンは
  過大で、実完了よりかなり早く起床する。③Safety — 変動が大きいと 50% でも
  マージン不足で oversleep する (§2.2, Fig. 2)。
- [paper] 代替手法の限界: HyPI は I/O サイズ別の減衰率を使うがオフラインプロファイリングが
  必要で実行時変動に追従できない。EHP は直近 epoch の最小 I/O 時間を使い epoch を
  10ms に短縮するが、過度に保守的(早く完了した 1 個の I/O が次 epoch の sleep を
  支配し過剰 undersleep)で、epoch ベースの限界も引き継ぐ (§2.3, Fig. 2)。
- [paper] **latency shelving**: LHP/HyPI/EHP は「実測 I/O 総時間」のみに依存するため、
  デバイス由来の遅延と、予測誤差やスケジューリング遅延によるソフトウェア起因の
  oversleep を区別できない。CPU 競合下では OS 由来の遅延をデバイスレイテンシと
  誤解釈して sleep 目標を膨張させ、過剰 sleep 状態に固着する。回復には複数 epoch を
  要する (§2.3, Fig. 20(a))。
- [paper] LinnOS の NN による fast/slow 二値予測は hybrid polling に必要な精密な時刻
  推定を与えない (§2.3)。モード切替系の先行研究(Select-ISR / CINT はアプリ分類、
  HyPI / EHP は固定 I/O サイズ閾値、CPU 使用率で切り替える研究 [13])は静的閾値や
  事前定義クラスに依存し、一時的な OS スケジューラ遅延を実行時に検出する機構を
  欠く (§2.4)。
- [paper] 近年の研究 [40] が指摘した open problem =「高度に動的な I/O ワークロード下での
  正確な sleep 時間推定」に PAS/DPAS は取り組む (§6)。

## System model & assumptions
- [paper] 対象は Linux カーネルの multi-queue block layer における NVMe SSD の I/O 完了
  検出。PAS/DPAS はカーネル内実装で、polling は pvsync2 + hipri フラグの同期 polled I/O
  経路を使う (§3.6, §4.2)。CINT が使う非同期 I/O(non-urgent)は本研究のスコープ外 (§4.1)。
- [paper] sleep 結果の二値判定(起床時に I/O 未完了なら UNDER、完了済なら OVER)は、
  デバイスからの明示的シグナル無しに、カーネルの poll 関数の改変だけで得られる (§3.1)。
  sleep には Linux の高分解能タイマー hrtimer を使う (§3.1, Fig. 3)。
- [paper] PAS は LHP と同じバケット構造(サイズ × read/write)で I/O を分類し、バケットごとに
  制御変数を持つ (§3.1)。per-device モードは I/O が直列化されている想定で、並行 I/O には
  per-core モード(コアごとに PAS 変数一式)で対応する(メモリ増と引き換え)(§3.4)。
- [paper] EHP と同様、各 CPU に polled 用と割り込み用の 2 本のデバイスキューを割り当てる。
  CPU 数がデバイスキュー数を大きく超えると割り込みキューが複数 CPU で共有され性能が
  劣化しうる (§3.6)。
- [paper] パラメータはデバイス非依存を志向: (UP, DN) は適応速度の制御であり絶対
  レイテンシに依存しないため robust な設定を決められる (§3.2)。動的感度調整により
  実行時チューニング不要 (§3.3, §4.4)。唯一のチューナブルは DPAS の QD 閾値 θ で、
  NAND flash SSD は 1、3D XPoint SSD は 3 に経験的に設定 (§3.5, §4.4)。
- [paper] 優先順位の仮定: oversleep 回避 > undersleep 回避 (§2.1)。また DPAS はデフォルトで
  I/O 性能最大化を優先する(CPU 余裕を優先するモードは将来拡張)(§5)。
- [paper] 評価環境: Xeon Gold 6230(20 コア、2.10GHz)× 1、192GB DDR4-2666、
  Ubuntu 18.04、kernel 5.18。hyper-threading は無効(有効化すると Optane で割り込みの
  4KB random read IOPS が classic polling 比最大 40% 低下したため)(§4.1)。
- [inference] 評価はシングルソケット 1 台のみで、NUMA 跨ぎやマルチソケットでの
  タイマー・キャッシュ挙動は検証されていない。また polled 経路は direct I/O
  (FIO direct mode / RocksDB の POSIX I/O を pvsync2 に置換)前提で (§4.2, §4.4)、
  buffered I/O やユーザ空間 I/O(SPDK / io_uring は §6 で言及されるのみ)への適用は
  本文の実験範囲外。

## Approach
- [paper] **PAS(Prompt, Accurate, Safe)— 二値 sleep 結果によるレイテンシ追跡 (§3.1)**:
  設計目標は ①epoch を待たず即応、②連続変化する I/O 時間の下側包絡線(lower envelope)を
  密に追跡、③デバイス起因の遅延と予測誤差起因の oversleep の分離。実測 I/O 時間の
  代わりに直近 2 I/O の sleep 結果ペア (sr_pnlt, sr_last) を使う:
  - (UNDER, UNDER): sleep がまだ短い → 増やす。(OVER, OVER): まだ長い → 減らす。
  - (UNDER, OVER): 包絡線を下から横切った → 少し減らす。(OVER, UNDER): 上から
    横切った → 少し増やす (§3.1)。
  - ワークフロー (Fig. 3): 初期状態は (OVER, UNDER)、sleep 時間 D_MIN = 0.1µs(初期
    oversleep を避けつつ実レイテンシまで ramp up)。結果が同じ(case 1/2)なら調整係数
    adjust に UP を加算 / DN を減算して加速。結果が異なる(case 3/4)なら sleep が真の
    レイテンシに到達したとみなし adjust を 1∓DN / 1±UP にリセット。新 sleep 時間 =
    現 sleep 時間 × adjust。hrtimer で sleep 後、改変 poll 関数が UNDER/OVER を返し
    結果をシフトする (§3.1, Fig. 3)。
  - 例 (Fig. 4): (UP,DN)=(0.05,0.1) で I/O #1–#3 で sleep を増やし真のレイテンシ 18µs に
    到達、#3 で初 oversleep。#4 で (UNDER,OVER) を観測して即座に短縮し、以後は包絡線
    近傍で微調整 (§3.1, Fig. 4)。
- [paper] **パラメータ設計 (§3.2)**: spreadsheet ベースのシミュレータ PAS-Sim で、Samsung
  983 ZET 上の YCSB 実行から採った write I/O レイテンシトレース(8–15 セクタ、変動の
  大きい部分トレース)を入力に (UP, DN) を掃引。指標は T_under / T_over(under/over sleep
  総時間をトレース総 I/O 時間で正規化。前者は CPU オーバーヘッド、後者は性能ペナルティの
  推定)(§3.2)。T_over < 0.05 のセルの中で T_under 最小の (UP, DN) = (0.01, 0.1)
  (DN/UP 比 10)をベースライン構成に採用 (Table 1)。DN/UP 比の掃引では比 1→4 で
  T_over が急減し 4 以降はほぼ変化せず、T_under は比とともに増え続ける (Fig. 6)。
  Fig. 5 の実トレースでは安定区間(約 38µs)で包絡線を正確に追跡、急変区間では慎重に
  増やし oversleep 検出後に急減(T_over=0.03, T_under=0.26)(§3.2, Fig. 5)。
- [paper] **動的感度調整 (§3.3)**: 固定 (UP, DN) は I/O 挙動の変化に適応できないため、
  直近 2 結果が同じなら UP と DN を (1+HEATUP) 倍(感度不足とみなす)、異なるなら
  (1−COOLDN) 倍(過敏とみなす)。UP:DN 比は 1:10 固定、UP は [0.001, 0.01] に制限。
  PAS-Sim で HEATUP を掃引し (HEATUP, COOLDN) = (0.05, 0.1) を全実験共通に採用
  (デバイスごとのチューニング無しで機能するかを試すため)(§3.3, Fig. 7, Fig. 8)。
- [paper] **並行 I/O 対応 (§3.4)**: per-device モードでは ①未完了 I/O のせいで古い sleep
  結果に基づいて調整してしまう(oversleep を検出できず sleep が指数的に増加)、
  ②連続完了で重要な結果ペアが上書きされ方向転換のリセットを逃す、③共有制御変数の
  ロックが I/O を直列化、という 3 問題が起きる (Fig. 9(a), §3.4)。対策は per-core モード
  (コアごとに PAS 変数、自 CPU 発行の I/O の結果のみ参照)(Fig. 9(b))。同一 CPU を
  複数スレッドが共有する場合は、同じ sleep 時間を使う I/O 群のうち最初に完了した 1 個
  だけが結果を提出し、新しい結果を最初に見た I/O だけが sleep 時間を更新する
  (Fig. 7 の Step 3/9、Fig. 9(c))。
- [paper] **DPAS — 動的モード切替 (§3.5)**: PAS が継承する hybrid polling の原理的限界は
  2 つ。①カーネルタイマーの間接的 task-switch オーバーヘッド(cache eviction、
  working-set 再ロード等)によりアプリ知覚レイテンシが増える。Optane で classic polling
  134K IOPS に対し、oversleep が起きない固定 1µs sleep の LHP は 129K IOPS(4% 劣化)。
  ②CPU 過負荷時は OS スケジューラが定刻に起こせず深刻な oversleep が起きる。LHP は
  これをデバイス遅延と誤解釈して sleep を増やす(latency shelving)が、PAS は正しく
  OVER と判定して sleep を積極的に縮め、持続的競合下では sleep がゼロに崩壊 =
  「timer failure」状態(タイマー原語を空振りし続ける高コスト busy-wait で、LHP や
  割り込みより悪化)(§3.5)。
  - DPAS はコアごとに classic polling(CP)/ PAS normal / PAS overloaded / 割り込み(INT)の
    4 モードを切り替える (Fig. 10)。監視対象は timer failure(sleep 時間のゼロ崩壊という
    特徴的挙動で正確に検出)と I/O キュー深さ(QD)(§3.5)。
  - PAS normal で N_PAS(既定 100)I/O を発行して平均 QD を取得。QD = 1(単一スレッド
    発行)なら CP モードへ。CP は 1 CPU 1 スレッド実行を強制するので、N_CP(既定
    1,000)I/O 発行後に自動的に PAS normal に戻り適応性を保つ (§3.5)。
  - N_PAS I/O 内に timer failure を検出したら PAS overloaded へ。さらに N_PAS I/O で QD を
    再確認し、QD = 1 に落ちたら PAS normal に復帰、QD > θ なら INT モードで N_INT
    (既定 10,000)I/O を発行後 PAS overloaded に戻る。N_INT を N_CP の 10 倍にするのは、
    深刻な競合は収まるのに時間がかかり、早すぎる PAS 復帰(busy-wait)のペナルティの
    方が重大なため (§3.5)。θ は NAND flash = 1、3D XPoint = 3(前者はより積極的に INT へ、
    後者は timer failure に曝されつつも PAS overloaded に長く留まり IOPS を稼ぐ)(§3.5)。
- [paper] **実装 (§3.6)**: Linux の multi-queue block layer に実装。PAS バケットエントリは
  37B(adjust, duration, UP, DN, sr_pnlt, sr_last 等)× 16 バケット = コアあたり 592B、
  DPAS のモード切替ロジック +104B/コア、グローバル変数 +100B/コア。変更は 9 ソース
  ファイル、+1,224 行 / −30 行(トレース機能を除く)(§3.6)。

## Evaluation
- Setup [paper]: 上記 1 台構成 (§4.1)。SSD 3 種 = Intel Optane DC P5800X 400GB
  (3D XPoint)、Samsung 983 ZET 480GB(SLC ベース Z-NAND、ZSSD)、SK hynix P41
  Gold 1TB(TLC NAND)。比較手法は INT / CP / LHP / EHP / PAS / DPAS。CP は
  Select-ISR のレイテンシ重視アプリ、INT は Select-ISR のスループット重視アプリと
  CINT の urgent I/O に相当するとして代表させる。各実験 5 回の平均 (§4.1)。
  マイクロベンチは XFS + FIO direct mode 10 秒/run、pvsync2 + hipri (§4.2)。
- スレッドスケーラビリティ(4KB random read, 1–20 スレッド, Fig. 11)[paper]:
  Optane で CP は INT 比最大 +30%(read IOPS。write は +27%、紙面の都合で図は省略)、
  8 スレッド以降はデバイス飽和で利得消滅。全 SSD で CP と DPAS が LHP/EHP/PAS を
  デバイス飽和まで上回る。LHP は常時 CPU 約半分を消費、EHP/PAS はレイテンシに応じて
  CPU 使用を調整。PAS は hybrid polling 中最小の CPU 使用率で、LHP 比平均 −21 ポイント。
  DPAS は主に CP モードで動作し CPU 90% 超を使用(Optane 20 スレッド時を除く)(§4.2)。
- パラメータ感度 (Fig. 12) [paper]: 4T@Optane(競合なし)で N_CP を増やすと CP の
  上限に接近、N_CP=1,000 でスループット利得の大半(1.27×)を確保しつつ応答性を維持。
  32T@P41(重競合)で N_INT=100 はモードスラッシングで INT 比 0.84× に劣化、
  N_INT=10,000 で 0.97× に回復、それ以上は利得僅少 (§4.2)。
- 大きい I/O (Fig. 13) [paper]: I/O サイズ拡大とともに polling 系の優位は漸減。128KB read
  では全デバイスで(P41 は 16–32KB でも)EHP の IOPS 利得が消滅。DPAS も P41 の
  128KB read で INT 比約 −1%(99.95 パーセンタイルレイテンシ増と相関、P41 のみの
  パターン)(§4.2)。
- 実トレース再生(SNIA IOTTA: Baleen Regions 5–7 / Systor '17 VDI 30 分 / Slacker
  HelloBench 57 コンテナ起動 I/O。再生スレッド 1 本を専用 4 CPU に固定、容量超過
  アドレスは剰余で写像)(§4.3) [paper]: 大 I/O 支配の Baleen では INT との差が全 SSD で
  小さく、小 I/O の多い Systor/Slacker は polling 系が有利。LHP と PAS は概ね EHP より
  高 IOPS で、PAS は一貫して LHP より低 CPU。CP は P41 以外で概ね最高 IOPS だが
  Slacker/Systor で分散が大きく平均を落とす。DPAS は全テストで near-best、P41 では
  CP を上回る (Fig. 14)。ZSSD/P41 の変動は内部 GC が原因と推定(presumably)(§4.3)。
- YCSB on RocksDB(XFS、POSIX I/O を pvsync2 に置換。op 数 = D:8M / E:250K /
  A,B,C,F:3M)(§4.4):
  - スレッドスケーラビリティ (Fig. 15) [paper]: 6 ワークロードの幾何平均で、Optane では
    LHP/EHP/PAS が 8 スレッドまで INT 比 +5–8%、CP と DPAS はさらに上。8 スレッド超は
    飽和により CP が INT を下回り tail latency が顕著に増加、DPAS は緩やかな低下。
    ZSSD では CP が大きく劣化する一方 DPAS は 16 スレッドまで INT を上回る。P41 は
    利得が小さいが全スレッド数で一貫した優位 (§4.4)。
  - CPU 競合(4 CPU に 2–32 スレッド, Fig. 16)[paper]: スレッド数 > CPU 数で CP の OPS は
    急落。PAS は Optane/ZSSD で 2–8 スレッド、P41 で 2–4 スレッドまで利得を保つが、
    ZSSD/P41 の 16–32 スレッドでは INT を大きく下回る(LHP/EHP の劣化は PAS より軽い)。
    DPAS は timer failure 通知に反応して INT モードに切り替えて劣化を緩和し、2–4
    スレッドでは CP モードを維持して全手法中最高 OPS(CPU 使用増と引き換え)(§4.4)。
  - モード内訳 (Fig. 17) [paper]: (a) YCSB-C 8T@Optane では持続的 timer failure で PAS
    overloaded に留まる(平均 QD が θ=3 未満で INT へ行かない)まま INT 比 +12.3%。
    (b) YCSB-B 4T@ZSSD では PAS normal と CP を往復し、RocksDB バックグラウンド
    スレッドの断続的 CPU 過負荷で約 2% の I/O が INT モード。DPAS +10.3% に対し
    CP は +0.3% のみ。(c) YCSB-A 8T@P41 では全 CPU で timer failure が発生し大半が
    INT モードへ移行、ただし CPU2 は PAS normal に残留(INT へ移った CPU が多くの
    I/O を処理して CPU2 の負荷を下げるため)。4 CPU 合計 OPS は INT 比 −2.8% に
    留まる(PAS 単体は −9.3%)(§4.4)。
  - I/O 干渉 (Fig. 18) [paper]: パルス型 I/O 生成器(パラメータ = I/O サイズ、目標 IOPS、
    パルス間隔。例: (128KB, 1,000 IOPS, 40ms) は 40ms ごとに 128KB read を 40 連発)を
    CPU4–7 で 4 本(各 1,000 IOPS、計 500MB/s、間隔 40–640ms)動かし、CPU0–3 の
    YCSB 4 スレッドを測定。LHP はパルス間隔が長いほど(特に高速デバイスで)劣化、
    EHP は 160–640ms で一貫した低下。PAS と DPAS は全間隔で安定 (§4.4)。
  - レイテンシ分析(YCSB B、80ms パルス, Fig. 19)[paper]: ZSSD では CP はどの
    パルス間隔でも INT を上回れない。Optane では CP の平均レイテンシは READ/UPDATE
    とも INT より低いが、ZSSD では CP の UPDATE 平均が INT より大幅に高い。CP は
    P90 までは INT 同等だが P99.99 は 17×、最大は 30×。DPAS は干渉中も最大 90% の
    I/O を CP モードで発行し tail は増えるが CP よりはるかに小さい (§4.4)。
  - sleep トレース分析(YCSB A、320ms パルス、4,096–7,680B read, Fig. 20)[paper]:
    LHP は次 epoch まで調整せず、スパイク収束後に oversleep し、その超過を
    デバイスレイテンシと誤解釈して複数サイクル持ち越す。EHP も減速終了後に
    oversleep し回復に複数 epoch。PAS は PAS-Sim と整合する密な包絡線追跡。DPAS は
    QD 推定 → CP モード → PAS normal 復帰、timer failure 時は PAS overloaded で QD を
    取り直して判断、という遷移がトレースで確認できる。timer 遅延自体は全 hybrid
    polling 手法に生じるが、即応するのは PAS/DPAS のみ (§4.4)。
  - CPU + I/O 競合の複合(4 CPU に YCSB 4 スレッド + 生成器 4 本, Fig. 21)[paper]:
    DPAS は INT 比で Optane +9% / ZSSD +7% / P41 +5% の平均 OPS 改善(abstract の
    9%/5% はこの設定の Optane と P41 に対応)。PAS も一貫して改善するが DPAS より
    やや低い。CP/LHP/EHP は顕著に劣化しデバイスによっては INT を下回る。DPAS の
    モード配分はデバイス・ワークロード依存で、θ が高い Optane では PAS overloaded の
    滞在が長い (§4.4)。
  - チューニング無し追加検証 (Fig. 22) [paper]: 追加の NAND flash SSD 8 台 + 3D XPoint
    1 台で同一設定を実行し、SN850X を除く全デバイスで DPAS が他手法を上回る。
    CP/LHP/EHP は複数の SSD で INT を下回る (§4.4)。
  - エネルギー (Fig. 23) [paper]: テスト機はアイドル 110W、負荷時最大 200W で、手法間の
    消費電力(power draw)差は計測できず。CPU 競合が高いと CP の実行時間の長さに
    起因して CP が最多エネルギー消費、競合が下がると差は縮小 (§4.4)。
- [inference] 評価がカバーしていないもの:
  - Select-ISR / CINT との比較は CP / INT を「相当物」として代用しており (§4.1)、両手法の
    実装そのものとの直接比較ではない(CINT の割り込み coalescing の効果は測られて
    いない。§5 でも coalescing は future work)。
  - polled 経路は pvsync2(同期 I/O)のみで、io_uring / SPDK 系の非同期・ユーザ空間
    polling(§6 で言及)との比較や統合は無い。DB エンジンが非同期 I/O を使う場合に
    PAS の「直近 2 I/O」フィードバックがどう機能するかは未評価。
  - FIO は 10 秒/run と短く (§4.2)、SSD 内部 GC の長周期挙動(§4.3 で変動要因として
    推定されている)を跨ぐ長時間安定性は示されていない。
  - θ は「NAND=1 / 3D XPoint=3」というデバイス種別の事前知識を要し、Fig. 22 の
    追加デバイス検証もこの 2 値の割当を前提とする。SN850X で劣る理由の分析は無い。
  - write 系マイクロベンチは「紙面の都合で省略」(§4.2) されており、図として提示される
    マイクロベンチ結果は read 中心。

## Limitations
- Stated [paper]:
  - PAS は hybrid polling の 2 つの原理的限界(タイマー起因のレイテンシ増 ≈ Optane で
    4%、CPU 過負荷時の timer failure = busy-wait 化)を単体では解決できない。これが
    DPAS の動機 (§3.5)。
  - per-core モードはメモリ使用増を伴う(ただし実装上はコアあたり 1KB 未満)(§3.4, §3.6)。
  - CPU 数がデバイスキュー数を大きく超えると割り込みキュー共有で I/O 性能が劣化
    しうる(単一キュー化やキューマッパの動的割当という OS 側変更で緩和可能と提案)
    (§3.6)。
  - DPAS は P41 の 128KB read で INT 比約 −1% (§4.2, Fig. 13)、Fig. 17(c) の重競合
    シナリオで INT 比 −2.8% (§4.4)、追加デバイス検証では SN850X で他手法に勝てない
    (§4.4, Fig. 22)。
  - DPAS は割り込み coalescing を持たず、INT モード中に並行 I/O が殺到すると interrupt
    storm を起こしうる。動的 urgency 閾値 + vIC 系の coalescing の統合は future work
    (vIC は仮想化環境でしか検証されていない)(§5)。
  - デフォルトの DPAS は I/O 性能優先で CPU を使い切る方向(Fig. 11 で CPU 90% 超)。
    CPU 余裕優先のモード(CP 経路を無効化)は拡張案に留まる (§5, §4.2)。
- Inferred [inference]:
  - timer failure の検出は「sleep 時間のゼロ崩壊」という PAS 固有の挙動に依存する
    (§3.5)。つまり DPAS の競合検出は PAS を経由して初めて得られる信号であり、
    INT/CP モード滞在中は N_CP / N_INT 本の I/O を発行し切るまで環境変化に反応
    できない。競合がパルス間隔より細かく変動するワークロードでの応答遅れは
    Fig. 18 の設定(40–640ms)より短い周期については示されていない。
  - PAS の「下側包絡線追跡」は設計上 undersleep 側に寄る(T_over < 0.05 を制約に
    T_under を最小化、Fig. 5 でも T_under=0.26)。CPU 効率の観点では LHP より良い
    ものの、polling 時間は残るため、CPU 課金が支配的なクラウド DB 環境で
    「割り込みより常に得か」は Fig. 23 のエネルギー結果(差は主に実行時間由来)
    だけでは判断できない。
  - per-core モードはコア間で学習した sleep 時間を共有しない(Fig. 9(b) の設計)。
    同一デバイスに対する統計がコア数分に分割されるため、低 IOPS ワークロード
    (コアあたりの I/O が疎)では収束が遅くなるはずだが、この領域の評価は無い。

## Relations
- [[2026-cidr-houlborg-xnvme.md]](xNVMe/nvmefs): 同じく「高速 NVMe に対して I/O 経路を
  どう選ぶか」を扱うが層が異なる。xNVMe はユーザ空間(io_uring / SPDK / FDP)の
  経路切替を DBMS(DuckDB)側に統合し、DPAS はカーネル内の完了検出方式
  (割り込み/polling/hybrid)を実行時に切り替える。DPAS の §6 も SPDK / io_uring を
  polling 採用フレームワークとして言及しており、「経路選択(xNVMe)× 完了方式選択
  (DPAS)」は直交する設計軸として比較できる。
- [[2026-fast-zhan-buffered-io.md]](WSBuffer): 同じ FAST '26 の Linux カーネル I/O スタック
  再設計だが、WSBuffer は buffered write 経路(ページキャッシュ)を、DPAS は direct/polled
  経路の完了検出を対象とする。「高速 SSD 時代にカーネル I/O スタックのどこが
  ボトルネックか」を書き込みバッファ側と完了検出側から挟む関係。
- [[2026-fast-ren-lsm-scheduling.md]](HATS): 接点は「LSM ストアのバックグラウンドタスクが
  フォアグラウンド性能を乱す」問題。DPAS は RocksDB のバックグラウンドスレッドによる
  断続的 CPU 過負荷を timer failure として検出し INT モードへ逃がす (Fig. 17(b)) のに対し、
  HATS は compaction 自体をスケジューリングで抑制する。カーネル側の適応 vs
  ストア側のスケジューリングという補完関係。

## Idea seeds
- [inference] DPAS のモード切替は QD と timer failure という OS レベル信号のみで駆動され、
  I/O の「意味」(フォアグラウンド txn の commit 待ち WAL fsync か、compaction の
  バルク read か)を知らない。DB エンジンが I/O ごとに urgency ヒントを渡し、完了方式
  (polled queue / interrupt queue)を選ばせる co-design は、§5 が挙げる動的 urgency
  閾値の具体化になる。最初の検証: 公開 artifact(kernel 5.18 + RocksDB/YCSB 一式、
  Appendix A)上で RocksDB の compaction I/O を interrupt キュー、フォアグラウンド
  read/WAL を polled キューに静的に振り分けるだけの改造を行い、Fig. 17(b) 型の
  ワークロードで P99 と CPU 使用率を DPAS 素の状態と比較する。
- [inference] 「latency shelving」(OS 遅延をデバイス遅延と誤解釈して予測を膨張させ固着)は
  hybrid polling 固有ではなく、実測レイテンシ統計に基づく DB 内部の適応機構
  (レプリカ選択、adaptive timeout、learned I/O cost model)にも同型の問題があるはず。
  PAS の核心は「予測の正誤を二値で自己評価できる形に観測を設計した」ことにある。
  検証: tail-aware なレプリカ選択(HATS のスコアリング等)に対し、CPU 競合注入時に
  レイテンシ推定が何 epoch 分過大に留まるかを測り、二値フィードバック型の推定器と
  比較する。
- [question] PAS の直近 2 結果 + 乗法的調整は、制御理論的には増分型のバンバン制御に
  近い。I/O レイテンシが二峰性(例: SSD 内部キャッシュヒット vs ミス、GC 中 vs 平常)を
  持つ場合、単一の sleep 時間が 2 つの包絡線の間で振動する可能性がある。バケットが
  サイズ × 方向のみ (§3.1) でレイテンシモードを区別しないのは十分か。検証:
  PAS-Sim 相当の再現(トレース入力 + 制御則は §3.1–3.3 に完全記述あり)に人工的な
  二峰性トレースを与え、T_over/T_under の劣化を観察する。
- [question] クラウド DB のように CPU がハイパーバイザ配下で steal される環境では、
  timer failure の頻度と θ の妥当性が物理機と大きく変わるはず(vIC が仮想化環境でのみ
  検証済みという §5 の記述とも接続)。DPAS の閾値群(N_PAS/N_CP/N_INT/θ)を VM 上で
  再感度分析する実験は、artifact があるため着手しやすい。

## Changelog
- 2026-07-06: created (status: read)
