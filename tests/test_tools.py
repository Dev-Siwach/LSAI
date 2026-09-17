import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.file_manager import FileManager
from tools.spreadsheet import SpreadsheetTool
from tools.sandbox import Sandbox
from tools.rag_engine import RagEngine
from tools.doc_parser import DocParser
from tools.deliverable_gen import DeliverableGenerator


class TestFileManager(unittest.TestCase):
    def setUp(self):
        self.fm = FileManager()
        self.fm.settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        self.fm.settings.DELIVERABLES_DIR.mkdir(parents=True, exist_ok=True)

    def test_allowed_paths_and_traversal_prevention(self):
        # Allowed upload file
        allowed_path = str(self.fm.settings.UPLOADS_DIR / "sample.txt")
        self.assertTrue(self.fm._is_path_allowed(allowed_path))

        # Disallowed absolute path
        self.assertFalse(self.fm._is_path_allowed("/etc/shadow"))
        self.assertFalse(self.fm._is_path_allowed("/tmp/hacked.txt"))

        # Path traversal with .. escaping uploads directory
        traversal = str(self.fm.settings.UPLOADS_DIR / ".." / ".." / "etc" / "passwd")
        self.assertFalse(self.fm._is_path_allowed(traversal))

        # Prefix overlap attack (e.g. /path/to/uploads_evil should be rejected)
        evil_path = str(self.fm.settings.UPLOADS_DIR) + "_evil/secret.txt"
        self.assertFalse(self.fm._is_path_allowed(evil_path))

    def test_write_read_and_metadata(self):
        filename = "audit_log_sample.txt"
        filepath = str(self.fm.settings.UPLOADS_DIR / filename)

        # Write
        returned_path = self.fm.write_file(filepath, "Sovereign Industrial System Ready")
        self.assertEqual(returned_path, filepath)

        # Read
        content = self.fm.read_file(filepath)
        self.assertEqual(content, "Sovereign Industrial System Ready")

        # Metadata
        info = self.fm.get_file_info(filepath)
        self.assertEqual(info["name"], filename)
        self.assertEqual(info["extension"], ".txt")
        self.assertTrue(info["is_file"])
        self.assertGreater(info["size"], 0)

        # List
        files = self.fm.list_files("uploads")
        self.assertTrue(any(f["name"] == filename for f in files))

        # Delete
        self.assertTrue(self.fm.delete_file(filepath))
        self.assertFalse(os.path.exists(filepath))

    def test_edge_cases_empty_and_not_found(self):
        with self.assertRaises(ValueError):
            self.fm.read_file("")

        with self.assertRaises(ValueError):
            self.fm.write_file("   ", "content")

        with self.assertRaises(FileNotFoundError):
            self.fm.read_file(str(self.fm.settings.UPLOADS_DIR / "non_existent_999.txt"))

        with self.assertRaises(PermissionError):
            self.fm.read_file("/etc/hosts")

        with self.assertRaises(ValueError):
            self.fm.list_files("invalid_directory_name")


