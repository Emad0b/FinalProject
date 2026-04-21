from __future__ import annotations

from fastapi import FastAPI

from .routes.config import router as config_router
from .routes.readings import router as readings_router

app = FastAPI(title="Hyperlocal Air Monitor API", version="1.0.0")
app.include_router(readings_router)
app.include_router(config_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

