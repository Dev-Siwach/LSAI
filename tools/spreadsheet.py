import csv
from pathlib import Path
from typing import List, Dict, Any, Optional


class SpreadsheetTool:
    """Tool for reading, analyzing, and modifying .xlsx and .csv files.

    Provides high-performance CSV handling via standard library and
    lazy-loads openpyxl for Excel workbooks.
    """

    def __init__(self, file_manager):
        self.file_manager = file_manager

    def _get_path(self, filepath: str) -> Path:
        """Resolve and validate path via file_manager."""
        if not filepath or not str(filepath).strip():
            raise ValueError("Filepath cannot be empty")
        path = Path(filepath)
        if not self.file_manager._is_path_allowed(path):
            raise PermissionError(f"Access denied: {filepath}")
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        return path

    def read_csv(self, filepath: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """Read a CSV file and return its data, headers, and total row count."""
        path = self._get_path(filepath)

        data: List[List[str]] = []
        headers: List[str] = []
        total_rows = 0

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            try:
                headers = next(reader)
            except StopIteration:
                return {"headers": [], "data": [], "row_count": 0, "total_rows": 0}

            for i, row in enumerate(reader):
                total_rows += 1
                if limit is None or i < limit:
                    data.append(row)

        return {
            "headers": headers,
            "data": data,
            "row_count": len(data),
            "total_rows": total_rows,
        }

    def read_xlsx(
        self, filepath: str, sheet_name: Optional[str] = None, limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """Read an XLSX file and return data from a specific sheet."""
        try:
            import openpyxl
        except ImportError:
            raise ImportError("openpyxl is required for reading .xlsx files. Please install openpyxl.")

        path = self._get_path(filepath)
        wb = openpyxl.load_workbook(path, data_only=True)

        try:
            if sheet_name and sheet_name not in wb.sheetnames:
                raise ValueError(f"Sheet '{sheet_name}' not found. Available sheets: {wb.sheetnames}")

            sheet = wb[sheet_name] if sheet_name else wb.active

            data: List[list] = []
            headers: List = []

            for i, row in enumerate(sheet.iter_rows(values_only=True)):
                if i == 0:
                    headers = list(row)
                else:
                    if limit is not None and len(data) >= limit:
                        break
                    data.append(list(row))

            return {
                "sheet_name": sheet.title,
                "available_sheets": wb.sheetnames,
                "headers": headers,
                "data": data,
                "row_count": len(data),
            }
        finally:
            wb.close()

    def get_summary(self, filepath: str) -> Dict[str, Any]:
        """Provide an accurate structural summary of the spreadsheet.

        For CSV: reads headers and counts total rows without external dependencies.
        For XLSX: uses openpyxl metadata.
        """
        path = self._get_path(filepath)
        ext = path.suffix.lower()

        if ext == ".csv":
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                try:
                    headers = next(reader)
                except StopIteration:
                    return {"type": "csv", "headers": [], "total_rows": 0}
                row_count = sum(1 for _ in reader)
            return {
                "type": "csv",
                "headers": headers,
                "total_rows": row_count,
            }
        elif ext == ".xlsx":
            try:
                import openpyxl
            except ImportError:
                raise ImportError("openpyxl is required for inspecting .xlsx files. Please install openpyxl.")

            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
            sheets_info = {}
            for sn in wb.sheetnames:
                sheet = wb[sn]
                sheets_info[sn] = {
                    "max_row": sheet.max_row,
                    "max_column": sheet.max_column,
                }
            wb.close()
            return {
                "type": "xlsx",
                "sheets": sheets_info,
            }
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

    def update_xlsx_cell(
        self,
        filepath: str,
        sheet_name: str,
        row: int,
        col: int,
        value: Any,
        save_as: Optional[str] = None,
    ) -> str:
        """Update a specific cell (1-indexed row/col) in an XLSX file.

        Args:
            row: 1-indexed row number (must be >= 1).
            col: 1-indexed column number (must be >= 1).
        """
        if row < 1 or col < 1:
            raise ValueError(f"Row ({row}) and col ({col}) must be >= 1 (1-indexed).")

        try:
            import openpyxl
        except ImportError:
            raise ImportError("openpyxl is required for updating .xlsx files. Please install openpyxl.")

        path = self._get_path(filepath)
        wb = openpyxl.load_workbook(path)

        try:
            if sheet_name not in wb.sheetnames:
                raise ValueError(f"Sheet '{sheet_name}' not found. Available: {wb.sheetnames}")

            sheet = wb[sheet_name]
            sheet.cell(row=row, column=col, value=value)

            if save_as:
                save_path = Path(save_as)
                if not self.file_manager._is_path_allowed(save_path):
                    raise PermissionError(f"Access denied: {save_as}")
            else:
                save_path = path

            wb.save(save_path)
            return str(save_path)
        finally:
            wb.close()
