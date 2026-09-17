"""Comprehensive Edge Case & Audit Test Suite (Phases 1 - 4).

Tests boundary conditions, security traversal attempts, air-gap integrity,
error handling, empty/malformed inputs, and resilience across all modules.
"""

import asyncio
import socket
import pytest
from unittest.mock import MagicMock

from config.settings import get_settings, get_model_for_task, get_profile_config
from core.network_monitor import NetworkMonitor, SecurityException
from core.model_manager import ModelManager, ModelError
from core.orchestrator import Orchestrator, TaskStatus
from tools.file_manager import FileManager
from tools.spreadsheet import SpreadsheetTool
from tools.sandbox import Sandbox
from tools.deliverable_gen import DeliverableGenerator
from fastapi.testclient import TestClient
from api.main import app


class TestPhase1EdgeCases:
    """Audit Phase 1: Settings, paths, models, and configuration edge cases."""

    def test_get_model_for_task_unknown_defaults_to_reasoning(self):
        result = get_model_for_task("completely_unknown_task_type")
        assert result["selected_model_id"] == "deepseek-r1:32b"
        assert result["category"] == "reasoning"

    def test_get_model_for_task_empty_string(self):
        result = get_model_for_task("")
        assert result["selected_model_id"] == "deepseek-r1:32b"

    def test_get_profile_config_invalid_raises_keyerror(self):
        with pytest.raises(KeyError):
            get_profile_config("nonexistent_quantum_cluster")

    def test_fast_fallback_profile_routes_to_7b_counterparts(self):
        math_model = get_model_for_task("engineering_calculation", profile_name="fast_fallback")
        assert math_model["selected_model_id"] == "qwen2.5-coder:7b"

        reasoning_model = get_model_for_task("deep_reasoning", profile_name="fast_fallback")
        assert reasoning_model["selected_model_id"] == "deepseek-r1:7b"


class TestPhase2EdgeCases:
    """Audit Phase 2: Air-gap network monitor and model manager edge cases."""

    def test_airgap_whitelist_ipv6_loopback(self):
        nm = NetworkMonitor()
        assert nm.is_allowed("::1") is True
        assert nm.is_allowed("localhost") is True
        assert nm.is_allowed("127.0.0.1") is True

    def test_airgap_blocks_external_and_records_audit(self):
        nm = NetworkMonitor()
        nm.start()
        try:
            initial_blocked = nm.stats["blocked_requests"]
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            with pytest.raises(SecurityException):
                s.connect(("1.1.1.1", 80))
            s.close()

            assert nm.stats["blocked_requests"] == initial_blocked + 1
            last_event = nm.events[-1]
            assert last_event["destination"] == "1.1.1.1"
            assert last_event["status"] == "BLOCKED"
        finally:
            nm.stop()

    @pytest.mark.asyncio
    async def test_model_manager_unreachable_endpoint_raises_model_error(self):
        mgr = ModelManager()
        # Point to an unreachable port
        mgr.base_url = "http://127.0.0.1:59999/v1/"
        mgr._client = None  # Reset client

        with pytest.raises(ModelError):
            await mgr.generate_completion("qwen3.8-27b", [{"role": "user", "content": "hi"}])
        await mgr.close()


class TestPhase3EdgeCases:
    """Audit Phase 3: Tools, storage, sandbox, and deliverable generators."""

    def test_file_manager_path_traversal_prefix_attack(self):
        fm = FileManager()
        settings = get_settings()

        fake_path = str(settings.UPLOADS_DIR) + "_fake/secret.txt"
        assert fm._is_path_allowed(fake_path) is False

        with pytest.raises(PermissionError):
            fm.read_file(fake_path)

    def test_spreadsheet_tool_invalid_coordinates(self):
        fm = FileManager()
        sheet = SpreadsheetTool(fm)

        with pytest.raises(ValueError):
            sheet.update_xlsx_cell("nonexistent.xlsx", "Sheet1", row=0, col=1, value="err")

    def test_sandbox_airgap_blocks_urllib(self):
        sandbox = Sandbox()
        code = (
            "import urllib.request\n"
            "try:\n"
            "    urllib.request.urlopen('http://google.com', timeout=1)\n"
            "except Exception as e:\n"
            "    print(f'CAUGHT: {type(e).__name__}')\n"
        )
        res = sandbox.execute_code(code)
        assert res["success"] is True
        assert "CAUGHT: PermissionError" in res["stdout"] or "CAUGHT: URLError" in res["stdout"]

    def test_deliverable_gen_unique_filenames(self):
        gen = DeliverableGenerator()
        path1 = gen._generate_filepath("note", ".docx")
        path2 = gen._generate_filepath("note", ".docx")
        assert path1.suffix == ".docx"
        assert path2.suffix == ".docx"
        assert path1 != path2


class TestPhase4EdgeCases:
    """Audit Phase 4: Orchestrator self-correction, SSE, and API security boundaries."""

    @pytest.mark.asyncio
    async def test_orchestrator_handles_empty_prompt(self):
        orch = Orchestrator()
        task_id = await orch.run_task(prompt="   ")
        assert task_id is not None

        # Wait for completion
        for _ in range(20):
            state = orch.get_task_state(task_id)
            if state["status"] in ("COMPLETED", "FAILED"):
                break
            await asyncio.sleep(0.1)

        state = orch.get_task_state(task_id)
        assert state["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_orchestrator_cancellation_aborts_steps(self):
        orch = Orchestrator()
        mock_sandbox = MagicMock()
        mock_sandbox.execute_code.return_value = {"success": True, "stdout": "", "stderr": "", "exit_code": 0}
        orch._sandbox = mock_sandbox

        task_id = await orch.run_task(prompt="Calculate pipe wall thickness")
        orch.cancel_task(task_id)

        await asyncio.sleep(0.2)
        state = orch.get_task_state(task_id)
        assert state["cancelled"] is True
        assert state["status"] in (TaskStatus.CANCELLED, TaskStatus.PLANNING, TaskStatus.EXECUTING)

    def test_api_path_traversal_encoded_dots_and_slashes(self):
        client = TestClient(app)
        resp = client.get("/api/deliverables/download/%2e%2e%2f%2e%2e%2fetc%2fshadow")
        assert resp.status_code in (400, 403, 404)

    def test_api_security_exception_handler_returns_403(self):
        """Verify that SecurityException triggers the 403 JSON exception handler."""
        from fastapi import APIRouter
        test_router = APIRouter()

        @test_router.get("/api/test-security-trigger")
        def trigger_sec_violation():
            raise SecurityException("Air-gap violation: blocked connection to 8.8.8.8:53")

        app.include_router(test_router)

        client = TestClient(app)
        resp = client.get("/api/test-security-trigger")
        assert resp.status_code == 403
        data = resp.json()
        assert data["error"] == "AIRGAP_VIOLATION_INTERCEPTED"
        assert data["airgap_enforced"] is True
        assert data["sovereign_status"] == "BLOCKED"
        assert "Air-gap violation" in data["message"]
