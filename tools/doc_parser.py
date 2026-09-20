import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


class DocParser:
    """Document Parser using Docling, pypdf fallback, OCR, and Vision Pre-processing."""

    def __init__(self):
        pass

    def parse_pdf(self, filepath: str) -> Dict[str, Any]:
        """Parse PDF document into structured markdown using Docling or fallback."""
        path = Path(filepath)
        if not path.exists():
            return {
                "success": False,
                "error": f"File not found: {filepath}",
                "content": "",
            }

        # Attempt 1: Docling DocumentConverter
        try:
            from docling.document_converter import DocumentConverter
            converter = DocumentConverter()
            result = converter.convert(str(path))
            markdown_content = result.document.export_to_markdown()
            return {
                "success": True,
                "content": markdown_content,
                "metadata": {
                    "source": str(path),
                    "parser": "docling",
                },
            }
        except ImportError:
            pass
        except Exception:
            pass

        # Attempt 2: pypdf fallback
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            text_parts = [page.extract_text() or "" for page in reader.pages]
            full_text = "\n\n".join(text_parts).strip()
            return {
                "success": True,
                "content": full_text,
                "metadata": {
                    "source": str(path),
                    "parser": "pypdf",
                    "pages": len(reader.pages),
                },
            }
        except ImportError:
            pass
        except Exception as e:
            return {
                "success": False,
                "error": f"PDF parsing error: {str(e)}",
                "content": "",
            }

        # Attempt 3: Standard library PDF text stream extractor (zero-dependency fallback)
        try:
            raw_bytes = path.read_bytes()
            extracted = self._extract_raw_pdf_text(raw_bytes)
            if extracted and extracted.strip():
                return {
                    "success": True,
                    "content": extracted.strip(),
                    "metadata": {
                        "source": str(path),
                        "parser": "native_stream_fallback",
                    },
                }
        except Exception:
            pass

        return {
            "success": False,
            "error": "No PDF parser available. Install docling or pypdf.",
            "content": "",
        }

    def _extract_raw_pdf_text(self, raw_bytes: bytes) -> str:
        """Extract text from uncompressed or FlateDecode PDF streams using stdlib only."""
        import re
        import zlib

        extracted_lines = []

        # Find all stream ... endstream blocks
        stream_matches = re.findall(rb"stream[\r\n]+(.*?)[\r\n]+endstream", raw_bytes, re.DOTALL)
        for s in stream_matches:
            data = s
            # Try decompressing if flate compressed
            try:
                data = zlib.decompress(s)
            except Exception:
                pass

            decoded = data.decode("latin-1", errors="ignore")
            # Match Tj and TJ text operations
            tj_matches = re.findall(r"\((.*?)\)\s*Tj", decoded)
            for m in tj_matches:
                cleaned = m.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
                if cleaned.strip():
                    extracted_lines.append(cleaned)

        if not extracted_lines:
            # Fallback direct scan on whole file
            decoded = raw_bytes.decode("latin-1", errors="ignore")
            tj_matches = re.findall(r"\((.*?)\)\s*Tj", decoded)
            for m in tj_matches:
                cleaned = m.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
                if cleaned.strip():
                    extracted_lines.append(cleaned)

        return "\n".join(extracted_lines)

    def prepare_vision_image(self, filepath: str, max_size: Tuple[int, int] = (1024, 1024)) -> str:
        """Prepare an image (e.g. P&ID) for Qwen2-VL by optimizing size/format."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {filepath}")

        try:
            from PIL import Image
        except ImportError:
            raise ImportError("Pillow is required for image processing. Please install pillow.")

        try:
            with Image.open(path) as img:
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                else:
                    img = img.copy()

                img.thumbnail(max_size, Image.Resampling.LANCZOS)

                fd, temp_path = tempfile.mkstemp(suffix=".jpg", prefix="vision_opt_")
                os.close(fd)
                img.save(temp_path, format="JPEG", quality=85)
                return temp_path
        except Exception as e:
            raise ValueError(f"Failed to process image: {str(e)}")

    def ocr_extract(self, filepath: str) -> str:
        """Fallback local OCR extraction using Tesseract."""
        path = Path(filepath)
        if not path.exists():
            return f"File not found: {filepath}"

        try:
            from PIL import Image
            import pytesseract
        except ImportError as e:
            return f"OCR dependencies missing ({e}). Install pillow and pytesseract."

        try:
            with Image.open(path) as img:
                text = pytesseract.image_to_string(img)
                return text.strip()
        except Exception as e:
            return f"OCR Extraction failed: {str(e)}"
