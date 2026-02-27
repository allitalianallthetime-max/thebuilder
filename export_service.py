"""
export_service.py — The Print Shop
=====================================
Converts blueprints into downloadable files.
- PDF blueprints with forge styling
- Plain text export
- JSON data export

Endpoints:
- POST /export/pdf   — Generate PDF blueprint
- POST /export/text  — Plain text export
- GET  /health
"""

import os
import io
import secrets
import logging
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [EXPORT] %(levelname)s %(message)s")
log = logging.getLogger("export")

app = FastAPI()

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

class ExportRequest(BaseModel):
    blueprint:    str
    project_type: str
    junk_desc:    str
    build_id:     int = 0
    user_email:   str = "anonymous"

async def verify(x_internal_key: str):
    if not x_internal_key or not INTERNAL_API_KEY or \
       not secrets.compare_digest(x_internal_key, INTERNAL_API_KEY):
        raise HTTPException(status_code=403, detail="Unauthorized")

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/export/pdf")
async def export_pdf(req: ExportRequest, x_internal_key: str = Header(None)):
    await verify(x_internal_key)

    # ── 2.3: Input validation ──
    if len(req.blueprint) > 100000:
        raise HTTPException(status_code=400, detail="Blueprint too large to export (max 100,000 chars).")

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.colors import HexColor, black, white
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib.units import inch

        buffer = io.BytesIO()
        doc    = SimpleDocTemplate(
            buffer, pagesize=letter,
            topMargin=0.75*inch, bottomMargin=0.75*inch,
            leftMargin=0.75*inch, rightMargin=0.75*inch
        )

        forge_orange = HexColor("#FF6600")
        forge_dark   = HexColor("#1a1a1a")
        forge_grey   = HexColor("#888888")

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "ForgeTitle",
            fontName="Helvetica-Bold",
            fontSize=28,
            textColor=forge_orange,
            spaceAfter=4,
            leading=32
        )
        subtitle_style = ParagraphStyle(
            "ForgeSubtitle",
            fontName="Helvetica",
            fontSize=10,
            textColor=forge_grey,
            spaceAfter=20
        )
        header_style = ParagraphStyle(
            "ForgeHeader",
            fontName="Helvetica-Bold",
            fontSize=14,
            textColor=forge_orange,
            spaceBefore=16,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            "ForgeBody",
            fontName="Helvetica",
            fontSize=10,
            textColor=forge_dark,
            leading=16,
            spaceAfter=8
        )
        meta_style = ParagraphStyle(
            "ForgeMeta",
            fontName="Helvetica",
            fontSize=8,
            textColor=forge_grey
        )

        story = []

        # Header
        story.append(Paragraph("THE BUILDER", title_style))
        story.append(Paragraph("AoC3P0 Systems · AI-Powered Engineering Forge · Round Table Blueprint", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=2, color=forge_orange))
        story.append(Spacer(1, 12))

        # Build info
        story.append(Paragraph(f"PROJECT: {req.project_type.upper()}", header_style))
        story.append(Paragraph(f"PARTS: {req.junk_desc}", body_style))
        if req.build_id:
            story.append(Paragraph(f"BUILD ID: #{req.build_id}", meta_style))
        story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#333333")))
        story.append(Spacer(1, 12))

        # Blueprint content — with markdown conversion
        story.append(Paragraph("BLUEPRINT", header_style))

        # ── 3.5: Markdown → PDF conversion ────────────────────────────────────
        code_style = ParagraphStyle(
            'Code', parent=body_style,
            fontName='Courier', fontSize=8, leading=11,
            textColor=HexColor("#00cc66"),
            backColor=HexColor("#0a0a0a"),
            leftIndent=12, rightIndent=12,
            spaceBefore=4, spaceAfter=4,
        )
        bullet_style = ParagraphStyle(
            'Bullet', parent=body_style,
            leftIndent=20, bulletIndent=8,
            spaceBefore=2, spaceAfter=2,
        )

        in_code_block = False
        code_buffer = []

        import re
        def md_inline(text):
            """Convert inline markdown: **bold**, *italic*, `code`."""
            text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
            text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
            text = re.sub(r'`(.+?)`', r'<font face="Courier" size="8" color="#ff6600">\1</font>', text)
            return text

        for line in req.blueprint.split("\n"):
            stripped = line.strip()

            # Code block toggle
            if stripped.startswith("```"):
                if in_code_block:
                    # End code block — flush buffer
                    code_text = "\n".join(code_buffer)
                    safe_code = code_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    story.append(Paragraph(safe_code.replace("\n", "<br/>"), code_style))
                    code_buffer = []
                    in_code_block = False
                else:
                    in_code_block = True
                continue

            if in_code_block:
                code_buffer.append(line)
                continue

            # Empty line
            if not stripped:
                story.append(Spacer(1, 6))
            # Horizontal rule
            elif stripped in ("---", "***", "___"):
                story.append(Spacer(1, 4))
                story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#442200")))
                story.append(Spacer(1, 4))
            # Headers
            elif stripped.startswith("###"):
                clean = stripped.lstrip("#").strip()
                story.append(Paragraph(md_inline(clean), header_style))
            elif stripped.startswith("##"):
                clean = stripped.lstrip("#").strip()
                story.append(Paragraph(md_inline(clean), header_style))
            elif stripped.startswith("#"):
                clean = stripped.lstrip("#").strip()
                story.append(Paragraph(md_inline(clean), title_style))
            # Bullet points
            elif stripped.startswith("- ") or stripped.startswith("* "):
                content = stripped[2:]
                story.append(Paragraph(f"• {md_inline(content)}", bullet_style))
            # Numbered lists
            elif re.match(r'^\d+\.\s', stripped):
                story.append(Paragraph(md_inline(stripped), bullet_style))
            # Regular text
            else:
                story.append(Paragraph(md_inline(stripped), body_style))

        # Flush any unclosed code block
        if code_buffer:
            code_text = "\n".join(code_buffer)
            safe_code = code_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(safe_code.replace("\n", "<br/>"), code_style))

        # Footer
        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=1, color=forge_orange))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "Generated by The Builder · AoC3P0 Systems · Always wear PPE · Build responsibly.",
            meta_style
        ))

        doc.build(story)
        buffer.seek(0)

        filename = f"blueprint_{req.project_type.replace(' ', '_').lower()}_{req.build_id}.pdf"
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="PDF generation requires reportlab. Add 'reportlab' to requirements."
        )
    except Exception as e:
        log.error(f"PDF generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/export/text")
async def export_text(req: ExportRequest, x_internal_key: str = Header(None)):
    await verify(x_internal_key)

    # ── 2.3: Input validation ──
    if len(req.blueprint) > 100000:
        raise HTTPException(status_code=400, detail="Blueprint too large to export (max 100,000 chars).")

    content = f"""
================================================================================
THE BUILDER — AoC3P0 SYSTEMS
AI-Powered Engineering Forge · Round Table Blueprint
================================================================================

PROJECT:  {req.project_type.upper()}
PARTS:    {req.junk_desc}
BUILD ID: #{req.build_id}

================================================================================
BLUEPRINT
================================================================================

{req.blueprint}

================================================================================
Generated by The Builder · AoC3P0 Systems
Always wear PPE. Build responsibly.
================================================================================
""".strip()

    buffer   = io.BytesIO(content.encode("utf-8"))
    filename = f"blueprint_{req.project_type.replace(' ', '_').lower()}_{req.build_id}.txt"

    return StreamingResponse(
        buffer,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
