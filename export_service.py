"""
export_service.py — The Print Shop
=====================================
Thread-safe PDF Generator with Tier-Based Watermarking.
Monetization engine for pushing upgrades.
"""

import os
import io
import secrets
import logging
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [EXPORT] %(levelname)s %(message)s")
log = logging.getLogger("export")

app = FastAPI(title="The Builder - Print Shop")

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

class ExportRequest(BaseModel):
    blueprint:    str
    project_type: str
    junk_desc:    str
    build_id:     int = 0
    user_email:   str = "anonymous"
    tier:         str = "starter"  # NEW: Used for watermarking

def verify_internal(x_internal_key: str = Header(None)):
    if not x_internal_key or not secrets.compare_digest(x_internal_key, INTERNAL_API_KEY):
        raise HTTPException(status_code=403, detail="Unauthorized")

@app.get("/health")
def health(): return {"status": "healthy"}

# ── 1. The CPU-Bound PDF Generator (Runs in Threadpool) ──────────────────────
# Notice 'async' is removed. FastAPI will safely put this heavy task on a background thread!
@app.post("/export/pdf", dependencies=[Depends(verify_internal)])
def export_pdf(req: ExportRequest):
    if len(req.blueprint) > 100000:
        raise HTTPException(status_code=400, detail="Blueprint too large.")

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib.units import inch
        import re

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch, leftMargin=0.75*inch, rightMargin=0.75*inch)
        
        styles = getSampleStyleSheet()
        forge_orange = HexColor("#FF6600")
        
        # ── MONETIZATION: The "Upgrade to Pro" Watermark ──
        def draw_watermark(canvas, doc):
            canvas.saveState()
            canvas.setFont("Helvetica-Bold", 36)
            canvas.setFillGray(0.5, 0.15) # Light grey, highly transparent
            canvas.translate(8.5*inch/2, 11*inch/2)
            canvas.rotate(45)
            canvas.drawCentredString(0, 0, "STARTER TIER - UPGRADE TO PRO")
            canvas.restoreState()

        title_style = ParagraphStyle("ForgeTitle", fontName="Helvetica-Bold", fontSize=28, textColor=forge_orange, spaceAfter=4)
        body_style = ParagraphStyle("ForgeBody", fontName="Helvetica", fontSize=10, leading=16, spaceAfter=8)
        
        story = [
            Paragraph("THE BUILDER", title_style),
            Paragraph(f"PROJECT: {req.project_type.upper()}", body_style),
            HRFlowable(width="100%", thickness=2, color=forge_orange),
            Spacer(1, 12)
        ]

        def md_inline(text):
            text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
            return text

        for line in req.blueprint.split("\n"):
            stripped = line.strip()
            if not stripped: story.append(Spacer(1, 6))
            else: story.append(Paragraph(md_inline(stripped), body_style))

        # Render with Watermark if not Pro/Master
        if req.tier in ["guest", "starter", "none"]:
            doc.build(story, onFirstPage=draw_watermark, onLaterPages=draw_watermark)
        else:
            doc.build(story) # Clean export for paying customers!

        buffer.seek(0)
        filename = f"blueprint_{req.build_id}.pdf"
        return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={filename}"})

    except Exception as e:
        log.error(f"PDF error: {e}")
        raise HTTPException(status_code=500, detail="PDF generation failed.")

@app.post("/export/text", dependencies=[Depends(verify_internal)])
def export_text(req: ExportRequest):
    content = f"THE BUILDER — PROJECT: {req.project_type.upper()}\n\n{req.blueprint}"
    if req.tier in ["guest", "starter"]:
        content += "\n\n*** Upgrade to PRO to remove watermarks and unlock all features. ***"
        
    buffer = io.BytesIO(content.encode("utf-8"))
    return StreamingResponse(buffer, media_type="text/plain", headers={"Content-Disposition": f"attachment; filename=blueprint_{req.build_id}.txt"})
