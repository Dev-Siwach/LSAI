import os
import unittest
from pathlib import Path
from tools.file_manager import FileManager
from tools.spreadsheet import SpreadsheetTool
from tools.sandbox import Sandbox
import tempfile
import openpyxl

class TestTools(unittest.TestCase):
    def setUp(self):
        self.fm = FileManager()
        # Create uploads directory if not exists
        self.fm.settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    def test_file_manager_allowed_paths(self):
        allowed_path = str(self.fm.settings.UPLOADS_DIR / "test.txt")
        self.assertTrue(self.fm._is_path_allowed(allowed_path))
        
        disallowed_path = "/tmp/secret.txt"
        self.assertFalse(self.fm._is_path_allowed(disallowed_path))

    def test_file_manager_write_read_list(self):
        filename = "test_doc.txt"
        filepath = str(self.fm.settings.UPLOADS_DIR / filename)
        
        # Write
        self.fm.write_file(filepath, "Hello World")
        
        # Read
        content = self.fm.read_file(filepath)
        self.assertEqual(content, "Hello World")
        
        # List
        files = self.fm.list_files("uploads")
        self.assertTrue(any(f["name"] == filename for f in files))
        
        # Delete
        self.assertTrue(self.fm.delete_file(filepath))
        self.assertFalse(os.path.exists(filepath))

    def test_spreadsheet_tool(self):
        st = SpreadsheetTool(self.fm)
        
        # Create a dummy xlsx
        filepath = str(self.fm.settings.UPLOADS_DIR / "test_sheet.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Data"
        ws.append(["A", "B"])
        ws.append([1, 2])
        wb.save(filepath)
        
        # Read xlsx
        result = st.read_xlsx(filepath)
        self.assertEqual(result["sheet_name"], "Data")
        self.assertEqual(result["headers"], ["A", "B"])
        self.assertEqual(len(result["data"]), 1)
        
        # Update cell
        st.update_xlsx_cell(filepath, "Data", 2, 1, 100)
        result2 = st.read_xlsx(filepath)
        self.assertEqual(result2["data"][0][0], 100)
        
        # Cleanup
        self.fm.delete_file(filepath)

    def test_sandbox_subprocess(self):
        sb = Sandbox()
        # Force subprocess mode for testing (no docker assumption)
        sb.docker_available = False 
        
        # Basic execution
        result = sb.execute_code("print('Hello from sandbox')", timeout=5)
        self.assertTrue(result["success"])
        self.assertIn("Hello from sandbox", result["stdout"])
        
        # Syntax error
        result2 = sb.execute_code("print('Broken", timeout=5)
        self.assertFalse(result2["success"])
        self.assertIn("SyntaxError", result2["stderr"])

if __name__ == "__main__":
    unittest.main()
