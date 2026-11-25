"""Daily UTC budget with atomic cost accumulation in Redis."""
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from app.config import settings
from app.redis_client import r

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

def budget_period() -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return f"day14:cost:{now:%Y-%m-%d}", int(midnight.timestamp())

def check_budget() -> None:
    key, _ = budget_period()
    if float(r.get(key) or 0) >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily LLM budget exhausted")

def record_cost(input_tokens: int, output_tokens: int) -> float:
    cost = (input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K) / 1000
    key, expires_at = budget_period()
    with r.pipeline(transaction=True) as pipe:
        pipe.incrbyfloat(key, cost)
        pipe.expireat(key, expires_at)
        pipe.execute()
    return cost