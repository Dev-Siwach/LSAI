"""Agent Routes for Sovereign On-Premise Agentic AI Workbench.

Provides endpoints for launching tasks, streaming live execution telemetry via SSE,
polling task status, and inspecting session conversation context.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.orchestrator import orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Agent"])


class AgentRunRequest(BaseModel):
    """Payload to dispatch an agent task."""
    prompt: str = Field(..., min_length=1, description="User prompt or industrial command")
    session_id: Optional[str] = Field(None, description="Optional conversation session ID")
    task_type: Optional[str] = Field(None, description="Optional manual override for task type")
    file_paths: Optional[List[str]] = Field(default_factory=list, description="Attached workspace file paths")
    profile: Optional[str] = Field(None, description="Hardware profile override")


class AgentRunResponse(BaseModel):
    """Response returned immediately upon task dispatch."""
    task_id: str
    session_id: str
    status: str
    stream_url: str


@router.post("/run", response_model=AgentRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_agent_task(request: AgentRunRequest) -> AgentRunResponse:
    """Launch an agent task through the 3-Stage Sovereign Pipeline."""
    task_id = await orchestrator.run_task(
        prompt=request.prompt,
        session_id=request.session_id,
        task_type=request.task_type,
        file_paths=request.file_paths,
        profile=request.profile,
    )
    state = orchestrator.get_task_state(task_id)
    session_id = state["session_id"] if state else (request.session_id or "")

    return AgentRunResponse(
        task_id=task_id,
        session_id=session_id,
        status="PENDING",
        stream_url=f"/api/agent/stream/{task_id}",
    )


@router.get("/stream/{task_id}")
async def stream_agent_events(task_id: str):
    """SSE endpoint streaming live agent thought process, tool execution, and deliverables."""
    state = orchestrator.get_task_state(task_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    async def event_generator():
        curr = orchestrator.get_task_state(task_id)
        if curr and curr["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            event_name = f"task_{curr['status'].lower()}"
            yield f"event: {event_name}\ndata: {json.dumps(curr)}\n\n"
            return

        async for event in orchestrator.stream_events(task_id):
            event_name = event.get("event", "message")
            data_str = json.dumps(event)
            yield f"event: {event_name}\ndata: {data_str}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/task/{task_id}")
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """Retrieve full execution status, step results, and deliverables for a task."""
    state = orchestrator.get_task_state(task_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return state


@router.get("/tasks")
async def list_recent_tasks(limit: int = Query(50, ge=1, le=200)) -> List[Dict[str, Any]]:
    """List recent agent tasks."""
    return orchestrator.list_tasks(limit=limit)


@router.post("/cancel/{task_id}")
async def cancel_agent_task(task_id: str) -> Dict[str, Any]:
    """Cancel an in-flight agent task."""
    success = orchestrator.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return {"task_id": task_id, "status": "CANCELLED", "success": True}


@router.get("/history/{session_id}")
async def get_session_history(session_id: str) -> Dict[str, Any]:
    """Retrieve multi-turn conversation history for a given session."""
    history = orchestrator.get_session_history(session_id)
    return {
        "session_id": session_id,
        "turns_count": len(history),
        "history": history,
    }


@router.delete("/history/{session_id}")
async def clear_session_history(session_id: str) -> Dict[str, Any]:
    """Reset conversation context for a session."""
    cleared = orchestrator.clear_session(session_id)
    return {"session_id": session_id, "cleared": cleared}
