import os
from pathlib import Path
from typing import List, Dict, Any, Union, Optional
from config.settings import get_settings


class FileManager:
    """Agent File Read/Write/List Tool for the workspace."""

    def __init__(self):
        self.settings = get_settings()
        # Define allowed root directories for agent operations
        self.allowed_dirs = [
            self.settings.UPLOADS_DIR,
            self.settings.DELIVERABLES_DIR,
            self.settings.SCRATCH_DIR,
            self.settings.SAMPLES_DIR,
        ]

    def _is_path_allowed(self, path: Union[str, Path]) -> bool:
        """Check if a path is within the allowed workspace directories.

        Uses Path.is_relative_to() for proper containment — immune to
        prefix-overlap attacks like '/data/uploads_evil/'.
        """
        try:
            abs_path = Path(path).resolve()
            for allowed_dir in self.allowed_dirs:
                resolved_dir = allowed_dir.resolve()
                try:
                    if abs_path.is_relative_to(resolved_dir):
                        return True
                except (TypeError, AttributeError):
                    # Fallback for older python
                    if str(abs_path).startswith(str(resolved_dir) + os.sep) or abs_path == resolved_dir:
                        return True
            return False
        except Exception:
            return False

    def list_files(self, directory: str = "uploads") -> List[Dict[str, Any]]:
        """List files in a specific workspace directory."""
        if not directory or not isinstance(directory, str):
            raise ValueError(f"Invalid directory category: {directory}")

        dir_key = directory.strip().lower()
        dir_map = {
            "uploads": self.settings.UPLOADS_DIR,
            "deliverables": self.settings.DELIVERABLES_DIR,
            "scratch": self.settings.SCRATCH_DIR,
            "samples": self.settings.SAMPLES_DIR,
        }

        target_dir = dir_map.get(dir_key)
        if not target_dir:
            raise ValueError(f"Unknown directory category: {directory}. Allowed: {list(dir_map.keys())}")

        target_dir.mkdir(parents=True, exist_ok=True)

        files = []
        for file_path in sorted(target_dir.iterdir(), key=lambda p: p.name):
            if file_path.is_file():
                files.append({
                    "name": file_path.name,
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "extension": file_path.suffix.lower(),
                })
        return files

    def read_file(self, filepath: str) -> str:
        """Read text content from a file in the workspace."""
        if not filepath or not str(filepath).strip():
            raise ValueError("Filepath cannot be empty")

        path = Path(filepath)
        if not self._is_path_allowed(path):
            raise PermissionError(f"Access denied: {filepath} is outside allowed workspace directories.")

        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File not found: {filepath}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            raise ValueError(f"Cannot read {filepath} as text. It may be a binary file.")

    def write_file(self, filepath: str, content: str) -> str:
        """Write text content to a file in the workspace."""
        if not filepath or not str(filepath).strip():
            raise ValueError("Filepath cannot be empty")

        path = Path(filepath)
        if not self._is_path_allowed(path):
            raise PermissionError(f"Access denied: {filepath} is outside allowed workspace directories.")

        # Ensure parent directory exists and is allowed
        if not self._is_path_allowed(path.parent):
            raise PermissionError(f"Access denied: Parent directory {path.parent} is outside allowed workspace directories.")

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return str(path)

    def delete_file(self, filepath: str) -> bool:
        """Delete a file in the workspace."""
        if not filepath or not str(filepath).strip():
            return False

        path = Path(filepath)
        if not self._is_path_allowed(path):
            raise PermissionError(f"Access denied: {filepath} is outside allowed workspace directories.")

        if path.exists() and path.is_file():
            path.unlink()
            return True
        return False

    def get_file_info(self, filepath: str) -> Dict[str, Any]:
        """Get metadata for a specific workspace file."""
        if not filepath or not str(filepath).strip():
            raise ValueError("Filepath cannot be empty")

        path = Path(filepath)
        if not self._is_path_allowed(path):
            raise PermissionError(f"Access denied: {filepath} is outside allowed workspace directories.")

        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        stat = path.stat()
        return {
            "name": path.name,
            "path": str(path),
            "size": stat.st_size,
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
            "extension": path.suffix.lower(),
            "modified_time": stat.st_mtime,
        }
