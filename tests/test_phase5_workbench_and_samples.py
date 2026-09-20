"""Comprehensive Phase 5 Verification Test Suite.

Tests:
1. Sample Industrial Datasets Integrity (SOP, PDF Inspection, P&ID PNG)
2. Demo Data Seeder Script (Execution, RAG Ingestion, Verification Queries)
3. Air-Gapped Test Workbench Web UI (Serving, Static Files, Samples API)
4. End-to-End Orchestrator Execution across all 4 Demo Scenarios
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from PIL import Image

from api.main import app
from config.settings import get_settings
from core.orchestrator import orchestrator
from scripts import generate_samples, seed_demo_data
from tools.doc_parser import DocParser


class TestSampleDatasets(unittest.TestCase):
    """Verify integrity, format, and content of generated industrial sample datasets."""

    def setUp(self):
        self.settings = get_settings()
        self.samples_dir = self.settings.SAMPLES_DIR
        # Ensure files are generated
        generate_samples.generate_all_samples()

    def test_sop_file_content_and_standards(self):
        sop_path = self.samples_dir / "refinery_sop_402.txt"
        self.assertTrue(sop_path.exists())
        self.assertGreater(sop_path.stat().st_size, 1000)

        content = sop_path.read_text(encoding="utf-8")
        self.assertIn("SOP-REF-402-REV4", content)
        self.assertIn("ASME B31.3", content)
        self.assertIn("PSV-402", content)
        self.assertIn("7.20 mm", content)
        self.assertIn("10-HC-402", content)
        self.assertIn("ADMINISTRATIVE APPROVAL HIERARCHY", content)

    def test_inspection_pdf_validity_and_parsing(self):
        pdf_path = self.samples_dir / "inspection_report_sample.pdf"
        self.assertTrue(pdf_path.exists())
        self.assertGreater(pdf_path.stat().st_size, 500)

        # Validate PDF header
        raw_bytes = pdf_path.read_bytes()
        self.assertTrue(raw_bytes.startswith(b"%PDF-1.4"))

        # Validate extraction via DocParser
        parser = DocParser()
        result = parser.parse_pdf(str(pdf_path))
        self.assertTrue(result["success"], f"Failed to parse PDF: {result.get('error')}")
        self.assertIn("AVDU-02", result["content"])
        self.assertIn("7.15 mm", result["content"])
        self.assertIn("DEFICIENT", result["content"])

    def test_pid_image_validity_and_vision_prep(self):
        pid_path = self.samples_dir / "pid_drawing_sample.png"
        self.assertTrue(pid_path.exists())
        self.assertGreater(pid_path.stat().st_size, 10000)

        # Validate PIL can open the image
        with Image.open(pid_path) as img:
            self.assertEqual(img.format, "PNG")
            self.assertGreaterEqual(img.width, 1200)
            self.assertGreaterEqual(img.height, 800)

        # Test preparation for vision model
        parser = DocParser()
        opt_path = parser.prepare_vision_image(str(pid_path), max_size=(800, 600))
        try:
            self.assertTrue(os.path.exists(opt_path))
            with Image.open(opt_path) as opt_img:
                self.assertLessEqual(opt_img.width, 800)
                self.assertLessEqual(opt_img.height, 600)
        finally:
            if os.path.exists(opt_path):
                os.remove(opt_path)


class TestDataSeeder(unittest.TestCase):
    """Verify demo data seeding script execution and resilience."""

    def test_ensure_samples_exist_idempotent(self):
        # Should not raise exception
        seed_demo_data.ensure_samples_exist(force=False)
        seed_demo_data.ensure_samples_exist(force=True)

    @patch("scripts.seed_demo_data.RagEngine")
    def test_seed_rag_database_with_mock(self, mock_rag_cls):
        mock_engine = MagicMock()
        mock_engine.ingest_document.return_value = 4
        mock_rag_cls.return_value = mock_engine

        stats = seed_demo_data.seed_rag_database(force=True)
        self.assertTrue(stats["rag_online"])
        self.assertGreater(stats["total_chunks"], 0)
        self.assertTrue(mock_engine.ingest_document.called)

    @patch("scripts.seed_demo_data.RagEngine")
    def test_verify_knowledge_base_queries(self, mock_rag_cls):
        mock_engine = MagicMock()
        mock_engine.search.return_value = [
            {"score": 0.94, "text": "PSV-402 set pressure is 258 psig.", "metadata": {}}
        ]
        mock_rag_cls.return_value = mock_engine

        success = seed_demo_data.verify_knowledge_base()
        self.assertTrue(success)
        self.assertEqual(mock_engine.search.call_count, 3)

    @patch("scripts.seed_demo_data.seed_rag_database")
    @patch("scripts.seed_demo_data.ensure_samples_exist")
    def test_main_cli_execution(self, mock_ensure, mock_seed):
        mock_seed.return_value = {
            "sop_chunks": 3,
            "pdf_chunks": 2,
            "total_chunks": 5,
            "rag_online": False,
        }

        with patch.object(sys, "argv", ["seed_demo_data.py", "--force"]):
            ret = seed_demo_data.main()
            self.assertEqual(ret, 0)
            mock_ensure.assert_called_with(force=True)


class TestWorkbenchUI(unittest.TestCase):
    """Verify FastAPI routes serving the static test workbench UI and samples API."""

    def setUp(self):
        self.client = TestClient(app)

    def test_serve_demo_page(self):
        res = self.client.get("/demo")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("content-type", ""))
        self.assertIn("LSAI Sovereign Workbench", res.text)
        self.assertIn("PS ID: 26117", res.text)
        self.assertIn("ONE-CLICK DEMO SCENARIOS", res.text)
        self.assertIn("ASME B31.3", res.text)
        self.assertIn("card-stage-1", res.text)
        self.assertIn("card-stage-2", res.text)
        self.assertIn("card-stage-3", res.text)

    def test_serve_static_index(self):
        res = self.client.get("/static/index.html")
        self.assertEqual(res.status_code, 200)
        self.assertIn("LSAI Sovereign Workbench", res.text)

    def test_list_samples_api(self):
        res = self.client.get("/api/rag/samples")
        self.assertEqual(res.status_code, 200)
        samples = res.json()
        self.assertIsInstance(samples, list)
        self.assertGreaterEqual(len(samples), 3)

        filenames = [s["filename"] for s in samples]
        self.assertIn("refinery_sop_402.txt", filenames)
        self.assertIn("inspection_report_sample.pdf", filenames)
        self.assertIn("pid_drawing_sample.png", filenames)

        for s in samples:
            self.assertIn("title", s)
            self.assertIn("category", s)
            self.assertIn("description", s)
            self.assertIn("size_bytes", s)


class TestEndToEndDemoScenarios(unittest.IsolatedAsyncioTestCase):
    """Test all 4 core demonstration scenarios required by Problem Statement ID 26117."""

    def setUp(self):
        # Patch deliverable generators if optional docx/openpyxl libraries are missing
        self.patchers = []
        try:
            import docx  # noqa: F401
        except ImportError:
            p_docx = patch.object(
                orchestrator.deliverable_gen,
                "generate_docx_approval_note",
                return_value="/tmp/test_note.docx",
            )
            self.patchers.append(p_docx)
            p_docx.start()

        try:
            import openpyxl  # noqa: F401
        except ImportError:
            p_xlsx = patch.object(
                orchestrator.deliverable_gen,
                "generate_excel_calculation_sheet",
                return_value="/tmp/test_calc.xlsx",
            )
            self.patchers.append(p_xlsx)
            p_xlsx.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    async def _wait_for_task(self, task_id: str, timeout_seconds: float = 3.0) -> dict:
        """Helper to wait for background execution pipeline to complete."""
        max_iterations = int(timeout_seconds / 0.05)
        for _ in range(max_iterations):
            state = orchestrator.get_task_state(task_id)
            if state and state["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
                return state
            await asyncio.sleep(0.05)
        return orchestrator.get_task_state(task_id) or {}

    async def test_scenario_1_engineering_calculation_and_sandbox(self):
        """Scenario 1: Model Auto-Selection & Code Execution (ASME B31.3)."""
        prompt = (
            "Calculate minimum required pipe wall thickness under ASME B31.3 for 10-inch pipe "
            "at 258 psig and verify the calculation in the sandbox."
        )
        task_id = await orchestrator.run_task(prompt=prompt, profile="laptop_quantized")
        state = await self._wait_for_task(task_id)

        self.assertIsNotNone(state)
        self.assertEqual(state["task_type"], "engineering_calculation")
        self.assertIn("qwen", state["plan"]["selected_model"]["selected_model_id"].lower())
        self.assertEqual(state["status"], "COMPLETED")

        # Verify deliverables were produced
        deliverables = state["deliverables"]
        self.assertGreater(len(deliverables), 0)
        types = [d["type"] for d in deliverables]
        self.assertTrue("docx" in types or "xlsx" in types)

    async def test_scenario_2_scanned_inspection_to_word_approval_note(self):
        """Scenario 2: Scanned Report Analysis, RAG Cross-Referencing & Word Approval Note."""
        settings = get_settings()
        pdf_path = str(settings.SAMPLES_DIR / "inspection_report_sample.pdf")

        prompt = (
            "Read the attached scanned ultrasonic thickness inspection report for Line 10-HC-402-CS300, "
            "check against SOP-402 safety directive, and draft a formal PSU Word approval note."
        )
        task_id = await orchestrator.run_task(
            prompt=prompt,
            file_paths=[pdf_path],
            profile="laptop_quantized",
        )
        state = await self._wait_for_task(task_id)

        self.assertIsNotNone(state)
        self.assertEqual(state["task_type"], "scanned_document_ocr")
        self.assertEqual(state["status"], "COMPLETED")

        # Ensure Word document (.docx) was synthesized
        types = [d["type"] for d in state["deliverables"]]
        self.assertIn("docx", types)

    async def test_scenario_3_multimodal_pid_drawing_understanding(self):
        """Scenario 3: Multimodal P&ID Understanding with Vision Model."""
        settings = get_settings()
        pid_path = str(settings.SAMPLES_DIR / "pid_drawing_sample.png")

        prompt = (
            "Analyze the attached P&ID drawing for Column C-101. Identify valve tags PSV-402, "
            "PCV-101, and instrument transmitter FT-102."
        )
        task_id = await orchestrator.run_task(
            prompt=prompt,
            file_paths=[pid_path],
            profile="laptop_quantized",
        )
        state = await self._wait_for_task(task_id)

        self.assertIsNotNone(state)
        self.assertEqual(state["task_type"], "vision_pid_inspection")
        self.assertIn("vl", state["plan"]["selected_model"]["selected_model_id"].lower())
        self.assertEqual(state["status"], "COMPLETED")

    def test_scenario_4_airgap_sovereign_proof(self):
        """Scenario 4: Live Air-Gap Sovereign Proof via Network Verify Endpoint."""
        with TestClient(app) as client:
            res = client.post("/api/network/verify")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertTrue(data["airgap_verified"])
            self.assertTrue(data["intercepted"])
            self.assertIn("8.8.8.8", data["target"])


if __name__ == "__main__":
    unittest.main()
