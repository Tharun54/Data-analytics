"""CSE Plus — AI data analytics SaaS. Entry point: `uvicorn app.main:app`."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import init_db
from .routers import analyses, auth, dashboards, datasets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    logging.getLogger("cseplus").info("engine=%s model=%s", "ai" if settings.ai_enabled else "demo", settings.model)
    yield


app = FastAPI(title="CSE Plus API", version="0.1.0", lifespan=lifespan)
for r in (auth.router, analyses.router, datasets.router, dashboards.router):
    app.include_router(r)


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True, "engine": "ai" if settings.ai_enabled else "demo"}


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    """Single-page app: every non-API route serves index.html; the client router takes over."""
    if path.startswith("api/"):
        raise HTTPException(404, "Not found")
    return FileResponse(STATIC / "index.html")
