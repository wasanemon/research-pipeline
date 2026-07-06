---
title: "TierScape: Harnessing Multiple Compressed Tiers to Tame Server Memory TCO"
authors: ["Sandeep Kumar", "et al."]
venue: "EuroSys"
year: 2026
ids: {doi: "10.1145/3767295.3769321", arxiv: "", dblp: ""}
urls: {paper: "https://doi.org/10.1145/3767295.3769321", pdf: "none", code: ""}
status: abstract-only
read_date: 2026-07-06
tags: [memory-tiering, compressed-memory, tco, data-placement, cost-model, cold-data, datacenter]
---

> **ソース注記**: 本ノートは **abstract のみ** に基づく(PDF 未取得)。abstract は
> Semantic Scholar Graph API(DOI: 10.1145/3767295.3769321)経由で機械取得した。
> 使用したソース URL: https://doi.org/10.1145/3767295.3769321
> 著者は機械取得メタデータの "Sandeep Kumar et al." のみ確認済みで、完全な著者リストは
> 未検証。本文アンカー(§/Fig./Table)は一切使えないため、全アンカーは (abstract)。

## TL;DR
データセンタのメモリ TCO 増大に対し、従来の単一圧縮 tier 方式ではなく、圧縮
アルゴリズム・圧縮オブジェクト用メモリアロケータ・格納先メディアの組合せで実装した
**複数の圧縮メモリ tier** を複数の byte-addressable tier と併用し、warm データを
低レイテンシ圧縮 tier に・cold データを最も TCO 節約効果の高い tier に置き分ける
tiered memory システム TierScape の提案 (abstract)。アクセスプロファイルの継続監視に
基づく調整可能な解析的コストモデルが tier 間の配置・移行を導く (abstract)。実ベンチ
マーク群で、SOTA tiering 比で性能同等のままメモリ TCO を 15.1–23.6 パーセントポイント
削減、または TCO 同等のまま性能を 2.61–10.0 パーセントポイント改善と主張 (abstract)。

## Problem & motivation
- [paper] 現代のデータセンタではメモリ TCO の増大への対処として tiered memory
  システムが標準的(the norm)になっている (abstract)。
- [paper] 従来の tiering ソリューションは**単一の**圧縮メモリ tier を用いる。これに
  対し本論文は、異なる圧縮アルゴリズム・圧縮オブジェクト用メモリアロケータ・
  圧縮オブジェクトの格納先メディアの組合せで実装される複数の圧縮 tier を活用する
  (abstract)。
- [paper] 各圧縮 tier はアクセスレイテンシ・データ圧縮率・単位メモリ使用コストの
  スペクトラム上の異なる点を占め、メモリ TCO 節約とアプリケーション性能影響の間の
  豊かで柔軟なトレードオフを可能にする (abstract)。
- [paper] 鍵となる利点: warm データを低レイテンシ圧縮 tier に置いて妥当な性能影響に
  抑えつつ、同時に cold データを最も TCO 節約効果の高い tier に置くことで、積極的な
  TCO 節約機会が得られる (abstract)。
- [paper] アプリケーションのデータアクセスプロファイルの継続監視に基づく、包括的で
  厳密かつ調整可能(tunable)な性能–TCO トレードオフの解析的コストモデルを備え、
  これに導かれて複数の圧縮 tier と byte-addressable tier をまたぐデータ配置・移行を
  動的に管理する (abstract)。
- [paper] 著者らは、TierScape がプロダクションデータセンタ環境のアプリケーションで
  SLA を考慮した performance per dollar を最良化するための重要なサーバシステム
  構成・最適化能力である、と位置付ける (abstract)。
- [paper] 実世界ベンチマーク群において、SOTA tiering ソリューション比で、性能同等を
  維持しつつメモリ TCO を 15.1–23.6 パーセントポイント削減、あるいはメモリ TCO
  同等を維持しつつ性能を 2.61–10.0 パーセントポイント改善 (abstract)。
- [question] 「percentage points」の基準(何に対する割合の差分か)、対象ベンチマークの
  内訳、比較した SOTA tiering ソリューションの具体名は abstract からは不明。要本文。

## System model & assumptions
(abstract-only のため未記載)

## Approach
(abstract-only のため未記載)

## Evaluation
(abstract-only のため未記載)

## Limitations
(abstract-only のため未記載)

## Relations
- [inference] [[2026-edbt-lee-cxl-pools.md]]: 同じく「サーバメモリの TCO 削減」を動機と
  する研究だが、手段が対照的(あちらは CXL スイッチ経由のメモリプーリング、こちらは
  圧縮 tier の多段化)。メモリ TCO 削減のアプローチ比較軸(プール共有 vs 圧縮)として
  接続する。本文同士の引用関係は未確認。
- [inference] [[2026-sigmod-chen-cloudjump3.md]]: hot/cold データの階層間配置・移行を
  動的に管理するという問題構造が共通(あちらはクラウド DB のストレージ階層、こちらは
  サーバ内メモリ階層)。tiering の制御をどの層(DB カーネル vs メモリ管理)で行うかの
  対比軸になり得る。本文同士の引用関係は未確認。

## Idea seeds
- [question] 圧縮オブジェクトの「格納先メディア(backing media)」として具体的に何を
  想定しているか(DRAM のみか、NVM/SSD/CXL メモリを含むか)は abstract から読め
  ない。深読み時に最初に確認すべき点。
- [inference] larger-than-memory な DBMS の buffer manager は、TierScape が依存する
  「アプリケーションのデータアクセスプロファイル」(abstract) をページ粒度で既に
  持っている(LRU/クロック情報、ページ種別)。汎用の OS レベル監視ではなく DB 側の
  アクセス知識を圧縮 tier 配置のヒントとして渡すと、warm/cold 判定の精度がどれだけ
  変わるかは検証しうるテーマ。最初の検証: 本文を深読みして監視・配置の粒度と
  インタフェースを特定した上で、buffer pool のページ温度統計と OS 側判定の一致率を
  測る実験を設計する。
- [question] 解析的コストモデルは「調整可能(tunable)」(abstract) とされるが、
  チューニングパラメータを誰が(運用者か自動か)どう決めるのかは不明。DB ワーク
  ロードのように位相が急変する場合(バッチ流入、HTAP の analytics 混在)への追随性は
  深読みで確認したい。

## Changelog
- 2026-07-06: created (status: abstract-only)
