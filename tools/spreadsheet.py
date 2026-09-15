import csv
from pathlib import Path
from typing import List, Dict, Any, Union, Optional
import openpyxl

class SpreadsheetTool:
    """Tool for reading, analyzing, and modifying .xlsx and .csv files."""
    
    def __init__(self, file_manager):
        self.file_manager = file_manager
        
    def _get_path(self, filepath: str) -> Path:
        """Resolve and validate path via file_manager."""
        path = Path(filepath)
        if not self.file_manager._is_path_allowed(path):
            raise PermissionError(f"Access denied: {filepath}")
        return path

    def read_csv(self, filepath: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """Read a CSV file and return its data and summary."""
        path = self._get_path(filepath)
        
        data = []
        headers = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            try:
                headers = next(reader)
            except StopIteration:
                return {"headers": [], "data": [], "row_count": 0}
                
            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break
                data.append(row)
                
        return {
            "headers": headers,
            "data": data,
            "row_count": len(data)
        }

    def read_xlsx(self, filepath: str, sheet_name: Optional[str] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        """Read an XLSX file and return data from a specific sheet."""
        path = self._get_path(filepath)
        wb = openpyxl.load_workbook(path, data_only=True)
        
        if sheet_name and sheet_name not in wb.sheetnames:
            raise ValueError(f"Sheet {sheet_name} not found. Available sheets: {wb.sheetnames}")
            
        sheet = wb[sheet_name] if sheet_name else wb.active
        
        data = []
        headers = []
        
        for i, row in enumerate(sheet.iter_rows(values_only=True)):
            if i == 0:
                headers = list(row)
            else:
                if limit and i > limit:
                    break
                data.append(list(row))
                
        return {
            "sheet_name": sheet.title,
            "available_sheets": wb.sheetnames,
            "headers": headers,
            "data": data,
            "row_count": len(data)
        }
        
    def summary(self, filepath: str) -> Dict[str, Any]:
        """Provide a structural summary of the spreadsheet."""
        path = self._get_path(filepath)
        ext = path.suffix.lower()
        
        if ext == ".csv":
            result = self.read_csv(filepath, limit=5)
            return {
                "type": "csv",
                "headers": result["headers"],
                "total_rows": result["row_count"], # this is just a sample limit length if we optimize later, but for now we read all if no limit. wait, limit=5 returns row_count=5. We should get total.
            }
        elif ext == ".xlsx":
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
            sheets_info = {}
            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                sheets_info[sheet_name] = {
                    "max_row": sheet.max_row,
                    "max_column": sheet.max_column
                }
            return {
                "type": "xlsx",
                "sheets": sheets_info
            }
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

    def get_summary(self, filepath: str) -> Dict[str, Any]:
        """Provide an accurate structural summary of the spreadsheet."""
        path = self._get_path(filepath)
        ext = path.suffix.lower()
        
        if ext == ".csv":
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                try:
                    headers = next(reader)
                except StopIteration:
                    headers = []
                row_count = sum(1 for _ in reader)
            return {
                "type": "csv",
                "headers": headers,
                "total_rows": row_count,
            }
        elif ext == ".xlsx":
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
            sheets_info = {}
            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                sheets_info[sheet_name] = {
                    "max_row": sheet.max_row,
                    "max_column": sheet.max_column
                }
            return {
                "type": "xlsx",
                "sheets": sheets_info
            }
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

    def update_xlsx_cell(self, filepath: str, sheet_name: str, row: int, col: int, value: Any, save_as: Optional[str] = None) -> str:
        """Update a specific cell (1-indexed row/col) in an XLSX file."""
        path = self._get_path(filepath)
        wb = openpyxl.load_workbook(path)
        
        if sheet_name not in wb.sheetnames:
            raise ValueError(f"Sheet {sheet_name} not found.")
            
        sheet = wb[sheet_name]
        sheet.cell(row=row, column=col, value=value)
        
        save_path = self._get_path(save_as) if save_as else path
        wb.save(save_path)
        return str(save_path)
