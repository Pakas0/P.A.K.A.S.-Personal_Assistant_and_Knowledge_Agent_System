import os
import uuid
from utils.documents.docx_builder import build_docx
from utils.documents.xlsx_builder import build_xlsx
from utils.documents.pptx_builder import build_pptx
from utils.documents.pdf_builder import build_pdf
from config import BASE_DIR

TMP_EXPORT_DIR = os.path.join(BASE_DIR, "data", "tmp_exports")

async def generate_document(format: str, title: str, sections: list = None, table_data: dict = None) -> dict:
    """
    Dipanggil dari dalam tool-calling loop, mirip web_search().
    Return dict: {"file_path": str} kalau sukses, atau {"error": str} kalau gagal.
    """
    os.makedirs(TMP_EXPORT_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex[:8]}_{title[:30].replace(' ', '_')}.{format}"
    output_path = os.path.join(TMP_EXPORT_DIR, filename)

    try:
        if format == "docx":
            build_docx(title, sections or [], output_path)
        elif format == "pdf":
            build_pdf(title, sections or [], output_path)
        elif format == "pptx":
            build_pptx(title, sections or [], output_path)
        elif format == "xlsx":
            if not table_data:
                return {"error": "table_data wajib diisi untuk format xlsx"}
            build_xlsx(title, table_data.get("headers", []), table_data.get("rows", []), output_path)
        else:
            return {"error": f"Format tidak didukung: {format}"}
        return {"file_path": output_path}
    except Exception as e:
        return {"error": str(e)}
