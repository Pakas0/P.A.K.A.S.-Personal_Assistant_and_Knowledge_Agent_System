from openpyxl import Workbook

def build_xlsx(sheet_title: str, headers: list[str], rows: list[list], output_path: str) -> str:
    """
    headers: baris pertama (bold).
    rows: list of list, tiap inner list = 1 baris data.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]  # Excel sheet title limit is 31 chars
    ws.append(headers)
    for cell in ws[1]:
        cell.font = cell.font.copy(bold=True)
    for row in rows:
        ws.append(row)
    wb.save(output_path)
    return output_path
