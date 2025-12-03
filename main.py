from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
import time
import uuid
from datetime import datetime
from typing import Dict, Optional

# メモリ内データストア（Redis/PostgreSQLの代替）
locks: Dict[str, tuple] = {}  # {lock_key: (value, expire_time)}
reservations: Dict[str, str] = {}
slots: Dict[int, dict] = {}
idempotent_cache: Dict[str, dict] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初期データ投入
    global slots
    for i in range(1, 11):
        slots[i] = {
            'id': i,
            'agent_id': f'agent_{i}',
            'booked': False,
            'version': 0,
            'booked_at': None
        }
    
    yield

app = FastAPI(lifespan=lifespan)

# ==================== Redis分散ロック（モック） ====================

def acquire_lock(key: str, value: str, ttl: int = 10) -> bool:
    '''Redis SET NX EX のシミュレーション'''
    current_time = time.time()
    
    # 期限切れロックの削除
    if key in locks:
        _, expire_time = locks[key]
        if current_time > expire_time:
            del locks[key]
    
    # ロック取得試行
    if key not in locks:
        locks[key] = (value, current_time + ttl)
        return True
    return False

def release_lock(key: str, value: str) -> bool:
    '''Luaスクリプト相当: 自分のロックのみ解放'''
    if key in locks and locks[key][0] == value:
        del locks[key]
        return True
    return False

@app.post("/reserve/agent/{agent_id}")
async def reserve_agent(agent_id: str, request_id: str = None):
    '''Redis分散ロックによる予約制御'''
    if not request_id:
        request_id = str(uuid.uuid4())
    
    lock_key = f"lock:agent:{agent_id}"
    
    # ロック取得
    if not acquire_lock(lock_key, request_id, ttl=10):
        raise HTTPException(status_code=409, detail=f"Agent {agent_id} is busy")
    
    try:
        # 予約処理シミュレーション
        time.sleep(0.05)
        
        # 予約情報保存
        reservations[agent_id] = request_id
        
        return {
            "status": "reserved",
            "agent_id": agent_id,
            "request_id": request_id
        }
    finally:
        # ロック解放
        release_lock(lock_key, request_id)

@app.get("/agent/{agent_id}/status")
async def get_agent_status(agent_id: str):
    '''エージェント状態確認'''
    lock_key = f"lock:agent:{agent_id}"
    return {
        "agent_id": agent_id,
        "reserved": agent_id in reservations,
        "locked": lock_key in locks,
        "reservation_id": reservations.get(agent_id)
    }

# ==================== 楽観的ロック ====================

@app.post("/reserve/slot/{slot_id}/optimistic")
async def reserve_slot_optimistic(slot_id: int, version: int = 0):
    '''楽観的ロック: version列によるrace condition対策'''
    if slot_id not in slots:
        raise HTTPException(404, "Slot not found")
    
    slot = slots[slot_id]
    
    # version確認 + 予約状態確認
    if slot['version'] != version:
        raise HTTPException(409, "Version mismatch")
    
    if slot['booked']:
        raise HTTPException(409, "Already booked")
    
    # 予約実行（version更新）
    slot['booked'] = True
    slot['version'] += 1
    slot['booked_at'] = datetime.now().isoformat()
    
    return {
        "status": "success",
        "slot_id": slot_id,
        "new_version": slot['version']
    }

# ==================== 悲観的ロック ====================

slot_locks: Dict[int, str] = {}

@app.post("/reserve/slot/{slot_id}/pessimistic")
async def reserve_slot_pessimistic(slot_id: int):
    '''悲観的ロック: SELECT FOR UPDATEのシミュレーション'''
    if slot_id not in slots:
        raise HTTPException(404, "Slot not found")
    
    lock_id = str(uuid.uuid4())
    
    # 行ロック取得
    if slot_id in slot_locks:
        raise HTTPException(409, "Slot is locked by another transaction")
    
    slot_locks[slot_id] = lock_id
    
    try:
        slot = slots[slot_id]
        
        if slot['booked']:
            raise HTTPException(409, "Slot already booked")
        
        # 予約実行
        slot['booked'] = True
        slot['booked_at'] = datetime.now().isoformat()
        
        return {
            "status": "success",
            "slot_id": slot_id,
            "agent_id": slot['agent_id']
        }
    finally:
        # ロック解放
        if slot_locks.get(slot_id) == lock_id:
            del slot_locks[slot_id]

# ==================== 冪等性実装 ====================

@app.post("/reserve/idempotent/{idempotency_key}")
async def reserve_idempotent(idempotency_key: str, slot_id: int):
    '''冪等性: 同じリクエストの重複実行を防ぐ'''
    
    # キャッシュ確認
    if idempotency_key in idempotent_cache:
        return {
            "status": "cached",
            "result": idempotent_cache[idempotency_key]
        }
    
    if slot_id not in slots:
        raise HTTPException(404, "Slot not found")
    
    slot = slots[slot_id]
    
    if slot['booked']:
        raise HTTPException(409, "Already booked")
    
    # 予約実行
    slot['booked'] = True
    slot['booked_at'] = datetime.now().isoformat()
    
    # 結果をキャッシュ
    result = {"slot_id": slot_id, "status": "success"}
    idempotent_cache[idempotency_key] = result
    
    return result

# ==================== リセット用 ====================

@app.post("/reset")
async def reset_all():
    '''デモ用: 全データリセット'''
    global slots, locks, reservations, idempotent_cache, slot_locks
    
    # スロットリセット
    for i in range(1, 11):
        slots[i] = {
            'id': i,
            'agent_id': f'agent_{i}',
            'booked': False,
            'version': 0,
            'booked_at': None
        }
    
    locks.clear()
    reservations.clear()
    idempotent_cache.clear()
    slot_locks.clear()
    
    return {"status": "reset complete"}

@app.get("/")
async def root():
    return {
        "message": "Reservation System PoC - Enterprise Grade",
        "endpoints": {
            "redis_lock": "/reserve/agent/{agent_id}",
            "optimistic": "/reserve/slot/{slot_id}/optimistic?version=0",
            "pessimistic": "/reserve/slot/{slot_id}/pessimistic",
            "idempotent": "/reserve/idempotent/{key}?slot_id=1",
            "reset": "/reset"
        }
    }