class TestSpreadsheetTool(unittest.TestCase):
    def setUp(self):
        self.fm = FileManager()
        self.st = SpreadsheetTool(self.fm)
        self.fm.settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    def test_csv_read_and_summary(self):
        csv_file = str(self.fm.settings.UPLOADS_DIR / "refinery_valves.csv")
        csv_content = "Valve_ID,Tag,Pressure_PSI,Status\nV-101,PRV-01,150.5,ACTIVE\nV-102,PRV-02,210.0,INSPECT\nV-103,PRV-03,85.2,ACTIVE\n"
        self.fm.write_file(csv_file, csv_content)

        try:
            # Full read
            result = self.st.read_csv(csv_file)
            self.assertEqual(result["headers"], ["Valve_ID", "Tag", "Pressure_PSI", "Status"])
            self.assertEqual(result["row_count"], 3)
            self.assertEqual(result["total_rows"], 3)
            self.assertEqual(result["data"][0], ["V-101", "PRV-01", "150.5", "ACTIVE"])

            # Limited read
            limited = self.st.read_csv(csv_file, limit=1)
            self.assertEqual(limited["row_count"], 1)
            self.assertEqual(limited["total_rows"], 3)
            self.assertEqual(limited["data"][0][0], "V-101")

            # Summary
            summary = self.st.get_summary(csv_file)
            self.assertEqual(summary["type"], "csv")
            self.assertEqual(summary["total_rows"], 3)
            self.assertIn("Tag", summary["headers"])
        finally:
            self.fm.delete_file(csv_file)

    def test_empty_csv(self):
        empty_file = str(self.fm.settings.UPLOADS_DIR / "empty.csv")
        self.fm.write_file(empty_file, "")
        try:
            res = self.st.read_csv(empty_file)
            self.assertEqual(res["headers"], [])
            self.assertEqual(res["data"], [])
            self.assertEqual(res["row_count"], 0)
        finally:
            self.fm.delete_file(empty_file)

    def test_xlsx_lazy_import_handling(self):
        dummy_path = str(self.fm.settings.UPLOADS_DIR / "dummy.xlsx")
        self.fm.write_file(dummy_path, "placeholder")
        try:
            # If openpyxl is not installed, verify it raises clear ImportError
            try:
                import openpyxl
            except ImportError:
                with self.assertRaises(ImportError) as ctx:
                    self.st.read_xlsx(dummy_path)
                self.assertIn("openpyxl is required", str(ctx.exception))
        finally:
            self.fm.delete_file(dummy_path)

    def test_invalid_coordinates(self):
        with self.assertRaises(ValueError):
            self.st.update_xlsx_cell("some.xlsx", "Sheet1", row=0, col=1, value="err")


