import os
from pathlib import Path
from typing import Dict, Any, Optional
from PIL import Image
import pytesseract

class DocParser:
    """Document Parser using Docling, OCR, and Vision Pre-processing."""
    
    def __init__(self):
        pass

    def parse_pdf(self, filepath: str) -> Dict[str, Any]:
        """Parse PDF document into structured markdown using Docling."""
        # Using Docling DocumentConverter
        try:
            from docling.document_converter import DocumentConverter
            converter = DocumentConverter()
            
            result = converter.convert(filepath)
            markdown_content = result.document.export_to_markdown()
            
            return {
                "success": True,
                "content": markdown_content,
                "metadata": {
                    "source": filepath,
                    "parser": "docling"
                }
            }
        except ImportError:
            # Fallback if docling is not installed or fails
            return {
                "success": False,
                "error": "Docling is not installed or available.",
                "content": ""
            }
        except Exception as e:
             return {
                "success": False,
                "error": f"Failed to parse document: {str(e)}",
                "content": ""
            }

    def prepare_vision_image(self, filepath: str, max_size: tuple = (1024, 1024)) -> str:
        """Prepare an image (e.g. P&ID) for Qwen2-VL by optimizing size/format."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {filepath}")
            
        try:
            img = Image.open(path)
            # Convert to RGB if necessary
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
                
            # Resize while preserving aspect ratio
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save to a temporary optimized file
            import tempfile
            temp_path = tempfile.mktemp(suffix=".jpg")
            img.save(temp_path, format="JPEG", quality=85)
            
            return temp_path
        except Exception as e:
            raise ValueError(f"Failed to process image: {str(e)}")

    def ocr_extract(self, filepath: str) -> str:
        """Fallback local OCR extraction using Tesseract."""
        try:
            img = Image.open(filepath)
            text = pytesseract.image_to_string(img)
            return text
        except Exception as e:
            return f"OCR Extraction failed: {str(e)}"
