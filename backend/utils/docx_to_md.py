"""
DOCX to Markdown Converter
Extracts paragraphs and tables from a .docx file in order and converts them to a Markdown string.
"""
from docx import Document
from docx.document import Document as _Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

def iter_block_items(parent):
    """
    Generate a reference to each paragraph and table child within *parent*,
    in document order. Each returned value is an instance of either Table or
    Paragraph.
    """
    if isinstance(parent, _Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise ValueError("something's not right")

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)

def docx_to_md(file_path_or_bytes) -> str:
    """Converts a .docx file to a Markdown string preserving tables."""
    doc = Document(file_path_or_bytes)
    md_lines = []
    
    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if text:
                # Basic heuristic for headings based on style or text content
                if block.style and getattr(block.style, 'name', None) and block.style.name.startswith('Heading'):
                    level = block.style.name[-1]
                    try:
                        level = int(level)
                        md_lines.append(f"{'#' * level} {text}")
                    except ValueError:
                        md_lines.append(f"# {text}")
                elif text.startswith('Section '):
                    md_lines.append(f"## {text}")
                else:
                    md_lines.append(text)
        elif isinstance(block, Table):
            md_lines.append("") # Newline before table
            for i, row in enumerate(block.rows):
                row_data = [cell.text.replace('\n', ' ').strip() for cell in row.cells]
                md_lines.append("| " + " | ".join(row_data) + " |")
                # Add separator after header
                if i == 0:
                    md_lines.append("|" + "|".join(["---"] * len(row.cells)) + "|")
            md_lines.append("") # Newline after table
            
    return "\n".join(md_lines)

if __name__ == "__main__":
    import sys
    md = docx_to_md("Fake contracts and reports/MPR_A_ON_TRACK_Month3_Day91.docx")
    print(md[:1000])
