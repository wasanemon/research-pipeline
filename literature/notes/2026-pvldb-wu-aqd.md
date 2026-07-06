---
title: "AQD: Online Adaptive Query Dispatcher for HTAP Databases"
authors: [Yang Wu, Tongliang Li, Xuanhe Zhou, Jianying Wang, Xinjun Yang, Wenchao Zhou, Chunxiao Xing, Yong Zhang]
venue: "PVLDB 19(7):1586-1599"
year: 2026
ids: {doi: "10.14778/3801059.3801071", arxiv: "", dblp: "journals/pvldb/WuLZWYZXZ26"}
urls: {paper: "https://www.vldb.org/pvldb/vol19/p1586-wu.pdf", pdf: "literature/pdfs/2026-pvldb-wu-aqd.pdf", code: "https://github.com/earthwuyang/aqd"}
status: read
read_date: 2026-07-06
tags: [htap, query-dispatch, dual-engine, polardb, learned-database, bandit, resource-management]
---

## TL;DR
デュアルエンジン HTAP(行=TP、列=AP)の「クエリをどちらで実行するか」を、
オフライン学習(LightGBM+誤分類コストを考慮した独自ブースティング)+
オンライン適応(Thompson sampling による残差学習)+資源均衡制御(Mahalanobis 距離+OCO)
の3段で決める、学習ベースでは初と主張するディスパッチャ。PolarDB カーネルに統合され、
コスト閾値方式比で平均レイテンシ 90% 超削減、HyBench スコア +15%(SOTA の BRAD 比 +9%)。

## Problem & motivation
- [paper] PolarDB の顧客クレームの約 20% が不適切な行/列ディスパッチ起因で、システム性能・
  体験に響く最大の課題 (§1)。
- [paper] 現行はコスト閾値ルール(推定コスト>閾値なら列エンジン)だが、コスト推定は
  不正確で誤分類が頻発。ワークロードドリフト(TP:AP 比の変動)にも不適応 (§1)。
- [paper] 課題: C1 エンジン間の CPU/メモリ均衡、C2 ディスパッチ判定はコンパイル
  クリティカルパス上でマイクロ秒級の制約、C3 誤分類コストの非対称性(長時間クエリの
  誤配置ほど損失大)、C4 実行時間計測ノイズ (§1)。
- [paper] Workload-Level Dispatch はオフライン完全情報でも NP-hard(Appendix A)(§2.1.2)。

## System model & assumptions
- [paper] 対象はデュアルエンジン型 HTAP(TiDB+TiFlash、PolarDB、HeatWave 等)(§1)。
  PolarDB 構成: proxy + TP クラスタ(RW/RO)+ AP クラスタ。AQD は RW ノード上で
  最適化器特徴と各ノードのハートビート(CPU/メモリ)を観測して判定 (§2.3)。
- [paper] 定式化: query-level は二値分類(regret = レイテンシ差 × 誤選択)、workload-level は
  資源バイアス制約付きオンライン最適化(行エンジンの平均資源消費−トラフィック比が
  目標 γ_T に一致)(§2.1)。
- [paper] 反実仮想(選ばなかったエンジンのレイテンシ)は EWMA(α=0.03)で推定
  (Doubly Robust 推定と比較し、高頻度・小サンプルでは EWMA が同等以上)(§4.2)。

## Approach
- [paper] **オフライン** (§3): 最適化器を計装し 142 特徴(行数/コスト統計 27、アクセス
  パターン 32、プラン形状 31、物理メタ 52)→ SHAP で 32 に削減(精度低下ほぼなし:
  全特徴 0.816 → top-32 0.81)。15 ワークロード(TPC-H/DS、HyBench、本番系トレース7種)を
  両エンジンで実行し 15万件超のラベル付きデータを構築。学習目標は
  log(ℓ_row)−log(ℓ_col) の回帰。**self-paced Taylor-weighted boosting**: レイテンシ差の
  Taylor 展開から導いた重み(クラス均衡/差の増幅/データセットサイズ/regret/focal/
  実行時間スケールの6因子の積)で「高コストな誤分類」に学習を集中、エポックごとに
  カリキュラム的に更新 (§3.3.3)。
