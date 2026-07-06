---
title: "Pisco: An Isolation Bug Case Reduction and Deduplication Framework"
authors: [Siyang Weng, Hongyu Yang, Zirui Hu, Rong Zhang, Zhicheng Pan, Chengcheng Yang, Xuan Zhou, Yuxing Chen, Xiaolong He, Anqun Pan]
venue: "PVLDB 19(6):1413-1426"
year: 2026
ids: {doi: "10.14778/3797919.3797944", arxiv: "", dblp: "journals/pvldb/WengYHZPYZCHP26"}
urls: {paper: "https://www.vldb.org/pvldb/vol19/p1413-weng.pdf", pdf: "literature/pdfs/2026-pvldb-weng-pisco.pdf", code: "https://github.com/DBHammer/Pisco"}
status: read
read_date: 2026-07-06
tags: [isolation-levels, testing, concurrency-control, mvcc, s2pl, bug-reduction, llm, serializability]
---

## TL;DR
分離レベル(IL)バグの生テストケース(数万操作・十数スレッド)を、①DBMS 内部状態
(バージョンチェーン・ロックテーブル)のミラーリングによる決定的再現、②依存グラフ
ベースの reduction unit を使った divide-and-conquer 縮約、③LLM マルチエージェントに
よる重複判定、の3段で「再現可能・簡潔・新規」なバグレポートに変換するフレームワーク。
縮約時間は C-Reduce の 20.0% / DDMin の 33.3%、重複判定精度は最大 91.6%。

