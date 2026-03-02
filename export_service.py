import os, io, secrets
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI()
class ExportRequest(BaseModel): blueprint: str; project_type: str; build_id: int; tier: str = "starter"

@app.post("/export/pdf")
def export_pdf(req: ExportRequest, x_internal_key: str = Header(None)):
    if not secrets.compare_digest(x_internal_key or "", os.getenv("INTERNAL_API_KEY")): raise HTTPException(403)
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = [Paragraph(f"BOB Engineering Document: {req.project_type}", getSampleStyleSheet()["Title"])]
    for line in req.blueprint.split("\n"): story.append(Paragraph(line.replace("<","&lt;").replace(">","&gt;"), getSampleStyleSheet()["Normal"]))
    
    def watermark(canvas, doc):
        canvas.saveState(); canvas.setFont("Helvetica-Bold", 36); canvas.setFillGray(0.5, 0.15)
        canvas.translate(250, 400); canvas.rotate(45); canvas.drawCentredString(0, 0, "EVALUATION TIER - UPGRADE REQUIRED")
        canvas.restoreState()

    if req.tier in ["guest", "starter"]: doc.build(story, onFirstPage=watermark, onLaterPages=watermark)
    else: doc.build(story)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=BOB_Schematic_{req.build_id}.pdf"})