- [paper] **オンライン** (§4, Alg. 1): ①LightGBM のマージン s_t(符号=推奨エンジン、
  大きさ=確信度)。②LinTS-Delta — 残差 Δ_t = log(1+ℓ̃_row)−log(1+ℓ̃_col) を線形文脈
  バンディットでモデル化し Thompson sampling で探索ボーナス u_t を生成、
  z_t = tanh(s_t + u_t)(再学習ではなく残差学習なのは軽量・即時性のためで、両エンジン
  二重実行も不要)。③資源制御 — 行エンジンの資源シェアの目標からの偏差を直近 K 件の
  共分散で正規化した Mahalanobis 距離 → r_t = tanh(d_t)。負荷適応係数
  ω_t(QPS 高→レイテンシ優先、低→資源均衡優先)で s_final = ω_t·z_t + (1−ω_t)·r_t、
  正なら列エンジン。目標シェア γ_t は OCO(射影付き勾配、β=c/√t)で周期更新。
- [paper] 遅延regretと資源逸脱の両方に regret bound を証明したと主張 (§1 contribution 3)。
- [paper] 実装: PolarDB カーネル内 C++、LightGBM C API、モデル ~10MB。特徴抽出+推論で
  1クエリあたり約 500µs (§5.1)。

## Evaluation
- Setup [paper]: dual Xeon Platinum 8269CY(26C×2)、768GB RAM。ベースライン: Row-only /
  Column-only / Cost-threshold(PolarDB デフォルト)/ BRAD(SOTA)ほか (§5.1-5.2)。
- [paper] ランダム生成クエリの並行実行で、コスト閾値方式比 平均レイテンシ 90% 超削減 (§1)。
- [paper] HyBench スコア 9.56 = コスト閾値比 +15%、BRAD 比 +9% (§1)。
- [paper] 個別ワークロードで tpch100 54% / airline 44% / employee 65% の改善、コスト閾値比で
  最適解への到達度最大 99%。分類精度は 11 ワークロードで ≥0.85 (p.8)。
- [inference] カバーされないもの(読了範囲では): ディスパッチ誤りが引き起こす
  データ鮮度面の影響(列レプリカの同期遅延はスコープ外に見える)、
  マルチテナント下での資源制御の干渉、学習モデル更新の運用(再訓練頻度)。

## Limitations
- Stated [paper]: 判定オーバーヘッド ~500µs/クエリ (§5.1) — 短い点クエリには相対的に
  大きい可能性(本文 §6 に limitations 節があるが精読外)。
- Inferred [inference]:
  - EWMA 反実仮想は「同種クエリが両エンジンに散らばって流れ続ける」ことを暗黙に仮定。
    ディスパッチが一方向に収束すると反対側の推定が陳腐化する(バンディットの探索で
    緩和される設計だが、その安全性は負荷次第)。
  - 資源制御は CPU/メモリの2次元のみで、ネットワークやストレージ帯域
    (列レプリカ同期)は対象外。Jasper が問題にした同期コストとは補完関係。

## Relations
- [[2026-pvldb-ding-jasper-htap]] — 同じ PolarDB/TiDB 系デュアルエンジン HTAP の最適化だが、
  Jasper=ストレージレイアウト側、AQD=ルーティング側。併用可能に見える(Jasper の
  選択的列化の下では AQD の反実仮想推定が難しくなる、という相互作用も考えられる)。
- BRAD(SOTA 比較対象)、learned optimizer 系研究の延長線。
- キュー内関連: TiRex(HTAIP)、Xiu ら(EDBT、LLM による HTAP 性能説明)。

## Idea seeds
- [inference] ディスパッチ判定は「どちらが速いか」だけで、「列側のデータがどれだけ
  新しいか(同期ラグ)」を無視している。freshness SLA を制約に入れた
  dispatch(stale を許すクエリだけ列へ)は Jasper のノートで書いた staleness-aware
  最適化と同じ穴に落ちる話で、両論文とも触れていない → HTAP の
  「isolation/freshness/routing の共同最適化」は開いたテーマに見える。
- [question] regret bound の証明 (§1) がどの仮定(線形残差モデルの実現可能性、
  ノイズの sub-Gaussian 性?)に依存しているか。フル版の Appendix を未読 — 理論の
  強さを評価するには要確認。

## Changelog
- 2026-07-06: created (status: read, PVLDB 公式 PDF を読解。§5 後半〜§7 は要点のみ)
- 2026-07-06: 検証パスによる修正(System model のデュアルエンジン例示のアンカーを §2.3 → §1 に訂正。PolarDB 構成の記述は §2.3 のまま)