## Problem & motivation
- [paper] IL 実装は理論定義から逸脱し isolation bug を生むが、生ケースは巨大
  (例: TiDB#42487 は 12 スレッド 23,261 操作)で、バグ関連操作は通常 2〜4
  トランザクション・10 操作以下 (§1, Fig. 1)。
- [paper] 採択されるバグレポートの3条件: 再現可能性(>94% は決定的に再現可能)、
  簡潔性(>98% は 4 トランザクション未満・8〜10 操作)、一意性(MySQL 公式で重複分析に
  平均114日/件)(§1)。
- [paper] 既存手法の穴: 順序列挙は組合せ爆発、依存推論は「時間重複なし」の強い仮定。
  delta debugging (DDMin) は依存を無視して関連操作を分断し試行が無駄になる。テキスト
  類似度ベースの重複判定は短い SQL 中心レポートに無力 (§1)。

## System model & assumptions
- [paper] 対象は「特定の実行順序で決定的に再現できる isolation bug」(先行研究で
  94% 超がこれに該当)(§3)。
- [paper] クライアント側トレースのみ必要: 各操作の開始/終了タイムスタンプ、アクセス
  データ項目、操作タイプ、返り値。Jepsen/TxCheck 等のブラックボックステスタと統合可能
  (§2.2, §6.2 末尾)。
- [paper] 内部状態シミュレーションは MVCC / S2PL を前提に設計。OCC・TO への適応は
  可能と主張(詳細はテクニカルレポート [59] 送り)(§2.1, §4 Adaptability)。
- [paper] Property 1: 同一データへ書き込む時間重複操作のうち、**最初に返った書き込みが
  必ず先にロックを獲得している**(ネットワーク遅延に依らない。証明は [59])(§4)。

## Approach
- [paper] **再現(§4)**: クライアントトレースから DBMS の版チェーン V とロックテーブル L を
  シミュレートし、競合操作(同一データ・少なくとも一方が書き)の実行順を演繹。
  非競合操作は同一バッチに入れて並列実行できる「操作バッチ列」を構築(Algo. 1, O(N))。
  読みは「元と同じ版が読めるバッチ」まで待たせ、書きはロック可用性+Property 1 で配置。
  同値が版チェーンに複数回現れる場合は、マッチする版ごとにバッチ列を列挙して再現確認
  (Data Version Disambiguation)。
- [paper] **縮約(§5)**: 有向依存グラフ G(辺 = 「op' が op の作った版に直接アクセス」)から
  各操作の Reduction Unit(RU)= 自身+到達可能な全操作、を再帰構築(O(|E|+|V|))。
  無先行操作の RU 群から divide-and-conquer + trial-and-error で RU 単位に除去。
  最悪 O(M log_M N)(N=全操作、M=バグ関連操作)、1-minimality を保証 (§5.2)。
- [paper] **重複排除(§6)**: 粗フィルタ = 33 の IL 関連特徴(one-hot+正規化)を相互情報量で
  重み付けし cosine 類似度で top-K(K=16)候補を選択。細ランキング = IL 実装の4機構
  (consistent read / mutual exclusion / first updater wins / serialization certifier)の
  ドメイン専門エージェント(定義文+実行例+擬似コードでプロンプト)による
  トーナメント式ペア比較(k=5 回・多数決・信頼度スコア・不一致時は CoT で段階検証、
  shared memory pool で simultaneous-talk)。読み操作には「期待されるアクセス挙動」
  (IL ごとの5分類: トランザクション開始時スナップショット/最初の非制御操作前/
  最初の読み前/直近コミット版/未コミット含む直近版)を注釈して LLM に渡す (§6.2.1)。

## Evaluation
- Setup [paper]: DBStorm でテストケース生成、Leopard で検出。1ヶ月で MySQL/TiDB/MariaDB
  の 670 バグケース(5,015〜24,737 操作)→ 専門家3名が 13 ユニークバグに分類 (Table 1)。
  2018〜2025 のバグレポートを収集したリポジトリを構築・公開 [58]。LLM は Qwen2.5-7B
  (ローカル GPU)(§7.1)。
- [paper] 再現: Pisco と Sequential は再現率 100%(Random は 15〜37%)。Pisco は
  Sequential 比最大 14.6× 高速(バッチ内並列のため)(Fig. 8-10, §7.2)。
- [paper] 縮約: 全ケースを最小形に縮約(C-Reduce 53% / DDMin 70%)。残存操作は
  C-Reduce が 19.2×、DDMin が 2.9× 多い。時間は C-Reduce の 20.0% / DDMin の 33.3%
  (Fig. 12-14, §7.3)。
- [paper] 重複判定率は最大 91.6%(abstract)。Pisco 支援で提出した新規バグは全て2日以内に
  受理 (§1 contributions)。
- [inference] 評価対象は MySQL 系(InnoDB)+ TiDB + MariaDB で、いずれもロック+MVCC 系。
  OCC 系 DBMS での再現・縮約の実証は無い(主張レベル)。

## Limitations
- Stated [paper]: 決定的に再現できるバグに限定(非決定的な残り ~6% は対象外)(§3)。
  同一バグの変種が同一パターンに縮約されるとは限らず、パターン照合だけでは重複判定
  できない(だから LLM を使う)(§5.2 末尾)。
- Inferred [inference]:
  - 内部状態ミラーは「DBMS が教科書的な S2PL/MVCC で動く」ことを仮定した再実装であり、
    実装固有の最適化(early lock release、async commit 等)があるとシミュレーションと
    実機の乖離が生じ得る。Adaptability の主張 (§4) は理論的で、乖離検出の仕組みは
    本文に見当たらない。
  - 重複判定はレポートコーパスの網羅性と LLM の判断に依存。7B モデルでの 91.6% が
    実運用の受理判断にどこまで信頼されるかは開いている(最終判断は人間レビュー前提)。

## Relations
- 前提技術/比較: DBStorm(生成)、Leopard(検証オラクル)、Jepsen/TxCheck(統合先)、
  DDMin/C-Reduce(縮約ベースライン)、D-Bot(LLM 診断)。
- [[2026-arxiv-egorov-flintkv]] の Idea seeds で挙げた「durable linearizability 違反の
  テスティング」と補完関係: Pisco は IL 違反(並行実行)、FlintKV の事例は crash 後の
  永続性違反。両者を跨ぐ「crash+並行」の縮約フレームワークは空白に見える。

## Idea seeds
- [inference] Pisco の内部状態ミラー(版チェーン+ロックテーブルのクライアント側
  シミュレーション)は、テスティング以外にも「実行履歴から CC プロトコルの逸脱を
  説明する」一般ツールになり得る。検証: Pisco のシミュレータ部分(公開コード)を
  単体で取り出し、既知バグの説明生成に使えるか確認。
- [question] Property 1(最初に返った書きが先にロック獲得)は S2PL 前提。async commit /
  group commit で応答順とコミット順が乖離する系(例: TiDB の async commit)でも成り立つか。
  テクニカルレポートの証明の仮定を確認する価値あり。
- [inference] 縮約の 1-minimality は「操作の除去」に限る。SQL 文内の述語単純化・スキーマ
  縮小(C-Reduce が得意な軸)との組み合わせは未探索に見える — バグレポートの実用上の
  簡潔性はそちらも効く。

## Changelog
- 2026-07-06: created (status: read, PVLDB 公式 PDF を読解)
