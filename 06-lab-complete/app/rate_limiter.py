"""Atomic sliding window shared by workers and preserved across restarts."""
import hashlib
import math
import uuid
from fastapi import HTTPException
from app.config import settings
from app.redis_client import r

# Redis TIME avoids clock skew; Lua makes pruning/counting/admission atomic.
SLIDING_WINDOW = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000 + tonumber(clock[2]) / 1000
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - 60000)
local count = redis.call('ZCARD', KEYS[1])
if count >= tonumber(ARGV[1]) then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    return math.ceil(tonumber(oldest[2]) + 60000 - now)
end
redis.call('ZADD', KEYS[1], now, ARGV[2])
redis.call('PEXPIRE', KEYS[1], 60000)
return 0
"""

def check_rate_limit(key: str) -> None:
    digest = hashlib.sha256(key.encode()).hexdigest()
    delay_ms = int(r.eval(SLIDING_WINDOW, 1, f"day14:rate:{digest}",
                          settings.rate_limit_per_minute, uuid.uuid4().hex))
    if delay_ms:
        raise HTTPException(status_code=429, detail="Rate limit exceeded",
                            headers={"Retry-After": str(max(1, math.ceil(delay_ms / 1000)))})