import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import docx
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
import pptx
from pptx.util import Inches as PptxInches, Pt as PptxPt

from config.settings import get_settings

class DeliverableGenerator:
    """Deliverable generation tool for .docx, .xlsx, and .pptx."""
    
    def __init__(self):
        self.settings = get_settings()
        self.deliverables_dir = self.settings.DELIVERABLES_DIR
        
    def _generate_filepath(self, prefix: str, ext: str) -> Path:
        """Generate a unique filepath for a new deliverable."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}{ext}"
        return self.deliverables_dir / filename

    def generate_docx_approval_note(self, data: Dict[str, Any]) -> str:
        """
        Generate a formatted PSU/government .docx note sheet.
        data should contain: ref_number, subject, findings, recommendations, annexures
        """
        doc = docx.Document()
        
        # Header
        header = doc.add_heading('OFFICIAL APPROVAL NOTE', 0)
        header.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Ref & Date
        ref_para = doc.add_paragraph()
        ref_para.add_run('Ref No: ').bold = True
        ref_para.add_run(data.get('ref_number', 'N/A') + '\t\t\t')
        ref_para.add_run('Date: ').bold = True
        ref_para.add_run(datetime.now().strftime('%d-%b-%Y'))
        
        doc.add_paragraph('_' * 80)
        
        # Subject
        subj_para = doc.add_paragraph()
        subj_para.add_run('Subject: ').bold = True
        subj_para.add_run(data.get('subject', 'N/A'))
        
        doc.add_heading('1. Findings', level=1)
        doc.add_paragraph(data.get('findings', 'No findings provided.'))
        
        if 'tabular_data' in data and data['tabular_data']:
            # Create a table
            table_data = data['tabular_data']
            if len(table_data) > 0:
                table = doc.add_table(rows=1, cols=len(table_data[0]))
                table.style = 'Table Grid'
                hdr_cells = table.rows[0].cells
                for i, col_name in enumerate(table_data[0].keys()):
                    hdr_cells[i].text = col_name
                    
                for row_data in table_data:
                    row_cells = table.add_row().cells
                    for i, val in enumerate(row_data.values()):
                        row_cells[i].text = str(val)
        
        doc.add_heading('2. Recommendations', level=1)
        doc.add_paragraph(data.get('recommendations', 'No recommendations provided.'))
        
        doc.add_heading('3. Annexures', level=1)
        doc.add_paragraph(data.get('annexures', 'None'))
        
        filepath = self._generate_filepath("Approval_Note", ".docx")
        doc.save(filepath)
        return str(filepath)

    def generate_excel_calculation_sheet(self, data: Dict[str, Any]) -> str:
        """
        Generate .xlsx workbook with calculations.
        data should contain: title, headers, rows
        """
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Calculations"
        
        title = data.get("title", "Engineering Calculation Sheet")
        ws.append([title])
        title_cell = ws['A1']
        title_cell.font = Font(size=14, bold=True)
        
        ws.append([]) # Empty row
        
        headers = data.get("headers", [])
        if headers:
            ws.append(headers)
            # Style headers
            for col in range(1, len(headers) + 1):
                cell = ws.cell(row=3, column=col)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="000080", end_color="000080", fill_type="solid")
                cell.alignment = Alignment(horizontal="center")
                
        for row_data in data.get("rows", []):
            ws.append(row_data)
            
        filepath = self._generate_filepath("Calc_Sheet", ".xlsx")
        wb.save(filepath)
        return str(filepath)

    def generate_pptx_briefing(self, data: Dict[str, Any]) -> str:
        """
        Generate .pptx summary slides.
        data should contain: title, subtitle, slides (list of dicts with 'title' and 'content')
        """
        prs = pptx.Presentation()
        
        # Title Slide
        title_slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(title_slide_layout)
        title = slide.shapes.title
        subtitle = slide.placeholders[1]
        
        title.text = data.get("title", "Executive Briefing")
        subtitle.text = data.get("subtitle", datetime.now().strftime('%Y-%m-%d'))
        
        # Content Slides
        bullet_slide_layout = prs.slide_layouts[1]
        for slide_data in data.get("slides", []):
            slide = prs.slides.add_slide(bullet_slide_layout)
            shapes = slide.shapes
            title_shape = shapes.title
            body_shape = shapes.placeholders[1]
            
            title_shape.text = slide_data.get("title", "Slide")
            
            tf = body_shape.text_frame
            content = slide_data.get("content", [])
            if isinstance(content, list):
                for item in content:
                    p = tf.add_paragraph()
                    p.text = item
                    p.level = 0
            else:
                tf.text = content
                
        filepath = self._generate_filepath("Briefing", ".pptx")
        prs.save(filepath)
        return str(filepath)
