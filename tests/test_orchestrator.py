"""Tests for Core Orchestrator (Phase 4).

Verifies 3-stage pipeline (Plan, Execute, Synthesize), self-correction retry loop,
model auto-routing, multi-turn session retention, and live SSE event broadcasting.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from core.orchestrator import (
    Orchestrator,
    PlanStep,
    TaskPlan,
    TaskStatus,
)


@pytest.fixture
def mock_tools():
    """Create mock tools for orchestrator testing."""
    mock_sandbox = MagicMock()
    mock_sandbox.execute_code.return_value = {
        "success": True,
        "stdout": "Calculated t_min = 0.1652 in\nVerification: PASS",
        "stderr": "",
        "exit_code": 0,
        "mode": "subprocess",
    }

    mock_rag = MagicMock()
    mock_rag.search.return_value = [
        {"text": "Refinery SOP 402: High pressure valve compliance rule.", "score": 0.95, "metadata": {"sop": "402"}}
    ]

    mock_doc = MagicMock()
    mock_doc.parse_pdf.return_value = {
        "success": True,
        "content": "Inspection Report: Pipe 10-H-01 corrosion rate 0.42 mm/yr.",
        "metadata": {"parser": "mock"},
    }
    mock_doc.prepare_vision_image.return_value = {
        "dimensions": (1920, 1080),
        "channels": 3,
        "format": "PNG",
    }

    mock_deliverable = MagicMock()
    mock_deliverable.generate_docx_approval_note.return_value = "/tmp/mock_approval_note.docx"
    mock_deliverable.generate_excel_calculation_sheet.return_value = "/tmp/mock_calc_sheet.xlsx"
    mock_deliverable.generate_xlsx_calculation_sheet.return_value = "/tmp/mock_calc_sheet.xlsx"
    mock_deliverable.generate_pptx_briefing.return_value = "/tmp/mock_briefing.pptx"

    mock_file_mgr = MagicMock()
    mock_file_mgr.list_files.return_value = []
    mock_file_mgr.read_file.return_value = "sample content"
    mock_file_mgr.write_file.return_value = "/tmp/mock_file.txt"

    mock_spreadsheet = MagicMock()
    mock_spreadsheet.read_csv.return_value = {"headers": ["A", "B"], "data": [["1", "2"]], "row_count": 1}

    return {
        "sandbox": mock_sandbox,
        "rag": mock_rag,
        "doc": mock_doc,
        "deliverable": mock_deliverable,
        "file_mgr": mock_file_mgr,
        "spreadsheet": mock_spreadsheet,
    }


@pytest.fixture
def orchestrator(mock_tools):
    """Instantiate orchestrator with injected mock tools."""
    return Orchestrator(
        sandbox=mock_tools["sandbox"],
        rag_engine=mock_tools["rag"],
        doc_parser=mock_tools["doc"],
        deliverable_gen=mock_tools["deliverable"],
        file_mgr=mock_tools["file_mgr"],
        spreadsheet_tool=mock_tools["spreadsheet"],
    )


class TestIntentClassificationAndRouting:
    """Verify Stage 1 intent classifier and model auto-routing."""

    def test_intent_classification_engineering_calculation(self, orchestrator):
        prompt = "Calculate the pipe wall minimum allowable thickness under ASME B31.3"
        intent = orchestrator.classify_intent(prompt)
        assert intent == "engineering_calculation"

    def test_intent_classification_vision_pid(self, orchestrator):
        prompt = "Analyze the P&ID diagram and identify all shutoff valves"
        intent = orchestrator.classify_intent(prompt)
        assert intent == "vision_pid_inspection"

    def test_intent_classification_scanned_ocr(self, orchestrator):
        prompt = "Extract corrosion data from this scanned ultrasonic inspection report"
        intent = orchestrator.classify_intent(prompt)
        assert intent == "scanned_document_ocr"

    def test_intent_classification_code_execution(self, orchestrator):
        prompt = "Write a python script to simulate pressure drop and run in sandbox"
        intent = orchestrator.classify_intent(prompt)
        assert intent == "code_execution"

    def test_intent_classification_sop_compliance(self, orchestrator):
        prompt = "Check refinery SOP compliance and approval hierarchy clearance"
        intent = orchestrator.classify_intent(prompt)
        assert intent == "sop_compliance"

    def test_intent_classification_deep_reasoning_default(self, orchestrator):
        prompt = "What are the strategic maintenance trade-offs for catalyst bed replacement?"
        intent = orchestrator.classify_intent(prompt)
        assert intent == "deep_reasoning"

    @pytest.mark.asyncio
    async def test_stage_1_plan_generates_model_and_steps(self, orchestrator):
        prompt = "Calculate pipe wall minimum allowable thickness under ASME B31.3"
        plan = await orchestrator._stage_1_plan(
            task_id="test-task-1",
            prompt=prompt,
        )
        assert isinstance(plan, TaskPlan)
        assert plan.task_type == "engineering_calculation"
        assert plan.selected_model["selected_model_id"] == "qwen3.8-27b"
        assert len(plan.steps) >= 2
        assert any(s.tool == "sandbox" for s in plan.steps)


class TestWorkerExecutionAndSelfCorrection:
    """Verify Stage 2 execution and autonomous self-correction retry loop."""

    @pytest.mark.asyncio
    async def test_successful_step_execution(self, orchestrator):
        plan = TaskPlan(
            task_id="test-task-2",
            task_type="engineering_calculation",
            selected_model={"selected_model_id": "qwen3.8-27b", "model_name": "Qwen-3.8-27B"},
            summary="Test plan",
            steps=[
                PlanStep(
                    step_id=1,
                    name="run_sandbox",
                    tool="sandbox",
                    action="execute_code",
                    parameters={"code": "print('hello')"},
                    description="Run sandbox",
                )
            ],
        )

        results = await orchestrator._stage_2_execute("test-task-2", plan, "prompt")
        assert len(results) == 1
        assert results[0]["status"] == "SUCCESS"
        assert results[0]["retries"] == 0

    @pytest.mark.asyncio
    async def test_self_correction_retry_loop_success_after_failure(self, orchestrator, mock_tools):
        """Step fails on attempt 1, then succeeds on attempt 2 after self-correction."""
        call_count = 0

        def side_effect_sandbox(code):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"success": False, "stderr": "SyntaxError: invalid syntax", "exit_code": 1}
            return {"success": True, "stdout": "Corrected and passed", "stderr": "", "exit_code": 0}

        mock_tools["sandbox"].execute_code.side_effect = side_effect_sandbox

        plan = TaskPlan(
            task_id="test-task-retry",
            task_type="engineering_calculation",
            selected_model={"selected_model_id": "qwen3.8-27b", "model_name": "Qwen-3.8-27B"},
            summary="Retry plan",
            steps=[
                PlanStep(
                    step_id=1,
                    name="flaky_step",
                    tool="sandbox",
                    action="execute_code",
                    parameters={"code": "broken code"},
                    description="Flaky step",
                    max_retries=3,
                )
            ],
        )

        # Set task in orchestrator state
        orchestrator.tasks["test-task-retry"] = MagicMock(cancelled=False, errors=[])

        results = await orchestrator._stage_2_execute("test-task-retry", plan, "prompt")
        assert len(results) == 1
        assert results[0]["status"] == "SUCCESS"
        assert results[0]["retries"] == 1  # Succeeded on attempt 2 (1 retry)
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_step_failure_after_exhausting_all_retries(self, orchestrator, mock_tools):
        """Step consistently fails through all 3 retries."""
        mock_tools["sandbox"].execute_code.return_value = {
            "success": False,
            "stderr": "Persistent failure",
            "exit_code": 1,
        }

        plan = TaskPlan(
            task_id="test-task-fail",
            task_type="engineering_calculation",
            selected_model={"selected_model_id": "qwen3.8-27b", "model_name": "Qwen-3.8-27B"},
            summary="Fail plan",
            steps=[
                PlanStep(
                    step_id=1,
                    name="always_fail",
                    tool="sandbox",
                    action="execute_code",
                    parameters={"code": "broken"},
                    description="Always fail",
                    max_retries=3,
                )
            ],
        )

        orchestrator.tasks["test-task-fail"] = MagicMock(cancelled=False, errors=[])
        results = await orchestrator._stage_2_execute("test-task-fail", plan, "prompt")
        assert len(results) == 1
        assert results[0]["status"] == "FAILED"
        assert plan.steps[0].status == "FAILED"


class TestStage3SynthesisAndDeliverables:
    """Verify Stage 3 deliverable generation and synthesis reporting."""

    @pytest.mark.asyncio
    async def test_synthesis_generates_docx_and_xlsx(self, orchestrator):
        plan = TaskPlan(
            task_id="test-task-synth",
            task_type="engineering_calculation",
            selected_model={"selected_model_id": "qwen3.8-27b", "model_name": "Qwen-3.8-27B"},
            summary="Synthesis plan",
            steps=[],
        )

        synth = await orchestrator._stage_3_synthesize(
            task_id="test-task-synth",
            prompt="Calculate ASME pipe thickness and export to excel calculation sheet",
            plan=plan,
            step_results=[{"name": "calc", "status": "SUCCESS", "result": "t_min=0.1652"}],
        )

        deliverables = synth["deliverables"]
        assert len(deliverables) >= 2
        types = [d["type"] for d in deliverables]
        assert "docx" in types
        assert "xlsx" in types
        assert "Sovereign Agentic Workbench — Execution Synthesis" in synth["synthesis"]
        assert "100% On-Premise Sovereign" in synth["synthesis"]


class TestSessionContextAndSSE:
    """Verify multi-turn session retention and SSE event streaming."""

    def test_session_history_management(self, orchestrator):
        sid = "session-123"
        orchestrator.append_session_message(sid, "user", "Hello first turn")
        orchestrator.append_session_message(sid, "assistant", "Response first turn")

        history = orchestrator.get_session_history(sid)
        assert len(history) == 2
        assert history[0]["content"] == "Hello first turn"
        assert history[1]["content"] == "Response first turn"

        orchestrator.clear_session(sid)
        assert len(orchestrator.get_session_history(sid)) == 0

    @pytest.mark.asyncio
    async def test_end_to_end_run_task_and_sse_stream(self, orchestrator):
        prompt = "Calculate pipe wall minimum allowable thickness under ASME B31.3"
        task_id = await orchestrator.run_task(prompt=prompt, session_id="test-session")
        assert task_id in orchestrator.tasks

        # Wait briefly for background pipeline to complete
        for _ in range(30):
            state = orchestrator.get_task_state(task_id)
            if state["status"] in ("COMPLETED", "FAILED"):
                break
            await asyncio.sleep(0.1)

        final_state = orchestrator.get_task_state(task_id)
        assert final_state["status"] == "COMPLETED"
        assert len(final_state["deliverables"]) > 0
        assert final_state["synthesis"] is not None

        # Check session history was updated
        history = orchestrator.get_session_history("test-session")
        assert len(history) == 2  # user + assistant

    @pytest.mark.asyncio
    async def test_real_sse_event_streaming(self, orchestrator):
        task_id = "test-sse-task"
        orchestrator.tasks[task_id] = MagicMock(status=TaskStatus.PLANNING, cancelled=False, to_dict=lambda: {"status": "PLANNING"})

        received_events = []

        async def collect_events():
            async for ev in orchestrator.stream_events(task_id):
                received_events.append(ev)
                if ev.get("event") == "task_completed":
                    break

        collector = asyncio.create_task(collect_events())
        await asyncio.sleep(0.05)

        await orchestrator.emit_event(task_id, "step_started", {"step": 1})
        await orchestrator.emit_event(task_id, "task_completed", {"status": "COMPLETED"})

        await asyncio.wait_for(collector, timeout=2.0)
        assert len(received_events) == 2
        assert received_events[0]["event"] == "step_started"
        assert received_events[1]["event"] == "task_completed"
