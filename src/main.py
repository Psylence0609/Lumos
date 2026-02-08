"""FastAPI application entry point for the Smart Home Agent System."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from src.mqtt.client import mqtt_client
from src.devices.registry import device_registry
from src.agents.orchestrator import orchestrator
from src.storage.event_store import event_store
from src.api.websocket import ws_manager
from src.api.routes.devices import router as devices_router
from src.api.routes.commands import router as commands_router
from src.api.routes.agents import router as agents_router
from src.api.routes.threats import router as threats_router
from src.api.routes.patterns import router as patterns_router
from src.api.routes.voice import router as voice_router
from src.api.routes.simulation import router as simulation_router

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# Quiet noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
logging.getLogger("opentelemetry").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("mqtt").setLevel(logging.ERROR)
logging.getLogger("googleapiclient").setLevel(logging.WARNING)
logging.getLogger("src.mqtt.client").setLevel(logging.INFO)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info(f"Starting {settings.app_name}")

    # Initialize storage
    await event_store.initialize()

    # Load device config
    device_registry.load_from_yaml(settings.devices_config_path)

    # Connect MQTT
    try:
        await mqtt_client.connect()
    except Exception as e:
        logger.warning(f"MQTT broker not available: {e}. Running without MQTT.")

    # Start all devices
    if mqtt_client.is_connected:
        await device_registry.start_all()

    # Start orchestrator (which starts all sub-agents)
    try:
        await orchestrator.start()
    except Exception as e:
        logger.warning(f"Orchestrator start error (non-fatal): {e}")

    logger.info(f"{settings.app_name} is ready")
    yield

    # Shutdown
    logger.info("Shutting down...")
    try:
        await orchestrator.stop()
    except Exception:
        pass
    await device_registry.stop_all()
    await mqtt_client.disconnect()
    await event_store.close()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(devices_router, prefix="/api/v1")
app.include_router(commands_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(threats_router, prefix="/api/v1")
app.include_router(patterns_router, prefix="/api/v1")
app.include_router(voice_router, prefix="/api/v1")
app.include_router(simulation_router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_client.is_connected,
        "devices_count": len(device_registry.devices),
        "websocket_connections": ws_manager.connection_count,
        "agents": [a["agent_id"] for a in orchestrator.get_all_agent_info()],
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await ws_manager.connect(websocket)
    try:
        # Send initial state
        await ws_manager.send_to(websocket, "initial_state", {
            "devices": device_registry.get_all_states(),
            "energy": device_registry.get_energy_summary(),
            "agents": orchestrator.get_all_agent_info(),
        })

        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            logger.debug(f"WS received: {data}")
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await ws_manager.disconnect(websocket)


@app.get("/api/v1/events")
async def get_recent_events(limit: int = 50):
    """Get recent system events."""
    events = await event_store.get_recent_events(limit=limit)
    return [e.to_dict() for e in events]


# --- Certificate download endpoint (for iOS trust) ---
CERT_FILE = Path(__file__).parent.parent / "certs" / "cert.pem"


@app.get("/cert.pem")
async def download_certificate():
    """Download the self-signed certificate so it can be installed on mobile devices."""
    if CERT_FILE.exists():
        return FileResponse(
            str(CERT_FILE),
            media_type="application/x-x509-ca-cert",
            filename="smarthome.crt",
            headers={"Content-Disposition": "attachment; filename=smarthome.crt"},
        )
    return {"error": "Certificate not found"}


# Serve frontend static files (built React app)
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve the React SPA for all non-API routes."""
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
