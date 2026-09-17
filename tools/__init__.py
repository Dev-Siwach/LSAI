"""Tools package — lazy imports to avoid crashing when optional deps are missing."""

__all__ = [
    "FileManager",
    "SpreadsheetTool",
    "RagEngine",
    "Sandbox",
    "DocParser",
    "DeliverableGenerator",
]


def __getattr__(name: str):
    """Lazy-import tool classes on first access."""
    if name == "FileManager":
        from .file_manager import FileManager
        return FileManager
    if name == "SpreadsheetTool":
        from .spreadsheet import SpreadsheetTool
        return SpreadsheetTool
    if name == "RagEngine":
        from .rag_engine import RagEngine
        return RagEngine
    if name == "Sandbox":
        from .sandbox import Sandbox
        return Sandbox
    if name == "DocParser":
        from .doc_parser import DocParser
        return DocParser
    if name == "DeliverableGenerator":
        from .deliverable_gen import DeliverableGenerator
        return DeliverableGenerator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
