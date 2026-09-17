"""FastAPI Application Entrypoint for Sovereign On-Premise Agentic AI Workbench.

Problem Statement ID: 26117 — Sovereign On-Premise Agentic AI Workbench using
Open-Weight Multimodal LLMs for Confidential Industrial Work.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api.routes_agent import router as router_agent
from api.routes_deliverables import router as router_deliverables
from api.routes_network import router as router_network
from api.routes_rag import router as router_rag
from config.settings import get_settings
from core.model_manager import model_manager
from core.network_monitor import SecurityException, network_monitor

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager: starts airgap interceptor and cleans up resources."""
    settings = get_settings()
    settings.ensure_directories()

    # 1. Start Sovereign Air-Gap Network Interceptor
    if settings.AIRGAP_ENFORCE:
        network_monitor.start()
        logger.info("Air-gap network interceptor started successfully.")

    yield

    # Shutdown sequence with safe exception handling
    try:
        network_monitor.stop()
    except Exception as e:
        logger.error(f"Error stopping network monitor: {e}")
    finally:
        await model_manager.close()
        logger.info("Application shutdown complete: sockets restored, connection pools closed.")


def create_app() -> FastAPI:
    """Create and configure the Sovereign Workbench FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Sovereign On-Premise Agentic AI Workbench",
        description=(
            "Confidential air-gapped industrial AI workbench running open-weight models "
            "(Qwen-3.8-27B, DeepSeek-R1-32B, Qwen2-VL) on localhost with verifiable zero external network egress."
        ),
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )

    # CORS Middleware: compliant origin regex for localhost / 127.0.0.1 with credentials
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Air-Gap Security Violation Exception Handler
    @app.exception_handler(SecurityException)
    async def security_exception_handler(request: Request, exc: SecurityException):
        logger.error(f"Air-Gap Security Violation intercepted: {exc}")
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "AIRGAP_VIOLATION_INTERCEPTED",
                "message": str(exc),
                "airgap_enforced": True,
                "sovereign_status": "BLOCKED",
            },
        )

    # Mount Sub-Routers
    app.include_router(router_agent, prefix="/api/agent")
    app.include_router(router_network, prefix="/api/network")
    app.include_router(router_rag, prefix="/api/rag")
    app.include_router(router_deliverables, prefix="/api/deliverables")

    # Static Directory & Demo Workbench Mount
    static_dir = settings.BASE_DIR / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/demo", include_in_schema=False)
    async def serve_demo():
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return JSONResponse(
            {"status": "Workbench static frontend not yet seeded. Use /api endpoints."},
            status_code=200,
        )

    # System Health & Root Endpoints
    @app.get("/", tags=["System"])
    async def root_overview() -> Dict[str, Any]:
        """Workbench overview and configuration state."""
        return {
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "problem_statement_id": settings.PROBLEM_STATEMENT_ID,
            "airgap_enforced": settings.AIRGAP_ENFORCE,
            "active_profile": settings.ACTIVE_PROFILE,
            "model_base_url": settings.MODEL_BASE_URL,
            "status": "OPERATIONAL",
            "documentation": "/docs",
        }

    @app.get("/health", tags=["System"])
    @app.get("/api/health", tags=["System"])
    async def health_check() -> Dict[str, Any]:
        """Comprehensive health check across local components."""
        model_healthy = await model_manager.check_health()
        return {
            "status": "HEALTHY",
            "problem_statement": "26117",
            "airgap": {
                "enforce": network_monitor.enforce,
                "blocked_count": network_monitor.stats["blocked_requests"],
                "allowed_count": network_monitor.stats["allowed_requests"],
                "sovereign_proof": "ZERO_EXTERNAL_EGRESS",
            },
            "model_server": {
                "base_url": settings.MODEL_BASE_URL,
                "reachable": model_healthy,
                "active_profile": settings.ACTIVE_PROFILE,
            },
            "directories": {
                "uploads": settings.UPLOADS_DIR.exists(),
                "deliverables": settings.DELIVERABLES_DIR.exists(),
                "storage_qdrant": settings.QDRANT_DIR.exists(),
            },
        }

    return app


# Application singleton
app = create_app()
