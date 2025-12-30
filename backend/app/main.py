import asyncio
import logging

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, settings
from .deps import get_rate_limiter, get_settings, get_session_store
from .metrics import metrics_response, rate_limit_hits
from .routes import admin, auth, session, volunteer, ws
from .timers import maintenance_worker, session_enforcer

app = FastAPI(title="Lifeline API", version="0.1.0")

logging.basicConfig(level=logging.INFO)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(session.router)
app.include_router(volunteer.router)
app.include_router(ws.router)
app.include_router(admin.router)


def _error_payload(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        code = exc.detail.get("code", f"HTTP_{exc.status_code}")
        message = exc.detail.get("message", "Request failed")
        details = exc.detail.get("details")
    else:
        code = f"HTTP_{exc.status_code}"
        message = str(exc.detail)
        details = None
    return JSONResponse(status_code=exc.status_code, content=_error_payload(code, message, details))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content=_error_payload("VALIDATION_ERROR", "Invalid request payload", {"errors": exc.errors()}),
    )

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    limiter = get_rate_limiter()
    settings = get_settings()
    path = request.url.path
    if request.method == "POST" and path in ("/v1/session/request", "/v1/volunteer/accept"):
        token = request.headers.get("authorization", "")
        token_value = token.split(" ", 1)[1] if token.lower().startswith("bearer ") else "anon"
        token_hash = limiter.hash_token(token_value)
        ip = request.client.host if request.client else "unknown"
        limit = settings.seeker_session_rate_per_hour if path == "/v1/session/request" else settings.volunteer_accept_rate_per_hour
        key = f"ratelimit:{path}:{ip}:{token_hash}"
        result = limiter.check(key=key, limit=limit, window_seconds=3600)
        if not result.allowed:
            rate_limit_hits.labels(path=path).inc()
            return JSONResponse(
                status_code=429,
                content=_error_payload("RATE_LIMITED", "Rate limit exceeded"),
                headers={
                    "X-RateLimit-Limit": str(result.limit),
                    "X-RateLimit-Remaining": str(result.remaining),
                    "X-RateLimit-Reset": str(result.reset),
                },
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset)
        return response
    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/config/public")
def public_config(settings: Settings = Depends(get_settings)):
    return settings.public_config()


@app.get("/metrics")
def metrics():
    data, content_type = metrics_response()
    return Response(content=data, media_type=content_type)


@app.on_event("startup")
async def start_workers():
    store = get_session_store()
    app.state.enforcer_task = asyncio.create_task(session_enforcer(store, settings))
    app.state.maintenance_task = asyncio.create_task(maintenance_worker(store, settings))


@app.on_event("shutdown")
async def stop_workers():
    task = getattr(app.state, "enforcer_task", None)
    if task:
        task.cancel()
    maintenance = getattr(app.state, "maintenance_task", None)
    if maintenance:
        maintenance.cancel()
