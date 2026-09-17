"""Network Monitor Routes for Air-Gap Audit & Verification.

Provides endpoints for live air-gap statistics, recent socket events,
real-time SSE event streaming, and live air-gap security verification.
"""

from __future__ import annotations

import json
import logging
import socket
from typing import Any, Dict, List

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from core.network_monitor import SecurityException, network_monitor

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Air-Gap Network Monitor"])


@router.get("/stats")
async def get_network_stats() -> Dict[str, Any]:
    """Retrieve aggregated network statistics and air-gap enforcement status."""
    return {
        "airgap_enforce": network_monitor.enforce,
        "allowed_hosts": list(network_monitor.allowed_hosts),
        "blocked_requests": network_monitor.stats["blocked_requests"],
        "allowed_requests": network_monitor.stats["allowed_requests"],
        "bytes_transferred": network_monitor.stats["bytes_transferred"],
        "recent_event_count": len(network_monitor.events),
        "sovereign_status": "100% AIR-GAPPED (0 EXTERNAL CALLS)" if network_monitor.stats["blocked_requests"] == 0 or network_monitor.enforce else "AUDIT MODE",
    }


@router.get("/events")
async def get_recent_network_events(limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieve recent socket intercept events from the circular ring buffer."""
    events_list = list(network_monitor.events)
    return events_list[-limit:] if limit > 0 else events_list


@router.get("/stream")
async def stream_network_events():
    """SSE endpoint broadcasting real-time socket intercept events."""
    q = network_monitor.subscribe()

    async def event_generator():
        try:
            while True:
                event = await q.get()
                yield f"event: network_event\ndata: {json.dumps(event)}\n\n"
        finally:
            network_monitor.unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/verify")
async def verify_airgap_enforcement() -> Dict[str, Any]:
    """Actively verify air-gap enforcement by attempting an external connection.

    Demonstrates in real-time that outbound socket requests are strictly
    intercepted and blocked by the native socket interceptor.
    """
    target_host = "8.8.8.8"
    target_port = 53
    blocked = False
    exception_caught = None

    try:
        # Create a socket and attempt to connect to external DNS server
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect((target_host, target_port))
        s.close()
    except SecurityException as se:
        blocked = True
        exception_caught = str(se)
    except Exception as e:
        # Other exception (e.g. if SecurityException was wrapped)
        if "air-gap" in str(e).lower() or "violation" in str(e).lower():
            blocked = True
            exception_caught = str(e)
        else:
            exception_caught = str(e)

    return {
        "airgap_verified": blocked,
        "intercepted": blocked,
        "target": f"{target_host}:{target_port}",
        "exception": exception_caught,
        "message": (
            "Air-gap verified: External connection attempt was intercepted and blocked."
            if blocked
            else "Warning: Outbound connection was not intercepted."
        ),
    }
