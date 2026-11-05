import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import asynccontextmanager
import asyncio
import logging

from apps.backend.app.websocket.manager import manager
from apps.backend.app.database.config import init_db

# Import all routers
from apps.backend.app.api.jobs import router as jobs_router
from apps.backend.app.api.import_data import router as import_router
from apps.backend.app.api.dashboard import router as dashboard_router
from apps.backend.app.api.queue import router as queue_router
from apps.backend.app.api.customers import router as customers_router
from apps.backend.app.api.system import router as system_router
from apps.backend.app.api.auth import router as auth_router
from apps.backend.app.api.form141 import router as form141_router
from apps.backend.app.api.viewer import router as viewer_router


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Ensure DB tables exist
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.warning(f"Database auto-init note: {e}")

    # 2. Start WebSocket Redis pubsub background listener
    listener_task = asyncio.create_task(manager.listen_to_redis())
    yield
    # 3. Shutdown
    listener_task.cancel()

app = FastAPI(
    title="Form 141 Automation API",
    description="Production-grade API for managing Form 141 preparation, queueing, and human-in-the-loop payment handoff",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/api/static", StaticFiles(directory=static_dir), name="static")

# Register all modular routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(jobs_router)
app.include_router(import_router)
app.include_router(queue_router)
app.include_router(customers_router)
app.include_router(system_router)
app.include_router(form141_router)
app.include_router(viewer_router)


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and accept ping/pong or client requests
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

@app.get("/api/health")
async def health_check():
    return {"status": "online"}

from fastapi.responses import FileResponse

frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../desktop/dist"))
if not os.path.exists(frontend_dist):
    frontend_dist = os.path.abspath("apps/desktop/dist")

if os.path.exists(frontend_dist):
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="spa-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path == "api":
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not Found")
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        index_file = os.path.join(frontend_dist, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not Found")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8001))
    uvicorn.run("apps.backend.app.main:app", host="0.0.0.0", port=port)
