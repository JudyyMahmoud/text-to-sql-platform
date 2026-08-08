import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.router import api_router
from app.exceptions import register_exception_handlers
from app.logging_config import configure_logging

configure_logging()
logger = logging.getLogger("app")

app = FastAPI(
    title="Multi-Tenant Text-to-SQL and Document Chat Platform",
    description=(
        "Secure backend that lets authenticated users connect live business databases, "
        "upload documents, and chat with both sources through one conversational interface."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)


@app.middleware("http")
async def add_request_id_and_log(request: Request, call_next):
    request_id = str(uuid.uuid4())
    started = time.time()
    response = await call_next(request)
    elapsed_ms = int((time.time() - started) * 1000)
    response.headers["X-Request-ID"] = request_id
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({elapsed_ms}ms) [{request_id}]")
    return response


app.include_router(api_router)


@app.get("/")
async def root():
    return {
        "name": "Multi-Tenant Text-to-SQL and Document Chat Platform",
        "docs": "/docs",
        "health": "/api/health",
    }
