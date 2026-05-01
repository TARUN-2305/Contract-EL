"""
PDF Exporter Agent — agents/pdf_exporter.py
Uses fpdf2 to convert Markdown/JSON reports into professional PDFs.
"""
import os
import json
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from datetime import datetime

class PDFExporter:
    def __init__(self):
        pass

    def md_to_pdf(self, md_content: str, output_path: str, title: str = "ContractGuard AI Report"):
        """
        Converts Markdown to a simple, clean PDF.
        Supports headings (#, ##, ###), bold (**text**), lists (-), and basic tables.
        """
        pdf = FPDF()
        pdf.add_font("DejaVu", "", "fonts/DejaVuSans.ttf", uni=True)
        pdf.add_font("DejaVu", "B", "fonts/DejaVuSans-Bold.ttf", uni=True)
        
        pdf.add_page()
        pdf.set_left_margin(15)
        pdf.set_right_margin(15)
        
        # Header
        pdf.set_font("DejaVu", "B", 16)
        pdf.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        pdf.set_font("DejaVu", "", 10)
        pdf.cell(0, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        pdf.line(15, 30, 195, 30)
        pdf.ln(10)
        
        # We will do a very basic markdown parser for the PDF layout
        lines = md_content.split('\n')
        
        for line in lines:
            line = line.replace('\t', '    ') # Replace tabs
            # Headings
            if line.startswith('# '):
                pdf.set_font("DejaVu", "B", 18)
                pdf.ln(5)
                pdf.multi_cell(0, 10, line.replace('# ', '').replace('**', ''), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(2)
            elif line.startswith('## '):
                pdf.set_font("DejaVu", "B", 14)
                pdf.ln(5)
                pdf.multi_cell(0, 8, line.replace('## ', '').replace('**', ''), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            elif line.startswith('### '):
                pdf.set_font("DejaVu", "B", 12)
                pdf.ln(3)
                pdf.multi_cell(0, 6, line.replace('### ', '').replace('**', ''), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            elif line.startswith('> '):
                # Blockquote (AI Summary)
                pdf.set_font("DejaVu", "", 11)
                pdf.set_text_color(50, 50, 50)
                pdf.multi_cell(0, 6, line.replace('> ', '').replace('**', ''), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(0, 0, 0)
                pdf.ln(2)
            elif line.startswith('- '):
                # Bullet points
                pdf.set_font("DejaVu", "", 11)
                clean_line = line.replace('**', '')
                pdf.multi_cell(0, 6, f"  \u2022 {clean_line[2:]}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            elif line.startswith('|') and '---' not in line:
                # Basic Table Rows
                pdf.set_font("DejaVu", "", 9)
                pdf.cell(0, 5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            elif line.strip() == '' or '---' in line:
                pdf.ln(3)
            else:
                # Normal paragraph text
                pdf.set_font("DejaVu", "", 11)
                clean_line = line.replace('**', '')
                if clean_line.strip():
                    pdf.multi_cell(0, 6, clean_line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        pdf.output(output_path)
        return output_path

    def export_compliance_report(self, compliance_md_path: str, output_dir: str = "data/reports") -> str:
        """Read a compliance MD file and output a PDF."""
        if not os.path.exists(compliance_md_path):
            raise FileNotFoundError(f"Markdown file not found: {compliance_md_path}")
            
        with open(compliance_md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
            
        filename = os.path.basename(compliance_md_path).replace('.md', '.pdf')
        out_path = os.path.join(output_dir, filename)
        
        return self.md_to_pdf(md_content, out_path, title="Contract Compliance & Risk Report")

# ── CLI Test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    exporter = PDFExporter()
    test_md = """# Compliance & Risk Report
**Project:** Test Project
**Contractor:** XYZ Corp
    
## AI Executive Summary
> This is a highly tailored executive summary highlighting the critical delay in M1.

## Metric Overview
| Item | Value | Status |
|---|---|---|
| Day Number | 30 of 730 | On Track |
| LD Accumulated | Rs. 0 | Clear |

### [CRITICAL] [C01] Milestone Missed
**What happened:**
The contractor has missed the M1 milestone by 15 days.
    """
    out = exporter.md_to_pdf(test_md, "data/reports/test_report.pdf")
    print(f"Test PDF generated at {out}")
