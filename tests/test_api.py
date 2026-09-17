"""Integration Test Suite for FastAPI Workbench Server (Phase 4).

Tests system endpoints, network monitor audit routes, RAG vector retrieval routes,
secure deliverable download endpoints (with path traversal security tests),
and agent task dispatch, status, and cancellation.
"""

import io
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from api.main import app
from config.settings import get_settings


@pytest.fixture(scope="module")
def client():
    """Shared TestClient for API integration tests."""
    with TestClient(app) as test_client:
        yield test_client


class TestSystemEndpoints:
    """Verify system-level overview and health endpoints."""

    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["problem_statement_id"] == "26117"
        assert data["status"] == "OPERATIONAL"
        assert "app_name" in data
        assert "version" in data

    def test_health_check_endpoints(self, client):
        for path in ["/health", "/api/health"]:
            response = client.get(path)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "HEALTHY"
            assert data["problem_statement"] == "26117"
            assert "airgap" in data
            assert data["airgap"]["sovereign_proof"] == "ZERO_EXTERNAL_EGRESS"
            assert "directories" in data


class TestNetworkRoutes:
    """Verify air-gap network monitoring, events, and verification endpoints."""

    def test_network_stats(self, client):
        response = client.get("/api/network/stats")
        assert response.status_code == 200
        data = response.json()
        assert "airgap_enforce" in data
        assert "allowed_hosts" in data
        assert "blocked_requests" in data
        assert "allowed_requests" in data

    def test_network_events(self, client):
        response = client.get("/api/network/events?limit=10")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_airgap_verification_endpoint(self, client):
        """Verify that the verification probe actively intercepts external connection attempts."""
        response = client.post("/api/network/verify")
        assert response.status_code == 200
        data = response.json()
        assert data["airgap_verified"] is True
        assert data["intercepted"] is True
        assert "Air-gap verified" in data["message"]


class TestDeliverableRoutes:
    """Verify deliverable download, listing, and path-traversal prevention."""

    def test_list_deliverables(self, client):
        response = client.get("/api/deliverables/list")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_download_existing_deliverable(self, client):
        settings = get_settings()
        test_file = settings.DELIVERABLES_DIR / "test_artifact.txt"
        test_file.write_text("Sovereign verified content")

        try:
            response = client.get(f"/api/deliverables/download/{test_file.name}")
            assert response.status_code == 200
            assert response.text == "Sovereign verified content"
            assert "attachment" in response.headers.get("Content-Disposition", "")
        finally:
            if test_file.exists():
                test_file.unlink()

    def test_path_traversal_prevention_dotdot(self, client):
        """Verify ../../ traversal attempts are rejected."""
        response = client.get("/api/deliverables/download/..%2F..%2Fetc%2Fpasswd")
        assert response.status_code in (400, 403, 404)

    def test_path_traversal_prevention_slashes(self, client):
        """Verify slash-separated paths are rejected."""
        response = client.get("/api/deliverables/download/etc/passwd")
        assert response.status_code in (400, 404)

    def test_nonexistent_deliverable_returns_404(self, client):
        response = client.get("/api/deliverables/download/nonexistent_file_99999.docx")
        assert response.status_code == 404

    def test_deliverable_info_and_delete(self, client):
        settings = get_settings()
        test_file = settings.DELIVERABLES_DIR / "temp_info_test.txt"
        test_file.write_text("temporary info test")

        try:
            info_res = client.get(f"/api/deliverables/info/{test_file.name}")
            assert info_res.status_code == 200
            assert info_res.json()["filename"] == test_file.name

            del_res = client.delete(f"/api/deliverables/{test_file.name}")
            assert del_res.status_code == 200
            assert del_res.json()["deleted"] is True
            assert not test_file.exists()
        finally:
            if test_file.exists():
                test_file.unlink()


class TestRagRoutes:
    """Verify document upload, text ingestion, and vector search endpoints."""

    def test_rag_info(self, client):
        response = client.get("/api/rag/info")
        assert response.status_code == 200
        data = response.json()
        assert "collection_name" in data
        assert "embedding_model" in data

    def test_rag_upload_disallowed_extension_fails(self, client):
        file_content = b"executable binary"
        response = client.post(
            "/api/rag/upload",
            files={"file": ("malicious.exe", io.BytesIO(file_content), "application/octet-stream")},
        )
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"]

    def test_rag_upload_valid_text_document(self, client):
        doc_content = b"Refinery SOP 402: Emergency shutoff valve operation protocol."
        response = client.post(
            "/api/rag/upload",
            files={"file": ("sop_402_test.txt", io.BytesIO(doc_content), "text/plain")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "sop_402_test.txt" in data["filename"]

    def test_rag_search_query(self, client):
        response = client.post(
            "/api/rag/search",
            json={"query": "shutoff valve operation", "limit": 3},
        )
        assert response.status_code == 200
        results = response.json()
        assert isinstance(results, list)


class TestAgentRoutes:
    """Verify agent task execution, polling, cancellation, and session history."""

    def test_agent_run_missing_prompt_returns_422(self, client):
        response = client.post("/api/agent/run", json={})
        assert response.status_code == 422

    def test_agent_run_success_and_status(self, client):
        payload = {
            "prompt": "Calculate ASME B31.3 pipe wall thickness for 150 psig NPS 10",
            "session_id": "api-test-session-1",
            "task_type": "engineering_calculation",
        }
        response = client.post("/api/agent/run", json=payload)
        assert response.status_code == 202
        data = response.json()
        task_id = data["task_id"]
        assert task_id is not None
        assert data["status"] == "PENDING"
        assert "/api/agent/stream/" in data["stream_url"]

        # Poll status
        status_res = client.get(f"/api/agent/task/{task_id}")
        assert status_res.status_code == 200
        task_state = status_res.json()
        assert task_state["task_id"] == task_id

    def test_agent_task_not_found(self, client):
        response = client.get("/api/agent/task/nonexistent-task-id-1234")
        assert response.status_code == 404

    def test_agent_cancel_task(self, client):
        # Create a task
        create_res = client.post(
            "/api/agent/run",
            json={"prompt": "Long running analysis task", "session_id": "cancel-session"},
        )
        task_id = create_res.json()["task_id"]

        cancel_res = client.post(f"/api/agent/cancel/{task_id}")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "CANCELLED"

    def test_session_history_and_clear(self, client):
        sid = "multi-turn-session"
        # Run turn 1
        client.post(
            "/api/agent/run",
            json={"prompt": "Turn 1 prompt", "session_id": sid},
        )
        time.sleep(0.1)

        history_res = client.get(f"/api/agent/history/{sid}")
        assert history_res.status_code == 200
        history_data = history_res.json()
        assert history_data["session_id"] == sid
        assert history_data["turns_count"] >= 1

        # Clear session
        del_res = client.delete(f"/api/agent/history/{sid}")
        assert del_res.status_code == 200
        assert del_res.json()["cleared"] is True
