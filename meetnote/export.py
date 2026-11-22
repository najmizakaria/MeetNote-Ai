"""Word document generation for meeting minutes."""
from __future__ import annotations
from io import BytesIO
from docx import Document
from docx.shared import Pt, RGBColor


def make_docx(title: str, date: str, transcript: str, notes: dict | None) -> bytes:
    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(10)
    normal.font.color.rgb = RGBColor(30, 51, 57)
    doc.add_heading(title or "Meeting", 0)
    doc.add_paragraph(f"Meeting date: {date}")
    if notes:
        doc.add_heading("Meeting overview", 1)
        doc.add_paragraph(notes.get("overview", ""))
        for field, heading in (("key_points", "Key points"), ("decisions", "Decisions"),
                               ("open_questions", "Open questions")):
            doc.add_heading(heading, 1)
            for item in notes.get(field, []):
                doc.add_paragraph(str(item), style="List Bullet")
        doc.add_heading("Action items", 1)
        for item in notes.get("action_items", []):
            doc.add_paragraph(
                f"{item['task']} — Owner: {item['owner']} — Due: {item['deadline']}",
                style="List Bullet",
            )
    doc.add_heading("Full transcript", 1)
    doc.add_paragraph(transcript or "No speech transcribed")
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