class TestSandbox(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        # Explicitly test subprocess isolation engine
        self.sb.docker_available = False

    def test_subprocess_basic_execution(self):
        res = self.sb.execute_code("a = 15; b = 27; print(f'Sum: {a + b}')")
        self.assertTrue(res["success"])
        self.assertIn("Sum: 42", res["stdout"])
        self.assertEqual(res["exit_code"], 0)

    def test_subprocess_syntax_error(self):
        res = self.sb.execute_code("def broken_syntax(")
        self.assertFalse(res["success"])
        self.assertIn("SyntaxError", res["stderr"])
        self.assertNotEqual(res["exit_code"], 0)

    def test_subprocess_runtime_exception(self):
        res = self.sb.execute_code("x = 1 / 0")
        self.assertFalse(res["success"])
        self.assertIn("ZeroDivisionError", res["stderr"])
        self.assertNotEqual(res["exit_code"], 0)

    def test_subprocess_timeout(self):
        res = self.sb.execute_code("import time\ntime.sleep(5)", timeout=1)
        self.assertFalse(res["success"])
        self.assertIn("timed out", res["stderr"].lower())
        self.assertEqual(res["exit_code"], -1)

    def test_airgap_network_blocking_inside_sandbox(self):
        # Code attempts to establish socket connection inside sandbox
        unauthorized_script = """
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('127.0.0.1', 80))
"""
        res = self.sb.execute_code(unauthorized_script, timeout=5)
        self.assertFalse(res["success"])
        self.assertIn("Air-gap violation", res["stderr"])
        self.assertIn("PermissionError", res["stderr"])

    def test_empty_code_handling(self):
        res = self.sb.execute_code("")
        self.assertTrue(res["success"])
        self.assertEqual(res["stdout"], "")
        self.assertEqual(res["exit_code"], 0)

    def test_memory_limit_parsing(self):
        self.assertEqual(self.sb._parse_memory_limit_bytes("512m"), 512 * 1024 * 1024)
        self.assertEqual(self.sb._parse_memory_limit_bytes("1g"), 1024 * 1024 * 1024)
        self.assertEqual(self.sb._parse_memory_limit_bytes("128k"), 128 * 1024)
        self.assertEqual(self.sb._parse_memory_limit_bytes("invalid"), 512 * 1024 * 1024)


class TestRagEngine(unittest.TestCase):
    def test_text_chunking_edge_cases(self):
        # Mock client and encoder for isolated test
        mock_client = MagicMock()
        mock_encoder = MagicMock()
        mock_encoder.get_sentence_embedding_dimension.return_value = 128

        engine = RagEngine(client=mock_client, encoder=mock_encoder)

        # Empty text
        self.assertEqual(engine._chunk_text(""), [])
        self.assertEqual(engine._chunk_text("   "), [])

        # Normal text
        text = "word " * 150
        chunks = engine._chunk_text(text, chunk_size=50, overlap=10)
        self.assertGreater(len(chunks), 1)

        # Overlap greater than chunk_size (must not cause infinite loop)
        safe_chunks = engine._chunk_text(text, chunk_size=30, overlap=50)
        self.assertGreater(len(safe_chunks), 0)

    def test_ingest_and_search_with_mock(self):
        mock_client = MagicMock()
        mock_encoder = MagicMock()
        mock_encoder.get_sentence_embedding_dimension.return_value = 3
        mock_encoder.encode.return_value = [[0.1, 0.2, 0.3]]

        engine = RagEngine(client=mock_client, encoder=mock_encoder)

        # Ingestion
        count = engine.ingest_document("SOP_402", "Emergency shutdown valve procedure text.")
        self.assertEqual(count, 1)
        self.assertTrue(mock_client.upsert.called)

        # Search
        mock_hit = MagicMock()
        mock_hit.score = 0.95
        mock_hit.payload = {"text": "Emergency valve note", "doc_id": "SOP_402"}
        mock_client.search.return_value = [mock_hit]

        results = engine.search("emergency valve", limit=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["score"], 0.95)
        self.assertEqual(results[0]["text"], "Emergency valve note")


class TestDocParser(unittest.TestCase):
    def setUp(self):
        self.parser = DocParser()

    def test_nonexistent_pdf(self):
        res = self.parser.parse_pdf("/nonexistent/report.pdf")
        self.assertFalse(res["success"])
        self.assertIn("File not found", res["error"])

    def test_ocr_extract_nonexistent(self):
        res = self.parser.ocr_extract("/nonexistent/image.png")
        self.assertIn("File not found", res)

    def test_vision_image_preparation(self):
        # We test with PIL which is installed in this environment
        from PIL import Image
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img = Image.new("RGB", (2000, 1500), color="blue")
            img.save(f.name)
            png_path = f.name

        try:
            opt_path = self.parser.prepare_vision_image(png_path, max_size=(500, 500))
            self.assertTrue(os.path.exists(opt_path))
            with Image.open(opt_path) as opt_img:
                self.assertLessEqual(opt_img.width, 500)
                self.assertLessEqual(opt_img.height, 500)
            os.remove(opt_path)
        finally:
            if os.path.exists(png_path):
                os.remove(png_path)


class TestDeliverableGenerator(unittest.TestCase):
    def setUp(self):
        self.gen = DeliverableGenerator()

    def test_filepath_generation(self):
        fp = self.gen._generate_filepath("Refinery_Report", ".docx")
        self.assertTrue(str(fp).endswith(".docx"))
        self.assertIn("Refinery_Report", str(fp))
        self.assertTrue(self.gen.deliverables_dir.exists())

    def test_lazy_imports_error_on_missing_libs(self):
        data = {
            "ref_number": "IOCL/REF/2026/044",
            "subject": "Boiler Inspection Note",
            "findings": "Ultrasonic thickness measurement nominal.",
            "recommendations": "Authorize continued operation.",
        }

        # Check docx generation
        try:
            import docx
            # If docx happens to be installed, it should create file successfully
            doc_path = self.gen.generate_docx_approval_note(data)
            self.assertTrue(os.path.exists(doc_path))
            os.remove(doc_path)
        except ImportError:
            with self.assertRaises(ImportError) as ctx:
                self.gen.generate_docx_approval_note(data)
            self.assertIn("python-docx is required", str(ctx.exception))

        # Check excel generation
        try:
            import openpyxl
            sheet_path = self.gen.generate_excel_calculation_sheet({"title": "Test", "headers": ["A"], "rows": [[1]]})
            self.assertTrue(os.path.exists(sheet_path))
            os.remove(sheet_path)
        except ImportError:
            with self.assertRaises(ImportError) as ctx:
                self.gen.generate_excel_calculation_sheet({"headers": ["A"], "rows": []})
            self.assertIn("openpyxl is required", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
