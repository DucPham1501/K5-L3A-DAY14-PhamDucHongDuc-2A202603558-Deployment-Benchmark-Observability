"""Production agent entry point: uvicorn app.main:app."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from redis.exceptions import RedisError
from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import ask as llm_ask

class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
            **getattr(record, "fields", {}),
        }, ensure_ascii=False)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("day14.agent")
logger.handlers = [handler]
logger.setLevel(settings.log_level.upper())
logger.propagate = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Do not ping here: /health must work without Redis.
    logger.info("startup", extra={"fields": {"environment": settings.environment}})
    yield
    # Uvicorn drains requests before entering lifespan shutdown.
    r.close()
    logger.info("shutdown")

app = FastAPI(title="Production AI Agent", lifespan=lifespan)

@app.middleware("http")
async def log_request(request: Request, call_next):
    started = time.perf_counter()
    request_id = uuid.uuid4().hex
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        logger.info("http_request", extra={"fields": {
            "request_id": request_id, "method": request.method,
            "path": request.url.path, "status": status,
            "ms": round((time.perf_counter() - started) * 1000, 2),
        }})

@app.exception_handler(RedisError)
async def redis_error(request: Request, exc: RedisError):
    logger.warning("redis_unavailable")
    return JSONResponse(status_code=503, content={"detail": "State store unavailable"})

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"status": "ready"}

@app.post("/ask")
def ask(body: AskRequest, key: str = Depends(verify_api_key)):
    check_rate_limit(key)
    check_budget()
    # The synchronous mock runs in FastAPI's thread pool, allowing request drain.
    answer = llm_ask(body.question)
    input_tokens = max(1, len(body.question) // 4)
    output_tokens = max(1, len(answer) // 4)
    cost = record_cost(input_tokens, output_tokens)
    logger.info("llm_call", extra={"fields": {
        "input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost,
    }})
    return {"question": body.question, "answer": answer,
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost}}