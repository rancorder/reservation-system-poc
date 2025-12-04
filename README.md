# Reservation System PoC - Enterprise Grade

**1時間実装**

## 🎯 実装内容

### ✅ Redis分散ロック（メモリ実装）
- 原子的なロック取得・解放
- タイムアウト制御（10秒自動解放）
- race condition完全対策

### ✅ トランザクション制御
- **楽観的ロック**: version列によるCAS
- **悲観的ロック**: 行ロックシミュレーション
- ACID特性の実装

### ✅ 冪等性実装
- idempotency keyによる重複実行防止
- メモリキャッシュ

### ✅ 負荷試験
- k6による並行性テスト
- 100並行リクエスト対応

## 🚀 起動方法
```bash
# API起動
uvicorn main:app --reload

# 負荷試験（別ターミナル）
k6 run load_test.js
```

## 📊 APIエンドポイント
```bash
# Redis分散ロック
curl -X POST http://localhost:8000/reserve/agent/agent_1

# 楽観的ロック
curl -X POST http://localhost:8000/reserve/slot/1/optimistic?version=0

# 悲観的ロック
curl -X POST http://localhost:8000/reserve/slot/2/pessimistic

# 冪等性
curl -X POST http://localhost:8000/reserve/idempotent/key123?slot_id=3

# リセット
curl -X POST http://localhost:8000/reset
```

## 🛠️ 技術スタック

- Python 3.11
- FastAPI (async)
- メモリ内実装（Redis/PostgreSQL相当）

## 📝 実装ポイント

**Redis分散ロック:**
- TTL付きロック
- Luaスクリプト相当の原子性保証

**楽観的ロック:**
- version列でCAS実装

**悲観的ロック:**
- 行ロックのシミュレーション

**実装時間: 60分**

## 💡 Note

Docker環境がない場合のため、メモリ内実装で動作確認。
本番環境ではRedis/PostgreSQLに置き換え可能。
ロジック・アルゴリズムは本番同等。
