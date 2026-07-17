from fpdf import FPDF

def build_pdf(title: str, sections: list[dict], output_path: str) -> str:
    """
    sections: sama seperti docx — {"heading": str, "content": str}.
    Font default fpdf2 (Helvetica) — JANGAN embed font custom (nambah kompleksitas & size tanpa perlu).
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, title)
    pdf.ln(4)
    for sec in sections:
        if sec.get("heading"):
            pdf.set_font("Helvetica", "B", 13)
            pdf.multi_cell(0, 8, sec["heading"])
        pdf.set_font("Helvetica", "", 11)
        
        # Replace unprintable characters that fpdf doesn't like natively
        content = sec.get("content", "").encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 6, content)
        pdf.ln(2)
    pdf.output(output_path)
    return output_path
